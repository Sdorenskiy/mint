"""Экспертные материалы аудита — то, что знает эксперт, а не проверяемый документ.

- Чек-листы по типам документов: checklists.yaml рядом с программой (вне git); пока его нет — образец
  checklists.example.yaml. Тип документа определяется по словам из его названия (начало документа и имя
  файла), каждый пункт чек-листа — отдельный вопрос модели по всему документу.
- Документы базы знаний «учитывать в аудите всегда» (правила экспертов): попадают в каждую проверку целиком, без
  поиска; если не помещаются — самые близкие к проверяемому тексту фрагменты.
- Карточки систем: что система умеет, что в планах, какие ограничения. Карточка подключается, когда система
  упоминается в проверяемом тексте; по каждой упомянутой системе модель выписывает, что документ от неё требует.

Роли документов базы хранятся в папке базы (audit_roles.json), вместе с самой базой: при обновлении программы
они не затираются и в репозиторий не попадают.
"""

import json
import logging
import os
import re
from pathlib import Path

import numpy as np
import yaml

from .bm25 import BM25_STOP_WORDS, bm25_tokenize
from .config import APP_DIR
from .i18n import get_lang
from .kb import kb_file, load_kb_snapshot, parent_order
from .passages import merge_adjacent
from .prompts import render
from .search import _source_header
from .text import atomic_write_json, short_path

logger = logging.getLogger("MINT")

# ---------------------------------------------------------------- чек-листы по типам документов

CHECKLIST_MAX = 25          # пунктов чек-листа на один аудит (каждый — запрос к модели)
TITLE_CHARS = 2000          # тип документа ищется в имени файла и в начале документа (титульный лист)


def checklists_path() -> Path:
    """Свои чек-листы: MINT_CHECKLISTS (из окружения или .env) или checklists.yaml рядом с программой."""
    p = os.environ.get("MINT_CHECKLISTS", "").strip()
    if not p:
        return APP_DIR / "checklists.yaml"
    path = Path(os.path.expanduser(p))
    return path if path.is_absolute() else APP_DIR / path


def checklists_example_path(lang=None) -> Path:
    lang = lang or get_lang()
    en = APP_DIR / "checklists.example.en.yaml"
    return en if lang == "en" and en.exists() else APP_DIR / "checklists.example.yaml"


def _items(value):
    if isinstance(value, str):
        value = value.split("\n")
    return [str(x).strip(" \t-•*–—") for x in (value or []) if str(x).strip(" \t-•*–—")]


def _normalize_checklists(data):
    data = data if isinstance(data, dict) else {}
    types = []
    for t in data.get("types") or []:
        if not isinstance(t, dict) or not str(t.get("name") or "").strip():
            continue
        match = t.get("match") or []
        if isinstance(match, str):
            match = re.split(r"[;,\n]", match)
        types.append({"name": str(t["name"]).strip(), "match": [str(m).strip() for m in match if str(m).strip()],
                      "items": _items(t.get("items"))})
    return {"common": _items(data.get("common")), "types": types}


def load_checklists(path=None, lang=None):
    """Чек-листы: {"common": [пункты для любого документа], "types": [{name, match, items}], "source": откуда
    ("file" — свой файл, "example" — образец, "none" — нет ни того, ни другого), "path": файл}."""
    own = Path(path) if path else checklists_path()
    for src, p in (("file", own), ("example", checklists_example_path(lang))):
        if p.is_file():
            try:
                data = _normalize_checklists(yaml.safe_load(p.read_text(encoding="utf-8")))
            except Exception as e:
                logger.warning(f"Чек-листы {p} не прочитаны: {str(e)[:160]}")
                continue
            return {**data, "source": src, "path": str(p)}
    return {"common": [], "types": [], "source": "none", "path": str(own)}


_CHECKLISTS_HEADER = (
    "# Чек-листы аудита MINT по типам документов (свой файл: в репозиторий не попадает).\n"
    "# common — пункты для любого документа; types — тип документа: name — название, match — слова, по которым\n"
    "# MINT узнаёт тип в начале документа или в имени файла, items — пункты чек-листа.\n"
    "# Каждый пункт — отдельный вопрос модели по всему документу: пишите так, чтобы ответ можно было найти в тексте.\n"
)


def save_checklists(data, path=None):
    """Записывает чек-листы в свой файл (по умолчанию checklists.yaml рядом с программой)."""
    p = Path(path) if path else checklists_path()
    clean = _normalize_checklists(data)
    body = yaml.safe_dump(clean, allow_unicode=True, sort_keys=False, width=120)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(_CHECKLISTS_HEADER + body, encoding="utf-8")
    os.replace(tmp, p)
    return str(p)


def _yo(escaped):
    """«е» и «ё» в регулярном выражении — одна буква (в названиях пишут по-разному)."""
    return "".join("[её]" if c in "её" else "[ЕЁ]" if c in "ЕЁ" else c for c in escaped)


def _phrase_re(phrase):
    words = [_yo(re.escape(w)) for w in phrase.split()]
    return re.compile(r"(?<!\w)" + r"[\s\-_]+".join(words) + r"(?!\w)", re.IGNORECASE)


TITLE_LINE_MAX = 150        # строка или ячейка титульного листа с названием документа — не длиннее


def _title_like(head, start, end):
    """Слово на позиции start…end — в названии документа, а не в ссылке на другой документ: строка (ячейка
    таблицы) короткая и слово не в кавычках («… Техническое задание на развитие» — название чужого документа)."""
    a = head.rfind("\n", 0, start) + 1
    b = head.find("\n", end)
    b = len(head) if b == -1 else b
    line = head[a:b]
    if line.lstrip().startswith("|"):           # титульный лист таблицей — по ячейке
        a = head.rfind("|", a, start) + 1
        c = head.find("|", end, b)
        b = b if c == -1 else c
    segment, before = head[a:b], head[a:start]
    quoted = before.count("«") > before.count("»") or before.count("\"") % 2 == 1 or before.count("“") > before.count("”")
    return len(segment.strip()) <= TITLE_LINE_MAX and not quoted


def detect_document_type(md_text, filename, checklists):
    """Тип документа по словам match: ищутся в имени файла и в названии в начале документа — в коротких строках
    (ячейках таблицы) и не в кавычках: «на основании технического задания …» и «… Техническое задание на развитие»
    — ссылки на другие документы. Побеждает тип, слово которого встретилось раньше всех. → (тип или None, слово)."""
    stem = os.path.splitext(os.path.basename(filename or ""))[0].replace("_", " ")
    head = stem + "\n" + (md_text or "")[:TITLE_CHARS]
    best = None
    for t in (checklists or {}).get("types") or []:
        for word in t.get("match") or []:
            if len(word) < 2:
                continue
            m = next((m for m in _phrase_re(word).finditer(head)
                      if m.start() <= len(stem) or _title_like(head, m.start(), m.end())), None)
            if m and (best is None or (m.start(), -len(word)) < (best[0], -len(best[2]))):
                best = (m.start(), t, word)
    return (best[1], best[2]) if best else (None, "")


def checklist_items(checklists, doc_type=None, with_common=True):
    """Пункты для аудита: общие (если with_common) и типа doc_type, без повторов, не больше CHECKLIST_MAX."""
    items = (list(checklists.get("common") or []) if with_common else []) + list((doc_type or {}).get("items") or [])
    return list(dict.fromkeys(items))[:CHECKLIST_MAX]


# ---------------------------------------------------------------- роли документов базы

ROLES_FILE = "audit_roles.json"


def load_roles(cfg):
    """{"always": [документы «учитывать всегда»], "cards": [карточки систем]} из папки базы."""
    p = kb_file(cfg, ROLES_FILE)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {k: [str(x) for x in (data.get(k) or []) if str(x).strip()] for k in ("always", "cards")}


def save_roles(cfg, always=(), cards=()):
    cfg.kb_path.mkdir(parents=True, exist_ok=True)
    cards = list(dict.fromkeys(cards))
    always = [d for d in dict.fromkeys(always) if d not in cards]     # документ — либо правило, либо карточка
    atomic_write_json(kb_file(cfg, ROLES_FILE), {"always": always, "cards": cards})


# ---------------------------------------------------------------- карточки систем: названия и упоминания

_ALIAS_LINE_RE = re.compile(
    r"(?im)^[\W_]*(?:названи[яе](?:\s+системы)?|другие\s+названия|также\s+называ\w*|синонимы|"
    r"names?|other\s+names|also\s+known\s+as|aliases)[\W_]*:\s*(.+)$")
# «… System A Актуально на: …» — строки карточки склеились при разборе: названия — до следующей подписи «Слово …:»
_NEXT_LABEL_RE = re.compile(r"\s+[А-ЯЁA-Z][а-яёa-z]+(?:\s+[а-яёa-z]+){0,3}\s*:\s")
_CARD_TITLE_RE = re.compile(r"(?i)^(?:карточка\s+(?:системы|компонента|сервиса)?|system\s+card|card)[\s:—–-]*")
_ABBR_WORD_RE = re.compile(r"^[A-ZА-ЯЁ0-9][A-ZА-ЯЁ0-9.\-]*$")


def card_names(text, filename=""):
    """Названия системы из карточки: строка «Названия: А, Б» и название из первого заголовка («Карточка системы
    «Система А»» → «Система А»); если нет ни того, ни другого — имя файла."""
    names = []
    for m in _ALIAS_LINE_RE.finditer(text or ""):
        value = _NEXT_LABEL_RE.split(m.group(1), maxsplit=1)[0]
        names += [x.strip(" \t«»\"'*_.") for x in re.split(r"[,;]", value)]
    heading = next((ln.lstrip("#").strip() for ln in (text or "").split("\n") if ln.startswith("#")), "")
    if heading:
        quoted = re.search(r"«([^»]{2,80})»|\"([^\"]{2,80})\"", heading)
        title = (quoted.group(1) or quoted.group(2)) if quoted else _CARD_TITLE_RE.sub("", heading)
        names.append(title.strip(" \t«»\"'*_.:"))
    if not [n for n in names if n]:
        stem = os.path.splitext(os.path.basename(filename))[0].replace("_", " ")
        names.append(_CARD_TITLE_RE.sub("", stem).strip(" -"))
    return [n for n in dict.fromkeys(n for n in names if len(n) >= 2)]


def _word_pattern(word):
    if _ABBR_WORD_RE.match(word) and any(c.isalpha() for c in word) and word.upper() == word:
        return re.escape(word)                                   # сокращение — как написано (СА, но не «са»)
    stem = word[:-2] if len(word) >= 5 and word[-1].isalpha() else word     # окончание меняется: Система/Системы
    body = _yo(re.escape(stem))
    return "(?i:" + body + (r")\w{0,4}" if stem != word else ")")


def names_pattern(names):
    """Одно регулярное выражение для всех названий системы (длинные — первыми)."""
    alts = []
    for name in sorted(names, key=len, reverse=True):
        words = name.split()
        if words:
            alts.append(r"[\s\-]+".join(_word_pattern(w) for w in words))
    return re.compile(r"(?<!\w)(?:" + "|".join(alts) + r")(?!\w)") if alts else None


def count_mentions(pattern, text):
    return len(pattern.findall(text or "")) if pattern is not None else 0


# ---------------------------------------------------------------- материалы для аудита

# Разделы документа-основания, которые не несут требований, но совпадают по словам с любым разделом проверяемого
# документа (те же сокращения и термины): в проверку раздела не идут
_NO_REQUIREMENTS_RE = re.compile(
    r"(?i)^\W*(?:[\dА-ЯA-Z]{1,3}[.)]?\s*)*(?:обозначени\w*\s+и\s+сокращени|перечень\s+(?:сокращени|обозначени|"
    r"терминов|ссылочн)|сокращени\w*\s*(?:и\s+обозначени\w*)?\s*$|термины\s+и\s+(?:определени|сокращени)|"
    r"определени\w*\s*$|ссылочн\w*\s+документ|нормативн\w*\s+ссылк|содержание\s*$|оглавление\s*$|"
    r"лист\s+регистрации|abbreviations|acronyms|terms\s+and\s+(?:definitions|abbreviations)|definitions\s*$|"
    r"(?:table\s+of\s+)?contents\s*$|references\s*$|normative\s+references)")
RRF_K = 60                    # слияние двух порядков (по словам и по смыслу), как в поиске по базе


def no_requirements(heading_path):
    """Раздел без требований: сокращения, термины, содержание, ссылочные документы."""
    return bool(_NO_REQUIREMENTS_RE.search((heading_path or "").split(" → ")[-1].strip()))


class ExpertMaterials:
    """Правила и карточки из базы, подготовленные один раз на аудит: фрагменты базы (parent) по документам."""

    def __init__(self, parent_store, order, always, cards, kind="expert", vectors=None):
        self.parent_store = parent_store
        self.order = order
        self.kind = kind              # "expert" — правила 📌 и карточки 🗂️; "basis" — документы-основания 📎
        self.always = always          # [{"source", "ids": [parent_id в порядке текста], "chars"}]
        self.cards = cards            # [{"source", "ids", "chars", "names", "pattern"}]
        self.vectors = vectors or {}  # parent_id → векторы его child-фрагментов (нормированы): близость по смыслу
        units = [p for d in always + cards for p in d["ids"]]
        keys = {p: _keys(parent_store[p].get("text") or "") for p in units}
        df = {}
        for ks in keys.values():
            for k in ks:
                df[k] = df.get(k, 0) + 1
        n = max(1, len(units))
        self.keys = keys
        self.idf = {k: float(np.log(1 + n / v)) for k, v in df.items()}
        self.card_sources = {d["source"] for d in cards}

    @property
    def empty(self):
        return not self.always and not self.cards

    def total_chars(self):
        return sum(d["chars"] for d in self.always + self.cards)

    def mentioned_cards(self, text, min_count=1):
        """Карточки систем, упомянутых в тексте: [(карточка, сколько раз)] — чаще упомянутые первыми."""
        found = [(c, count_mentions(c["pattern"], text)) for c in self.cards]
        return sorted([x for x in found if x[1] >= min_count], key=lambda x: -x[1])

    def card_text(self, card, max_chars):
        """Текст карточки для вопроса «что документ требует от системы» (склеенные фрагменты, до max_chars)."""
        blocks, total = [], 0
        for ids, text in sorted(merge_adjacent(card["ids"], self.parent_store, self.order),
                                key=lambda g: self.order.get(g[0][0], 0)):
            if blocks and total + len(text) > max_chars:
                break
            blocks.append(text[:max_chars])
            total += len(text)
        return "\n\n".join(blocks)


def _keys(text):
    return {t for t in bm25_tokenize(text) if t not in BM25_STOP_WORDS and len(t) >= 3}


def load_expert_materials(cfg):
    """Правила «учитывать всегда» и карточки систем из базы знаний; None — ролей не задано или базы нет."""
    roles = load_roles(cfg)
    if not roles["always"] and not roles["cards"]:
        return None
    snap = load_kb_snapshot(cfg)
    if snap is None:
        return None
    order = parent_order(snap)
    by_source = {}
    for p, pd in snap.parent_store.items():
        by_source.setdefault(pd.get("source", ""), []).append(p)
    for ids in by_source.values():
        ids.sort(key=order.get)

    def doc(name):
        ids = by_source.get(name) or []
        return {"source": name, "ids": ids, "chars": sum(len(snap.parent_store[p].get("text") or "") for p in ids)}

    always = [doc(n) for n in roles["always"] if by_source.get(n)]
    cards = []
    for n in roles["cards"]:
        if not by_source.get(n):
            continue
        d = doc(n)
        head = "\n".join(snap.parent_store[p].get("text") or "" for p in d["ids"][:3])
        d["names"] = card_names(head, n)
        d["pattern"] = names_pattern(d["names"])
        cards.append(d)
    m = ExpertMaterials(snap.parent_store, order, always, cards)
    return None if m.empty else m


def query_vector(materials, text, cfg):
    """Вектор текста для близости по смыслу к фрагментам materials; None — у materials нет векторов или
    эмбеддинг недоступен (тогда отбор только по словам)."""
    if materials is None or not materials.vectors:
        return None
    from .search import _query_vector
    from .text import smart_truncate
    dim = len(next(iter(materials.vectors.values()))[0])
    vec, _why = _query_vector(smart_truncate(text or "", max_chars=cfg.audit_query_chars), cfg, dim)
    return vec[0] if vec is not None else None


def _ranking(materials, units, rank_text, query_vec, card_ids):
    """Порядок фрагментов по близости к rank_text: по словам (сумма idf общих слов, делённая на корень из числа
    слов фрагмента — длинный перечень не выигрывает сам по себе) и, если есть векторы, по смыслу (лучший child
    фрагмента); два порядка сливаются (RRF). → {parent_id: балл} (0 — ничего общего)."""
    q = _keys(rank_text or "")

    def lexical(p):
        ks = materials.keys.get(p, set())
        s = sum(materials.idf.get(k, 0.0) for k in ks & q) / max(1.0, len(ks)) ** 0.5
        return s * (2.0 if p in card_ids else 1.0)

    lex = {p: lexical(p) for p in units}
    ranks = [{p: r for r, p in enumerate(sorted((p for p in units if lex[p] > 0), key=lambda p: -lex[p]), 1)}]
    if query_vec is not None:
        dense = {p: float(np.max(materials.vectors[p] @ query_vec)) for p in units if p in materials.vectors}
        ranks.append({p: r for r, p in enumerate(sorted(dense, key=lambda p: -dense[p]), 1)})
    return {p: sum(1.0 / (RRF_K + rk[p]) for rk in ranks if p in rk) for p in units}


def select_pinned(materials, rank_text, budget, mention_text=None, cards=None, query_vec=None):
    """Фрагменты правил и карточек (или документов-оснований) для одного запроса аудита — как найденные нормы
    ({id, ids, source, block, short}), отдельно от лимита норм поиска. Карточки — систем, упомянутых в mention_text
    (по умолчанию в rank_text), или явно заданные cards. Всё помещается в budget — целиком; иначе — самые близкие к
    rank_text фрагменты (карточки упомянутых систем — в первую очередь; query_vec — ещё и близость по смыслу), в
    порядке текста. У документов-оснований разделы без требований (сокращения, термины, содержание) не берутся, а
    бюджет делится между документами поровну: большой общий документ не вытесняет частный."""
    if materials is None or budget <= 0:
        return []
    if cards is None:
        cards = [c for c, _n in materials.mentioned_cards(rank_text if mention_text is None else mention_text)]
    docs = list(materials.always) + list(cards)
    ps = materials.parent_store
    basis = materials.kind == "basis"
    units = [p for d in docs for p in d["ids"] if not (basis and no_requirements(ps[p].get("heading_path")))]
    if not units:
        return []
    size = {p: len(ps[p].get("text") or "") for p in units}
    if sum(size.values()) <= budget:
        chosen = set(units)
    else:
        score = _ranking(materials, units, rank_text, query_vec, {p for c in cards for p in c["ids"]})
        ranked = sorted((p for p in units if score[p] > 0), key=lambda p: (-score[p], materials.order.get(p, 0)))
        chosen, total = set(), 0

        def take(candidates, limit):
            nonlocal total
            used = 0
            for p in candidates:
                if p in chosen or total + size[p] > budget or used + size[p] > limit:
                    continue
                chosen.add(p)
                total += size[p]
                used += size[p]

        if basis and len(docs) > 1:             # сначала каждому документу — его доля бюджета
            share = budget // len(docs)
            for d in docs:
                mine = set(d["ids"])
                take([p for p in ranked if p in mine], share)
        take(ranked, budget)
    doc_rank = {d["source"]: i for i, d in enumerate(docs)}
    groups = merge_adjacent([p for p in units if p in chosen], ps, materials.order)
    groups.sort(key=lambda g: (doc_rank.get(ps[g[0][0]].get("source", ""), 0), materials.order.get(g[0][0], 0)))
    items = []
    for ids, text in groups:
        pd = ps[ids[0]]
        if len(ids) > 1:
            pd = {**pd, "text": text}
        src = pd.get("source", "")
        basis = materials.kind == "basis"
        mark = "📎" if basis else "🗂️" if src in materials.card_sources else "📌"
        path = pd.get("heading_path") or ""
        items.append({"id": ids[0], "ids": list(ids), "source": src, "path": path, "pinned": True, "basis": basis,
                      "block": render("context_block", header=_source_header(pd, text), body=text),
                      "short": f"{mark} {src}" + (f" › {short_path(path)}" if path else "")})
    return items

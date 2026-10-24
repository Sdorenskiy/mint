"""Документы-основания: документы базы знаний, по которым разработан проверяемый документ.

Документ сам называет своё основание — на титуле («разработан в соответствии с требованиями документов: «…
Техническое задание на развитие» (ОРГ.10.0.123.ТЗ.4)») и в разделе «Ссылочные документы». Если такой документ
есть в базе, его фрагменты, ближайшие к проверяемому разделу, идут в каждую проверку раздела и в ответы на пункты
— как правила экспертов, но отдельным блоком: «документ должен им соответствовать».

Зачем: нормы к разделу ищутся по тексту самого раздела и находят похожие места других документов, а требование,
которое касается всего документа (куда передаются данные, через какую подсистему), в тексте раздела другими
словами — и поиском не находится. Документ-основание MINT знает заранее и не ищет.

    from mint.basis import basis_references, find_basis_documents
    refs = basis_references(md_text)                 # [{title, code}] — ссылки из документа
    found = find_basis_documents(refs, cfg, exclude=("Проверяемый.docx",))
    found["docs"]       # [{source, by: "code" | "title", ref}] — документы базы
    found["missing"]    # ссылки, которых в базе нет
"""

import os
import re

from .bm25 import BM25_STOP_WORDS, bm25_tokenize
from .kb import load_kb_snapshot, parent_order

TITLE_ZONE_CHARS = 6000     # титульный лист и начало документа: здесь документ называет своё основание
BASIS_WINDOW = 1500         # ссылки — в стольких символах после «в соответствии с», «на основании» …
KB_TITLE_PARENTS = 3        # начало документа базы (его название) — столько первых фрагментов
KB_CODE_PARENTS = 6         # шифр документа базы ищется дальше: он бывает на листе утверждения, а не на титуле
BASIS_DOCS_MAX = 5          # документов-оснований на аудит
TITLE_MATCH_MIN = 0.75      # доля значимых слов названия из ссылки, которые есть в начале документа базы
TITLE_KEYS_MIN = 3          # название из ссылки — не короче стольких значимых слов
TITLE_NEAR = 0.15           # по названию берутся и документы с долей совпавших слов не ниже лучшей минус столько

_BASIS_WORDS_RE = re.compile(r"(?i)в\s+соответстви\w*\s+с|на\s+основани\w*|основани\w*\s+для|согласно|"
                             r"разработан\w*\s+(?:по|на|в)|по\s+требовани\w*|требованиями\s+документ\w*|"
                             r"in\s+accordance\s+with|based\s+on|pursuant\s+to|developed\s+(?:under|according)")
_REF_SECTION_RE = re.compile(r"(?i)ссылочн\w*\s+документ|нормативн\w*\s+ссылк|перечень\s+ссылочн|"
                             r"основани\w*\s+(?:для\s+)?разработк|\breferences?\b|reference\s+documents")
# шифр документа: буквы, затем не меньше двух сегментов через точку — «ОРГ.10.0.123.ТЗ.4», «RU.17701729.50-01»
_CODE_RE = re.compile(r"(?<![\w.])([A-ZА-ЯЁ][A-ZА-ЯЁ0-9-]*(?:\.[A-ZА-ЯЁ0-9-]+){2,})(?!\w)")
_QUOTE_RE = re.compile(r"«([^«»\n]{12,250})»|“([^“”\n]{12,250})”")
_CODE_NEAR_QUOTE = 160      # шифр сразу после названия в кавычках — шифр этого документа


def _keys(text):
    return {t for t in bm25_tokenize(text or "") if t not in BM25_STOP_WORDS and len(t) >= 3}


def _refs_in(text):
    """Ссылки в куске текста: название в кавычках (с шифром сразу после него) и отдельные шифры."""
    refs, used = [], set()
    for m in _QUOTE_RE.finditer(text):
        title = (m.group(1) or m.group(2)).strip()
        tail = text[m.end():m.end() + _CODE_NEAR_QUOTE]
        cm = _CODE_RE.search(tail.split("«", 1)[0])
        code = cm.group(1) if cm else ""
        if cm:
            used.add(m.end() + cm.start())
        refs.append({"title": title, "code": code})
    for cm in _CODE_RE.finditer(text):
        if cm.start() not in used:
            refs.append({"title": "", "code": cm.group(1)})
    return refs


def _ref_section_lines(md_text):
    """Строки раздела «Ссылочные документы» (и похожих): строка таблицы — ячейки через пробел."""
    from .sections import document_blocks
    lines = []
    for b in document_blocks(md_text):
        last = (b["path"] or "").split(" → ")[-1]
        if b["level"] or not last or not _REF_SECTION_RE.search(last):
            continue
        for line in b["text"].split("\n"):
            s = line.strip()
            if not s or re.fullmatch(r"[|\s:-]+", s):
                continue
            if s.startswith("|"):
                s = " ".join(c.strip() for c in s.strip("|").split("|") if c.strip())
            lines.append(s)
    return lines


def basis_references(md_text):
    """Ссылки проверяемого документа на документы-основания: с титула (после «в соответствии с», «на основании» …)
    и из раздела «Ссылочные документы». → [{title, code}] без повторов, сначала — с титула."""
    head = (md_text or "")[:TITLE_ZONE_CHARS]
    refs = []
    for m in _BASIS_WORDS_RE.finditer(head):
        refs += _refs_in(head[m.start():m.start() + BASIS_WINDOW])
    for line in _ref_section_lines(md_text):
        found = _refs_in(line)
        if found:
            refs += found
        else:                                    # название без кавычек — строка целиком
            title = re.sub(r"^[\d.)\s№-]+", "", line).strip()
            if 12 <= len(title) <= 250:
                refs.append({"title": title, "code": ""})
    out, seen = [], set()
    for r in refs:
        key = r["code"] or " ".join(sorted(_keys(r["title"])))
        if key and key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _cited(zone, pos):
    """Шифр в начале документа базы стоит после «в соответствии с …» — этот документ на него ссылается, а не он сам."""
    return bool(_BASIS_WORDS_RE.search(zone[max(0, pos - 300):pos]))


def _own_text(zone):
    """Начало документа базы без его собственных ссылок на основания («разработан в соответствии с …» и до
    BASIS_WINDOW символов дальше, не дальше следующего заголовка): документ того же семейства, который ссылается
    на то же ТЗ, иначе совпал бы с ним по названию."""
    cut, out, pos = [], [], 0
    for m in _BASIS_WORDS_RE.finditer(zone):
        if cut and m.start() < cut[-1][1]:
            continue
        end = min(len(zone), m.start() + BASIS_WINDOW)
        head = re.search(r"\n#{1,6} ", zone[m.end():end])
        cut.append((m.start(), m.end() + head.start() if head else end))
    for a, b in cut:
        out.append(zone[pos:a])
        pos = b
    out.append(zone[pos:])
    return " ".join(out)


def find_basis_documents(refs, cfg, exclude=(), snapshot=None, max_docs=BASIS_DOCS_MAX):
    """Документы базы по ссылкам: по шифру в начале документа базы (или в имени файла), иначе — по названию (не
    меньше TITLE_MATCH_MIN значимых слов названия есть в начале документа базы). exclude — документы, которые не
    берутся (сам проверяемый документ, уже отмеченные 📌 и 🗂️). → {"docs": [{source, by, ref}], "missing":
    [ссылки без документа в базе]}."""
    snap = snapshot if snapshot is not None else load_kb_snapshot(cfg)
    if snap is None or not refs:
        return {"docs": [], "missing": list(refs or [])}
    order = parent_order(snap)
    by_source = {}
    for p, pd in snap.parent_store.items():
        by_source.setdefault(pd.get("source", ""), []).append(p)
    skip = {os.path.basename(x) for x in exclude if x}
    zones, code_zones = {}, {}
    for src, ids in by_source.items():
        if not src or os.path.basename(src) in skip:
            continue
        ids.sort(key=order.get)
        stem = os.path.splitext(os.path.basename(src))[0].replace("_", " ")
        # раздел «Ссылочные документы» в начале документа базы — чужие названия и шифры, не его
        own = [p for p in ids[:KB_CODE_PARENTS]
               if not _REF_SECTION_RE.search((snap.parent_store[p].get("heading_path") or "").split(" → ")[-1])]
        zones[src] = stem + "\n" + "\n".join(snap.parent_store[p].get("text") or "" for p in own[:KB_TITLE_PARENTS])
        code_zones[src] = stem + "\n" + "\n".join(snap.parent_store[p].get("text") or "" for p in own)
    zone_keys = {src: _keys(_own_text(z)) for src, z in zones.items()}
    docs, missing, taken = [], [], set()
    for ref in refs:
        hits, by = [], ""
        code = re.sub(r"\s+", "", ref.get("code") or "")
        if code:
            # шифр в PDF бывает разорван переносом строки — между символами допускается пробел
            pattern = re.compile(r"(?<![\w.])" + r"\s*".join(re.escape(c) for c in code) + r"(?![\w])")
            for src, zone in code_zones.items():
                if any(not _cited(zone, m.start()) for m in pattern.finditer(zone)):
                    hits.append(src)
            by = "code" if hits else ""
        title_keys = _keys(ref.get("title"))
        if not hits and len(title_keys) >= TITLE_KEYS_MIN:
            scored = sorted(((len(title_keys & zk) / len(title_keys), src) for src, zk in zone_keys.items()),
                            reverse=True)
            best = scored[0][0] if scored else 0
            if best >= TITLE_MATCH_MIN:            # и почти такие же: у двух редакций ТЗ названия чуть разные
                hits = [src for score, src in scored if score >= max(TITLE_MATCH_MIN, best - TITLE_NEAR)][:2]
                by = "title"
        if not hits:
            missing.append(ref)
            continue
        for src in hits:
            if src not in taken and len(docs) < max_docs:
                taken.add(src)
                docs.append({"source": src, "by": by, "ref": ref})
    return {"docs": docs, "missing": missing}


def basis_materials(cfg, sources, snapshot=None):
    """Фрагменты документов-оснований для select_pinned (как правила экспертов, но со значком 📎). None — нечего."""
    from .expert import ExpertMaterials
    sources = [s for s in dict.fromkeys(sources or []) if s]
    if not sources:
        return None
    snap = snapshot if snapshot is not None else load_kb_snapshot(cfg)
    if snap is None:
        return None
    order = parent_order(snap)
    docs = []
    for name in sources:
        ids = sorted((p for p, pd in snap.parent_store.items() if pd.get("source") == name), key=order.get)
        if ids:
            docs.append({"source": name, "ids": ids,
                         "chars": sum(len(snap.parent_store[p].get("text") or "") for p in ids)})
    if not docs:
        return None
    return ExpertMaterials(snap.parent_store, order, docs, [], kind="basis", vectors=_child_vectors(snap, sources))


def _child_vectors(snap, sources):
    """Векторы child-фрагментов документов-оснований из индекса базы: parent_id → матрица (по строке на child).
    Близость раздела к фрагменту по смыслу — без запросов к модели эмбеддингов, кроме вектора самого раздела."""
    import numpy as np

    from .kb import index_vectors
    wanted = set(sources)
    rows = [(i, m["parent_id"]) for i, m in enumerate(snap.metadata or [])
            if m.get("source") in wanted and m.get("parent_id") in snap.parent_store]
    if not rows or getattr(snap.index, "ntotal", 0) != len(snap.metadata or []):     # индекс не совпадает с базой
        return {}
    try:
        vecs = index_vectors(snap.index, [i for i, _p in rows])
    except Exception:
        return {}
    by_parent = {}
    for (_i, p), v in zip(rows, vecs):
        by_parent.setdefault(p, []).append(v)
    return {p: np.asarray(v, dtype="float32") for p, v in by_parent.items()}


def reference_label(ref):
    """Ссылка для лога и интерфейса: «Название» (шифр)."""
    title, code = (ref.get("title") or "").strip(), (ref.get("code") or "").strip()
    if title and code:
        return f"«{title}» ({code})"
    return f"«{title}»" if title else code

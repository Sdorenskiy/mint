"""Глоссарий сокращений: автосбор из документов и свой glossary.json."""

import json
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path

from .bm25 import BM25_STOP_WORDS, bm25_tokenize
from .config import _read_text_any
from .i18n import N_, tr

logger = logging.getLogger("MINT")


# Зачем: пользователь пишет «СЗИ», а в регламенте — «средства защиты информации» (или наоборот).
# Глоссарий связывает их: BM25 ищет и по расшифровке, реранкер видит расшифровку в запросе,
# а модель получает «Справочник сокращений» и может расшифровать аббревиатуру в ответе.
#
# Формат glossary.json: {"СЗИ": "средства защиты информации", ...}. Ключи на «_» — комментарии.
# Свои записи важнее найденных автоматически.

AUTO_GLOSSARY_FILE = "auto_glossary.json"

LEGACY_GLOSSARY_KEYS = ("bm25_expansions", "bm25_phrase_boost", "rerank_abbreviations", "query_suffixes")

GLOSSARY_FUNCTION_WORDS = frozenset(
    "и в во по для на с со к ко от о об при из за до а или не над под "
    "of and for the to in on at by with a an or".split())


_ABBR_CORE = r"[A-ZА-ЯЁ][A-ZА-ЯЁa-zа-яё0-9]{1,11}"

_GL_WORD_RE = re.compile(r"[A-Za-zА-ЯЁа-яё0-9]+")

_GL_PAREN_AFTER_RE = re.compile(rf"\(\s*({_ABBR_CORE})\s*\)")                     # «полная форма (СОКР)»

_GL_ABBR_PAREN_RE = re.compile(rf"(?<![A-Za-zА-ЯЁа-яё0-9])({_ABBR_CORE})\s*\(([^()\n]{{3,160}})\)")  # «СОКР (полная)»

_GL_LIST_LINE_RE = re.compile(rf"^(?:[-•*·–—]\s*|\d+[.)]\s*)?({_ABBR_CORE})\s*[—–:-]\s*(.{{3,200}})$")

_GL_BREAK_RE = re.compile(r"[.;:!?\n()\[\]|]")


def is_abbreviation(token):
    """«СЗИ», «ПДн», «ГосСОПКА», «SLA»: от 2 заглавных букв, заглавных не меньше половины."""
    if not token or not (2 <= len(token) <= 12) or not re.fullmatch(_ABBR_CORE, token):
        return False
    upper = sum(1 for c in token if c.isupper())
    letters = sum(1 for c in token if c.isalpha())
    return 2 <= upper <= 10 and upper * 2 >= letters


def _abbr_letters(abbr):
    return [c.lower().replace("ё", "е") for c in abbr if c.isupper()]


def _letters_cover(words, letters, max_extra=2):
    """Покрывают ли слова (по порядку) все буквы сокращения: каждое значимое слово начинается со своей
    буквы и может «забрать» ещё до max_extra следующих букв, если они идут в нём по порядку (ГОСТ, НСД);
    служебные слова можно пропускать. Первое и последнее слово — значимые."""
    n, m = len(words), len(letters)
    if not n or not m or n > 2 * m + 4:
        return False
    if words[0] in GLOSSARY_FUNCTION_WORDS or words[-1] in GLOSSARY_FUNCTION_WORDS:
        return False
    memo = {}

    def f(i, k):
        key = (i, k)
        if key in memo:
            return memo[key]
        if i == n:
            res = k == m
        elif k == m:
            res = False
        else:
            w = words[i]
            res = False
            if w in GLOSSARY_FUNCTION_WORDS:
                res = f(i + 1, k)
            if not res and w[0] == letters[k]:
                res = f(i + 1, k + 1)
                pos, j = 0, k + 1
                while not res and j < m and j - k <= max_extra:
                    p = w.find(letters[j], pos + 1)
                    if p == -1:
                        break
                    pos, j = p, j + 1
                    res = f(i + 1, j)
        memo[key] = res
        return res

    return f(0, 0)


def _gl_spans(text):
    return [(m.group(0).lower().replace("ё", "е"), m.start(), m.end()) for m in _GL_WORD_RE.finditer(text)]


def _gl_clean_full(s):
    s = re.sub(r"\s+", " ", s).strip(" \t,;:—–-«»\"'")
    words = [w for w in s.split() if w[:1].isalpha() and w.lower() not in GLOSSARY_FUNCTION_WORDS]
    title_case = len(words) > 1 and all(w[0].isupper() for w in words)     # «Service Level Agreement»
    if len(s) > 1 and s[0].isupper() and s[1:2].islower() and not title_case:
        s = s[0].lower() + s[1:]
    return s


def _gl_match_forward(abbr, text):
    """Расшифровка в начале text: кратчайший префикс, где каждое слово даёт одну букву
    («средства защиты информации»); если такого нет — допускаются буквы внутри слов («ГОСТ»)."""
    letters = _abbr_letters(abbr)
    spans = _gl_spans(text)[: 2 * len(letters) + 4]
    words = [w for w, _, _ in spans]
    for max_extra in (0, 2):
        for e in range(1, len(words) + 1):
            if _letters_cover(words[:e], letters, max_extra):
                return _gl_clean_full(text[spans[0][1]:spans[e - 1][2]])
    return None


def _gl_match_backward(abbr, text):
    """Расшифровка в конце text (кратчайший суффикс; сначала строгое совпадение по первым буквам слов)."""
    letters = _abbr_letters(abbr)
    spans = _gl_spans(text)[-(2 * len(letters) + 4):]
    words = [w for w, _, _ in spans]
    for max_extra in (0, 2):
        for s in range(len(words) - 1, -1, -1):
            if _letters_cover(words[s:], letters, max_extra):
                return _gl_clean_full(text[spans[s][1]:spans[-1][2]])
    return None


def extract_abbreviations(text):
    """Пары (сокращение, расшифровка, вес) из текста. Вес: перечень/таблица сокращений — 3,
    «СОКР (расшифровка)» — 2, «расшифровка (СОКР)» — 1. Расшифровка принимается, только если
    первые буквы её слов складываются в сокращение."""
    text = text or ""
    found = []
    for m in _GL_PAREN_AFTER_RE.finditer(text):
        abbr = m.group(1)
        if not is_abbreviation(abbr):
            continue
        window = text[max(0, m.start() - 300):m.start()]
        breaks = [b.end() for b in _GL_BREAK_RE.finditer(window)]
        segment = window[breaks[-1]:] if breaks else window
        full = _gl_match_backward(abbr, segment)
        if full:
            found.append((abbr, full, 1))
    for m in _GL_ABBR_PAREN_RE.finditer(text):
        abbr = m.group(1)
        if is_abbreviation(abbr):
            full = _gl_match_forward(abbr, m.group(2))
            if full:
                found.append((abbr, full, 2))
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            for i in range(len(cells) - 1):
                if is_abbreviation(cells[i]):
                    full = _gl_match_forward(cells[i], cells[i + 1])
                    if full:
                        found.append((cells[i], full, 3))
            continue
        m = _GL_LIST_LINE_RE.match(s)
        if m and is_abbreviation(m.group(1)):
            full = _gl_match_forward(m.group(1), m.group(2))
            if full:
                found.append((m.group(1), full, 3))
    return [(a, f, w) for a, f, w in found if len(f) >= 4 and f.lower() != a.lower()]


def build_auto_glossary(parent_store):
    """Сокращения из всех фрагментов базы. Падежные формы одной расшифровки голосуют вместе;
    показывается самая «весомая» форма (из перечня сокращений, если он есть)."""
    votes = defaultdict(lambda: defaultdict(float))
    forms = defaultdict(Counter)
    sources = defaultdict(set)
    for pd in parent_store.values():
        for abbr, full, w in extract_abbreviations(pd.get("text") or ""):
            key = " ".join(bm25_tokenize(full))
            votes[abbr][key] += w
            forms[(abbr, key)][full] += w
            if pd.get("source"):
                sources[abbr].add(pd["source"])
    out = {}
    for abbr in sorted(votes):
        opts = votes[abbr]
        best = max(opts, key=opts.get)
        out[abbr] = {
            "full": forms[(abbr, best)].most_common(1)[0][0],
            "weight": round(opts[best], 1),
            "variants": len(opts),
            "sources": sorted(sources[abbr])[:5],
        }
    return out


def load_manual_glossary(path: Path):
    """Свой глоссарий. Понимает и старый формат v17 (bm25_expansions / rerank_abbreviations / ...)."""
    if not path or not path.is_file():
        return {}
    try:
        data = json.loads(_read_text_any(path))   # UTF-8 (с BOM или без) или Windows-1251 — после правки в Блокноте
    except Exception as e:
        logger.warning(f"⚠️ Глоссарий {path} не прочитан ({str(e)[:120]}).")
        return {}
    if not isinstance(data, dict):
        logger.warning(f"⚠️ Глоссарий {path} должен быть JSON-объектом — игнорируется.")
        return {}

    if any(k in data and isinstance(data[k], (dict, list)) for k in LEGACY_GLOSSARY_KEYS):
        out = {}
        for k, v in (data.get("rerank_abbreviations") or {}).items():
            if str(v).strip():
                out[str(k).strip()] = str(v).strip()
        have = {k.lower() for k in out}
        for k, forms_ in (data.get("bm25_expansions") or {}).items():
            if str(k).lower() not in have and isinstance(forms_, (list, tuple)) and forms_:
                out[str(k).strip().upper()] = " ".join(str(x) for x in forms_)
        logger.warning(
            f"📘 {path}: глоссарий в старом формате v17 — использованы rerank_abbreviations и bm25_expansions; "
            "bm25_phrase_boost и query_suffixes больше не нужны. Новый формат: {\"СЗИ\": \"средства защиты информации\"}."
        )
        return out

    out = {}
    for k, v in data.items():
        k = str(k).strip()
        if not k or k.startswith("_"):
            continue
        if isinstance(v, (list, tuple)):
            v = v[0] if v else ""
        v = str(v or "").strip()
        out[k] = v or None          # пустое значение — убрать ошибочную запись, найденную в документах
    return out


class Glossary:
    def __init__(self, manual: dict, auto: dict):
        removed = {a for a, f in manual.items() if not f}
        own = {a: f for a, f in manual.items() if f}
        merged = {a: f for a, f in auto.items() if a not in removed}
        merged.update(own)
        self.entries = merged
        self.origin = {a: (N_("свой") if a in own else N_("из документов")) for a in merged}
        self.manual_count = len(own)
        self.removed_count = sum(1 for a in removed if a in auto)
        self.auto_count = sum(1 for a in auto if a not in own and a not in removed)
        self._patterns = []
        self._full_forms = []      # (основы слов расшифровки, токен сокращения) — для поиска «полная форма → СОКР»
        for abbr, full in merged.items():
            # короткие (2 буквы: «ПО», «ИБ») — только с точным регистром, чтобы не путать с предлогами
            flags = re.IGNORECASE if len(abbr) >= 3 else 0
            pat = re.compile(rf"(?<![A-Za-zА-ЯЁа-яё0-9]){re.escape(abbr)}(?![A-Za-zА-ЯЁа-яё0-9])", flags)
            self._patterns.append((abbr, full, pat))
            stems = frozenset(t for t in bm25_tokenize(full) if t not in BM25_STOP_WORDS)
            abbr_tokens = bm25_tokenize(abbr)
            if len(stems) >= 2 and len(abbr_tokens) == 1 and abbr_tokens[0] not in BM25_STOP_WORDS:
                self._full_forms.append((stems, abbr_tokens[0]))

    def __len__(self):
        return len(self.entries)

    def find(self, text, limit=None):
        """Сокращения из глоссария, встретившиеся в тексте, — в порядке первого появления."""
        if not text or not self._patterns:
            return []
        hits = []
        for abbr, full, pat in self._patterns:
            m = pat.search(text)
            if m:
                hits.append((m.start(), abbr, full))
        hits.sort()
        out = [(a, f) for _, a, f in hits]
        return out[:limit] if limit else out

    def bm25_terms(self, query, weight=0.5):
        """Дополнительные термины BM25 (с весом 0.5) в обе стороны: слова расшифровки, если в запросе есть
        сокращение («СЗИ» → «средства защиты информации»), и сокращение, если в запросе есть вся его
        расшифровка («средства защиты информации» → «СЗИ»)."""
        q_tokens = set(bm25_tokenize(query))
        seen, out = set(), []
        for _abbr, full in self.find(query):
            for t in bm25_tokenize(full):
                if t in BM25_STOP_WORDS or t in seen or t in q_tokens:
                    continue
                seen.add(t)
                out.append((t, weight))
        for stems, abbr_token in self._full_forms:
            if abbr_token not in q_tokens and abbr_token not in seen and stems <= q_tokens:
                seen.add(abbr_token)
                out.append((abbr_token, weight))
        return out

    def enrich_query(self, query, max_chars=1500):
        """Добавляет расшифровки к запросу реранкера."""
        extra = [f"{a} ({f})" for a, f in self.find(query)]
        if not extra:
            return (query or "")[:max_chars]
        return f"{query}\n{'; '.join(extra)}"[:max_chars]

    def reference_block(self, question, context="", max_entries=20):
        """«Справочник сокращений» для модели: сначала сокращения из вопроса, затем из контекста."""
        found = self.find(question)
        names = {a for a, _ in found}
        for a, f in self.find(context):
            if a not in names:
                found.append((a, f))
                names.add(a)
        found = found[:max_entries]
        return "\n".join(f"- {a} — {f}" for a, f in found)

    def rows(self):
        return [{tr("Сокращение"): a, tr("Расшифровка"): f, tr("Откуда"): tr(self.origin[a])}
                for a, f in sorted(self.entries.items())]

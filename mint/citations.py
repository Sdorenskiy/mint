"""Проверка ссылок в ответе чата.

Промпт требует ссылку [Источник: файл, раздел] на каждый факт. Ссылка сверяется с фрагментами, которые модель
реально получила: файл должен быть среди источников контекста, а раздел — среди заголовков этого файла
(путь заголовков, заголовки внутри фрагмента, название таблицы). Ссылка мимо контекста — признак выдуманного
утверждения: она помечается ⚠️, а под ответом показывается предупреждение. Проверка детерминированная, без
вызова модели.
"""

import re

from .bm25 import normalize_token
from .i18n import tr

MARK = " ⚠️"

_CITE_RE = re.compile(r"\[\s*(?:Источник|Источники|Source|Sources)\s*:\s*([^\[\]\n]+?)\s*\]", re.IGNORECASE)

_BLOCK_RE = re.compile(r"^=== (?:ИСТОЧНИК|SOURCE): (.*) ===$", re.MULTILINE)

_HEADING_LINE_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)

_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)*|[a-zа-яё]+")

_EXT_RE = re.compile(r"\.(?:docx?|pdf|txt|md)$", re.IGNORECASE)

# слова, которыми модель оформляет ссылку, а не название раздела
_GENERIC = frozenset(normalize_token(w) for w in (
    "раздел разделы подраздел пункт п глава часть стр см таблица табл "
    "section subsection chapter clause part page p see table".split()))


def _tokens(text):
    toks = set()
    for t in _TOKEN_RE.findall((text or "").lower().replace("ё", "е")):
        toks.add(t.replace(",", ".").rstrip(".") if t[0].isdigit() else normalize_token(t))
    return toks


def _norm_file(name):
    n = _EXT_RE.sub("", (name or "").strip().lower().replace("ё", "е"))
    return re.sub(r"[\s_\-]+", " ", n).strip(" .«»\"'")


def context_sources(context):
    """Файлы контекста и слова их заголовков: {норм. имя файла: {"name": имя, "tokens": set}}."""
    index = {}
    blocks = list(_BLOCK_RE.finditer(context or ""))
    for i, m in enumerate(blocks):
        end = blocks[i + 1].start() if i + 1 < len(blocks) else len(context)
        parts = m.group(1).split(" | ")
        name = parts[0].strip()
        entry = index.setdefault(_norm_file(name), {"name": name, "tokens": set()})
        for head in parts[1:] + _HEADING_LINE_RE.findall(context[m.end():end]):
            entry["tokens"] |= _tokens(head)
    return index


def _match_file(cited, index):
    n = _norm_file(cited)
    if not n:
        return None
    if n in index:
        return index[n]
    for key, entry in index.items():
        if min(len(n), len(key)) >= 4 and (n in key or key in n):
            return entry
    return None


def _split_citation(inner, index):
    """«файл, раздел; файл2» → [(файл, раздел), (файл2, "")]. Имя файла с запятой узнаётся по контексту."""
    out = []
    names = sorted((e["name"] for e in index.values()), key=len, reverse=True)
    for piece in (p.strip() for p in inner.split(";")):
        if not piece:
            continue
        low = piece.lower()
        for name in names:
            for form in (name, _EXT_RE.sub("", name)):
                if form and low.startswith(form.lower()):
                    out.append((piece[:len(form)], piece[len(form):].lstrip(" ,:—–-")))
                    break
            else:
                continue
            break
        else:
            file_part, _, section = piece.partition(",")
            section = section.strip()
            if section and _match_file(section, index) is not None:    # «a.docx, b.docx» — два файла
                out += [(file_part.strip(), ""), (section, "")]
            else:
                out.append((file_part.strip(), section))
    return out


def _section_ok(section, entry):
    toks = _tokens(section) - _GENERIC
    if not toks:
        return True
    missing = toks - entry["tokens"]
    return not missing or (len(toks) >= 4 and len(missing) <= len(toks) // 4)


def check_citations(answer, context):
    """Ссылки ответа: [{"text", "start", "end", "ok", "reason"}]; reason — "file" (файла нет среди источников
    контекста) или "section" (у файла в контексте нет такого раздела)."""
    index = context_sources(context)
    out = []
    for m in _CITE_RE.finditer(answer or ""):
        reason = None
        for cited_file, section in _split_citation(m.group(1), index):
            entry = _match_file(cited_file, index)
            if entry is None:
                reason = "file"
                break
            if not _section_ok(section, entry):
                reason = reason or "section"
        out.append({"text": m.group(0), "start": m.start(), "end": m.end(), "ok": reason is None, "reason": reason})
    return out


def cited_files(answer, context):
    """Файлы, на которые ссылается ответ: имя из контекста, если ссылка на него указывает, иначе — как написано."""
    index = context_sources(context)
    names = []
    for m in _CITE_RE.finditer(answer or ""):
        for cited_file, _section in _split_citation(m.group(1), index):
            entry = _match_file(cited_file, index)
            names.append(entry["name"] if entry else cited_file)
    return names


def mark_invalid(answer, checks):
    """Ответ с пометкой ⚠️ после каждой ссылки, которой нет в контексте."""
    text = answer or ""
    for c in sorted((c for c in checks if not c["ok"]), key=lambda c: c["start"], reverse=True):
        text = text[:c["end"]] + MARK + text[c["end"]:]
    return text


def citation_warning(invalid_texts):
    """Предупреждение под ответом (пустая строка — все ссылки в порядке)."""
    if not invalid_texts:
        return ""
    return tr("⚠️ Ссылки, которых нет среди найденных фрагментов ({n}): {refs}. Утверждения с этими ссылками "
              "проверьте по документам — модель могла их додумать.", n=len(invalid_texts),
              refs="; ".join(dict.fromkeys(invalid_texts)))

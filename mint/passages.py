"""Сборка контекста для модели из найденных parent-фрагментов.

1. Склейка соседей. Соседние parent-фрагменты одного документа перекрываются (parent_overlap); если найдены оба,
   они склеиваются в один блок без повтора перекрытия и в порядке документа. Блоки идут по релевантности
   лучшего участника, поэтому самый полезный текст остаётся первым.
2. Окно вокруг найденного места. Фрагмент длиннее лимита обрезается не с начала, а вокруг найденного child
   (или самого плотного по словам вопроса места); перед окном ставится ближайший заголовок выше него, чтобы
   модель верно указала раздел в ссылке.
"""

import re

from .bm25 import bm25_tokenize, densest_span
from .text import smart_truncate

ELLIPSIS = "…"

MIN_OVERLAP = 20             # столько символов перекрытия достаточно, чтобы считать фрагменты соседями

_HEADING_RE = re.compile(r"^#{1,6}\s+\S.*$", re.MULTILINE)

_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}")


# ---------------------------------------------------------------- склейка соседних фрагментов

def join_overlapping(a, b):
    """Текст a + b без повтора перекрытия (конец a совпадает с началом b) или None, если перекрытия нет.
    Берётся самое длинное совпадение (не длиннее b и половины a): в тексте с повторами короткое совпадение
    бывает и случайным."""
    if not a or not b or len(b) < MIN_OVERLAP:
        return None
    probe = b[:MIN_OVERLAP]
    pos = a.find(probe, max(0, len(a) - min(len(b), len(a) // 2)))
    while pos != -1:
        if b.startswith(a[pos:]):
            return a[:pos] + b
        pos = a.find(probe, pos + 1)
    return None


def merge_adjacent(selected, parent_store, order):
    """Группы из выбранных parent_id: подряд идущие текстовые фрагменты одного документа с подтверждённым
    перекрытием склеиваются. order — номер фрагмента в базе (фрагменты документа хранятся подряд, в порядке
    текста). Возвращает [(ids в порядке документа, текст)] в порядке лучшего (самого релевантного) участника."""
    rank = {p: i for i, p in enumerate(selected)}
    by_source = {}
    for p in selected:
        pd = parent_store[p]
        if pd.get("type") != "table" and p in order:
            by_source.setdefault(pd.get("source", ""), []).append(p)

    groups, grouped = [], set()
    for ps in by_source.values():
        ps.sort(key=order.get)
        ids, text = [ps[0]], parent_store[ps[0]].get("text") or ""
        for p in ps[1:]:
            joined = None
            if order[p] == order[ids[-1]] + 1:
                joined = join_overlapping(text, parent_store[p].get("text") or "")
            if joined is None:
                groups.append((ids, text))
                ids, text = [p], parent_store[p].get("text") or ""
            else:
                ids, text = ids + [p], joined
        groups.append((ids, text))
    grouped = {p for ids, _ in groups for p in ids}
    groups += [([p], parent_store[p].get("text") or "") for p in selected if p not in grouped]
    groups.sort(key=lambda g: min(rank[p] for p in g[0]))
    return groups


# ---------------------------------------------------------------- окно вокруг найденного места

def _snap_start(text, s, latest, max_shift):
    """Начало окна сдвигается вперёд к началу строки, предложения или слова (не дальше latest)."""
    if s <= 0:
        return 0
    if text[s - 1] == "\n":
        return s
    zone = text[s:min(latest, s + max_shift)]
    k = zone.find("\n")
    if k != -1:
        return s + k + 1
    m = re.search(r"[.!?;]\s+", zone)
    if m:
        return s + m.end()
    k = zone.find(" ")
    return s + k + 1 if k != -1 else s


def _drop_trailing_heading(body, keep_until=0):
    """Убирает последнюю строку, если это заголовок (или его обрубок после обрезки по точке): заголовок в конце
    окна без своего текста модели не нужен. keep_until — длина, которую нельзя отрезать (найденное место)."""
    nl = body.rfind("\n")
    if nl != -1 and nl >= keep_until and body[nl + 1:].lstrip().startswith("#"):
        return body[:nl].rstrip()
    return body


def _focus_table(text, limit, anchor, term_weights):
    """Таблица: название и шапка остаются, из строк — те, что вокруг найденной строки."""
    lines = text.split("\n")
    head_n = 1
    if len(lines) > 2 and _TABLE_SEP_RE.match(lines[2]):
        head_n = 3
    elif len(lines) > 1 and lines[1].lstrip().startswith("|"):
        head_n = 2
    head, rows = lines[:head_n], lines[head_n:]
    if not rows:
        return smart_truncate(text, limit)
    at = None
    if anchor:
        row_set = set(rows)
        for ln in anchor.split("\n"):
            if ln.strip() and ln in row_set and ln not in head:
                at = rows.index(ln)
                break
    if at is None and term_weights:
        scores = [sum(term_weights.get(t, 0.0) for t in set(bm25_tokenize(r))) for r in rows]
        if max(scores) > 0:
            at = scores.index(max(scores))
    at = at or 0
    budget = limit - len("\n".join(head)) - 2 * (len(ELLIPSIS) + 1)
    lo = hi = at
    used = len(rows[at]) + 1
    grew = True
    while grew:
        grew = False
        if hi + 1 < len(rows) and used + len(rows[hi + 1]) + 1 <= budget:
            hi += 1
            used += len(rows[hi]) + 1
            grew = True
        if lo > 0 and used + len(rows[lo - 1]) + 1 <= budget:
            lo -= 1
            used += len(rows[lo]) + 1
            grew = True
    out = head + ([ELLIPSIS] if lo > 0 else []) + rows[lo:hi + 1] + ([ELLIPSIS] if hi < len(rows) - 1 else [])
    return "\n".join(out)


def focus_passage(text, limit, anchor=None, term_weights=None, is_table=False):
    """Текст фрагмента не длиннее limit (с точностью до заголовка и многоточий). Если длиннее — окно вокруг
    найденного места: anchor (текст найденного child) или самого плотного по словам запроса участка; если ни
    того ни другого нет — начало фрагмента, как раньше. Вырезанные края помечаются «…»; перед окном —
    ближайший заголовок выше него («## …»), чтобы модель верно назвала раздел."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    if is_table:
        return _focus_table(text, limit, anchor, term_weights)

    span = None
    if anchor:
        pos = text.find(anchor.strip())
        if pos != -1:
            span = (pos, pos + len(anchor.strip()))
    if span is None and term_weights:
        s, e, score = densest_span(text, term_weights, max(100, limit // 2))
        if score:
            span = (s, e)
    head_cut = _drop_trailing_heading(smart_truncate(text, limit), span[1] if span else 0)
    if span is None or span[1] <= len(head_cut):
        return head_cut                     # найденное и так в начале — обрезка как раньше

    reserve = min(150, limit // 8)          # заголовок перед окном и многоточия
    size = max(100, limit - reserve)
    a0, a1 = span
    s = a0 if a1 - a0 >= size else a0 - (size - (a1 - a0)) // 2
    s = max(0, min(s, len(text) - size))
    s = _snap_start(text, s, a0, size // 4)
    line_start = text.rfind("\n", 0, s) + 1
    if _HEADING_RE.match(text, line_start) and line_start < s:
        s = line_start                      # начало попало внутрь строки заголовка — берём заголовок целиком
    s += len(text[s:]) - len(text[s:].lstrip())
    rest = text[s:]
    body = smart_truncate(rest, size).strip()
    if s + len(body) < a1:                  # граница предложения отрезала бы найденное — режем по слову
        k = max(size, a1 - s)
        piece = rest[:k]
        if k < len(rest):
            sp = piece.rfind(" ")
            if sp >= a1 - s:
                piece = piece[:sp]
        body = piece.strip()
    body = _drop_trailing_heading(body, a1 - s)
    end = s + len(body)

    prefix = ""
    if s > 0:
        heads = list(_HEADING_RE.finditer(text, 0, s))
        if heads and not body.startswith("#"):
            prefix = heads[-1].group(0).strip() + "\n\n"
        prefix += ELLIPSIS + " "
    suffix = ""
    if end < len(text):
        last_line = body[body.rfind("\n") + 1:]
        suffix = ("\n" if last_line.lstrip().startswith("#") else " ") + ELLIPSIS
    return f"{prefix}{body}{suffix}"

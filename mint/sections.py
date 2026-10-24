"""Структура документа для аудита: блоки с путём заголовков, оглавление и части для проверки по разделам.

Раньше документ резался на части по размеру: таблица отрывалась от своего заголовка, процесс из одной таблицы
оказывался в двух частях, а модель, видя кусок таблицы с середины, писала «нумерация начинается с 3.2».
Теперь часть — это раздел документа (заголовок с его текстом и таблицами); мелкие соседние разделы
объединяются, крупный режется, и каждая часть знает, из какого она раздела.
"""

import re

from .i18n import tr
from .text import heading_path_str, split_with_overlap_pos

_ATX_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}")

SOFT_FACTOR = 1.5      # раздел до 1,5 лимита части не режется: таблица процесса остаётся целой со своим заголовком
TABLE_ROOM = 300       # место в части под заголовок и пометку «продолжение таблицы»


def _is_table(text):
    lines = [ln for ln in text.split("\n") if ln.strip()]
    return len(lines) >= 2 and all(ln.lstrip().startswith("|") for ln in lines)


def document_blocks(md):
    """Блоки Markdown по порядку: [{text, level, title, path}]. level > 0 — заголовок («#» × level), path —
    путь заголовков «Раздел → Подраздел» (у заголовка — включая его самого)."""
    stack, blocks = [], []

    def path():
        return heading_path_str([t for _, t in stack])

    def add_text(lines):
        text = "\n".join(lines).strip()
        if text:
            blocks.append({"text": text, "level": 0, "title": "", "path": path()})

    in_code = False
    for para in re.split(r"\n[ \t]*\n", md or ""):
        buf = []
        for line in para.split("\n"):
            if line.lstrip().startswith(("```", "~~~")):
                in_code = not in_code            # «# комментарий» в блоке кода — не заголовок
            m = None if in_code else _ATX_RE.match(line)
            if m and not line.lstrip().startswith("|"):
                add_text(buf)
                buf = []
                level, title = len(m.group(1)), m.group(2).strip()
                stack = [s for s in stack if s[0] < level] + [(level, title)]
                blocks.append({"text": line.strip(), "level": level, "title": title, "path": path()})
            else:
                buf.append(line)
        add_text(buf)
    return blocks


def document_outline(blocks, max_chars=6000):
    """Оглавление документа (заголовки с отступом по уровню) — для проверки части, когда документ целиком
    в окно модели не помещается."""
    lines, total = [], 0
    for b in blocks:
        if b["level"]:
            line = "  " * (b["level"] - 1) + b["title"]
            if total + len(line) + 1 > max_chars:
                lines.append("…")
                break
            lines.append(line)
            total += len(line) + 1
    return "\n".join(lines)


def section_label(path, max_chars=90):
    """Короткое название раздела для заключения: последний заголовок пути («2.2.3 Описание …»)."""
    last = (path or "").split(" → ")[-1].strip()
    return last if len(last) <= max_chars else last[:max_chars - 1].rstrip() + "…"


def _split_table(block, max_chars):
    """Большая таблица → части по строкам; шапка повторяется, у продолжения — пометка, с какой строки."""
    lines = [ln for ln in block["text"].split("\n") if ln.strip()]
    if len(lines) >= 2 and _TABLE_SEP_RE.match(lines[1]):
        header, body = lines[:2], lines[2:]
    else:
        header, body = lines[:1], lines[1:]
    limit = max(max_chars // 2, max_chars - TABLE_ROOM)
    chunks, cur, cur_len, first_row = [], [], len("\n".join(header)), 1
    for row in body:
        if cur and cur_len + len(row) + 1 > limit:
            chunks.append((first_row, cur))
            first_row += len(cur)
            cur, cur_len = [], len("\n".join(header))
        cur.append(row)
        cur_len += len(row) + 1
    if cur:
        chunks.append((first_row, cur))
    out = []
    for i, (row_no, rows) in enumerate(chunks):
        text = "\n".join(header + rows)
        if i:
            text = tr("(продолжение таблицы: строки с {n}-й, шапка повторена)", n=row_no) + "\n" + text
        out.append({**block, "text": text, "continued": bool(i)})
    return out


def _expand(block, max_chars):
    """Блок длиннее лимита части → несколько блоков (таблица — по строкам, текст — по предложениям)."""
    if len(block["text"]) <= max_chars or block["level"]:
        return [block]
    if _is_table(block["text"]):
        return _split_table(block, max_chars)
    return [{**block, "text": chunk, "continued": bool(i)}
            for i, (_s, _e, chunk) in enumerate(split_with_overlap_pos(block["text"], max_chars, 0))]


def _pack(blocks, max_chars):
    """Блоки → группы не длиннее лимита; заголовок в конце группы переносится в следующую — к своему тексту."""
    groups, cur, cur_len = [], [], 0
    for b in blocks:
        add = len(b["text"]) + (2 if cur else 0)
        if cur and cur_len + add > max_chars:
            carry = []
            while len(cur) > 1 and cur[-1]["level"]:
                carry.insert(0, cur.pop())
            groups.append(cur)
            cur = carry
            cur_len = len("\n\n".join(x["text"] for x in cur))
            add = len(b["text"]) + (2 if cur else 0)
        cur.append(b)
        cur_len += add
    if cur:
        groups.append(cur)
    return groups


def _make_part(blocks):
    spans, texts, pos = [], [], 0
    for b in blocks:
        spans.append((pos, b["path"]))
        texts.append(b["text"])
        pos += len(b["text"]) + 2
    first = blocks[0]
    return {"text": "\n\n".join(texts), "path": first["path"], "spans": spans,
            "continued": not first["level"] and bool(first["path"])}


def split_document_parts(md, max_chars):
    """Документ → части для проверки по разделам: [{text, path, spans, continued}].
    Раздел (заголовок, его текст и таблицы) не режется, если он не длиннее SOFT_FACTOR × max_chars; соседние
    мелкие разделы объединяются до max_chars; длинный раздел режется (таблица — по строкам с повтором шапки).
    path — раздел, с которого начинается часть; spans — [(смещение в тексте части, путь раздела)];
    continued — часть начинается не с заголовка (продолжение раздела)."""
    max_chars = max(50, int(max_chars))
    units = []
    for b in document_blocks(md):
        if b["level"] or not units:
            units.append([b])
        else:
            units[-1].append(b)

    parts, cur, cur_len = [], [], 0
    for unit in units:
        u_len = len("\n\n".join(b["text"] for b in unit))
        if cur and cur_len + 2 + u_len <= max_chars:
            cur += unit
            cur_len += 2 + u_len
            continue
        if cur:
            carry = []                       # заголовки без текста в конце части — к своему тексту, в следующую
            while len(cur) > 1 and cur[-1]["level"]:
                carry.insert(0, cur.pop())
            parts.append(_make_part(cur))
            if carry:
                unit = carry + unit
                u_len = len("\n\n".join(b["text"] for b in unit))
            cur, cur_len = [], 0
        if u_len <= max_chars * SOFT_FACTOR:
            cur, cur_len = list(unit), u_len
            continue
        expanded = [x for b in unit for x in _expand(b, max_chars)]
        groups = _pack(expanded, max_chars)
        for g in groups[:-1]:
            parts.append(_make_part(g))
        cur = groups[-1]
        cur_len = len("\n\n".join(b["text"] for b in cur))
    if cur:
        parts.append(_make_part(cur))
    return parts


def whole_document_part(md):
    """Весь документ одной частью (режим «весь документ одним запросом»): с разделами для привязки замечаний."""
    blocks = document_blocks(md)
    if not blocks:
        return {"text": (md or "").strip(), "path": "", "spans": [], "continued": False}
    return _make_part(blocks)


def part_path_at(part, offset):
    """Раздел, к которому относится место в тексте части (по смещению)."""
    path = part.get("path", "")
    for start, p in part.get("spans") or []:
        if start <= offset:
            path = p
        else:
            break
    return path

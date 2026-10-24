"""Обработка текста: нормализация, обрезка по границам, разметка."""

import json
import os
import re
import tempfile
from pathlib import Path


def smart_truncate(text, max_chars=1500):
    """Обрезает текст по границе предложения / строки / ячейки таблицы."""
    if len(text) <= max_chars:
        return text

    slice_zone = text[:max_chars + 200]
    # Граница принимается, только если сохраняет хотя бы половину лимита: иначе «Заголовок\n» + длинный абзац
    # без точек обрезался до одного заголовка и весь текст фрагмента терялся.
    for m in reversed(list(re.finditer(r'(?<=[.!?])\s+|\n|\|', slice_zone))):
        end_pos = m.end()
        if end_pos <= max_chars + 50:
            if end_pos >= max_chars // 2:
                return text[:end_pos].strip()
            break

    space_fallback = slice_zone[:max_chars].rfind(" ")
    if space_fallback > max_chars // 2:
        return slice_zone[:space_fallback].strip()

    return text[:max_chars].strip()


def clean_docling_markdown(raw_md_text):
    """Убирает повторы, которые Docling создаёт для объединённых ячеек и дублированного текста."""
    cleaned_lines = []
    for line in (raw_md_text or "").split("\n"):
        strip_line = line.strip()

        if "|" in strip_line and len(strip_line) > 10:
            raw_cells = line.split("|")
            cleaned_cells = []
            prev_cell_text = None   # объединённая ячейка Docling = одинаковый текст в СОСЕДНИХ ячейках

            for cell in raw_cells:
                cell_strip = cell.strip()
                if cell_strip.startswith(":") or cell_strip.startswith("-"):
                    cleaned_cells.append(cell)
                    prev_cell_text = None
                    continue
                if re.match(r"^\d+\.?$", cell_strip) or cell_strip.lower() in ["№", "№ п/п", "п/п"]:
                    cleaned_cells.append(cell)
                    prev_cell_text = None
                    continue
                if cell_strip and len(cell_strip) > 10 and cell_strip == prev_cell_text:
                    cleaned_cells.append(" ")
                    continue
                prev_cell_text = cell_strip or None

                internal_match = re.search(r"(.{15,250})\s+\1", cell_strip)
                if internal_match:
                    u_phrase = internal_match.group(1).strip()
                    deduped = cell_strip[:internal_match.start()] + u_phrase + cell_strip[internal_match.end():]
                    cell = cell.replace(cell_strip, deduped)

                cleaned_cells.append(cell)

            line = "|".join(cleaned_cells)

        elif len(strip_line) > 20:
            text_match = re.search(r"(.{15,250})\s+\1", strip_line)
            if text_match:
                unique_phrase = text_match.group(1).strip()
                if strip_line.count(unique_phrase) > 1:
                    deduped = strip_line[:text_match.start()] + unique_phrase + strip_line[text_match.end():]
                    line = line.replace(strip_line, deduped)

        cleaned_lines.append(line)

    return compact_markdown_tables("\n".join(cleaned_lines))


_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
_SEPARATOR_CELL_RE = re.compile(r"\s*:?-{2,}:?\s*")


def compact_markdown_tables(md):
    """Убирает выравнивание в таблицах Markdown: «| a      | b   |» → «| a | b |», «|------|---|» → «|---|---|».
    Docling выравнивает столбцы пробелами и чёрточками по самой длинной ячейке столбца: документ с таблицами
    вырастает вдвое — это лишние токены модели и лишние части при аудите. Текст ячеек не меняется."""
    out = []
    for line in (md or "").split("\n"):
        if _TABLE_ROW_RE.match(line):
            cells = _CELL_SPLIT_RE.split(line.strip())[1:-1]
            if cells and all(_SEPARATOR_CELL_RE.fullmatch(c) for c in cells):
                cells = [(":" if c.strip().startswith(":") else "") + "---"
                         + (":" if c.strip().endswith(":") and len(c.strip()) > 1 else "") for c in cells]
            else:
                cells = [" ".join(c.split()) for c in cells]
            line = "| " + " | ".join(cells) + " |"
        out.append(line)
    return "\n".join(out)


def clean_table_markdown(raw_table_md):
    cleaned_lines = []
    for line in (raw_table_md or "").split("\n"):
        cells = [c.strip() for c in line.split("|") if c.strip()]
        is_separator = bool(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells)
        if len(cells) > 1 and len(set(cells)) == 1 and not is_separator:
            line = f"| {cells[0]} |"
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def split_with_overlap_pos(text, chunk_size, overlap):
    """Режет текст на чанки с перекрытием. Возвращает [(start, end, chunk)] — смещения чанка
    в тексте (после .strip() исходного текста): по ним чанк привязывается к заголовку раздела."""
    text = (text or "").strip()
    if not text:
        return []
    chunk_size = max(50, int(chunk_size))
    overlap = max(0, int(overlap))
    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 4)
    if len(text) <= chunk_size:
        return [(0, len(text), text)]

    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            end = start + _chunk_cut(text[start:end], chunk_size)
        raw = text[start:end]
        piece = raw.strip()
        if piece:
            lead = len(raw) - len(raw.lstrip())
            chunks.append((start + lead, start + lead + len(piece), piece))
        if end >= n:
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = end
        elif next_start < end:
            # перекрытие начинается с целого слова, а не с его середины
            sp = text.find(" ", next_start, min(end, next_start + 40))
            if sp != -1 and text[next_start - 1:next_start] not in (" ", "\n"):
                next_start = sp + 1
        start = next_start
    return chunks


_HEADING_LINE_RE = re.compile(r"^#{1,6}\s")

_SENTENCE_ENDS = (". ", "! ", "? ", "; ", ".\n", "!\n", "?\n", ";\n")


def _chunk_cut(window, chunk_size):
    """Длина чанка внутри окна: по приоритету — граница абзаца, строки, предложения, слова.
    Раньше бралась самая правая из всех границ, то есть почти всегда последний пробел: чанки рвались
    посреди предложения даже при абзаце в пределах окна. Заголовок («## …») в конце чанка переносится
    в следующий — вместе со своим текстом."""
    half, third = chunk_size // 2, chunk_size // 3
    cut = window.rfind("\n\n")
    if cut >= half:
        end = cut + 2
    else:
        cut = window.rfind("\n")
        if cut >= half:
            end = cut + 1
        else:
            cut = max(window.rfind(s) for s in _SENTENCE_ENDS)
            if cut >= third:
                end = cut + 2
            else:
                cut = window.rfind(" ")
                if cut < third:
                    return len(window)
                end = cut
    body = window[:end].rstrip()
    nl = body.rfind("\n")
    if nl >= third and _HEADING_LINE_RE.match(body[nl + 1:].lstrip()):
        end = nl + 1
    return end


def split_table_markdown(md, max_chars):
    """Режет markdown-таблицу по группам СТРОК; шапка колонок повторяется в каждой части."""
    lines = [ln for ln in (md or "").split("\n") if ln.strip()]
    if not lines:
        return []
    if len("\n".join(lines)) <= max_chars:
        return ["\n".join(lines)]

    if len(lines) >= 2 and re.match(r"^\s*\|?\s*:?-{2,}", lines[1]):
        header, body = lines[:2], lines[2:]
    else:
        header, body = lines[:1], lines[1:]
    header_len = len("\n".join(header))

    parts, cur, cur_len = [], [], header_len
    for row in body:
        add = len(row) + 1
        if cur and cur_len + add > max_chars:
            parts.append("\n".join(header + cur))
            cur, cur_len = [], header_len
        cur.append(row)
        cur_len += add
    if cur:
        parts.append("\n".join(header + cur))
    return parts or ["\n".join(lines)]


def heading_path_str(stack, max_chars=220):
    """Путь заголовков «Раздел → Подраздел»; слишком длинный путь укорачивается слева."""
    parts = [h.strip() for h in stack if h and h.strip()]
    s = " → ".join(parts)
    if len(s) <= max_chars:
        return s
    while len(parts) > 1 and len("… → " + " → ".join(parts)) > max_chars:
        parts = parts[1:]
    return ("… → " + " → ".join(parts))[:max_chars]


def short_path(path, max_chars=90):
    path = path or ""
    return path if len(path) <= max_chars else "…" + path[-(max_chars - 1):]


def _is_table_block(block):
    lines = [ln for ln in block.split("\n") if ln.strip()]
    return len(lines) >= 2 and all(ln.lstrip().startswith("|") for ln in lines)


def split_into_sections(md_text, max_chars):
    """Нарезка текста на разделы по абзацам (аудит и контроль исправлений).
    Абзац длиннее max_chars делится (таблица — по строкам с повтором шапки, текст — по границам предложений):
    раньше большая таблица становилась одним разделом в несколько раз больше лимита и не помещалась в окно
    модели. Заголовок в конце раздела переносится в следующий раздел — к своему тексту."""
    max_chars = max(50, int(max_chars))
    blocks = []
    for p in (md_text or "").split("\n\n"):
        p = p.strip()
        if not p:
            continue
        if len(p) <= max_chars:
            blocks.append(p)
        elif _is_table_block(p):
            blocks.extend(split_table_markdown(p, max_chars))
        else:
            blocks.extend(c for _s, _e, c in split_with_overlap_pos(p, max_chars, 0))

    sections, current, cur_len = [], [], 0
    for b in blocks:
        if current and cur_len + 2 + len(b) > max_chars:
            carry = []
            while len(current) > 1 and _HEADING_LINE_RE.match(current[-1]) and "\n" not in current[-1]:
                carry.insert(0, current.pop())
            sections.append("\n\n".join(current))
            current = carry
            cur_len = len("\n\n".join(current))
        cur_len += (2 if current else 0) + len(b)
        current.append(b)
    if current:
        sections.append("\n\n".join(current))
    return sections


def norm_for_match(s):
    return re.sub(r"[^0-9a-zа-яё]+", " ", (s or "").lower().replace("ё", "е")).strip()


def quote_in_text(quote, text):
    """Цитата найдена в тексте? Сравнение без учёта регистра, знаков препинания и markdown."""
    nq = norm_for_match(quote)
    if len(nq) < 12:
        return False
    return nq in norm_for_match(text)


def _json_end(s, start):
    """Где кончается JSON-значение, начатое скобкой s[start] («[» или «{»), с учётом строк; -1 — не закрыто."""
    depth, in_str, esc = 0, False, False
    for k in range(start, len(s)):
        c = s[k]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return k
    return -1


def _json_loads(chunk):
    """json.loads, который прощает висячие запятые («[1, 2,]», «{"a": 1,}»); None — не разобрано."""
    for t in (chunk, re.sub(r",\s*([\]}])", r"\1", chunk)):
        try:
            return json.loads(t)
        except Exception:
            pass
    return None


def _array_ok(v):
    """Ответ-массив: из объектов или массивов (номера внутри объекта — «found»: [3, 7] — не ответ целиком)."""
    return isinstance(v, list) and all(isinstance(x, (dict, list)) for x in v)


def extract_json(text, kind="array"):
    """Достаёт JSON-массив/объект из ответа модели. Допускает обёртку ```json, лишний текст (в том числе со
    скобками) до и после, висячие запятые. Массив, который модель не закрыла (ответ оборван) или не написала
    вовсе (объекты по одному на строку), собирается из целых объектов. None — ничего не разобрано."""
    s = re.sub(r"```(?:json)?", "", (text or "")).strip()
    pairs = (("[", "]"), ("{", "}")) if kind == "array" else (("{", "}"), ("[", "]"))
    for open_ch, close_ch in pairs:             # обычный случай: от первой открывающей до последней закрывающей
        i, j = s.find(open_ch), s.rfind(close_ch)
        if i != -1 and j > i:
            v = _json_loads(s[i:j + 1])
            if v is not None and (kind != "array" or (open_ch == "[" and _array_ok(v))):
                return v
    want = "[" if kind == "array" else "{"
    for start in [k for k, c in enumerate(s) if c == want]:        # первое целое значение нужного вида
        end = _json_end(s, start)
        if end != -1:
            v = _json_loads(s[start:end + 1])
            if v is not None and (kind != "array" or _array_ok(v)):
                return v
    if kind == "array":                         # массив оборван или не написан — целые объекты по порядку
        objs, k = [], 0
        while True:
            start = s.find("{", k)
            if start == -1:
                break
            end = _json_end(s, start)
            if end == -1:
                break
            v = _json_loads(s[start:end + 1])
            if isinstance(v, dict):
                objs.append(v)
            k = end + 1
        if objs:
            return objs
    return None


def atomic_write_json(path: Path, data):
    """Запись JSON через временный файл: читатели никогда не видят наполовину записанный файл."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

"""Разбор документов: .docx (Docling), .pdf (mint/pdfparse.py, без моделей), .md и .txt (здесь).

parse_document() — структура для базы знаний (текстовые блоки с путём заголовков и таблицы),
document_to_markdown() — Markdown для аудита и контроля исправлений. Оба выбирают разбор по расширению файла.
"""

import logging
import os
import re
import tempfile
import threading

from .cache import _process_cache
from .i18n import N_, tr
from .text import clean_docling_markdown, compact_markdown_tables, heading_path_str

logger = logging.getLogger("MINT")

SUPPORTED_FORMATS = ("docx", "pdf", "md", "txt")          # загрузчики в интерфейсе принимают эти расширения

STRUCTURE_LABELS = {
    "styles": N_("стили заголовков Word"),
    "outline": N_("закладки PDF"),
    "toc": N_("страница «Содержание»"),
    "slides": N_("заголовки слайдов"),
    "font": N_("размер и жирность шрифта (приблизительно)"),
    "markdown": N_("заголовки Markdown"),
    "numbering": N_("нумерованные строки"),
    "none": N_("заголовков нет"),
}


class DocumentUnreadable(ValueError):
    """Документ не читается без распознавания (скан, испорченная кодировка) или формат не поддерживается.
    Текст исключения — для пользователя."""


def document_format(filename):
    """Расширение файла, если MINT его читает («docx», «pdf», «md», «txt»), иначе None."""
    ext = os.path.splitext(filename or "")[1].lower().lstrip(".")
    return ext if ext in SUPPORTED_FORMATS else None


def _docling_converter():
    """Один DocumentConverter на процесс: его создание дороже самого разбора .docx."""
    cache = _process_cache()
    conv = cache.get("docling")
    if conv is None:
        from docling.document_converter import DocumentConverter
        conv = cache["docling"] = DocumentConverter()
    return conv


def _docx_backend_convert(path):
    """.docx — бэкендом Word из Docling напрямую. Это тот же код, которым DocumentConverter разбирает .docx (простой
    конвейер без моделей: стили заголовков, списки, таблицы), но без импорта конвейера PDF с моделями — поэтому
    PyTorch и разбор PDF Docling'а не нужны. ImportError — в установленном Docling этого бэкенда нет."""
    from pathlib import Path

    from docling.backend.msword_backend import MsWordDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.document import InputDocument
    in_doc = InputDocument(path_or_stream=Path(path), format=InputFormat.DOCX, backend=MsWordDocumentBackend)
    backend = getattr(in_doc, "_backend", None)
    if backend is None:
        backend = MsWordDocumentBackend(in_doc=in_doc, path_or_stream=Path(path))
    if getattr(in_doc, "valid", True) is False or not backend.is_valid():
        raise DocumentUnreadable(tr("Docling не открыл файл как документ Word (.docx): файл повреждён или это другой "
                                    "формат с расширением .docx."))
    return backend.convert()


def docx_parser():
    """Как разбирать .docx: «backend» — бэкендом Word напрямую (по умолчанию), «converter» — через
    DocumentConverter (MINT_DOCX_PARSER=converter: для сравнения или если бэкенд в вашем Docling устроен иначе)."""
    return "converter" if os.environ.get("MINT_DOCX_PARSER", "").strip().lower() == "converter" else "backend"


def docling_convert(filename, data: bytes):
    """Конвертирует .docx Docling'ом. Импорт ленивый: без Docling работает всё, кроме загрузки .docx."""
    lock = _process_cache().setdefault("docling_lock", threading.Lock())
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, os.path.basename(filename) or "document.docx")
        with open(path, "wb") as f:
            f.write(data)
        with lock:   # разбор по очереди: конвертер общий для всех сеансов
            if docx_parser() == "backend":
                try:
                    return _docx_backend_convert(path)
                except ImportError as e:
                    if _process_cache().get("docx_backend_missing") is None:
                        _process_cache()["docx_backend_missing"] = True
                        logger.warning(f"Бэкенд Word из Docling недоступен ({e}) — .docx через DocumentConverter")
            return _docling_converter().convert(path).document


def compile_docx_to_markdown(filename, data: bytes):
    return clean_docling_markdown(docling_convert(filename, data).export_to_markdown())


def _label_of(item):
    lab = getattr(item, "label", "")
    lab = getattr(lab, "value", lab)
    return str(lab or "").lower()


def _item_page(item):
    prov = getattr(item, "prov", None)
    if not prov:
        return None
    first = prov[0] if isinstance(prov, (list, tuple)) else prov
    return getattr(first, "page_no", None) or None


def _table_to_markdown(table, document):
    for kwargs in ({"doc": document}, {}):
        try:
            md = table.export_to_markdown(**kwargs)
            if md and md.strip():
                return compact_markdown_tables(md.strip())
        except Exception:
            continue
    return ""


def _table_caption(table, document):
    try:
        return (table.caption_text(document) or "").strip()
    except Exception:
        return ""


_SKIP_LABELS = {"page_header", "page_footer", "picture", "chart"}

_HEADING_LABELS = {"section_header", "title"}


def collect_structure(document):
    """Документ Docling в порядке чтения: текстовые блоки с путём заголовков и таблицы.
    Возвращает (units, tables, pages_real); (None, None, False) — если структуру прочитать не удалось."""
    try:
        stack, units, tables, pages = [], [], [], set()
        for item, _level in document.iterate_items():
            label = _label_of(item)
            if label in _SKIP_LABELS:
                continue
            page = _item_page(item)
            if page:
                pages.add(page)

            if label == "table":
                md = _table_to_markdown(item, document)
                if md:
                    tables.append({
                        "md": md,
                        "path": heading_path_str(stack),
                        "caption": _table_caption(item, document),
                        "page": page,
                    })
                continue

            text = (getattr(item, "text", "") or "").strip()
            if len(text) < 2:
                continue
            if label in _HEADING_LABELS:
                try:
                    level = max(1, int(getattr(item, "level", 1) or 1))
                except Exception:
                    level = 1
                stack = [text] if label == "title" else stack[:level - 1] + [text]
                units.append({"text": text, "path": heading_path_str(stack), "page": page, "level": level})
            else:
                units.append({"text": text, "path": heading_path_str(stack), "page": page, "level": 0})

        if not units and not tables:
            return None, None, False
        return units, tables, len(pages) > 1
    except Exception as e:
        logger.warning(f"⚠️ Структура документа не прочитана ({str(e)[:120]}): плоский режим без заголовков.")
        return None, None, False


def collect_structure_flat(document):
    """Запасной режим (как в прежних версиях): весь текст подряд, без заголовков."""
    units, tables = [], []
    for el in list(getattr(document, "texts", []) or []):
        txt = (getattr(el, "text", "") or "").strip()
        if len(txt) >= 2:
            units.append({"text": txt, "path": "", "page": _item_page(el), "level": 0})
    for table in list(getattr(document, "tables", []) or []):
        md = _table_to_markdown(table, document)
        if md:
            tables.append({"md": md, "path": "", "caption": "", "page": _item_page(table)})
    return units, tables, False


# ---------------------------------------------------------------- .md и .txt

_ATX_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_SETEXT_RE = re.compile(r"^\s{0,3}(=+|-+)\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
_NUM_HEAD_RE = re.compile(r"^((?:\d{1,2}\.){0,4}\d{1,2})\.?\s+(\S.*)$")


def decode_text(data: bytes):
    """Текст файла: UTF-8 (с BOM и без), UTF-16 с BOM, иначе Windows-1251 (русские .txt из Windows)."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1251", errors="replace")


def _inline_md(text):
    """Markdown-разметка внутри строки → обычный текст: картинки — подпись, ссылки — текст (адрес), без * и `."""
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)[^)]*\)", r"\1 (\2)", text)
    text = re.sub(r"(\*\*|__|`)", "", text)
    return text.strip()


def _dehyphen(text):
    return re.sub(r"(\w)[-\u00ad] (?=[a-zа-яё])", r"\1", text)


def parse_markdown(text):
    """Markdown → (units, tables): заголовки # и подчёркнутые ===/---, абзацы, таблицы | … |."""
    units, tables, stack, para, table, fence = [], [], [], [], [], None

    def flush_para():
        if para:
            units.append({"text": _dehyphen(" ".join(para)), "path": heading_path_str(stack), "page": None, "level": 0})
            para.clear()

    def flush_table():
        if not table:
            return
        if len(table) >= 2 and _TABLE_SEP_RE.match(table[1]):
            tables.append({"md": "\n".join(table), "path": heading_path_str(stack), "caption": "", "page": None,
                           "after": len(units)})
        else:
            para.extend(_inline_md(t) for t in table)
            flush_para()
        table.clear()

    def heading(level, title):
        nonlocal stack
        flush_para()
        flush_table()
        stack = stack[:level - 1] + [title]
        units.append({"text": title, "path": heading_path_str(stack), "page": None, "level": level})

    for raw in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.rstrip()
        mark = line.strip()[:3]
        if fence is not None:                               # блок кода — как есть, одним абзацем
            if mark == fence:
                fence = None
                flush_para()
            elif line.strip():
                para.append(line.strip())
            continue
        if mark in ("```", "~~~"):
            flush_para()
            flush_table()
            fence = mark
            continue
        m = _ATX_RE.match(line)
        if m:
            heading(len(m.group(1)), _inline_md(m.group(2)))
            continue
        if _SETEXT_RE.match(line) and len(para) == 1 and not table:
            title = para.pop()
            heading(1 if line.strip().startswith("=") else 2, title)
            continue
        if line.strip().startswith("|"):
            flush_para()
            table.append(line.strip())
            continue
        flush_table()
        if not line.strip():
            flush_para()
        else:
            para.append(_inline_md(line))
    flush_para()
    flush_table()
    return units, tables


def _is_text_heading(line):
    """Строка .txt похожа на заголовок: короткая, без точки в конце; с нумерацией «2.1 …» или ЗАГЛАВНЫМИ."""
    if len(line) > 100 or line.endswith((".", ",", ";", ":", "!", "?")) or not re.search(r"[A-Za-zА-Яа-яЁё]{3}", line):
        return None
    m = _NUM_HEAD_RE.match(line)
    if m:
        return min(m.group(1).count(".") + 1, 6)
    letters = re.sub(r"[^A-Za-zА-Яа-яЁё]", "", line)
    if len(letters) >= 6 and letters.isupper() and len(line.split()) >= 2:
        return 1
    return None


def parse_plain_text(text):
    """Обычный текст → (units, tables): абзацы через пустую строку; заголовки — нумерованные и ЗАГЛАВНЫЕ строки."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    blocks = [b for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) == 1 and text.count("\n") > 20:          # без пустых строк: абзац — каждая строка
        blocks = [ln for ln in text.split("\n") if ln.strip()]
    units, stack = [], []
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        level = _is_text_heading(lines[0])
        if level and (len(lines) == 1 or len(lines[0]) < 0.8 * max(len(x) for x in lines[1:])):
            stack = stack[:level - 1] + [lines[0]]
            units.append({"text": lines[0], "path": heading_path_str(stack), "page": None, "level": level})
            lines = lines[1:]
        if lines:
            units.append({"text": _dehyphen(" ".join(lines)), "path": heading_path_str(stack), "page": None, "level": 0})
    return units, []


# ---------------------------------------------------------------- выбор разбора по формату

def _problem_message(info):
    if info.get("problem") == "scan":
        return tr("В PDF нет текстового слоя (скан или картинки): без распознавания текста MINT его не прочитает. "
                  "Нужен исходный документ (.docx) или PDF, сохранённый из Word.")
    return tr("Текст в PDF повреждён: шрифты сохранены без кодировки, вместо букв — другие знаки. Так бывает после "
              "«Печати в PDF». Сохраните документ из Word через «Сохранить как PDF» или загрузите .docx.")


def parse_document(filename, data: bytes):
    """Документ любого поддерживаемого формата → {units, tables, pages_real, structured, info}.
    info: format, structure (ключ STRUCTURE_LABELS), headings, tables; для PDF — pages, empty_pages.
    Нечитаемый документ или неизвестный формат — DocumentUnreadable с объяснением для пользователя."""
    fmt = document_format(filename)
    if fmt == "docx":
        document = docling_convert(filename, data)
        units, tables, pages_real = collect_structure(document)
        structured = units is not None
        if not structured:
            units, tables, pages_real = collect_structure_flat(document)
        n_head = sum(1 for u in units if u["level"])
        info = {"format": "docx", "structure": "styles" if n_head else "none", "headings": n_head,
                "tables": len(tables)}
        return {"units": units, "tables": tables, "pages_real": pages_real, "structured": structured, "info": info}
    if fmt == "pdf":
        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            raise DocumentUnreadable(tr("Для .pdf нужен пакет pdfplumber: pip install pdfplumber")) from None
        from .pdfparse import parse_pdf
        res = parse_pdf(data)
        if res["info"].get("problem"):
            raise DocumentUnreadable(_problem_message(res["info"]))
        return {**res, "structured": True}
    if fmt in ("md", "txt"):
        text = decode_text(data)
        units, tables = parse_markdown(text) if fmt == "md" else parse_plain_text(text)
        n_head = sum(1 for u in units if u["level"])
        info = {"format": fmt, "structure": ("markdown" if fmt == "md" else "numbering") if n_head else "none",
                "headings": n_head, "tables": len(tables)}
        return {"units": units, "tables": tables, "pages_real": False, "structured": True, "info": info}
    raise DocumentUnreadable(tr("Формат файла «{name}» не поддерживается: подходят .docx, .pdf, .md и .txt.",
                                name=os.path.basename(filename or "")))


def document_to_markdown(filename, data: bytes):
    """Документ → Markdown для аудита и контроля исправлений (заголовки — #, таблицы — | … |)."""
    if document_format(filename) == "docx":
        return compile_docx_to_markdown(filename, data)
    if document_format(filename) == "md":
        return decode_text(data).replace("\r\n", "\n").replace("\r", "\n")
    from .pdfparse import blocks_to_markdown
    res = parse_document(filename, data)
    return blocks_to_markdown(res["units"], res["tables"])


def structure_note(info):
    """Откуда взята структура документа — одной фразой для пользователя."""
    if not info:
        return ""
    note = tr("Структура: {how}.", how=tr(STRUCTURE_LABELS.get(info.get("structure"), STRUCTURE_LABELS["none"])))
    if info.get("empty_pages"):
        note += " " + tr("⚠️ Страниц без текста: {n} из {total} (картинки или сканы) — их содержимое в базу не "
                         "попало.", n=info["empty_pages"], total=info.get("pages", "?"))
    return note

"""Разбор PDF без моделей: текстовый слой (pdfplumber) и структура из того, что уже есть в самом файле.

Источники заголовков по убыванию надёжности:
  1. закладки PDF (outline) — их ставят Word («Сохранить как PDF» с закладками), LaTeX, Aspose;
  2. страница «Содержание» с отточиями («2.1 Область применения ....... 6») — документы, напечатанные в PDF;
  3. слайды (альбомные страницы): заголовок — самая крупная строка вверху страницы;
  4. размер шрифта и нумерация («2.1 …» жирным) — для буклетов и прочего.
Убираются: строки, повторяющиеся у краёв страниц (колонтитулы, номера страниц, штамп и поля ЕСКД), страницы
оглавления, рамка страницы. Таблицы с линиями — в Markdown. Картинки не читаются (как и в .docx).

Без текстового слоя (скан) и с испорченной кодировкой шрифтов («Ɋɢɫɭɧɨɤ» вместо «Рисунок») документ не
индексируется — честное сообщение вместо мусора в базе. Распознавание (OCR) не используется: это модель.
"""

import io
import logging
import re
import statistics
from collections import Counter

from .text import heading_path_str

logger = logging.getLogger("MINT")

NUM_RE = re.compile(r"^((?:\d{1,2}\.){0,4}\d{1,2})\.?\s+(\S.+)$")
TOC_RE = re.compile(r"(?:\.\s?){4,}\s*\d{1,4}\s*$|…{2,}\s*\d{1,4}\s*$")
TOC_LINE_MAX = 300           # длиннее — не строка оглавления (и разбор длинной строки шёл бы долго)
TOC_LINE_RE = re.compile(r"^(?P<title>.*?[A-Za-zА-Яа-яЁё].*?)\s*(?:(?:\.\s?){3,}|…+)\s*(?P<page>\d{1,4})\s*$")
BULLET_RE = re.compile(r"^\s*(?:[-–—•●▪■❑❖◦*·∙]|\d{1,2}[.)]|[а-яa-z][)])\s+")
BOLD_RE = re.compile(r"bold|black|heavy|semibold|demi|,b\b|-b\b|bd\b", re.I)
SPACED_RE = re.compile(r"^(?:\S ){3,}\S?$")
# Заглушки макета PowerPoint, которые остаются в PDF под настоящим заголовком слайда
PLACEHOLDER_RE = re.compile(r"^(?:Образец заголовка|Образец подзаголовка|Заголовок слайда|Click to edit Master title "
                            r"style|Click to add title)\s*", re.I)
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё]{3}")
# Признаки испорченной кодировки: глифы без Unicode («(cid:123)»), буквы из блоков, которых в русских и английских
# документах не бывает (IPA, Latin Extended-B — так выглядит кириллица со сдвинутыми кодами), частная область
_BAD_RE = re.compile(r"\(cid:\d+\)|[ƀ-ɏɐ-ʯ-�]")
_GOOD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]")
_CID_RE = re.compile(r"\(cid:\d+\)")

MIN_PAGE_CHARS = 30          # меньше — на странице нет текста (картинка или скан)


def _nkey(s):
    return re.sub(r"[^a-zа-я0-9]+", "", (s or "").lower().replace("ё", "е"))


def _zkey(s):
    return re.sub(r"\d+", "#", _nkey(s))


def _outline(pdf_bytes):
    """Закладки PDF: [{level, title, page (с 0)}]. pypdfium2 4.x и 5.x."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return []
    out = []
    try:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            for it in doc.get_toc():
                title = it.get_title() if hasattr(it, "get_title") else getattr(it, "title", "")
                if hasattr(it, "get_dest"):
                    dest = it.get_dest()
                    page = dest.get_index() if dest is not None else None
                else:
                    page = getattr(it, "page_index", None)
                title = re.sub(r"\s+", " ", title or "").strip()
                if title and page is not None and page >= 0:
                    out.append({"level": min(int(it.level) + 1, 6), "title": title, "page": int(page)})
        finally:
            doc.close()
    except Exception as e:
        logger.warning(f"Закладки PDF не прочитаны: {str(e)[:120]}")
        return []
    return out


def _page_lines(page):
    """Строки страницы в порядке текста в файле (наложенные надписи не перемешиваются): текст, координаты,
    размер шрифта, жирность. Повёрнутый текст отбрасывается."""
    p = page.filter(lambda o: o.get("object_type") != "char" or o.get("upright", True))
    out = []
    for ln in p.extract_text_lines(layout=False, strip=True, return_chars=True, x_tolerance=1.5,
                                   use_text_flow=True):
        chars = [c for c in ln["chars"] if c["text"].strip()]
        text = (ln["text"] or "").strip()
        if not chars or not text:
            continue
        if SPACED_RE.match(text):                     # «П о д п . и д а т а» — разрядка в штампе
            text = text.replace(" ", "")
        bold = sum(1 for c in chars if BOLD_RE.search(c.get("fontname", ""))) / len(chars)
        out.append({"text": text, "x0": ln["x0"], "x1": ln["x1"], "top": ln["top"], "bottom": ln["bottom"],
                    "size": statistics.median(round(c["size"], 1) for c in chars), "bold": bold > 0.6,
                    "nchars": len(chars)})
    return out


def _clean_rows(rows):
    rows = [[re.sub(r"\s+", " ", (c or "")).strip() for c in r] for r in rows or []]
    rows = [r for r in rows if any(r)]
    if not rows:
        return []
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    keep = [j for j in range(width) if any(r[j] for r in rows)]          # пустые колонки объединённых ячеек
    rows = [[r[j] for j in keep] for r in rows]
    j = 0
    while j < len(rows[0]) - 1:          # объединённая ячейка в шапке сдвигает колонки: соседние, которые нигде не
        if not any(r[j] and r[j + 1] for r in rows):           # заполнены одновременно, — одна колонка
            rows = [r[:j] + [r[j] or r[j + 1]] + r[j + 2:] for r in rows]
        else:
            j += 1
    return rows


def _table_md(rows):
    rows = _clean_rows(rows)
    if len(rows) < 2 or len(rows[0]) < 2:
        return ""
    md = ["| " + " | ".join(c.replace("|", "/") for c in rows[0]) + " |", "|" + "---|" * len(rows[0])]
    md += ["| " + " | ".join(c.replace("|", "/") for c in r) + " |" for r in rows[1:]]
    return "\n".join(md)


def _at_edge(ln, pg):
    """Строка у края страницы: колонтитул, номер страницы, поле со штампом."""
    return (ln["top"] < pg["h"] * 0.12 or ln["bottom"] > pg["h"] * 0.88
            or ln["x1"] < pg["w"] * 0.12 or ln["x0"] > pg["w"] * 0.88)


def _toc_entries(pages):
    """Страница оглавления («2.1 Область применения ....... 6») → [{level, title}] в порядке документа."""
    out = []
    for pg in pages:
        if not pg["toc"]:
            continue
        for ln in pg["lines"]:
            m = TOC_LINE_RE.match(ln["text"]) if len(ln["text"]) <= TOC_LINE_MAX else None   # строка оглавления короткая
            if not m:
                continue
            title = m.group("title").strip()
            num = NUM_RE.match(title)
            out.append({"level": min((num.group(1).count(".") + 1) if num else 1, 6), "title": title})
    return out


def text_quality(text):
    """Доля «испорченных» знаков среди букв и цифр: 0 — нормальный текст, больше 0.15 — кодировка испорчена."""
    bad = len(_BAD_RE.findall(text or ""))
    good = len(_GOOD_RE.findall(_CID_RE.sub(" ", text or "")))
    return bad / max(1, bad + good)


def parse_pdf(data: bytes):
    """PDF → {units, tables, pages_real, info}. units/tables — в формате parsing.collect_structure;
    у таблиц ещё after — после какого блока текста она стоит (для Markdown). info: structure (outline | toc |
    slides | font | none), pages, headings, tables, empty_pages и problem (scan | damaged) — документ не читается."""
    import pdfplumber

    outline = _outline(data)
    pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            w, h = float(page.width), float(page.height)
            lines = _page_lines(page)
            tables = []
            try:
                for t in page.find_tables():
                    x0, top, x1, bottom = t.bbox
                    if (x1 - x0) > 0.9 * w and (bottom - top) > 0.85 * h:
                        continue                          # рамка страницы (ЕСКД) или фон слайда, а не таблица
                    md = _table_md(t.extract())
                    if md:
                        tables.append({"bbox": t.bbox, "md": md, "key": _zkey(md)})
            except Exception as e:
                logger.warning(f"Таблицы на странице {page.page_number} не прочитаны: {str(e)[:120]}")
            n_chars = sum(ln["nchars"] for ln in lines)
            toc = bool(lines) and sum(1 for ln in lines if TOC_RE.search(ln["text"])) >= max(3, 0.3 * len(lines))
            pages.append({"w": w, "h": h, "lines": lines, "tables": tables, "chars": n_chars, "toc": toc})
            try:
                page.close()                              # не держать в памяти разобранные страницы
            except Exception:
                pass

    n = len(pages)
    empty = sum(1 for pg in pages if pg["chars"] < MIN_PAGE_CHARS)
    info = {"format": "pdf", "pages": n, "empty_pages": empty, "structure": "none", "headings": 0, "tables": 0,
            "problem": None}
    if not n or empty >= max(1, 0.5 * n):
        info["problem"] = "scan"
        return {"units": [], "tables": [], "pages_real": True, "info": info}
    sample = " ".join(ln["text"] for pg in pages for ln in pg["lines"])[:200000]
    info["bad_share"] = round(text_quality(sample), 3)
    if info["bad_share"] > 0.15:
        info["problem"] = "damaged"
        return {"units": [], "tables": [], "pages_real": True, "info": info}

    # повторяющиеся строки у краёв страниц и повторяющиеся таблицы (колонтитулы, штамп ЕСКД)
    edge_count, table_count = Counter(), Counter()
    for pg in pages:
        edge_count.update({_zkey(ln["text"]) for ln in pg["lines"] if _at_edge(ln, pg)})
        table_count.update({t["key"] for t in pg["tables"]})
    threshold = max(3, int(0.3 * n))
    repeated = {k for k, c in edge_count.items() if c >= threshold and k}
    repeated_tables = {k for k, c in table_count.items() if c >= threshold}

    sizes = Counter()
    for pg in pages:
        for ln in pg["lines"]:
            sizes[round(ln["size"] * 2) / 2] += ln["nchars"]
    body = sizes.most_common(1)[0][0] if sizes else 10.0

    if len(outline) < max(3, n // 15):        # 1–2 закладки на весь документ — не структура
        outline = []
    by_page = {}
    for e in outline:
        by_page.setdefault(e["page"], []).append(e)
    toc = [] if outline else _toc_entries(pages)
    slides = not outline and not toc and sum(1 for pg in pages if pg["w"] > pg["h"] * 1.2) > 0.8 * n
    info["structure"] = "outline" if outline else "toc" if toc else "slides" if slides else "font"

    def slide_title_line(pg):
        top = [ln for ln in pg["lines"] if ln["top"] < pg["h"] * 0.25 and _zkey(ln["text"]) not in repeated
               and WORD_RE.search(ln["text"])]
        return max(top, key=lambda ln: (ln["size"], -ln["top"])) if top else None

    slide_titles = [slide_title_line(pg) if slides else None for pg in pages]

    def clean_slide_title(text, page_no):
        text = PLACEHOLDER_RE.sub("", text).strip() or text      # скрытая заглушка макета перед заголовком
        m = re.search(r"\s(\d{1,3})$", text)                 # номер слайда в строке заголовка
        if m and int(m.group(1)) in (page_no, page_no - 1):
            text = text[:m.start()].strip()
        return text

    units, tables_out = [], []
    stack, para, para_page = [], [], None
    state = {"toc_i": 0, "last_head": None}

    def flush():
        nonlocal para
        if para:
            text = " ".join(para)
            # перенос по слогам: «сло- во» → «слово» (только перед строчной буквой)
            text = re.sub(r"(\w)[-­] (?=[a-zа-яё])", r"\1", text)
            units.append({"text": text, "path": heading_path_str(stack), "page": para_page, "level": 0})
            para = []

    def add_heading(level, text, page_no, ln=None):
        nonlocal stack
        flush()
        lh = state["last_head"]
        if (ln is not None and lh is not None and units and units[-1]["level"] == level
                and units[-1]["page"] == page_no and abs(ln["size"] - lh["size"]) < 0.6
                and 0 <= ln["top"] - lh["bottom"] < 0.8 * (lh["bottom"] - lh["top"])):
            units[-1]["text"] += " " + text               # заголовок в две строки
            stack[-1] = units[-1]["text"]
            units[-1]["path"] = heading_path_str(stack)
            state["last_head"] = ln
            return
        state["last_head"] = ln
        stack = stack[:level - 1] + [text]
        units.append({"text": text, "path": heading_path_str(stack), "page": page_no, "level": level})

    for pi, pg in enumerate(pages):
        if pg["toc"]:
            continue                                      # страница оглавления — не текст документа
        lines = pg["lines"]
        page_tables = pg["tables"]

        def in_table(ln):
            cx, cy = (ln["x0"] + ln["x1"]) / 2, (ln["top"] + ln["bottom"]) / 2
            return any(t["bbox"][0] - 2 <= cx <= t["bbox"][2] + 2 and t["bbox"][1] - 2 <= cy <= t["bbox"][3] + 2
                       for t in page_tables)

        pending = list(by_page.get(pi, []))
        slide_title = slide_titles[pi]
        prev, skip = None, 0
        for li, ln in enumerate(lines):
            if skip:
                skip -= 1
                continue
            text = ln["text"]
            if _at_edge(ln, pg) and (_zkey(text) in repeated or not WORD_RE.search(text)):
                continue
            if in_table(ln) or re.fullmatch(r"[\d\s\-–—/.]+", text):
                continue
            k1 = _nkey(text)
            nxt = _nkey(lines[li + 1]["text"]) if li + 1 < len(lines) else ""
            if pending:                                   # заголовок из закладок (бывает в две строки)
                hit = None
                for e in pending:
                    ek = _nkey(e["title"])
                    if not ek:
                        continue
                    if (k1.startswith(ek[:30]) or (ek.startswith(k1[:30]) and len(k1) >= 6)) and len(k1) <= len(ek) + 12:
                        hit, two = e, len(k1) < len(ek) and (k1 + nxt).startswith(ek[:40]) and len(ek) - len(k1) > 2
                        break
                if hit:
                    pending.remove(hit)
                    skip = 1 if two else 0
                    add_heading(hit["level"], hit["title"], pi + 1)
                    prev = None
                    continue
            if toc and state["toc_i"] < len(toc):          # заголовок из страницы оглавления
                matched, two = None, False
                for j in range(state["toc_i"], min(state["toc_i"] + 3, len(toc))):   # допускаем пропуск 1–2 пунктов
                    ek = _nkey(toc[j]["title"])
                    if len(k1) < 4 or not ek:
                        continue
                    if k1 == ek or (k1.startswith(ek) and len(k1) <= len(ek) + 3) or (ek.startswith(k1) and len(k1) >= 0.6 * len(ek)):
                        matched = j
                        break
                    if len(k1) < len(ek) and (k1 + nxt).startswith(ek):
                        matched, two = j, True
                        break
                if matched is not None:
                    state["toc_i"] = matched + 1
                    skip = 1 if two else 0
                    add_heading(toc[matched]["level"], toc[matched]["title"], pi + 1)
                    prev = None
                    continue
            if slides:
                if ln is slide_title:
                    add_heading(1, clean_slide_title(text, pi + 1), pi + 1)
                    prev = None
                    continue
            elif not outline and not toc:                 # размер шрифта и нумерация
                m = NUM_RE.match(text)
                short = (len(text) <= 100 and not text.endswith((".", ";", ",", ":")) and WORD_RE.search(text)
                         and not BULLET_RE.match(text))
                if short and (ln["size"] >= body + 2.0 or (ln["bold"] and m)):
                    level = (m.group(1).count(".") + 1) if m else (1 if ln["size"] >= body + 4 else 2)
                    add_heading(min(level, 6), text, pi + 1, ln)
                    prev = None
                    continue
            new_para = (prev is None or ln["top"] - prev["bottom"] > max(4.0, 0.7 * (prev["bottom"] - prev["top"]))
                        or BULLET_RE.match(text))
            if new_para:
                flush()
                para_page = pi + 1
            para.append(text)
            prev = ln
        flush()
        for t in page_tables:
            if t["key"] in repeated_tables:
                continue
            tables_out.append({"md": t["md"], "path": heading_path_str(stack), "caption": "", "page": pi + 1,
                               "after": len(units)})

    info["headings"] = sum(1 for u in units if u["level"])
    info["tables"] = len(tables_out)
    if info["structure"] == "font" and not info["headings"]:
        info["structure"] = "none"
    return {"units": units, "tables": tables_out, "pages_real": True, "info": info}


def blocks_to_markdown(units, tables):
    """Текст и таблицы одним Markdown в порядке документа (для аудита и контроля исправлений)."""
    out, ti = [], 0
    tables = sorted(tables, key=lambda t: t.get("after", 10 ** 9))
    for i, u in enumerate(units):
        while ti < len(tables) and tables[ti].get("after", 10 ** 9) <= i:
            out.append(tables[ti]["md"])
            ti += 1
        out.append(("#" * u["level"] + " " + u["text"]) if u["level"] else u["text"])
    out += [t["md"] for t in tables[ti:]]
    return "\n\n".join(out)

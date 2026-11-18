"""Fill a copy of a Word template from selected originals in the knowledge base."""
import contextvars
import io
import json
import re
import time
from functools import wraps
from copy import deepcopy
from dataclasses import dataclass

from .i18n import tr
from .draft_checkpoint import DraftExtractCheckpoint
from .evidence import quoted, verify_comparison
from .kb import source_path
from .parsing import document_to_markdown
from .prompts import render
from .search import search_parent_child
from .services import TRUNCATED_MARKERS, ask_llm

MAX_CHARS = 4000
ROW_LIMIT = 20
SECTION_PLAN_LIMIT = 24000
_DRAFT_METRICS = contextvars.ContextVar('mint_draft_metrics', default=None)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_EXAMPLE = re.compile(r"^\s*(?:пример|example|sample)\s*[:：]", re.I)
_PROTECTED = (".//w:fldChar | .//w:instrText | .//w:fldSimple | .//w:drawing | .//w:pict | .//w:object | "
              ".//w:sdt | .//w:ins | .//w:del | "
              ".//w:hyperlink | .//w:commentRangeStart | .//w:commentRangeEnd | .//w:commentReference")
_SIMPLE_P = {"pPr", "r", "proofErr", "bookmarkStart", "bookmarkEnd"}
_SIMPLE_RUN = {"rPr", "t", "lastRenderedPageBreak"}


class DraftError(ValueError):
    pass


def _normalized(text):
    return " ".join(text.split())


def _json(cfg, stage, payload):
    system = render("draft_system") + "\n" + render("draft_" + stage)
    content = json.dumps(payload, ensure_ascii=False)
    for _ in range(2):
        t0 = time.perf_counter()
        try:
            raw = ask_llm(system, content, cfg, temperature=0, max_tokens=min(3800, max(1500, cfg.max_tokens)))
        finally:
            metrics = _DRAFT_METRICS.get()
            if metrics is not None:
                item = metrics["stages"].setdefault(stage, {"llm_calls": 0, "llm_seconds": 0.0})
                item["llm_calls"] += 1
                item["llm_seconds"] = round(item["llm_seconds"] + time.perf_counter() - t0, 3)
        if raw.startswith("❌"):
            break
        if any(marker in raw for marker in TRUNCATED_MARKERS):
            continue
        try:
            data = json.loads(re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", raw.strip(), flags=re.I))
            if isinstance(data, dict):
                return data
        except (ValueError, TypeError):
            pass
    raise DraftError(tr("Не удалось получить полный ответ модели для этапа «{stage}».", stage=stage))



def _measure_draft(fn):
    """Collect per-stage LLM cost without logging text or affecting other sessions."""
    @wraps(fn)
    def measured(*args, **kwargs):
        metrics = {"stages": {}, "total_seconds": 0.0}
        token = _DRAFT_METRICS.set(metrics)
        started = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
            result["metrics"] = metrics
            return result
        finally:
            metrics["total_seconds"] = round(time.perf_counter() - started, 3)
            _DRAFT_METRICS.reset(token)
    return measured


def _records(data, key):
    rows = data.get(key)
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise DraftError(tr("Модель вернула неполный или неверный список."))
    return rows


def _text(row, key):
    value = row.get(key)
    return value.strip() if isinstance(value, str) else ""


def _batches(items, key, size=MAX_CHARS):
    batch, count = [], 0
    for item in items:
        length = len(key(item)) + 80
        if batch and count + length > size:
            yield batch
            batch, count = [], 0
        batch.append(item)
        count += length
    if batch:
        yield batch


def _source_chunks(markdown):
    section = ""
    lines = []
    for line in markdown.splitlines():
        if re.match(r"^#{1,6}\s", line):
            if lines:
                yield from _split_section(section, lines)
            section, lines = line.lstrip("# ").strip(), []
        else:
            lines.append(line)
    if lines:
        yield from _split_section(section, lines)


def _split_section(section, lines):
    for batch in _batches(lines, str):
        text = "\n".join(batch).strip()
        while len(text) > MAX_CHARS:
            cut = text.rfind(" ", MAX_CHARS // 2, MAX_CHARS)
            if cut < 0:
                cut = MAX_CHARS
            yield section, text[:cut]
            text = text[max(0, cut - 300):]
        if text:
            yield section, text


def _requirements(cfg, documents, issues, emit, *, reset_cache=False):
    """Extract verified requirements with durable per-fragment checkpoints."""
    requirements, seen, chunks, reused = {}, set(), 0, 0
    total = sum(1 for _, markdown in documents for _ in _source_chunks(markdown))
    emit("extract_total", total)
    for name, markdown in documents:
        checkpoint = DraftExtractCheckpoint(cfg, name, markdown)
        if reset_cache:
            checkpoint.clear()
        for local_index, (section, text) in enumerate(_source_chunks(markdown), 1):
            chunks += 1
            emit("extract", chunks)
            quotes = checkpoint.load(local_index, section, text)
            if quotes is None:
                try:
                    rows = _records(_json(cfg, "extract", {"source": name, "section": section, "text": text}),
                                    "requirements")
                except DraftError:
                    issues.append(tr("Не удалось разобрать фрагмент основания: {source} › {section}.",
                                     source=name, section=section or str(chunks)))
                    emit("extract_done", chunks)
                    continue
                quotes = []
                valid = True
                for row in rows:
                    quote = _text(row, "quote")
                    if not quote or _normalized(quote) not in _normalized(text):
                        issues.append(tr("В основании «{source}» не найдена цитата, указанная моделью.",
                                         source=name))
                        valid = False
                        continue
                    quotes.append(quote)
                # A partially invalid response is NOT checkpointed: retry it next run.
                if valid:
                    checkpoint.save(local_index, section, text, quotes)
            else:
                reused += 1
                emit("extract_cached", reused)
            for quote in quotes:
                key = (name, section, _normalized(quote))
                if key not in seen:
                    seen.add(key)
                    rid = f"R{len(requirements) + 1}"
                    requirements[rid] = {"id": rid, "source": name, "section": section, "quote": quote}
            emit("extract_done", chunks)
    return requirements, chunks


def _bookmarks(element):
    return element.xpath(".//w:bookmarkStart | .//w:bookmarkEnd")


def _simple(paragraph):
    return (not paragraph._p.xpath(_PROTECTED) and
            all(node.tag.split("}")[-1] in _SIMPLE_P for node in paragraph._p) and
            all(node.tag.split("}")[-1] in _SIMPLE_RUN for run in paragraph.runs for node in run._r))


def _heading(paragraph):
    style = paragraph.style.name.lower() if paragraph.style else ""
    return (style.startswith(("heading ", "заголовок ")) or
            bool(paragraph._p.xpath("./w:pPr/w:outlineLvl")))


@dataclass
class Slot:
    paragraph: object
    text: str
    section: str
    table: str = ""
    column: str = ""
    writable: bool = False
    following: tuple = ()

    def describe(self, key):
        return {"id": key, "section": self.section, "table": self.table, "column": self.column,
                "text": self.text, "writable": self.writable,
                "colors": sorted({str(r.font.color.rgb) for r in self.paragraph.runs if r.text.strip()})}


def _layout(doc):
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    slots, tables, examples = {}, {}, {}
    section, example_color, example = "", set(), False
    for idx, element in enumerate(doc.element.body):
        tag = element.tag.split("}")[-1]
        if tag == "p":
            p = Paragraph(element, doc)
            if _heading(p):
                section, example = p.text, False
                continue
            colored = {str(r.font.color.rgb) for r in p.runs if r.text.strip()}
            if _EXAMPLE.search(p.text):
                example = True
                example_color = colored - {"None", "000000"}
            if not p.text.strip():
                continue
            # Color is a hint scoped to an explicit example, never a global classification rule.
            if example and (_EXAMPLE.search(p.text) or (colored and colored <= example_color)):
                key = f"P{idx}"
                if _simple(p) and not _bookmarks(p._p):
                    examples[key] = p._p
                continue
            example = False
            if not p._p.xpath(_PROTECTED) and not (p.style and p.style.name.lower().startswith("toc")):
                slots[f"P{idx}"] = Slot(p, p.text, section, writable=_simple(p))
        elif tag == "tbl":
            table = Table(element, doc)
            if example:
                example = False
                if not element.xpath(_PROTECTED) and not _bookmarks(element) and not element.xpath(".//w:sectPr"):
                    examples[f"T{idx}"] = element
                continue
            if not table.rows:
                continue
            headings = [c.text for c in table.rows[0].cells]
            key = f"T{idx}"
            simple_rows = True
            for r, row in enumerate(table.rows):
                for c, cell in enumerate(row.cells):
                    for n, p in enumerate(cell.paragraphs):
                        if r > 0 or p.text:
                            merged = bool(cell._tc.xpath("./w:tcPr/w:gridSpan | ./w:tcPr/w:vMerge"))
                            slots[f"{key}.{r}.{c}.{n}"] = Slot(
                                p, p.text, section, key, headings[c] if c < len(headings) else "",
                                r > 0 and not merged and _simple(p))
                simple_rows &= (len(row.cells) == len(headings) and not row._tr.xpath(
                    ".//w:gridSpan | .//w:vMerge | .//w:tbl | .//w:bookmarkStart | .//w:bookmarkEnd | " + _PROTECTED))
            # A blank or instructional last row can supply formatting for additional rows.
            if simple_rows and len(table.rows) >= 2 and all(headings) and all(
                    len(c.paragraphs) == 1 and _simple(c.paragraphs[0]) for c in table.rows[-1].cells):
                tables[key] = table
    _join_instruction_blocks(slots)
    return slots, tables, examples


def _join_instruction_blocks(slots):
    """A bracketed instruction may span adjacent paragraphs in the template."""
    for key in list(slots):
        if key not in slots:
            continue
        first = slots[key]
        if first.table or not first.writable or not first.text.lstrip().startswith("[") or "]" in first.text:
            continue
        following = []
        element = first.paragraph._p.getnext()
        number = int(key[1:])
        for i in range(1, 8):
            member = f"P{number + i}"
            other = slots.get(member)
            if (other is None or other.section != first.section or not other.writable or
                    other.paragraph._p is not element or "[" in other.text):
                break
            following.append((member, other))
            if "]" in other.text:
                if other.text.rstrip().endswith("]"):
                    first.text = "\n".join([first.text] + [x.text for _, x in following])
                    first.following = tuple(x.paragraph for _, x in following)
                    for member, _ in following:
                        del slots[member]
                break
            element = element.getnext()


def _write_run(run, text):
    breaks = [deepcopy(x) for x in run._r.xpath("./w:lastRenderedPageBreak")]
    run.text = text
    for element in reversed(breaks):
        run._r.insert(1 if run._r.rPr is not None else 0, element)


def _replace(paragraph, start, end, text):
    """Edit text runs without rebuilding the paragraph or changing neighboring formatting."""
    pos = 0
    for run in paragraph.runs:
        old = run.text
        stop = pos + len(old)
        if start == end and pos <= start <= stop:
            _write_run(run, old[:start - pos] + text + old[start - pos:])
            return
        if start < stop and end > pos:
            prefix = old[:max(0, start - pos)]
            suffix = old[max(0, end - pos):]
            _write_run(run, prefix + (text if pos <= start < stop else "") + suffix)
        pos = stop
    if start == end:
        paragraph.add_run(text)


def _note(doc, paragraph, title, detail="", conflict=False):
    """Review notes must never alter visible Word text, especially narrow cells."""
    if not hasattr(doc, "add_comment"):
        return
    run = next((r for r in paragraph.runs if r.text.strip()), None)
    if run is None:
        run = paragraph.add_run("")  # zero-width anchor; no labels inside the document
    doc.add_comment(run, text=title + (": " + detail if detail else ""), author="MINT", initials="MINT")


def _safe_target(slot, target):
    if not slot.writable:
        return False
    if not slot.text.strip():
        return not target
    # Protect surrounding prose, cross-references and numbered headings.
    body = target.strip()
    if slot.following and target != slot.text.strip():
        return False
    return bool(body and slot.text.count(target) == 1 and (
        re.match(r"^\[\s*(?:указ\w*|укаж\w*|встав\w*|заполн\w*|опис\w*|прив\w*|перечисл\w*|"
                 r"enter|insert|fill|specify|describe|add|list)\b", body, re.I) and body.endswith("]") or
        re.match(r"^(?:укаж(?:ите|и|ать)|указыва\w+|заполн\w+|встав\w+|опиш\w+|"
                 r"уточн\w+|enter|insert|fill|specify|describe)\b", body, re.I) or
        re.fullmatch(r"[_…⋯.]{2,}", body)))


def _refs(row, requirements):
    ids = row.get("refs")
    if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or x not in requirements for x in ids):
        return []
    return list(dict.fromkeys(ids))



def covered_refs(text, refs, coverage):
    """Source IDs with a contiguous, locatable quotation of their real draft text.

    This proves the referenced content EXISTS in the output. It does not prove
    that the output semantically satisfies the whole source requirement.
    Missing/invalid mappings are review candidates, not confirmed omissions.
    """
    if not isinstance(coverage, dict):
        return set()
    return {rid for rid in refs if isinstance(coverage.get(rid), str) and quoted(coverage[rid], text)}


def _numbers_supported(text, refs, requirements):
    numbers = lambda value: {n.replace(",", ".") for n in _NUMBER.findall(value)}
    found = set().union(*(numbers(requirements[k]["quote"]) for k in refs))
    return numbers(text) <= found


def _format_ref(req):
    return f'{req["source"]} › {req["section"] or "—"}: «{req["quote"]}»'


def _find_fields(cfg, slots, issues, emit):
    fields, fixed = {}, {}
    for i, batch in enumerate(_batches(list(slots.items()), lambda item: item[1].text), 1):
        emit("layout", i)
        try:
            analysis = _json(cfg, "layout", {"blocks": [s.describe(k) for k, s in batch]})
            rows = _records(analysis, "fields")
        except DraftError:
            issues.append(tr("Не удалось разобрать часть шаблона: блок {n}.", n=i))
            continue
        allowed = dict(batch)
        occupied = {}
        for row in rows:
            key, target, purpose = (_text(row, k) for k in ("id", "target", "purpose"))
            slot = allowed.get(key)
            if slot is None or not purpose:
                continue
            safe = _safe_target(slot, target)
            start = slot.text.find(target) if target else 0
            end = start + len(target)
            ranges = occupied.setdefault(key, [])
            if any(start < b and end > a or (start, end) == (a, b) for a, b in ranges):
                continue
            ranges.append((start, end))
            fields[f"F{len(fields) + 1}"] = (key, start, end, purpose, safe)
        fixed_ids = analysis.get("fixed", [])
        if isinstance(fixed_ids, list):
            for key in fixed_ids:
                if isinstance(key, str) and key in allowed and key not in occupied and allowed[key].writable:
                    fixed[key] = allowed[key]
    return fields, fixed


def _candidates(purpose, requirements, size=MAX_CHARS * 2):
    """Lexical ranking over selected source excerpts; maintain source diversity."""
    from .bm25 import LightweightBM25

    rows = list(requirements.values())
    if sum(len(r["quote"]) + 95 for r in rows) <= size:
        return rows
    index = LightweightBM25([r["section"] + " " + r["quote"] for r in rows])
    scores = index.get_scores(purpose)
    ordered = sorted(zip(scores, rows), key=lambda x: -x[0])
    first, rest, sources = [], [], set()
    for score, row in ordered:
        if score > 0 and row["source"] not in sources:
            first.append(row)
            sources.add(row["source"])
        else:
            rest.append(row)
    selected, used = [], 0
    for row in first + rest:
        cost = len(row["quote"]) + 95
        if used + cost <= size:
            selected.append(row)
            used += cost
    return selected


def _candidate_budget(cfg):
    """Reserve response capacity for the model; do not assume unlimited context."""
    limit = int(getattr(cfg, "llm_context_tokens", 0) or 0)
    if limit <= 0:
        return MAX_CHARS * 2  # unknown context window: preserve conservative default
    output = min(3800, max(1500, int(cfg.max_tokens)))
    ratio = float(getattr(cfg, "chars_per_token", 0) or 2.5)
    # JSON wrapper, system prompt and safety margin also occupy the context.
    return min(SECTION_PLAN_LIMIT, max(1500, int(max(600, limit - output - 1100) * ratio)))


def _section_plan(cfg, fields, slots, requirements):
    """Plan source coverage for each template section BEFORE filling any field.

    A section-wide candidate pool complements field-specific retrieval, preventing
    generic placeholders from discarding requirements mentioned in the heading.
    Only verified quotations from selected documents may appear in this plan.
    """
    by_section = {}
    for field_id, (key, _start, _end, purpose, _safe) in fields.items():
        slot = slots[key]
        by_section.setdefault(slot.section, []).append((field_id, purpose, slot.column))
    budget = _candidate_budget(cfg)
    field_candidates, summary = {}, {}
    for section, entries in by_section.items():
        section_query = " ".join([section] + [purpose + " " + column for _, purpose, column in entries])
        group = _candidates(section_query, requirements, size=budget)
        selected_ids = set()
        for field_id, purpose, column in entries:
            query = " ".join([section, purpose, column])
            # Field-specific terms win, but the section context is not lost.
            focused = _candidates(query, requirements, size=max(1500, budget // 2))
            items, consumed, seen = [], 0, set()
            for row in focused + group:
                cost = len(row["quote"]) + 95
                if row["id"] in seen or consumed + cost > budget:
                    continue
                items.append(row)
                seen.add(row["id"])
                consumed += cost
            field_candidates[field_id] = items
            selected_ids.update(seen)
        summary[section or "—"] = {"fields": len(entries),
                                   "selected_ids": sorted(selected_ids, key=lambda k: int(k[1:])),
                                   "total_requirements": len(requirements)}
    return field_candidates, summary


def unresolved_candidates(section_plan, used):
    """Review candidates, NOT verified omissions. Shared by drafting and evaluation."""
    return {section: [rid for rid in plan["selected_ids"] if rid not in used]
            for section, plan in section_plan.items()}


def _wiki(cfg, query, glossary, sources):
    items, _ = search_parent_child(query[:cfg.max_query_chars], cfg, k_neighbors=5, return_items=True,
                                   glossary=glossary, exclude_sources=sources)
    if not isinstance(items, list):
        return {}
    return {f"N{i}": {"id": f"N{i}", "source": x["source"], "section": x["path"], "quote": x["block"]}
            for i, x in enumerate(items, 1)}


def _verify(cfg, text, refs, requirements, glossary, issues, sources):
    """Separate basis support from wiki comparison; verify evidence with shared rules."""
    try:
        norms = _wiki(cfg, text, glossary, sources)
    except Exception:
        issues.append(tr("Поиск норм в вики завершился ошибкой."))
        norms = {}
    try:
        row = _json(cfg, "check", {"claims": text, "evidence": [requirements[r] for r in refs],
                                  "norms": list(norms.values())})
    except DraftError:
        return "manual", tr("Модель не завершила проверку по основаниям.")
    # Basis support is independent of the presence or relevance of KB documents.
    if refs and row.get("supported") is not True:
        return "manual", _text(row, "support_reason") or tr("Формулировка требует сверки с основаниями.")
    ref = _text(row, "ref")
    norm = norms.get(ref)
    if not norm:
        return "unchecked", ""
    proof = verify_comparison(
        text, norm["quote"],
        {"status": _text(row, "status"), "ref": ref, "claim_quote": _text(row, "claim_quote"),
         "norm_quote": _text(row, "quote"), "applicability": _text(row, "applicability"),
         "applicability_reason": _text(row, "applicability_reason"),
         "scope_quote": _text(row, "scope_quote"), "reason": _text(row, "reason"),
         "source": norm["source"]})
    status = proof["status"]
    if status == "unchecked":
        return status, ""
    detail = (proof["reason"] + "\n" if proof["reason"] else "")
    detail += _format_ref({**norm, "quote": proof["norm_quote"]})
    return status, detail


def _number_column(header):
    return _normalized(header).lower().rstrip(".") in {"№", "№ п/п", "#", "no", "nº"}


def _row_plans(cfg, tables, requirements, issues, emit):
    plans = {}
    for i, (key, table) in enumerate(tables.items(), 1):
        headers = [c.text for c in table.rows[0].cells]
        sample = table.rows[-1]
        if any(not _safe_target(Slot(c.paragraphs[0], c.text, "", writable=True), c.text.strip())
               for c in sample.cells):
            continue
        emit("table", i)
        nearby = table._tbl.getprevious()
        caption = " ".join(nearby.xpath(".//w:t/text()")) if nearby is not None else ""
        candidates = _candidates(caption + " " + " ".join(headers), requirements)
        allowed = {r["id"]: r for r in candidates}
        try:
            rows = _records(_json(cfg, "rows", {"caption": caption, "columns": headers,
                                                "sample": [c.text for c in sample.cells],
                                                "requirements": candidates}), "rows")
        except DraftError:
            issues.append(tr("Не удалось подготовить строки таблицы: {table}.", table=key))
            continue
        valid = []
        for row in rows[:ROW_LIMIT]:
            cells = row.get("cells")
            refs = _refs(row, allowed)
            if (isinstance(cells, list) and len(cells) == len(headers) and
                    all(isinstance(x, str) for x in cells) and refs):
                values = ["" if _number_column(h) else x.strip() for h, x in zip(headers, cells)]
                if any(values) and _numbers_supported(" ".join(values), refs, allowed):
                    coverage = covered_refs(" | ".join(values), refs, row.get("coverage"))
                    if not any(values == other for other, _, _ in valid):
                        valid.append((values, refs, coverage))
                    continue
            issues.append(tr("Одна из предложенных строк таблицы «{table}» требует проверки.", table=key))
        if len(rows) > ROW_LIMIT:
            issues.append(tr("Часть предложенных строк таблицы «{table}» требует ручной вставки.", table=key))
        if valid:
            plans[key] = valid
    return plans


def _mark_wiki(doc, paragraph, status, detail):
    if status == "conflict":
        _note(doc, paragraph, tr("Противоречие с вики"), detail, conflict=True)
    elif status == "uncertain":
        _note(doc, paragraph, tr("Проверить применимость нормы"), detail)
    elif status == "unchecked":
        _note(doc, paragraph, tr("Проверка по вики не завершена"))


@_measure_draft
def create_draft(template, cfg, sources, glossary=None, progress=None, *, example=False, reset_extract_cache=False):
    """Return a new DOCX plus field/requirement coverage. Never alter the input files."""
    from docx import Document
    from docx.table import _Row

    emit = progress or (lambda *_: None)
    from docx.opc.exceptions import OpcError
    from zipfile import BadZipFile

    try:
        doc = Document(io.BytesIO(template))
    except (OpcError, BadZipFile, ValueError, KeyError) as exc:
        raise DraftError(tr("Не удалось прочитать файл DOCX.")) from exc
    issues, results, used = [], [], set()
    documents = []
    for name in dict.fromkeys(sources):
        try:
            path = source_path(cfg, name)
            markdown = document_to_markdown(name, path.read_bytes())
            if not markdown.strip():
                raise ValueError("empty source")
        except Exception:
            issues.append(tr("Не удалось прочитать оригинал основания: {source}.", source=name))
            continue
        documents.append((name, markdown))
    if not documents:
        raise DraftError(tr("Нет доступных оригиналов выбранных оснований."))
    if example:
        doc, slots, fields, tables = _from_example(doc, issues)
        examples, fixed = {}, {}
    else:
        slots, tables, examples = _layout(doc)
        fields, fixed = _find_fields(cfg, slots, issues, emit)
    requirements, chunks = _requirements(cfg, documents, issues, emit, reset_cache=reset_extract_cache)
    plans = _row_plans(cfg, tables, requirements, issues, emit) if requirements else {}
    candidates_by_field, section_plan = _section_plan(cfg, fields, slots, requirements)
    edits = []
    for i, (field, (key, start, end, purpose, safe)) in enumerate(fields.items(), 1):
        slot = slots[key]
        if slot.table in plans and slot.paragraph._p.getparent().getparent() is tables[slot.table].rows[-1]._tr:
            continue
        emit("fill", i)
        candidates = candidates_by_field.get(field, [])
        allowed = {r["id"]: r for r in candidates}
        try:
            row = _json(cfg, "fill", {"field": purpose, "section": slot.section, "column": slot.column,
                                      "requirements": candidates}) if candidates else {}
        except DraftError:
            row = {}
            issues.append(tr("Не удалось завершить заполнение поля: {field}.", field=purpose))
        refs, content = _refs(row, allowed), _text(row, "text")
        grounded = covered_refs(content, refs, row.get("coverage"))
        decision = _text(row, "status")
        status, detail = "missing", _text(row, "reason") or purpose
        if decision == "conflict" and len({requirements[r]["source"] for r in refs}) > 1:
            status = "basis_conflict"
            detail += "\n" + "\n".join(_format_ref(requirements[r]) for r in refs)
        elif decision == "filled" and refs and content and _numbers_supported(content, refs, requirements):
            if safe:
                status, detail = _verify(cfg, content, refs, requirements, glossary, issues, sources)
                if status != "manual":
                    used.update(grounded)
            else:
                status = "manual"
        edits.append((key, start, end, purpose, status, content, detail, refs, grounded, safe))

    # Apply from right to left so offsets stay tied to the original template.
    for key, start, end, purpose, status, content, detail, refs, grounded, safe in sorted(
            edits, key=lambda x: (x[0], -x[1])):
        slot = slots[key]
        p = slot.paragraph
        if slot.following and safe and status in {"checked", "conflict", "uncertain", "unchecked"}:
            end = len(p.text)
            for other in slot.following:
                _replace(other, 0, len(other.text), "")
        if status in {"checked", "conflict", "uncertain", "unchecked"}:
            _replace(p, start, end, content)
            _mark_wiki(doc, p, status, detail)
        elif status == "basis_conflict":
            if safe:
                _replace(p, start, end, "")
            _note(doc, p, tr("Противоречие в основаниях"), detail, conflict=True)
        elif status == "missing":
            # Keep the original instruction: deleting it would erase what the editor must supply.
            _note(doc, p, tr("Требуется уточнение"), detail)
        elif status == "manual":
            _note(doc, p, tr("Требуется ручная вставка"), detail or purpose)
        results.append({"field": purpose, "status": status, "text": content, "detail": detail, "refs": refs,
                        "unconfirmed_coverage": sorted(set(refs) - grounded) if status in
                        {"checked", "conflict", "uncertain", "unchecked"} else []})

    for key, rows in plans.items():
        table = tables[key]
        prototype = table.rows[-1]
        headers = [c.text for c in table.rows[0].cells]
        content_columns = [i for i, h in enumerate(headers) if not _number_column(h)]
        pristine = deepcopy(prototype._tr)
        written = 0
        for values, refs, grounded in rows:
            content = " | ".join(values)
            status, detail = _verify(cfg, content, refs, requirements, glossary, issues, sources)
            results.append({"field": key, "status": status, "text": content, "detail": detail, "refs": refs,
                            "unconfirmed_coverage": sorted(set(refs) - grounded) if status != "manual" else []})
            if status == "manual":
                continue
            if written:
                xml = deepcopy(pristine)
                table._tbl.append(xml)
                target = _Row(xml, table)
            else:
                target = prototype
            written += 1
            for i, (cell, value) in enumerate(zip(target.cells, values)):
                p = cell.paragraphs[0]
                _replace(p, 0, len(p.text), str(written) if i not in content_columns else value)
                if i in content_columns and not value:
                    _note(doc, p, tr("Уточнить"), headers[i])
            anchor = max((target.cells[i] for i in content_columns if values[i]), key=lambda c: c.width or 0)
            _mark_wiki(doc, anchor.paragraphs[0], status, detail)
            used.update(grounded)
        if not written:
            anchor = max((prototype.cells[i] for i in content_columns), key=lambda c: c.width or 0)
            _note(doc, anchor.paragraphs[0], tr("Требуется ручная вставка"))

    for i, slot in enumerate(fixed.values(), 1):
        emit("fixed", i)
        status, detail = _verify(cfg, slot.text, [], requirements, glossary, issues, sources)
        if status in {"conflict", "uncertain"}:
            _mark_wiki(doc, slot.paragraph, status, detail)
            results.append({"field": slot.section, "status": status, "text": slot.text,
                            "detail": detail, "refs": []})

    if not fields and not plans:
        issues.append(tr("В шаблоне не удалось определить места заполнения."))
    remove_examples = bool(fields or plans)
    if remove_examples:
        for example in examples.values():
            example.getparent().remove(example)
    buf = io.BytesIO()
    doc.save(buf)
    return {"docx": buf.getvalue(), "issues": issues, "results": results, "chunks": chunks,
            "requirements": list(requirements.values()), "used": used,
            "section_plan": section_plan,
            "unresolved_candidates": unresolved_candidates(section_plan, used),
            "removed_examples": len(examples) if remove_examples else 0}


def _from_example(sample, issues):
    """Build a clean Word document using the example's outline and simple table headings."""
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document()
    slots, fields, tables = {}, {}, {}
    section, paragraph, seen = "", None, set()
    for element in sample.element.body:
        tag = element.tag.split("}")[-1]
        if tag == "p":
            old = Paragraph(element, sample)
            if not old.text.strip() or not _heading(old):
                continue
            levels = old._p.xpath("./w:pPr/w:outlineLvl/@w:val")
            style_level = re.search(r"\d+", old.style.name if old.style else "")
            level = int(levels[0]) + 1 if levels else int(style_level.group()) if style_level else 1
            section = old.text.strip()
            doc.add_heading(section, level=max(1, min(9, level)))
            paragraph = doc.add_paragraph()
            key = f"P{len(slots) + 1}"
            slots[key] = Slot(paragraph, "", section, writable=True)
            fields[key] = (key, 0, 0, section, True)
        elif tag == "tbl" and paragraph is not None:
            table = Table(element, sample)
            if not table.rows:
                continue
            headers = tuple(c.text.strip() for c in table.rows[0].cells)
            if (section, headers) in seen:
                continue
            if (not all(headers) or len(set(headers)) != len(headers) or
                    table.rows[0]._tr.xpath(".//w:gridSpan | .//w:vMerge | .//w:tbl | .//w:bookmarkStart | .//w:bookmarkEnd | " + _PROTECTED)):
                issues.append(tr("Таблица образца в разделе «{section}» требует ручной сборки.", section=section))
                continue
            seen.add((section, headers))
            dst = doc.add_table(rows=2, cols=len(headers))
            dst.style = "Table Grid"
            for cell, header in zip(dst.rows[0].cells, headers):
                cell.text = header
            tables[f"T{len(tables) + 1}"] = dst
    if not fields:
        raise DraftError(tr("Не удалось определить разделы документа-образца по заголовкам Word."))
    return doc, slots, fields, tables

"""Human-approved, section-aware editing of an already generated DOCX.

No independent document generator: reuse Mint's exact-source citation checks,
template drafting prompt transport and run-preserving Word editing primitives.
Only plain, unprotected paragraphs and simple table cells are editable.
"""
import difflib
import hashlib
import io
from collections import defaultdict

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from .template_draft import (
    DraftError, Slot, _bookmarks, _candidate_budget, _candidates, _fill_block,
    _heading, _json, _numbers_supported, _replace, _refs, _simple,
    _text, covered_refs,
)

MAX_PROPOSAL_CHARS = 18000
MAX_COMMAND_CHARS = 3000
MAX_TARGETS = 500


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _eligible(paragraph):
    return (_simple(paragraph) and not _bookmarks(paragraph._p)
            and not _heading(paragraph)
            and not paragraph._p.xpath("./w:pPr/w:sectPr")
            and not (paragraph.style and paragraph.style.name.lower().startswith("toc")))


def _sections_and_cells(doc):
    """Return stable body-relative anchors; never identify a target by its text alone."""
    targets, paragraphs = [], defaultdict(list)
    sections_allowed = defaultdict(lambda: True)
    section = ""
    section_marker = None
    for index, element in enumerate(doc.element.body):
        kind = element.tag.split("}")[-1]
        if kind == "p":
            paragraph = Paragraph(element, doc)
            if _heading(paragraph):
                section = paragraph.text.strip() or "—"
                section_marker = index
                continue
            if not _eligible(paragraph):
                sections_allowed[section_marker] = False
                continue
            if paragraph._p.xpath("./w:pPr/w:numPr"):
                sections_allowed[section_marker] = False
            # Empty body paragraphs are selectable as sections, not individually:
            # unlimited blank placeholder lines should not flood the chooser.
            if section_marker is not None:
                paragraphs[section_marker].append((index, paragraph.text))
            if paragraph.text.strip() and len(targets) < MAX_TARGETS:
                targets.append({"id": f"p:{index}", "kind": "paragraph", "indexes": [index],
                                "section": section, "text": paragraph.text,
                                "label": f'{section or "Документ"} · {paragraph.text[:65]}'})
        elif kind == "tbl":
            if section_marker is not None:
                sections_allowed[section_marker] = False  # section text includes tables: edit cells separately
            table = Table(element, doc)
            for row_index, row in enumerate(table.rows):
                if row_index == 0:
                    continue  # table headers are protected
                for col_index, cell in enumerate(row.cells):
                    if len(targets) >= MAX_TARGETS:
                        break
                    if (cell._tc.xpath("./w:tcPr/w:gridSpan | ./w:tcPr/w:vMerge")
                            or len(cell.paragraphs) != 1 or not _eligible(cell.paragraphs[0])):
                        continue
                    text = cell.paragraphs[0].text
                    header = table.cell(0, col_index).text[:40]
                    targets.append({"id": f"t:{index}:{row_index}:{col_index}", "kind": "cell",
                                    "indexes": [index, row_index, col_index],
                                    "section": section, "text": text,
                                    "label": f'{section or "Таблица"} · {header}: {text[:50]}'})
    for marker, items in paragraphs.items():
        if not items or not sections_allowed[marker]:
            continue
        # A section target may contain several paragraphs but no interleaved
        # protected content or table; edits cannot accidentally erase a table.
        ids = [index for index, _ in items]
        combined = "\n".join(value for _, value in items if value.strip())
        if len(combined) > MAX_PROPOSAL_CHARS:
            continue
        title = Paragraph(doc.element.body[marker], doc).text.strip()
        targets.insert(0, {"id": f"s:{marker}", "kind": "section", "indexes": ids,
                           "section": title, "text": combined,
                           "label": f'{title} · текст раздела'})
    return targets


def list_targets(docx):
    try:
        doc = Document(io.BytesIO(docx))
    except Exception as exc:
        raise DraftError("Word document cannot be opened for editing") from exc
    return _sections_and_cells(doc)


def get_target(docx, target_id):
    return next((row for row in list_targets(docx) if row["id"] == target_id), None)


def propose_edit(cfg, docx, target_id, instruction, requirements, history=(), context=None):
    """Produce a text-only proposal. Does NOT change the Word document."""
    if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > MAX_COMMAND_CHARS:
        raise DraftError("Enter a non-empty edit request (up to 3000 characters).")
    target = get_target(docx, target_id)
    if target is None:
        raise DraftError("Selected Word fragment no longer exists or is protected.")
    original = target["text"]
    if not original and target["kind"] != "cell":
        raise DraftError("Selected section does not contain editable text.")
    if len(original) > MAX_PROPOSAL_CHARS:
        raise DraftError("Selected fragment is too large for one controlled change.")
    # Reuse the same source selection mechanism as initial drafting.
    extracted = {r["id"]: r for r in (requirements or []) if isinstance(r, dict) and r.get("id")}
    # Reuse the central applicability categories instead of allowing the chat
    # to reassign external obligations to the draft's target system.
    from .requirement_scope import partition
    indexed, external = partition(extracted, context)
    candidates = _candidates(" ".join((target["section"], original[:2500], instruction)),
                             indexed, size=_candidate_budget(cfg))
    allowed = {r["id"]: r for r in candidates}
    previous = [{"role": item["role"], "content": str(item["content"])[:3000]}
                for item in list(history)[-6:] if isinstance(item, dict)
                and item.get("role") in {"user", "assistant"}]
    row = _json(cfg, "edit", {"section": target["section"], "target_type": target["kind"],
                              "original": original, "request": instruction,
                              "document_context": context or {},
                              "external_context": _candidates(target["section"] + " " + instruction,
                                                              external, size=2000),
                              "requirements": candidates, "conversation": previous})
    text = _text(row, "text")
    if not text or len(text) > MAX_PROPOSAL_CHARS:
        raise DraftError("The model did not return a usable, bounded proposed revision.")
    if target["kind"] == "cell" and ("\n" in text or "\t" in text):
        raise DraftError("Table-cell edits must be a single line; choose another fragment.")
    refs = _refs(row, allowed)
    supported_quotes = covered_refs(text, refs, row.get("coverage"))
    warnings = []
    if set(refs) != supported_quotes:
        warnings.append("Some cited requirements do not have an exact output anchor.")
    if not refs:
        warnings.append("No source requirements are cited: check this change manually.")
    elif not _numbers_supported(text, refs, allowed):
        warnings.append("A number appears in the proposal without support in cited source excerpts.")
    # Direct instructions from the user may authorize editorial changes that do
    # not appear verbatim in basis sources; the user explicitly approves every edit.
    return {"target_id": target_id, "target_kind": target["kind"], "section": target["section"],
            "original": original, "text": text, "reason": _text(row, "reason"),
            "refs": refs, "coverage_confirmed": sorted(supported_quotes),
            "warnings": warnings, "sources": [allowed[r] for r in refs],
            "doc_sha256": digest(docx)}


def proposal_diff(proposal):
    before = proposal["original"].splitlines()
    after = proposal["text"].splitlines()
    return "\n".join(difflib.unified_diff(
        before, after, fromfile="Было", tofile="Предлагается", lineterm="")) or "(Text is unchanged)"


def apply_edit(docx, proposal):
    """Explicit acceptance only. Fail closed if document or selection changed."""
    if digest(docx) != proposal.get("doc_sha256"):
        raise DraftError("The document has changed since this proposal; prepare it again.")
    target = get_target(docx, proposal.get("target_id"))
    if target is None or target["text"] != proposal.get("original"):
        raise DraftError("The selected fragment changed; prepare the proposal again.")
    text = proposal.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_PROPOSAL_CHARS:
        raise DraftError("Invalid proposed replacement text.")
    if target["kind"] == "cell" and ("\n" in text or "\t" in text):
        raise DraftError("A table-cell replacement must be one line.")
    doc = Document(io.BytesIO(docx))
    if target["kind"] == "paragraph":
        item = Paragraph(doc.element.body[target["indexes"][0]], doc)
        if not _eligible(item):
            raise DraftError("Protected paragraph cannot be edited.")
        if "\n" in text and item._p.xpath("./w:pPr/w:numPr"):
            raise DraftError("Multiline edits of explicitly numbered paragraphs are not safe.")
        _fill_block(Slot(item, item.text, target["section"], writable=True),
                    0, len(item.text), text)
    elif target["kind"] == "section":
        ids = target["indexes"]
        blocks = [Paragraph(doc.element.body[index], doc) for index in ids]
        if not all(_eligible(p) and not p._p.xpath("./w:pPr/w:numPr") for p in blocks):
            raise DraftError("Protected or numbered content cannot be edited as a whole section.")
        # Replace at the first original paragraph, then remove only previously
        # vetted simple body paragraphs. Section headings and surrounding
        # tables, fields, numbering and protected content remain untouched.
        first = blocks[0]
        _fill_block(Slot(first, first.text, target["section"], writable=True),
                    0, len(first.text), text)
        for old in blocks[1:]:
            parent = old._p.getparent()
            if parent is not None:
                parent.remove(old._p)
    elif target["kind"] == "cell":
        body_index, row, col = target["indexes"]
        table = Table(doc.element.body[body_index], doc)
        cell = table.cell(row, col)
        if (cell._tc.xpath("./w:tcPr/w:gridSpan | ./w:tcPr/w:vMerge")
                or len(cell.paragraphs) != 1 or not _eligible(cell.paragraphs[0])):
            raise DraftError("Protected Word cell cannot be edited.")
        paragraph = cell.paragraphs[0]
        _replace(paragraph, 0, len(paragraph.text), text)
    else:
        raise DraftError("Unsupported Word edit target.")
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()

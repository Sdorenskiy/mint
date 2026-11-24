"""Experimental end-to-end V2 pilot for an explicitly selected empty section.

The original document and active generator are untouched. Only simple empty
body paragraphs are eligible. A separate per-need review checks the whole
proposed decomposition against the section and original linked evidence.
The pilot is always an unapproved draft, never a statement of completeness.
"""
import io
import json
import re
from collections import Counter
from zipfile import BadZipFile

from docx import Document
from docx.opc.exceptions import OpcError
from docx.text.paragraph import Paragraph

from .document_context import confirm_context
from .draft_derivation import derive_requirements
from .draft_function_analysis import analyze_functions, _compact
from .draft_registry import build_registry
from .draft_traceability import build_traceability
from .i18n import tr
from .template_draft import (DraftError, Slot, _COVER, _bookmarks, _candidate_budget,
                             _fill_block, _heading, _json, _load_draft_sources,
                             _measure_draft, _record_draft_diagnostic, _simple, _text)

_TOC = re.compile(r"^(?:table of contents|contents|оглавление|содержание)$", re.I)


def _open(template):
    try:
        return Document(io.BytesIO(template))
    except (OpcError, BadZipFile, ValueError, KeyError) as exc:
        raise DraftError(tr("Не удалось прочитать файл DOCX.")) from exc


def _empty_sections(doc):
    """Return stable body indices and safe anchors for empty leaf sections.

    Stop at the next heading. Do not treat a table, protected paragraph,
    section break or nonempty text as a fillable blank.
    """
    elements = list(doc.element.body)
    headings = [i for i, e in enumerate(elements)
                if e.tag.endswith("}p") and _heading(Paragraph(e, doc))]
    result = {}
    for i, start in enumerate(headings):
        end = headings[i + 1] if i + 1 < len(headings) else len(elements)
        heading = Paragraph(elements[start], doc)
        title = heading.text.strip()
        if not title or _COVER.search(title) or _TOC.fullmatch(title) or not _simple(heading):
            continue
        blanks = []
        valid = True
        for e in elements[start + 1:end]:
            # The final body-level sectPr is not part of the editable section.
            if e.tag.endswith("}sectPr") and e is elements[-1]:
                continue
            if not e.tag.endswith("}p"):
                valid = False
                break
            p = Paragraph(e, doc)
            if (p.text.strip() or not _simple(p) or _bookmarks(e)
                    or e.xpath("./w:pPr/w:sectPr | ./w:pPr/w:numPr")
                    or not p.style or p.style.name.lower().startswith(("toc", "list", "список"))):
                valid = False
                break
            # Whitespace-only paragraphs are left intact, not used as anchors.
            if p.text == "":
                blanks.append(p)
        if valid and blanks:
            result[start] = (title, blanks[0])
    return result


def pilot_sections(template):
    """List explicitly selectable empty sections without calling a model."""
    return [{"index": i, "title": value[0]}
            for i, value in _empty_sections(_open(template)).items()]


def _review_need(cfg, need, candidates, records, context, title):
    """Check section fit and coverage of the complete decomposition, not just each claim."""
    if not candidates or any(c["assessment"] != "model_supported" for c in candidates):
        return "needs_review"
    ids = set(records) | {c["id"] for c in candidates}
    for c in candidates:
        text = c["text"]
        # Only literal single paragraphs enter this pilot; never print temporary IDs.
        if ("\n" in text or "\r" in text or "\t" in text or
                any(word in ids for word in re.findall(r"\b[RP]\d+\b", text))):
            return "unsafe_text"
    refs = list(dict.fromkeys(rid for c in candidates
                             for rid in c["need_refs"] + c["state_refs"] + c["constraint_refs"]))
    payload = {"context": context, "section": title, "need": _compact(need),
               "requirements": [{"id": c["id"], "text": c["text"]} for c in candidates],
               "evidence": [_compact(records[rid]) for rid in refs]}
    if len(json.dumps(payload, ensure_ascii=False)) > _candidate_budget(cfg):
        return "review_context_limit"
    try:
        answer = _json(cfg, "pilot_coverage", payload)
    except DraftError:
        return "review_error"
    if not _text(answer, "reason"):
        return "review_incomplete"
    if answer.get("section_relevant") is False:
        return "out_of_section_proposal"
    if answer.get("covered") is False:
        return "coverage_gap"
    if answer.get("section_relevant") is True and answer.get("covered") is True:
        return "model_covered"
    return "review_incomplete"


@_measure_draft
def create_section_pilot(template, cfg, sources, source_roles, context, section_index,
                         progress=None, *, reset_extract_cache=False):
    """Run the actual registry → analysis → derivation → review → Word chain.

    Select a section by index from pilot_sections() for the same template.
    Partial output is allowed, with explicit pending IDs and no readiness claim.
    The caller must keep the result and its original-source text inside the
    local environment. This is not a sanitized diagnostic export.
    """
    doc = _open(template)
    context = confirm_context(context)
    target = _empty_sections(doc).get(section_index)
    if target is None:
        raise DraftError(tr("В шаблоне не удалось определить места заполнения."))
    title, paragraph = target
    emit = progress or (lambda *_: None)
    issues = []
    sources = list(dict.fromkeys(sources))
    if set(source_roles) - set(sources):
        raise ValueError("Invalid registry source role")
    documents = _load_draft_sources(cfg, sources, issues)
    roles = {name: source_roles[name] for name, _ in documents if name in source_roles}
    registry = build_registry(cfg, documents, roles, issues, emit, reset_cache=reset_extract_cache)
    records = registry["requirements"]
    analysis = analyze_functions(cfg, records, context, emit)
    derivation = derive_requirements(cfg, records, analysis, context, emit)
    proposals = derivation["requirements"]
    dispositions = dict(derivation["dispositions"])
    grouped = {}
    for item in proposals:
        grouped.setdefault(item["need_refs"][0], []).append(item)
    selected = []
    for index, (rid, candidates) in enumerate(grouped.items(), 1):
        emit("pilot_coverage", index)
        status = _review_need(cfg, records[rid], candidates, records, context, title)
        dispositions[rid] = status
        if status == "model_covered":
            selected.extend(candidates)
    results = []
    first = list(doc.element.body).index(paragraph._p)
    # Consolidate identical output text across different needs, preserving every link.
    by_text = {}
    for item in selected:
        by_text.setdefault(item["text"], []).append(item)
    if selected:
        # Reuse the existing safe writer; it generates separate Word paragraphs
        # and preserves paragraph style. Reopen the actual output before anchoring.
        _fill_block(Slot(paragraph, "", title, writable=True), 0, 0,
                    "\n".join(by_text))
    buf = io.BytesIO()
    doc.save(buf)
    output = buf.getvalue()
    reopened = _open(output)
    elements = list(reopened.element.body)
    actual = [Paragraph(e, reopened).text for e in elements[first:first + len(by_text)]
              if e.tag.endswith("}p")]
    if actual != list(by_text):
        raise DraftError(tr("Не удалось прочитать файл DOCX."))
    used = set()
    for text, items in by_text.items():
        refs = list(dict.fromkeys(rid for item in items
                                  for rid in item["need_refs"] + item["state_refs"] + item["constraint_refs"]))
        used.update(refs)
        results.append({"field": items[0]["id"], "proposal_ids": [item["id"] for item in items],
                        "section": title, "kind": "field", "status": "unchecked",
                        "text": text, "detail": "", "refs": refs, "confirmed_refs": refs})
    # The existing traceability views reflect exact output anchors, not proof
    # of semantic transfer. Keep unresolved needs separately from used evidence.
    result = {"docx": output, "issues": issues, "requirements": list(records.values()),
              "chunks": registry["chunks"], "results": results, "used": used,
              "section_plan": {title: {"selected_ids": list(dict.fromkeys(
                  rid for row in results for rid in row["refs"])),
                  "fields": len(results), "total_requirements": len(records)}},
              "document_context": context, "analysis": analysis, "derivation": derivation,
              "section_dispositions": dispositions, "section_index": section_index,
              "pilot_status": "partial_draft" if selected else "empty_draft",
              "requires_expert_review": True}
    result["traceability"] = build_traceability(result)
    _record_draft_diagnostic("pilot_section", {
        "inserted": len(by_text), "dispositions": dict(Counter(dispositions.values())),
        "cross_cutting_pending": len(derivation["cross_cutting_ids"]),
        "open_questions_pending": len(derivation["open_question_ids"]),
        "untyped_pending": len(derivation["untyped_ids"]),
        "source_read_errors": len(set(sources) - {name for name, _ in documents}),
    })
    return result

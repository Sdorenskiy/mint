"""Infer and validate the document's intended system before drafting.

The template is the primary authority for the *subject* of the new document.
Broad source documents are evidence for requirements, not a reliable signal
of which participant the resulting document is about.
"""
import io
import re
from docx import Document

from .template_draft import DraftError, _json, _heading

_CONTEXT_KEYS = ("target", "objective", "scope", "participants")
_LIMITS = {"target": 180, "objective": 1200, "scope": 1600, "participants": 800}


def normalize_context(proposed):
    """Bound, plain-text user-confirmed context; never execute embedded instructions."""
    if not isinstance(proposed, dict):
        raise DraftError("Не удалось прочитать контекст документа.")
    result = {}
    for name in _CONTEXT_KEYS:
        value = proposed.get(name, "")
        if not isinstance(value, str):
            value = ""
        result[name] = " ".join(value.split())[:_LIMITS[name]]
    return result


def confirm_context(proposed):
    """Require a nonempty target; empty scope/participants are valid and honest."""
    result = normalize_context(proposed)
    if not result["target"]:
        raise DraftError("Укажите целевую систему или объект документа.")
    return result


def template_outline(docx):
    """Only the uploaded Word template supplies positive evidence about the target."""
    try:
        doc = Document(io.BytesIO(docx))
    except Exception as exc:
        raise DraftError("Не удалось прочитать шаблон Word для определения контекста.") from exc
    headings, lead, content = [], [], []
    first_heading = False
    for paragraph in doc.paragraphs:
        value = paragraph.text.strip()
        if not value:
            continue
        if _heading(paragraph):
            headings.append(value[:280])
            first_heading = True
        elif not first_heading and len(lead) < 12:
            lead.append(value[:450])
        elif len(content) < 25:
            content.append(value[:350])
        if len(headings) >= 60 and len(content) >= 25:
            break
    # Titles often contain the target, while template instructions describe the
    # type of work; do not use external requirements to guess subject identity.
    return {"front_matter": lead[:12], "headings": headings[:60],
            "sample_instructions": content[:25]}


def infer_context(cfg, docx, source_names):
    """One bounded LLM call. Suggestions always need user confirmation."""
    outline = template_outline(docx)
    rows = _json(cfg, "context", {"template": outline,
                                  "selected_source_names": list(dict.fromkeys(source_names))[:50]})
    proposal = normalize_context(rows)
    confidence = str(rows.get("confidence", "low")).strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    return {**proposal, "confidence": confidence,
            "reason": str(rows.get("reason", ""))[:700]}


def context_search_terms(context):
    """Add confirmed focus to lexical retrieval. Never treat it as source evidence."""
    c = normalize_context(context) if context else {}
    return " ".join(c.get(k, "") for k in ("target", "objective", "scope"))

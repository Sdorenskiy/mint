"""Shared, deterministic evidence checks for audit findings and Word drafting.

This module does not determine whether a regulation is legally binding:
a model's applicability judgment is not independent evidence of authority.
It validates that *the alleged quotations* exist in the cited contexts and
that a substantive, explicitly reasoned comparison was supplied.
"""
import re

from .text import quote_in_text

_SOURCE_TAG = re.compile(r"\[(?:Источник|Source):\s*([^,\]\n]+)(?:,\s*([^\]\n]+))?\]", re.I)
_SOURCE_HEADER = re.compile(r"(?m)^===\s*(?:ИСТОЧНИК|SOURCE):\s*([^|\n=]+)", re.I)
_TABLE_NUMBER = re.compile(r"(?iu)\b(?:таблиц(?:а|е|ы|у|ей)|table)\s*(?:№|no\.?|#)?\s*\d+(?:\.\d+)*\b")
_WHITESPACE = re.compile(r"\s+")


def quoted(quote, source_text):
    """Exact content under Mint's existing quote normalizer, never model judgment."""
    return bool(isinstance(quote, str) and quote.strip() and
                isinstance(source_text, str) and source_text.strip() and quote_in_text(quote, source_text))


def source_reference(text):
    """Return the first explicit external-source citation, or None for internal findings."""
    m = _SOURCE_TAG.search(text or "")
    return (m.group(1).strip(), (m.group(2) or "").strip()) if m else None


def source_context(norms_text, source_name):
    """Locate the cited file's block, not some other retrieved document's quote.

    If the file occurs more than once, concatenate only its matching blocks.
    Unmarked contexts cannot certify a file-specific citation.
    """
    matches = list(_SOURCE_HEADER.finditer(norms_text or ""))
    parts = []
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        if name.casefold() == (source_name or "").strip().casefold():
            parts.append(norms_text[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(norms_text)])
    return "\n".join(parts)


def only_table_number_diff(left, right):
    """Reference numbers in *otherwise identical* sentences are not a conflict."""
    if not (_TABLE_NUMBER.search(left or "") and _TABLE_NUMBER.search(right or "")):
        return False
    clean = lambda s: _WHITESPACE.sub(" ", _TABLE_NUMBER.sub("ТАБЛИЦА", s or "").casefold()).strip()
    return clean(left) == clean(right) and (left or "").casefold() != (right or "").casefold()


def verify_comparison(claim_text, norm_text, model, *, claim_quote_required=True):
    """Validate one structured comparison, with a *single* shared contract.

    Outputs:
      conflict — well-formed evidence of an applicable semantic conflict, to be
                 displayed with citations (not a legal determination);
      checked — model asserts a compatible applicable requirement with evidence;
      uncertain — incomplete/ambiguous provenance or applicability; review;
      unchecked — no applicable normative comparison was established.
    """
    claim_quote = str(model.get("claim_quote") or "").strip()
    norm_quote = str(model.get("norm_quote") or "").strip()
    ref = str(model.get("ref") or "").strip()
    reason = str(model.get("reason") or "").strip()
    scope_reason = str(model.get("applicability_reason") or "").strip()
    applicability = str(model.get("applicability") or "").strip().lower()
    decision = str(model.get("status") or "").strip().lower()
    result = {"status": "unchecked", "claim_quote": claim_quote, "norm_quote": norm_quote,
              "ref": ref, "reason": reason, "applicability": applicability,
              "applicability_reason": scope_reason, "source": str(model.get("source") or "").strip()}

    if not norm_text or decision not in {"conflict", "checked", "uncertain"}:
        return result
    if not quoted(norm_quote, norm_text):
        return {**result, "status": "uncertain", "reason": "Citation not found in selected source"}
    if claim_quote_required and not quoted(claim_quote, claim_text):
        return {**result, "status": "uncertain", "reason": "Claim quote not found in checked document"}
    if applicability in {"not_applicable", "different_scope"}:
        return result
    if applicability != "applicable" or not scope_reason:
        return {**result, "status": "uncertain", "reason": reason or "Applicability is not established"}
    if decision == "uncertain" or not reason:
        return {**result, "status": "uncertain", "reason": reason or "Semantic comparison is incomplete"}
    if decision == "conflict" and only_table_number_diff(claim_quote, norm_quote):
        return result
    return {**result, "status": decision}

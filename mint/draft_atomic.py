"""Opt-in V3 experiment: full original scope -> literal candidates.

No obligation decisions, index writes, R-ID creation or Word generation.
Coordinates refer to parsed Markdown fragments, not raw Word byte offsets.
Mechanical validation is not semantic verification.
"""
from collections import Counter
import hashlib
import json
import re
import time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .draft_progress import tracked
from .draft_target_analysis import (_map_sources, _metric_pair, _verify_originals,
                                    _metric_cells, _metric_header_label,
                                    _METRIC_VALUE_LABELS, _METRIC_UNIT_LABELS)
from .draft_pilot_report import _number, safe_stage_metrics
from .template_draft import (DraftError, _candidate_budget, _json, _load_draft_sources,
                             _measure_draft)
from .version import MINT_VERSION

MAX_SAMPLE = 20
MAX_ITEMS = 12
STAGE = "atomic_extract"
MODE_STAGES = {"slots": STAGE, "assertions": "atomic_assertions"}


class Slots(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    actor: Optional[str] = None
    action: Optional[str] = None
    object: Optional[str] = None
    source_party: Optional[str] = None
    destination_party: Optional[str] = None
    data_type: Optional[str] = None
    data_content: Optional[str] = None
    interface: Optional[str] = None
    format: Optional[str] = None
    timing: Optional[str] = None
    condition: Optional[str] = None
    modality: Optional[str] = None
    constraint: Optional[str] = None
    access_class: Optional[str] = None
    protection: Optional[str] = None
    metric_subject: Optional[str] = None
    metric_value: Optional[str] = None
    metric_unit: Optional[str] = None


class Candidate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    first: int = Field(ge=1)
    last: int = Field(ge=1)
    fields: Slots


class AssertionCandidate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    first: int = Field(ge=1)
    last: int = Field(ge=1)
    text: Optional[str] = None


METRIC_KEYS = ("metric_subject", "metric_value", "metric_unit")
COUNTERS = ("fragments_total", "fragments_selected", "fragments_attempted", "fragments_processed",
            "fragments_complete", "fragments_failed", "source_read_errors", "source_count",
            "invalid_range", "recovery_attempted", "recovery_windows", "recovery_added",
            "batch_error", "context_limit", "invalid_payload", "response_limit",
            "invalid_shape", "empty_fields",
            "invalid_field", "invalid_metric", "duplicate", "accepted",
            "empty_response", "partial_fragments", "metric_table_fragments",
            "metric_table_rows", "metric_table_fallbacks", "ordinary_table_rows",
            "ordinary_table_fragments", "uncertain_table_rows", "context_records",
            "candidate_records", "model_windows", "response_items", "trace_omitted")


def prepare_atomic_sources(cfg, sources, progress=None):
    """Read explicitly selected A originals, without profile inference or retrieval."""
    issues, hashes = [], {}
    docs = _load_draft_sources(cfg, sources, issues, source_hashes=hashes, emit=progress)
    spans, sections = _map_sources(docs, {})
    revisions = {name: hashlib.sha256(md.encode("utf-8")).hexdigest() for name, md in docs}
    return {"hashes": hashes, "revisions": revisions, "spans": spans,
            "sections": sections, "issues": issues}


def _line_parts(text):
    """Keep exact source offsets even for repeated lines and CRLF."""
    parts, offset = [], 0
    for n, raw in enumerate(text.splitlines(keepends=True), 1):
        line = raw.rstrip("\r\n")
        parts.append({"n": n, "text": line, "start": offset, "end": offset + len(line)})
        offset += len(raw)
    return parts


def _selected_evidence(first, last, span, parts=None):
    """Shared source selection for both experimental model contracts."""
    parts = _line_parts(span["text"]) if parts is None else parts
    allowed = {p["n"]: p for p in parts}
    if (last < first or last - first >= 4
            or any(n not in allowed for n in range(first, last + 1))):
        return None
    start, end = allowed[first]["start"], allowed[last]["end"]
    quote = span["text"][start:end]
    if not quote.strip():
        return None
    table = span.get("table_context") or {}
    header = table.get("header", "")
    if header and (first != last or quote.strip() == header.strip()
                   or quote.strip() == table.get("separator", "").strip()
                   or not quote.strip().startswith("|")):
        return None
    return {"quote": quote, "start": start, "end": end, "first": first, "last": last}


def _validated_candidate(raw, span, parts=None, detail=None):
    """Select numbered original lines; the model never generates the quotation."""
    try:
        item = Candidate.model_validate(raw, strict=True)
    except ValidationError:
        return None, "invalid_shape"
    evidence = _selected_evidence(item.first, item.last, span, parts)
    if evidence is None:
        return None, "invalid_range"
    quote = evidence["quote"]
    fields = item.fields.model_dump(exclude_none=True)
    if not fields:
        return None, "empty_fields"
    table = span.get("table_context") or {}
    header = table.get("header", "")
    for k, v in fields.items():
        cause = ("empty" if not v.strip() else "too_long" if len(v) > 600 else
                 "not_literal" if v not in quote and not
                 (k in ("metric_subject", "metric_unit") and v in header) else None)
        if cause:
            if detail is not None:
                detail.update(field=k, cause=cause)
            return None, "invalid_field"
    if any(k in fields for k in METRIC_KEYS):
        if (not all(k in fields for k in METRIC_KEYS)
                or not _metric_pair({"quote": quote, "table_context": table},
                                    *(fields[k] for k in METRIC_KEYS))):
            return None, "invalid_metric"
    return {**evidence, "fields": fields}, "accepted"


def _validated_assertion(raw, span, parts=None, detail=None):
    """Select one literal contiguous assertion; no semantic fields required.

    Accept only a unique match within selected lines. Whitespace differences
    (e.g. CRLF) are tolerated; return the untouched original slice.
    """
    try:
        item = AssertionCandidate.model_validate(raw, strict=True)
    except ValidationError:
        return None, "invalid_shape"
    parts = _line_parts(span["text"]) if parts is None else parts
    evidence = _selected_evidence(item.first, item.last, span, parts)
    if evidence is None:
        return None, "invalid_range"
    if (span.get("table_context") or {}).get("header"):
        # The numbered row is the assertion, with its table context retained.
        if item.text is not None and " ".join(item.text.split()) != " ".join(evidence["quote"].split()):
            if detail is not None:
                detail.update(field="text", cause="not_full_row")
            return None, "invalid_field"
    else:
        text = (item.text or "").strip()
        if not text or len(text) > 4000:
            if detail is not None:
                detail.update(field="text", cause="empty" if not text else "too_long")
            return None, "invalid_field"
        pattern = r"\s+".join(re.escape(word) for word in text.split())
        if text[0].isalnum() or text[0] == "_":
            pattern = r"(?<!\w)" + pattern
        if text[-1].isalnum() or text[-1] == "_":
            pattern += r"(?!\w)"
        matches = list(re.finditer(r"(?=(" + pattern + r"))", evidence["quote"]))
        if len(matches) != 1:
            if detail is not None:
                detail.update(field="text", cause="ambiguous_literal" if matches else "not_literal")
            return None, "invalid_field"
        start = evidence["start"] + matches[0].start(1)
        end = evidence["start"] + matches[0].end(1)
        first = next(p["n"] for p in parts if p["start"] <= start < p["end"])
        last = next(p["n"] for p in parts if p["start"] < end <= p["end"])
        evidence = {"quote": span["text"][start:end], "start": start, "end": end,
                    "first": first, "last": last}
    return {**evidence, "fields": {}, "origin": "assertion"}, "accepted"


def _fact_key(fact):
    return fact["start"], fact["end"], tuple(sorted(fact["fields"].items()))


_REJECTION_CODES = {"invalid_range", "invalid_shape", "empty_fields", "invalid_field",
                    "invalid_metric", "invalid_payload", "batch_error", "context_limit", "response_limit"}
_REJECTION_FIELDS = set(Slots.model_fields) | {"text"}
_REJECTION_CAUSES = {"empty", "too_long", "not_literal", "ambiguous_literal", "not_full_row"}
MAX_TRACE_EVENTS = 1000
MAX_PRIVATE_EVENTS = 100
MAX_PRIVATE_CHARS = 100_000
MAX_PRIVATE_ITEM_CHARS = 8_000


def _record_rejection(trace, counts, code, detail=None, raw=None):
    """Only code-owned metadata in ordinary diagnostics. Raw parsed model
    candidates are captured only by explicit local opt-in, with a shared cap."""
    if trace is None:
        return
    event = {"code": code, "window": trace["windows"],
             "first_line": trace.get("first_line", 0), "last_line": trace.get("last_line", 0)}
    detail = detail or {}
    if detail.get("field") in _REJECTION_FIELDS:
        event["field"] = detail["field"]
    if detail.get("cause") in _REJECTION_CAUSES:
        event["cause"] = detail["cause"]
    budget = trace["budget"]
    if budget["events"] < MAX_TRACE_EVENTS:
        trace["rejections"].append(event)
        budget["events"] += 1
    else:
        counts["trace_omitted"] += 1
    if not budget["extended"] or raw is None:
        return
    # Do not capture transport errors, headers, configuration, or credentials.
    # Parsed model content itself can contain private source data.
    try:
        encoded = json.dumps(raw, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, RecursionError):
        budget["private_omitted"] += 1
        return
    if (budget["private_events"] >= MAX_PRIVATE_EVENTS or len(encoded) > MAX_PRIVATE_ITEM_CHARS
            or budget["private_chars"] + len(encoded) > MAX_PRIVATE_CHARS):
        budget["private_omitted"] += 1
        return
    trace["private"].append({**event, "candidate_json": encoded})
    budget["private_events"] += 1
    budget["private_chars"] += len(encoded)


def _extract_window(cfg, span, parts, counts, *, mode="slots", trace=None):
    payload = {"section": span["section"],
               "parts": [{"n": p["n"], "text": p["text"]} for p in parts]}
    if span.get("table_context"):
        payload["table_context"] = span["table_context"]
    if trace is not None:
        trace["windows"] += 1
        trace["first_line"] = parts[0]["n"] if parts else 0
        trace["last_line"] = parts[-1]["n"] if parts else 0
    if len(json.dumps(payload, ensure_ascii=False)) > _candidate_budget(cfg):
        counts["context_limit"] += 1
        _record_rejection(trace, counts, "context_limit")
        return [], "context_limit", True
    counts["model_windows"] += 1
    try:
        reply = _json(cfg, MODE_STAGES[mode], payload)
    except DraftError:
        counts["batch_error"] += 1
        _record_rejection(trace, counts, "batch_error")
        return [], "batch_error", False
    if not isinstance(reply, dict) or set(reply) != {"items"} or not isinstance(reply["items"], list):
        counts["invalid_payload"] += 1
        _record_rejection(trace, counts, "invalid_payload", raw=reply)
        return [], "invalid_payload", False
    items = reply["items"]
    counts["response_items"] += len(items)
    limited = len(items) >= MAX_ITEMS
    if limited:
        counts["response_limit"] += 1
        _record_rejection(trace, counts, "response_limit")
    facts, seen = [], set()
    partial = limited
    for raw in items[:MAX_ITEMS]:
        validate = _validated_assertion if mode == "assertions" else _validated_candidate
        detail = {}
        fact, status = validate(raw, span, parts, detail)
        if fact is None:
            counts[status] += 1
            _record_rejection(trace, counts, status, detail, raw)
            partial = True
            continue
        key = _fact_key(fact)
        if key in seen:
            counts["duplicate"] += 1
            continue
        seen.add(key)
        facts.append(fact)
    return facts, "partial" if partial else "processed", limited


_SUBJECT_LABELS = {"показатель", "наименование показателя", "metric", "indicator"}
_CONDITION_LABELS = {"условия", "условие", "условия измерения", "conditions", "condition"}
# A single explicit scalar only. Ranges, inequalities in the value cell,
# compound values and unfamiliar layouts use the existing model route.
_SCALAR = re.compile(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})+)(?:[.,][0-9]+)?")


def _structured_metrics(span, parts):
    """Return literal metric candidates for an entirely unambiguous table chunk.

    None means non-metric layout; [] means recognized header but unsafe row(s).
    No obligation, ownership, current/target status or semantic approval inferred.
    """
    table = span.get("table_context") or {}
    header, separator = table.get("header", ""), table.get("separator", "")
    if not header.strip().startswith("|") or not header.strip().endswith("|"):
        return None
    labels = [_metric_header_label(c).casefold() for c in _metric_cells(header)]
    aliases = (_SUBJECT_LABELS, _METRIC_VALUE_LABELS, _METRIC_UNIT_LABELS, _CONDITION_LABELS)
    columns = [[i for i, label in enumerate(labels) if label in names] for names in aliases]
    if (len(labels) not in (3, 4) or any(len(col) != 1 for col in columns[:3])
            or len(columns[3]) != len(labels) - 3):
        return None
    si, vi, ui = (col[0] for col in columns[:3])
    ci = columns[3][0] if columns[3] else None
    facts = []
    for part in parts:
        line = part["text"].strip()
        if not line or line == header.strip() or (separator and line == separator.strip()):
            continue
        if not line.startswith("|") or not line.endswith("|"):
            return []
        values = _metric_cells(line)
        if len(values) != len(labels) or not all(values[i] for i in (si, vi, ui)):
            return []
        # Do not guess at merged cells, multiple units, placeholders or rich markup.
        if not _SCALAR.fullmatch(values[vi]) or not re.fullmatch(r"[\w%°µμ/·.²³ -]+", values[ui]):
            return []
        if not any(ch.isalpha() for ch in values[ui]) and values[ui] not in {"%", "°"}:
            return []
        fields = dict(metric_subject=values[si], metric_value=values[vi], metric_unit=values[ui])
        if ci is not None and values[ci]:
            fields["condition"] = values[ci]
        fact, status = _validated_candidate({"first": part["n"], "last": part["n"],
                                             "fields": fields}, span, parts)
        if status != "accepted":
            return []
        fact["origin"] = "structured_table"
        facts.append(fact)
    return facts


# Structural context, never an inferred obligation. Keep every selected
# record available in the private registry; the normal view separates it.
_CONTEXT_SECTIONS = {"содержание", "оглавление", "история редакций", "история изменений",
                     "термины", "термины и определения", "сокращения", "contents",
                     "table of contents", "revision history", "change history", "terms",
                     "terms and definitions", "abbreviations"}
_DOCUMENT_TITLES = {"функциональные требования", "архитектурное решение",
                    "техническое задание", "functional requirements",
                    "architecture solution", "technical specification"}
_METADATA = re.compile(r"^(?:обозначение|редакция|версия документа|статус документа|статус|"
                       r"document id|revision|document version|document status)\s*(?::|№|\d)", re.I)
_EXAMPLE = re.compile(r"^(?:(?:условный|иллюстративный) пример\b|пример\s*:|"
                      r"(?:illustrative|hypothetical) example\b|example\s*:)", re.I)


def _context_section(span):
    for heading in span.get("section", "").split("›"):
        name = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", heading).strip().casefold()
        if name in _CONTEXT_SECTIONS:
            return True
    return False


def _record_role(span, fact):
    if fact.get("record_role") == "unresolved":
        return "unresolved"
    if _context_section(span):
        return "context"
    quote = fact["quote"].strip()
    if _EXAMPLE.match(quote):
        return "context"
    # Mark obvious document metadata, not the generic word "version" in
    # a requirement. A front-matter candidate needs structural evidence.
    section = span.get("section", "").strip().casefold()
    front = span.get("fragment", 0) in (1, 2) and (
        not section or section in _DOCUMENT_TITLES)
    if front:
        if _METADATA.match(quote):
            return "context"
        if not section and span["text"].lstrip().startswith("**") and not re.search(r"[.!?;]$", quote):
            return "context"
        if section in _DOCUMENT_TITLES and any(_METADATA.match(p.strip())
                for p in span["text"].splitlines()):
            first = next((p.strip() for p in span["text"].splitlines() if p.strip()), "")
            if quote == first and not re.search(r"[.!?;]$", quote):
                return "context"
            if re.fullmatch(r"(?:Все .{1,200} вымышлены\.|Не является документом .{1,200}\.)", quote, re.I):
                return "context"
    return "candidate"


def _ordinary_table_rows(span, parts):
    """Keep source rows rather than asking the model to select them.
    Preserve positional cells, never reconstruct a merged/missing value."""
    table = span.get("table_context") or {}
    header = table.get("header", "")
    if not header:
        return None
    headers = _metric_cells(header)
    labels = [_metric_header_label(c).casefold() for c in headers]
    header_ok = (header.strip().startswith("|") and header.strip().endswith("|")
                 and len(headers) > 0 and all(labels) and len(set(labels)) == len(labels))
    facts = []
    for part in parts:
        line = part["text"].strip()
        if not line or line == header.strip() or line == table.get("separator", "").strip():
            continue
        values = _metric_cells(line) if line.startswith("|") and line.endswith("|") else []
        aligned = (header_ok and len(values) == len(headers) and all(values)
                   and not re.search(r"<(?:td|th|table|br)\b|(?:rowspan|colspan)\s*=", line, re.I))
        fact = {"quote": part["text"], "start": part["start"], "end": part["end"],
                "first": part["n"], "last": part["n"], "fields": {}, "origin": "table_row",
                "table_row": {"headers": headers, "values": values,
                              "layout": "aligned" if aligned else "uncertain"}}
        if not aligned:
            fact["record_role"] = "unresolved"
        facts.append(fact)
    return facts


def _extract_fragment(cfg, span, counts, *, mode="slots", trace=None):
    parts = _line_parts(span["text"])
    table_facts = _structured_metrics(span, parts)
    if table_facts:
        counts["metric_table_fragments"] += 1
        counts["metric_table_rows"] += len(table_facts)
        counts["accepted"] += len(table_facts)
        return table_facts, "processed"
    if table_facts is not None:
        counts["metric_table_fallbacks"] += 1
    if mode == "assertions":
        rows = _ordinary_table_rows(span, parts)
        if rows is not None:
            # If the explicit metric layout was unsafe, don't imply that a
            # generic row is a successfully interpreted metric.
            if table_facts is not None:
                for row in rows:
                    row["record_role"] = "unresolved"
            uncertain = sum(row.get("record_role") == "unresolved" for row in rows)
            counts["ordinary_table_fragments"] += 1
            counts["ordinary_table_rows"] += len(rows)
            counts["uncertain_table_rows"] += uncertain
            counts["accepted"] += len(rows)
            status = "partial" if uncertain or not rows else "processed"
            counts["partial_fragments"] += int(status == "partial")
            return rows, status
    before_invalid = counts["invalid_field"]
    facts, status, limited = _extract_window(cfg, span, parts, counts, mode=mode, trace=trace)
    # Recover once with smaller disjoint windows when the original input or
    # output hits a limit. Keep all original candidates; never silently claim
    # completeness after splitting across a possible semantic boundary.
    # One bounded recovery for text literal failures in the simplified
    # contract too; don't repeat an identical single-line window.
    recover_literal = (mode == "assertions" and counts["invalid_field"] > before_invalid
                       and sum(bool(p["text"].strip()) for p in parts) > 1)
    if (limited or recover_literal) and len(parts) > 1:
        counts["recovery_attempted"] += 1
        seen = {_fact_key(fact) for fact in facts}
        middle = len(parts) // 2
        children = []
        for window in (parts[:middle], parts[middle:]):
            counts["recovery_windows"] += 1
            more, child_status, _ = _extract_window(cfg, span, window, counts, mode=mode, trace=trace)
            children.append(child_status)
            for fact in more:
                key = _fact_key(fact)
                if key not in seen:
                    seen.add(key)
                    facts.append(fact)
                    counts["recovery_added"] += 1
                else:
                    counts["duplicate"] += 1
        if facts or any(s in {"processed", "partial"} for s in children):
            status = "partial"
    counts["accepted"] += len(facts)
    counts["partial_fragments"] += int(status == "partial")
    counts["empty_response"] += int(status == "processed" and not facts)
    return facts, status


# Facets are navigation, not a determination that an assertion is a requirement.
# A candidate may appear in more than one view, but keeps one local ID.
FACT_GROUPS = {
    "interactions": {"source_party", "destination_party", "interface"},
    "participants": {"actor", "source_party", "destination_party"},
    "data": {"data_type", "data_content", "format"},
    "security": {"access_class", "protection"},
    "metrics": set(METRIC_KEYS),
    "timing": {"timing"},
    "actions": {"action", "object", "modality"},
    "constraints": {"condition", "constraint"},
}


def fact_rows(result):
    rows = []
    for span in result["fragments"]:
        for fact in span["facts"]:
            rows.append((span, fact))
    return rows


def fact_in_group(fact, group):
    role = fact.get("record_role", "candidate")
    if group in {"context", "unresolved"}:
        return role == group
    if role != "candidate":
        return False
    return group == "all" or bool(FACT_GROUPS.get(group, set()) & fact["fields"].keys())


@_measure_draft
def extract_atomic_sample(cfg, prepared, selected=None, progress=None, *, mode="slots", extended=False):
    """Cold scan using one of two contracts and the same source/table path."""
    if mode not in MODE_STAGES:
        raise ValueError("Invalid atomic extraction mode")
    spans = prepared["spans"]
    scope = "all" if selected is None else "sample"
    selected = list(spans) if selected is None else list(dict.fromkeys(selected))
    if not selected or (scope == "sample" and len(selected) > MAX_SAMPLE) or any(sid not in spans for sid in selected):
        raise ValueError("Invalid atomic scope")
    _verify_originals(cfg, prepared)
    emit = progress or (lambda *_: None)
    counts = Counter(fragments_total=len(spans), fragments_selected=len(selected),
                     source_count=len(prepared["hashes"]), source_read_errors=len(prepared["issues"]))
    result, diagnostics, private = [], [], []
    budget = {"events": 0, "extended": bool(extended), "private_events": 0,
              "private_chars": 0, "private_omitted": 0}
    selected_set = set(selected)
    jobs = [span for sid, span in spans.items() if sid in selected_set]
    for span in tracked(emit, STAGE, jobs):
        counts["fragments_attempted"] += 1
        before = counts.copy()
        started = time.perf_counter()
        trace = {"windows": 0, "rejections": [], "private": [], "budget": budget}
        facts, status = _extract_fragment(cfg, span, counts, mode=mode, trace=trace)
        for fact in facts:
            role = _record_role(span, fact) if mode == "assertions" else "candidate"
            if role != "candidate":
                fact["record_role"] = role
            counts["context_records" if role == "context" else "candidate_records"] += int(role != "unresolved")
        diagnostics.append({"fragment": len(result) + 1,
                            "structure": "table" if span.get("table_context") else "text",
                            "status": status, "windows": trace["windows"],
                            "seconds": round(time.perf_counter() - started, 3),
                            "counts": {k: counts[k] - before[k] for k in COUNTERS if counts[k] != before[k]},
                            "rejections": trace["rejections"]})
        if trace["private"]:
            private.append({"fragment": span["id"], "rejections": trace["private"]})
        counts["fragments_processed"] += int(status in {"processed", "partial"})
        counts["fragments_complete"] += int(status == "processed")
        counts["fragments_failed"] += int(status not in {"processed", "partial"})
        for index, fact in enumerate(facts, 1):
            fact["id"] = span["id"] + "." + str(index)
        result.append({**span, "revision": prepared["revisions"][span["source"]],
                       "status": status, "facts": facts})
    _verify_originals(cfg, prepared)
    output = {"format": "mint-atomic-sample/2", "scope": scope, "mode": mode, "fragments": result,
              "counts": dict(counts), "fragment_diagnostics": diagnostics, "requires_expert_review": True}
    if extended:
        output["private_diagnostics"] = {"fragments": private, "omitted": budget["private_omitted"]}
    return output


def atomic_private_diagnostics(result):
    """Separate explicitly enabled export. Never include model configuration."""
    detail = result.get("private_diagnostics")
    if detail is None:
        return None
    spans = {s["id"]: s for s in result["fragments"]}
    return {"format": "mint-atomic-private-diagnostics/1", "mint": MINT_VERSION,
            "mode": result["mode"], "omitted": detail["omitted"],
            "contract": MODE_STAGES[result["mode"]],
            "capture": "parsed_rejected_candidates_only",
            "fragments": [{**row, "text": spans[row["fragment"]]["text"],
                           "table_context": spans[row["fragment"]].get("table_context")}
                          for row in detail["fragments"]]}


def _safe_fragment_diagnostics(result):
    """Project every field explicitly; never copy arbitrary diagnostic objects."""
    rows = []
    statuses = {"processed", "partial", "context_limit", "batch_error", "invalid_payload"}
    for index, row in enumerate(result.get("fragment_diagnostics", ()), 1):
        rejections = []
        for event in row.get("rejections", ()):
            code = event.get("code")
            if code not in _REJECTION_CODES:
                continue
            clean = {"code": code, "window": _number(event.get("window")),
                     "first_line": _number(event.get("first_line")), "last_line": _number(event.get("last_line"))}
            if event.get("field") in _REJECTION_FIELDS:
                clean["field"] = event["field"]
            if event.get("cause") in _REJECTION_CAUSES:
                clean["cause"] = event["cause"]
            rejections.append(clean)
        rows.append({"fragment": index, "structure": "table" if row.get("structure") == "table" else "text",
                     "status": row["status"] if row.get("status") in statuses else "other",
                     "windows": _number(row.get("windows")), "seconds": _number(row.get("seconds")),
                     "counts": {k: _number(row.get("counts", {}).get(k)) for k in COUNTERS
                                if k in row.get("counts", {})}, "rejections": rejections})
    return rows


def atomic_diagnostics(result):
    """Fixed counters/codes and run-local ordinal numbers, no source text or IDs."""
    metrics = result.get("metrics", {})
    counts = result.get("counts", {})
    mode = "assertions" if result.get("mode") == "assertions" else "slots"
    groups = ("metrics",) if mode == "assertions" else FACT_GROUPS
    return {"format": "mint-atomic-analysis/2", "mint": MINT_VERSION, "mode": mode,
            "scope": "all" if result.get("scope") == "all" else "sample",
            "category_counts": {g: sum(fact_in_group(f, g) for _, f in fact_rows(result))
                                for g in groups},
            "requires_expert_review": True, "cold_run": True,
            "counts": {k: _number(counts.get(k)) for k in COUNTERS},
            "total_seconds": _number(metrics.get("total_seconds")),
            "stages": safe_stage_metrics(metrics, (MODE_STAGES[mode],)),
            "fragment_diagnostics": _safe_fragment_diagnostics(result),
            "expert_review": None}

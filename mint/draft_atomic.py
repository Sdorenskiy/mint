"""Opt-in V3 experiment: full original scope -> literal candidates.

No obligation decisions, index writes, R-ID creation or Word generation.
Coordinates refer to parsed Markdown fragments, not raw Word byte offsets.
Mechanical validation is not semantic verification.
"""
from collections import Counter
import hashlib
import json
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .draft_progress import tracked
from .draft_target_analysis import _map_sources, _metric_pair, _verify_originals
from .draft_pilot_report import _number, safe_stage_metrics
from .template_draft import (DraftError, _candidate_budget, _json, _load_draft_sources,
                             _measure_draft)
from .version import MINT_VERSION

MAX_SAMPLE = 20
MAX_ITEMS = 12
STAGE = "atomic_extract"


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


METRIC_KEYS = ("metric_subject", "metric_value", "metric_unit")
COUNTERS = ("fragments_total", "fragments_selected", "fragments_attempted", "fragments_processed",
            "fragments_complete", "fragments_failed", "source_read_errors", "source_count",
            "invalid_range", "recovery_attempted", "recovery_windows", "recovery_added",
            "batch_error", "context_limit", "invalid_payload", "response_limit",
            "invalid_shape", "empty_fields",
            "invalid_field", "invalid_metric", "duplicate", "accepted",
            "empty_response", "partial_fragments")


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


def _validated_candidate(raw, span, parts=None):
    """Select numbered original lines; the model never generates the quotation."""
    try:
        item = Candidate.model_validate(raw, strict=True)
    except ValidationError:
        return None, "invalid_shape"
    parts = _line_parts(span["text"]) if parts is None else parts
    allowed = {p["n"]: p for p in parts}
    if (item.last < item.first or item.last - item.first >= 4
            or any(n not in allowed for n in range(item.first, item.last + 1))):
        return None, "invalid_range"
    start, end = allowed[item.first]["start"], allowed[item.last]["end"]
    quote = span["text"][start:end]
    if not quote.strip():
        return None, "invalid_range"
    fields = item.fields.model_dump(exclude_none=True)
    if not fields:
        return None, "empty_fields"
    table = span.get("table_context") or {}
    header = table.get("header", "")
    if header and (item.first != item.last or quote.strip() == header.strip()
                   or quote.strip() == table.get("separator", "").strip()
                   or not quote.strip().startswith("|")):
        return None, "invalid_range"
    if any(not v.strip() or len(v) > 600 or
           (v not in quote and not (k in ("metric_subject", "metric_unit") and v in header))
           for k, v in fields.items()):
        return None, "invalid_field"
    if any(k in fields for k in METRIC_KEYS):
        if (not all(k in fields for k in METRIC_KEYS)
                or not _metric_pair({"quote": quote, "table_context": table},
                                    *(fields[k] for k in METRIC_KEYS))):
            return None, "invalid_metric"
    return {"quote": quote, "start": start, "end": end,
            "first": item.first, "last": item.last, "fields": fields}, "accepted"


def _fact_key(fact):
    return fact["start"], fact["end"], tuple(sorted(fact["fields"].items()))


def _extract_window(cfg, span, parts, counts):
    payload = {"section": span["section"],
               "parts": [{"n": p["n"], "text": p["text"]} for p in parts]}
    if span.get("table_context"):
        payload["table_context"] = span["table_context"]
    if len(json.dumps(payload, ensure_ascii=False)) > _candidate_budget(cfg):
        counts["context_limit"] += 1
        return [], "context_limit", True
    try:
        reply = _json(cfg, STAGE, payload)
    except DraftError:
        counts["batch_error"] += 1
        return [], "batch_error", False
    if not isinstance(reply, dict) or set(reply) != {"items"} or not isinstance(reply["items"], list):
        counts["invalid_payload"] += 1
        return [], "invalid_payload", False
    items = reply["items"]
    limited = len(items) >= MAX_ITEMS
    if limited:
        counts["response_limit"] += 1
    facts, seen = [], set()
    partial = limited
    for raw in items[:MAX_ITEMS]:
        fact, status = _validated_candidate(raw, span, parts)
        if fact is None:
            counts[status] += 1
            partial = True
            continue
        key = _fact_key(fact)
        if key in seen:
            counts["duplicate"] += 1
            continue
        seen.add(key)
        facts.append(fact)
    return facts, "partial" if partial else "processed", limited


def _extract_fragment(cfg, span, counts):
    parts = _line_parts(span["text"])
    facts, status, limited = _extract_window(cfg, span, parts, counts)
    # Recover once with smaller disjoint windows when the original input or
    # output hits a limit. Keep all original candidates; never silently claim
    # completeness after splitting across a possible semantic boundary.
    if limited and len(parts) > 1:
        counts["recovery_attempted"] += 1
        seen = {_fact_key(fact) for fact in facts}
        middle = len(parts) // 2
        children = []
        for window in (parts[:middle], parts[middle:]):
            counts["recovery_windows"] += 1
            more, child_status, _ = _extract_window(cfg, span, window, counts)
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
    return group == "all" or bool(FACT_GROUPS.get(group, set()) & fact["fields"].keys())


@_measure_draft
def extract_atomic_sample(cfg, prepared, selected=None, progress=None):
    """Cold scan of all prepared A originals by default; bounded manual diagnostic."""
    spans = prepared["spans"]
    scope = "all" if selected is None else "sample"
    selected = list(spans) if selected is None else list(dict.fromkeys(selected))
    if not selected or (scope == "sample" and len(selected) > MAX_SAMPLE) or any(sid not in spans for sid in selected):
        raise ValueError("Invalid atomic scope")
    _verify_originals(cfg, prepared)
    emit = progress or (lambda *_: None)
    counts = Counter(fragments_total=len(spans), fragments_selected=len(selected),
                     source_count=len(prepared["hashes"]), source_read_errors=len(prepared["issues"]))
    result = []
    selected_set = set(selected)
    jobs = [span for sid, span in spans.items() if sid in selected_set]
    for span in tracked(emit, STAGE, jobs):
        counts["fragments_attempted"] += 1
        facts, status = _extract_fragment(cfg, span, counts)
        counts["fragments_processed"] += int(status in {"processed", "partial"})
        counts["fragments_complete"] += int(status == "processed")
        counts["fragments_failed"] += int(status not in {"processed", "partial"})
        for index, fact in enumerate(facts, 1):
            fact["id"] = span["id"] + "." + str(index)
        result.append({**span, "revision": prepared["revisions"][span["source"]],
                       "status": status, "facts": facts})
    _verify_originals(cfg, prepared)
    return {"format": "mint-atomic-sample/2", "scope": scope, "fragments": result,
            "counts": dict(counts), "requires_expert_review": True}


def atomic_diagnostics(result):
    """Only fixed numeric counters; no filenames, text, IDs, model or raw errors."""
    metrics = result.get("metrics", {})
    counts = result.get("counts", {})
    return {"format": "mint-atomic-analysis/2", "mint": MINT_VERSION,
            "scope": "all" if result.get("scope") == "all" else "sample",
            "category_counts": {g: sum(fact_in_group(f, g) for _, f in fact_rows(result))
                                for g in FACT_GROUPS},
            "requires_expert_review": True, "cold_run": True,
            "counts": {k: _number(counts.get(k)) for k in COUNTERS},
            "total_seconds": _number(metrics.get("total_seconds")),
            "stages": safe_stage_metrics(metrics, (STAGE,)),
            "expert_review": None}

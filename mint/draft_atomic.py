"""Opt-in V3 experiment: selected original fragments -> literal candidates.

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
    quote: str = Field(min_length=1, max_length=4000)
    fields: Slots


METRIC_KEYS = ("metric_subject", "metric_value", "metric_unit")
COUNTERS = ("fragments_selected", "fragments_processed", "source_read_errors",
            "batch_error", "context_limit", "invalid_payload", "response_limit",
            "invalid_shape", "invalid_quote", "ambiguous_quote", "empty_fields",
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


def _validated_candidate(raw, span):
    """Reject nonliteral/ambiguous references; never accept repaired content."""
    try:
        item = Candidate.model_validate(raw, strict=True)
    except ValidationError:
        return None, "invalid_shape"
    quote = item.quote
    text = span["text"]
    start = text.find(quote)
    if not quote.strip() or start < 0:
        return None, "invalid_quote"
    if text.find(quote, start + 1) >= 0:
        return None, "ambiguous_quote"
    fields = item.fields.model_dump(exclude_none=True)
    if not fields:
        return None, "empty_fields"
    table = span.get("table_context") or {}
    header = table.get("header", "")
    if any(not v.strip() or len(v) > 600 or
           (v not in quote and not (k in ("metric_subject", "metric_unit") and v in header))
           for k, v in fields.items()):
        return None, "invalid_field"
    if any(k in fields for k in METRIC_KEYS):
        if (not all(k in fields for k in METRIC_KEYS)
                or (header and ("\n" in quote or quote not in text.splitlines()
                                or not quote.strip().startswith("|") or quote == header))
                or not _metric_pair({"quote": quote, "table_context": table},
                                    *(fields[k] for k in METRIC_KEYS))):
            return None, "invalid_metric"
    return {"quote": quote, "start": start, "end": start + len(quote),
            "fields": fields}, "accepted"


def _extract_fragment(cfg, span, counts):
    payload = {"section": span["section"], "text": span["text"]}
    if span.get("table_context"):
        payload["table_context"] = span["table_context"]
    if len(json.dumps(payload, ensure_ascii=False)) > _candidate_budget(cfg):
        counts["context_limit"] += 1
        return [], "context_limit"
    try:
        reply = _json(cfg, STAGE, payload)
    except DraftError:
        counts["batch_error"] += 1
        return [], "batch_error"
    if not isinstance(reply, dict) or set(reply) != {"items"} or not isinstance(reply["items"], list):
        counts["invalid_payload"] += 1
        return [], "invalid_payload"
    items = reply["items"]
    limited = len(items) >= MAX_ITEMS
    if limited:
        counts["response_limit"] += 1
    if not items:
        counts["empty_response"] += 1
    facts, seen = [], set()
    partial = limited
    for raw in items[:MAX_ITEMS]:
        fact, status = _validated_candidate(raw, span)
        if fact is None:
            counts[status] += 1
            partial = True
            continue
        key = (fact["start"], fact["end"], tuple(sorted(fact["fields"].items())))
        if key in seen:
            counts["duplicate"] += 1
            continue
        seen.add(key)
        counts["accepted"] += 1
        facts.append(fact)
    counts["partial_fragments"] += int(partial)
    return facts, "partial" if partial else "processed"


@_measure_draft
def extract_atomic_sample(cfg, prepared, selected, progress=None):
    """Bounded, deliberately cold pilot; selected IDs only, no persistent cache."""
    selected = list(dict.fromkeys(selected))
    spans = prepared["spans"]
    if not 1 <= len(selected) <= MAX_SAMPLE or any(sid not in spans for sid in selected):
        raise ValueError("Invalid atomic sample")
    _verify_originals(cfg, prepared)
    emit = progress or (lambda *_: None)
    counts = Counter(fragments_selected=len(selected), source_read_errors=len(prepared["issues"]))
    result = []
    selected_set = set(selected)
    jobs = [span for sid, span in spans.items() if sid in selected_set]
    for span in tracked(emit, STAGE, jobs):
        facts, status = _extract_fragment(cfg, span, counts)
        counts["fragments_processed"] += int(status in {"processed", "partial"})
        for index, fact in enumerate(facts, 1):
            fact["id"] = span["id"] + "." + str(index)
        result.append({**span, "revision": prepared["revisions"][span["source"]],
                       "status": status, "facts": facts})
    _verify_originals(cfg, prepared)
    return {"format": "mint-atomic-sample/1", "fragments": result,
            "counts": dict(counts), "requires_expert_review": True}


def atomic_diagnostics(result):
    """Only fixed numeric counters; no filenames, text, IDs, model or raw errors."""
    metrics = result.get("metrics", {})
    counts = result.get("counts", {})
    return {"format": "mint-atomic-analysis/1", "mint": MINT_VERSION,
            "requires_expert_review": True, "cold_run": True,
            "counts": {k: _number(counts.get(k)) for k in COUNTERS},
            "total_seconds": _number(metrics.get("total_seconds")),
            "stages": safe_stage_metrics(metrics, (STAGE,)),
            "expert_review": None}

"""Read-only V2 review and strictly allowlisted diagnostic export."""
from collections import Counter
from math import isfinite

from .draft_registry import KINDS, SOURCE_ROLES
from .version import MINT_VERSION

DISPOSITIONS = frozenset({
    "model_covered", "external_proposal", "allocation_unresolved",
    "invalid_allocation_evidence", "invalid_allocation_actor", "open_question",
    "invalid_response", "invalid_proposal", "duplicate_proposal", "needs_review",
    "unsafe_text", "review_context_limit", "review_error", "review_incomplete",
    "out_of_section_proposal", "coverage_gap", "model_supported_candidates",
    "missing_response", "duplicate_response", "batch_error",
})
ALLOCATION_STATUSES = frozenset({
    "not_grouped", "no_state_evidence", "allocation_context_limit", "proposed",
    "explicit_uncertain", "unsupported_assignment", "invalid_response",
    "missing_response", "duplicate_response", "batch_error",
})
GROUP_STATUSES = frozenset({"grouped", "invalid_group", "missing_response",
                            "duplicate_response", "batch_error"})
ALLOCATION_CATEGORIES = frozenset({"target", "shared", "interaction", "other", "uncertain"})
ASSESSMENT_STATUSES = frozenset({"model_supported", "needs_review",
                                 "assessment_incomplete", "assessment_error"})
STAGES = ("extract", "registry_type", "function_group", "function_allocation",
          "requirement_derivation", "requirement_assessment", "pilot_coverage")
LEGACY_STAGES = ("layout", "extract", "scope", "rows", "fill", "check", "fixed")
EXTRACTION = ("fragments_total", "fragments_completed", "cache_hits", "cache_misses",
              "failed_fragments", "invalid_quote_fragments", "duplicate_quotes", "accepted_records")


def review_rows(result):
    """Every extracted record appears once; evidence use is not obligation coverage."""
    derivation = result.get("derivation", {})
    dispositions = result.get("section_dispositions", {})
    linked = set(result.get("used", ()))
    pending = {rid: key for key in ("cross_cutting_ids", "open_question_ids", "untyped_ids")
               for rid in derivation.get(key, ())}
    rows = []
    for record in result.get("requirements", ()):
        rid = record["id"]
        status = dispositions.get(rid, pending.get(rid, "context_only"))
        if status == "context_only" and rid in linked:
            status = "linked_evidence"
        rows.append({**record, "disposition": status, "linked": rid in linked})
    return rows


def _number(value):
    return value if type(value) in (int, float) and isfinite(value) and value >= 0 else 0


def safe_stage_metrics(metrics, stages=STAGES + LEGACY_STAGES):
    """A fixed allowlist; never export a raw metrics object or its arbitrary keys."""
    values = metrics.get("stages", {})
    return {key: {field: _number(values[key].get(field))
                  for field in ("llm_calls", "llm_seconds")}
            for key in stages if key in values}


def diagnostic_export(result):
    """Construct from explicit keys only; never pass arbitrary nested metrics/text."""
    rows = review_rows(result)
    metrics = result.get("metrics", {})
    diagnostics = metrics.get("diagnostics", {})
    extraction = diagnostics.get("extraction", {})
    allowed = DISPOSITIONS | {"cross_cutting_ids", "open_question_ids", "untyped_ids",
                              "context_only", "linked_evidence"}
    counts = Counter(row["disposition"] if row["disposition"] in allowed else "other"
                     for row in rows)
    analysis = result.get("analysis", {})
    allocations = analysis.get("allocations", {})
    def count_codes(values, allowed):
        return dict(Counter(value if isinstance(value, str) and value in allowed
                            else "other" for value in values))

    return {
        "format": "mint-v2-diagnostics/1",
        "mint": MINT_VERSION,
        "requires_expert_review": True,
        "records": len(rows),
        "linked_records": sum(row["linked"] for row in rows),
        "inserted_paragraphs": len(result.get("results", ())),
        "issue_count": len(result.get("issues", ())),
        "kind_counts": dict(Counter(row.get("kind") if row.get("kind") in KINDS else "other"
                                    for row in rows)),
        "role_counts": dict(Counter(row.get("source_role") if row.get("source_role") in SOURCE_ROLES else "other"
                                    for row in rows)),
        "disposition_counts": dict(counts),
        "grouping_status_counts": count_codes(analysis.get("grouping", {}).values(), GROUP_STATUSES),
        "allocation_status_counts": count_codes((row.get("status") for row in allocations.values()),
                                                ALLOCATION_STATUSES),
        "allocation_category_counts": count_codes((row.get("category") for row in allocations.values()),
                                                  ALLOCATION_CATEGORIES),
        "assessment_status_counts": count_codes((row.get("assessment") for row in
                                                 result.get("derivation", {}).get("requirements", [])),
                                                ASSESSMENT_STATUSES),
        "context_limited_groups": _number(diagnostics.get("function_allocation", {}).get("context_limited_groups")),
        "expanded_groups": _number(diagnostics.get("function_allocation", {}).get("expanded_groups")),
        "stage_cache_hits": {key: _number(diagnostics.get(key, {}).get("cache_hits"))
                             for key in ("registry_type", "function_group")},
        "total_seconds": _number(metrics.get("total_seconds")),
        "extraction": {key: _number(extraction.get(key)) for key in EXTRACTION},
        "source_read_errors": _number(diagnostics.get("pilot_section", {}).get("source_read_errors")),
        "repair_attempts": _number(diagnostics.get("pilot_section", {}).get("repair_attempts")),
        "repair_successes": _number(diagnostics.get("pilot_section", {}).get("repair_successes")),
        "repair_skipped_missing_evidence": _number(diagnostics.get("pilot_section", {}).get("repair_skipped_missing_evidence")),
        "stages": safe_stage_metrics(metrics, STAGES),
    }


def diagnostic_package(result, *, pilot, input_key, review=None):
    """One export for this generation only, with optional matching expert marks.

    No text, source IDs, filenames, model name, timestamps, fingerprints,
    raw diagnostics, original Word or saved review metadata leave this function.
    A saved review of the same inputs is insufficient: require the same run ID.
    """
    from .draft_review import fingerprint, summary
    from .draft_traceability import build_traceability, trace_counts

    metrics = result.get("metrics", {})
    if pilot:
        generation = diagnostic_export(result)
    else:
        generation = {
            "records": len(result.get("requirements", [])),
            "linked_records": len(result.get("used", ())),
            "output_fields": len(result.get("results", [])),
            "issue_count": len(result.get("issues", [])),
            "total_seconds": _number(metrics.get("total_seconds")),
            "stages": safe_stage_metrics(metrics, LEGACY_STAGES),
            "extraction": {key: _number(metrics.get("diagnostics", {}).get(
                "extraction", {}).get(key)) for key in EXTRACTION},
        }
    trace = trace_counts(build_traceability(result))
    expert = None
    meta = review.get("meta", {}) if review else {}
    run_id = metrics.get("run_id")
    if (isinstance(run_id, str) and run_id and meta.get("input_fingerprint") == fingerprint(input_key)
            and meta.get("metrics", {}).get("run_id") == run_id):
        expert = summary(review)
    return {
        "format": "mint-draft-analysis/1",
        "mint": MINT_VERSION,
        "mode": "v2" if pilot else "legacy",
        "generation": generation,
        "traceability": trace,
        "expert_review": expert,
        "requires_expert_review": True,
        "caveat": "Aggregate diagnostics only; not proof of semantic accuracy or source completeness.",
    }

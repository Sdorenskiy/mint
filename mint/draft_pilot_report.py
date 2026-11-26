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
            "scope_counts": {key: _number(result.get("scope_counts", {}).get(key))
                             for key in ("target", "shared", "interaction", "other", "uncertain")},
            "removed_examples": _number(result.get("removed_examples")),
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
        "traceability_basis": "original_generation",
        "expert_review": expert,
        "requires_expert_review": True,
        "caveat": "Aggregate diagnostics only; not proof of semantic accuracy or source completeness.",
    }


# The registry has no Word anchors yet. Export only aggregate codes and numbers.
TARGET_STAGES = ("target_section_map", "target_profile", "target_function_discovery", "target_dossier", "target_extract", "registry_type", "scope",
                 "target_allocation", "target_verify", "target_summary", "target_derivation",
                 "requirement_assessment", "target_coverage")
_TARGET_COUNTERS = {
    "profile_status": ("no_candidates", "model_error", "invalid_response", "no_functions", "partial", "found", "context_limit"),
    "wiki_status": ("disabled", "source_error", "no_candidates", "model_error", "invalid_response", "no_functions", "partial", "found"),
    "wiki_context": ("sources", "read_errors", "needs_with_context", "spans_supplied", "function_searches", "allocation_budget_limit", "allocation_no_candidates"),
    "allocation_retry": ("attempted", "recovered", "exhausted"),
    "applicability": ("model_supported", "needs_review", "proposed", "unresolved"),
    "implementation": ("model_supported", "proposed", "unknown"),
    "scope_selection": ("selected", "offered"),
    "preliminary_applicability": ("target", "shared", "interaction", "other", "uncertain"),
    "function_links": ("linked_records", "shared_records", "unlinked_records"),
    "section_roles": ("need", "interface", "metric", "architecture", "constraint", "business", "reference", "unknown"),
    "fragment_status": ("failed", "invalid_quote", "cached", "processed"),
    "decisions": ("proposed", "model_supported", "applicability_supported", "missing_evidence", "wrong_actor", "invalid_response",
                  "missing_response", "duplicate_response", "batch_error", "missing_metric_evidence", "allocation_context_limit",
                  "review_context_limit", "review_error", "needs_review", "reference_unresolved"),
    "changes": ("new", "change", "already_supported", "external", "unknown", "explicit"),
    "outcomes": ("new", "change", "already_supported", "external", "unknown", "explicit",
                 "context_only", "untyped", "open_question", "model_covered", "coverage_gap",
                 "awaiting_decomposition", "expert_excluded", "implementation_unknown", "applicability_supported",
                 "group_context_limit", "model_supported_candidates", "missing_metric_evidence",
                 "missing_evidence", "wrong_actor", "invalid_response", "missing_response", "allocation_context_limit",
                 "duplicate_response", "batch_error", "review_context_limit", "review_error", "needs_review", "reference_unresolved"),
    "record_kinds": tuple(sorted(KINDS)),
    "index_revisions": ("missing", "unverified", "matched", "stale"),
    "retrieval": ("queries", "dense_queries", "reranked_queries", "low_confidence",
                  "matched_spans", "no_match", "no_index", "fallback_spans", "cache_hits"),
    "profile_retrieval": ("queries", "dense_queries", "reranked_queries", "low_confidence",
                          "matched_spans", "no_match", "no_index", "fallback_spans", "cache_hits"),
    "references": ("resolved", "ambiguous", "missing", "outside_scope", "unidentified_document", "unsupported_range"),
    "reference_gaps": ("ambiguous", "missing", "outside_scope", "unidentified_document", "unsupported_range", "cycle", "depth_limit", "budget_limit"),
    "summaries": ("draft", "invalid", "error", "context_limit"),
    "review_scope": ("included", "excluded", "notes"),
    "verification": ("batches", "cache_hits", "invalid_verdicts"),
    "allocation_validation": ("category", "change", "refs", "reason", "function", "function_name"),
    "dossiers": ("searches", "hybrid_hits", "fallback_hits", "reference_gaps", "limited_searches", "batch_errors",
                 "invalid_quotes", "facts", "supplemental_records", "cache_hits", "not_searched", "found",
                 "found_partial", "not_found", "context_limit", "error", "unresolved_facts", "covered_facts"),
    "proposal_kinds": ("functional", "interface", "metric", "constraint"),
    "proposal_assessments": tuple(sorted(ASSESSMENT_STATUSES)),
}


def target_registry_export(prepared, result):
    """Single safe file for STOP-1; never include input keys, profile, texts or raw stats."""
    data = result.get("diagnostics", {})
    preparation = prepared.get("metrics", {})
    analysis = result.get("metrics", {})
    counters = {key: {code: _number(data.get(key, {}).get(code)) for code in allowed}
                for key, allowed in _TARGET_COUNTERS.items()}
    counts = {key: _number(data.get(key)) for key in
              ("profile_functions", "groups", "verified_metrics", "source_read_errors")}
    extraction = analysis.get("diagnostics", {}).get("extraction", {})
    return {"format": "mint-draft-analysis/1", "mint": MINT_VERSION,
            "mode": "target_registry", "requires_expert_review": True,
            "phase": "collected" if result.get("phase") == "collected" else "decomposed",
            "counts": counts, "diagnostics": counters,
            "extraction": {key: _number(extraction.get(key)) for key in EXTRACTION},
            "preparation": {"total_seconds": _number(preparation.get("total_seconds")),
                            "stages": safe_stage_metrics(preparation, TARGET_STAGES)},
            "analysis": {"total_seconds": _number(analysis.get("total_seconds")),
                         "stages": safe_stage_metrics(analysis, TARGET_STAGES)},
            "expert_review": None,
            "caveat": "Model processing indicators only. No expert approval, semantic recall or Word coverage."}

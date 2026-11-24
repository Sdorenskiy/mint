"""Classify who a requirement obligates, once per draft.

Keep all extracted quotes for audit/traceability. Only target/shared obligations
may support generated target-system claims. External interactions remain context.
"""
from collections import Counter

from .template_draft import (MAX_CHARS, DraftError, _batches, _json, _records,
                             _record_draft_diagnostic, _text)

CATEGORIES = {"target", "shared", "interaction", "other", "uncertain"}
DRAFTABLE = {"target", "shared"}


def category_of(requirement):
    return requirement.get("applicability", {}).get("category", "uncertain")


def partition(requirements, context=None):
    """Older direct callers with no confirmed context remain backward compatible."""
    if context is None:
        return dict(requirements), {}
    direct = {k: v for k, v in requirements.items() if category_of(v) in DRAFTABLE}
    external = {k: v for k, v in requirements.items() if category_of(v) == "interaction"}
    return direct, external


def classify(cfg, requirements, context, issues, emit):
    """Use a single categorization stage, batched over all extracted requirements.

    An incomplete response is *uncertain*, never treated as target-specific.
    No hardcoded list of platform names, and no per-section classification calls.
    """
    if context is None or not requirements:
        return requirements
    normalized = {}
    decisions = {rid: "missing_response" for rid in requirements}
    groups = failed_groups = unexpected_rows = duplicate_rows = 0
    for rid, item in requirements.items():
        normalized[rid] = {**item, "applicability": {
            "category": "uncertain", "actor": "", "reason": "Применимость не подтверждена"}}
    for i, batch in enumerate(_batches(list(requirements.values()), lambda r: r["quote"],
                                       size=MAX_CHARS * 2), 1):
        emit("scope", i)
        groups += 1
        allowed = {r["id"]: r for r in batch}
        seen = set()
        try:
            rows = _records(_json(cfg, "scope", {"context": context, "requirements": batch}), "items")
        except DraftError:
            failed_groups += 1
            for rid in allowed:
                decisions[rid] = "batch_error"
            issues.append(f"Не удалось оценить применимость группы требований {i}; проверьте вручную.")
            continue
        for row in rows:
            rid, category = _text(row, "id"), _text(row, "category").lower()
            if rid not in allowed:
                unexpected_rows += 1
                continue
            if rid in seen:
                duplicate_rows += 1
            seen.add(rid)
            # Preserve the existing accepted classification; record malformed rows
            # without overriding an earlier valid decision.
            def rejected(code):
                if decisions[rid] not in {"classified", "explicit_uncertain"}:
                    decisions[rid] = code

            if category not in CATEGORIES:
                rejected("invalid_category")
                continue
            actor, reason = _text(row, "actor")[:180], _text(row, "reason")[:500]
            if not reason and category != "uncertain":
                # A confident classification must have a human-reviewable reason.
                rejected("missing_reason")
                continue
            if category in {"target", "shared", "interaction"} and not actor:
                # Without an identified obligated party, no confident assignment.
                rejected("missing_actor")
                continue
            decisions[rid] = "explicit_uncertain" if category == "uncertain" else "classified"
            normalized[rid]["applicability"] = {
                "category": category, "actor": actor,
                "reason": reason or "Недостаточно сведений для определения применимости"}
    _record_draft_diagnostic("scope", {
        "groups": groups, "failed_groups": failed_groups,
        "unexpected_rows": unexpected_rows, "duplicate_rows": duplicate_rows,
        "decision_counts": dict(Counter(decisions.values())),
        "decisions": decisions,
    })
    uncertain = sum(category_of(v) == "uncertain" for v in normalized.values())
    if uncertain:
        issues.append(f"Применимость {uncertain} требований не определена. Они не включены автоматически.")
    return normalized

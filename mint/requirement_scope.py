"""Classify who a requirement obligates, once per draft.

Keep all extracted quotes for audit/traceability. Only target/shared obligations
may support generated target-system claims. External interactions remain context.
"""
from .template_draft import MAX_CHARS, DraftError, _batches, _json, _records, _text

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
    for rid, item in requirements.items():
        normalized[rid] = {**item, "applicability": {
            "category": "uncertain", "actor": "", "reason": "Применимость не подтверждена"}}
    for i, batch in enumerate(_batches(list(requirements.values()), lambda r: r["quote"],
                                       size=MAX_CHARS * 2), 1):
        emit("scope", i)
        allowed = {r["id"]: r for r in batch}
        try:
            rows = _records(_json(cfg, "scope", {"context": context, "requirements": batch}), "items")
        except DraftError:
            issues.append(f"Не удалось оценить применимость группы требований {i}; проверьте вручную.")
            continue
        for row in rows:
            rid, category = _text(row, "id"), _text(row, "category").lower()
            if rid not in allowed or category not in CATEGORIES:
                continue
            actor, reason = _text(row, "actor")[:180], _text(row, "reason")[:500]
            if not reason and category != "uncertain":
                # A confident classification must have a human-reviewable reason.
                continue
            if category in {"target", "shared", "interaction"} and not actor:
                # Without an identified obligated party, no confident assignment.
                continue
            normalized[rid]["applicability"] = {
                "category": category, "actor": actor,
                "reason": reason or "Недостаточно сведений для определения применимости"}
    uncertain = sum(category_of(v) == "uncertain" for v in normalized.values())
    if uncertain:
        issues.append(f"Применимость {uncertain} требований не определена. Они не включены автоматически.")
    return normalized

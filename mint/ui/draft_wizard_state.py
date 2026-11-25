"""Session-only navigation for the V2 registry wizard (no model calls)."""

TARGET_KEYS = (
    "target_registry_prepared", "target_registry_preview", "target_registry_collected", "target_registry_result",
    "target_full_workbook", "target_registry_profile_draft", "target_registry_review_draft",
)


def clear_target(session):
    for key in TARGET_KEYS:
        session.pop(key, None)
    session.pop("target_registry_key", None)


def sync_target(session, key):
    """Only changed inputs invalidate the downstream target analysis."""
    if session.get("target_registry_key") != key:
        clear_target(session)
        session["target_registry_key"] = key


def apply_materials(session, materials):
    """Commit explicit material choices, not incidental widget reruns."""
    prior = session.get("draft_wizard_materials")
    changed = prior is None or prior["signature"] != materials["signature"]
    session["draft_wizard_materials"] = materials
    if changed:
        session.pop("draft_wizard_context", None)
        clear_target(session)
    return changed


def reachable_step(session, *, context_ready):
    """The last reachable step is based on actual artifacts, never on a click."""
    if not session.get("draft_wizard_materials"):
        return 1
    if not context_ready or not session.get("target_registry_collected"):
        return 2
    if not session.get("target_registry_result"):
        return 3
    return 4


def clamp_step(session, *, context_ready):
    step = max(1, min(session.get("draft_wizard_step", 1),
                      reachable_step(session, context_ready=context_ready)))
    session["draft_wizard_step"] = step
    return step

"""Offline checks for session navigation and invalidation, without Streamlit."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint.ui.draft_wizard_state import apply_materials, clamp_step, reachable_step, sync_target


def test_navigation():
    session = {"draft_wizard_step": 4}
    assert clamp_step(session, context_ready=False) == 1
    original = {"signature": ("fixture", "original"), "raw": b"template"}
    assert apply_materials(session, original)
    assert reachable_step(session, context_ready=False) == 2
    session["draft_wizard_context"] = {"confirmed": {"target": "Fixture"}}
    sync_target(session, "first")
    session.update(target_registry_prepared={"profile": []},
                   target_registry_collected=("profile", {"phase": "collected"}),
                   target_registry_review_draft={"selected": ["R1"]})
    assert reachable_step(session, context_ready=True) == 3
    session["target_registry_result"] = ("profile", {"phase": "decomposed"})
    assert reachable_step(session, context_ready=True) == 4
    session["draft_wizard_step"] = 2
    assert clamp_step(session, context_ready=True) == 2
    assert not apply_materials(session, dict(original))
    sync_target(session, "first")
    assert session["target_registry_result"][1]["phase"] == "decomposed"
    assert session["target_registry_review_draft"]["selected"] == ["R1"]
    assert apply_materials(session, {**original, "signature": ("fixture", "changed")})
    assert "target_registry_collected" not in session
    assert "target_registry_result" not in session
    assert "target_registry_review_draft" not in session
    assert "draft_wizard_context" not in session
    sync_target(session, "second")
    session["target_registry_collected"] = ("profile", {})
    sync_target(session, "changed context")
    assert "target_registry_collected" not in session


if __name__ == "__main__":
    test_navigation()
    print("ИТОГ: wizard navigation, unchanged materials, downstream invalidation")

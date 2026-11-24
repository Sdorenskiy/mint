"""Offline tests for V2 refinement, including rejected commitments."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mint import draft_derivation as derivation
from mint import template_draft as draft
from mint.prompts import default_prompts
from test_draft_function_analysis import CFG, CONTEXT, records


def analysis_result():
    return {
        "allocations": {
            "R1": {"status": "proposed", "category": "target", "actor": CONTEXT["target"],
                   "reason": "Notifications", "state_refs": ["R4"]},
            "R2": {"status": "proposed", "category": "target", "actor": CONTEXT["target"],
                   "reason": "Notifications", "state_refs": ["R4"]},
            "R3": {"status": "proposed", "category": "other", "actor": "Locker Inventory",
                   "reason": "External duty", "state_refs": ["R5"]}},
        "cross_cutting_ids": ["R6"], "open_question_ids": ["R7"], "untyped_ids": ["R8"],
    }


def item(**changes):
    result = {"text": "Reservation Desk must send confirmation to the visitor.",
              "actor": CONTEXT["target"], "mode": "derived", "reason": "Need and role",
              "need_refs": ["R1"], "state_refs": ["R4"], "constraint_refs": []}
    result.update(changes)
    return result


def run(reply, assessment=None, analysis=None):
    @draft._measure_draft
    def measured():
        return derivation.derive_requirements(CFG, records(), analysis or analysis_result(),
                                             CONTEXT, lambda *_: None)

    def model(_cfg, stage, payload):
        if stage == "requirement_assessment":
            assert {r["id"] for r in payload["evidence"]} == {"R1", "R4"}
            if isinstance(assessment, Exception):
                raise assessment
            return assessment if assessment is not None else {
                "supported": True, "correct_actor": True, "no_new_decisions": True,
                "reason": "Both sources support the refinement"}
        assert stage == "requirement_derivation"
        rid = payload["items"][0]["id"]
        assert rid != "R3"
        assert payload["constraints"] == []
        if rid == "R2":
            return {"items": [{"id": rid, "status": "open_question",
                               "question": "Which rejection notification is required?"}]}
        return reply

    with patch.object(derivation, "_json", side_effect=model), patch(
            "mint.draft_function_analysis._json", side_effect=model):
        return measured()


def response(*items):
    return {"items": [{"id": "R1", "status": "proposed", "requirements": list(items)}]}


def test_positive_and_open_items():
    result = run(response(item(), item(text="Reservation Desk must notify the visitor of confirmation.")))
    assert [r["id"] for r in result["requirements"]] == ["P1", "P2"]
    assert all(r["assessment"] == "model_supported" for r in result["requirements"])
    assert result["dispositions"] == {"R1": "model_supported_candidates",
                                     "R2": "open_question", "R3": "external_proposal"}
    assert result["generated_questions"][0]["need_id"] == "R2"
    assert result["cross_cutting_ids"] == ["R6"]
    assert result["open_question_ids"] == ["R7"]
    assert result["untyped_ids"] == ["R8"]


def test_structural_rejection():
    for change in ({"text": "Send confirmation within 30 seconds."},
                   {"actor": "Locker Inventory"}, {"state_refs": ["R5"]},
                   {"state_refs": []}, {"need_refs": ["R3"]},
                   {"constraint_refs": ["R6"]}, {"mode": "guess"}):
        result = run(response(item(**change)))
        assert not result["requirements"]
        assert result["dispositions"]["R1"] == "invalid_proposal"
    assert run(response(item(), item()))["dispositions"]["R1"] == "duplicate_proposal"
    assert run({"items": []})["dispositions"]["R1"] == "missing_response"
    result = run({"items": response(item())["items"] * 2})
    assert result["dispositions"]["R1"] == "duplicate_response"
    assert not result["requirements"]
    stale = analysis_result()
    stale["allocations"]["R1"]["state_refs"] = ["R999"]
    assert run(response(item()), analysis=stale)["dispositions"]["R1"] == "invalid_allocation_evidence"


def test_assessment_does_not_approve_uncertain_claims():
    for verdict, expected in (
        ({"supported": True, "correct_actor": False, "no_new_decisions": True}, "needs_review"),
        ({"supported": "true", "correct_actor": True, "no_new_decisions": True,
          "reason": "Not a boolean"}, "assessment_incomplete"),
        ({"supported": True, "correct_actor": True, "no_new_decisions": True}, "assessment_incomplete"),
        (draft.DraftError("timeout"), "assessment_error"),
    ):
        result = run(response(item()), verdict)
        assert result["requirements"][0]["assessment"] == expected
        assert result["dispositions"]["R1"] == "needs_review"


def test_prompts():
    for lang in ("ru", "en"):
        prompts = default_prompts(lang)
        assert all(k in prompts["draft_requirement_derivation"]
                   for k in ("need_refs", "state_refs", "constraint_refs", "open_question", "derived"))
        assert all(k in prompts["draft_requirement_assessment"]
                   for k in ("supported", "correct_actor", "no_new_decisions", "reason"))


if __name__ == "__main__":
    test_positive_and_open_items()
    test_structural_rejection()
    test_assessment_does_not_approve_uncertain_claims()
    test_prompts()
    print("ИТОГ: source-linked refinement, malformed decisions and assessment uncertainty")

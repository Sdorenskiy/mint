"""Offline functional analysis regressions using the V2 registry contract."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import draft_function_analysis as analysis
from mint import template_draft as draft
from mint.prompts import default_prompts

CFG = SimpleNamespace(max_tokens=1800, llm_context_tokens=12000, chars_per_token=2.5)
CONTEXT = {"target": "Reservation Desk", "objective": "Locker reservation",
           "scope": "Visitor notification", "participants": "Locker Inventory"}


def records():
    rows = [
        ("functional", "Visitors must receive confirmation of their reservation.", "need"),
        ("functional", "Visitors must be notified when a reservation is rejected.", "need"),
        ("functional", "The inventory service must allocate lockers.", "need"),
        ("current_state", "Reservation Desk owns visitor notifications.", "architecture"),
        ("current_state", "Locker Inventory owns locker allocation.", "architecture"),
        ("nonfunctional", "All reservation services must log rejected reservations.", "need"),
        ("open_question", "The confirmation timeout is to be agreed.", "need"),
        ("uncertain", "A separate condition might apply.", "unspecified"),
        ("non_requirement", "4.1 Reservations .... 5", "need"),
    ]
    return {f"R{i}": {"id": f"R{i}", "source": role + ".md", "section": "Synthetic",
                      "quote": quote, "kind": kind, "source_role": role,
                      "typing_status": ("explicit_uncertain" if kind == "uncertain" else
                                        "structural" if kind == "non_requirement" else "classified")}
            for i, (kind, quote, role) in enumerate(rows, 1)}


def run(rows):
    @draft._measure_draft
    def measured():
        return analysis.analyze_functions(CFG, rows, CONTEXT, lambda *_: None)
    return measured()


def test_group_and_allocate():
    def model(_cfg, stage, payload):
        ids = [r["id"] for r in payload["items"]]
        if stage == "function_group":
            assert ids == ["R1", "R2", "R3"]
            # Reverse model response order; source order must remain stable.
            return {"items": [{"id": rid, "group": "R1" if rid != "R3" else "R3"}
                              for rid in reversed(ids)]}
        assert stage == "function_allocation"
        assert {r["id"] for r in payload["current_state"]} == {"R4", "R5"}
        assert [r["id"] for r in payload["constraints"]] == ["R6"]
        assert [r["id"] for r in payload["open_questions"]] == ["R7"]
        return {"items": [
            {"id": rid, "category": "other" if rid == "R3" else "target",
             "actor": "Locker Inventory" if rid == "R3" else "Reservation Desk",
             "reason": "Linked fictional responsibility",
             "state_refs": ["R5" if rid == "R3" else "R4"]} for rid in ids
        ]}
    data = records()
    with patch.object(analysis, "_json", side_effect=model):
        result = run(data)
    assert [g["requirement_ids"] for g in result["groups"]] == [["R1", "R2"], ["R3"]]
    assert result["allocations"]["R1"]["state_refs"] == ["R4"]
    assert result["allocations"]["R3"]["category"] == "other"
    assert all(r["status"] == "proposed" for r in result["allocations"].values())
    assert result["cross_cutting_ids"] == ["R6"]
    assert result["open_question_ids"] == ["R7"]
    assert result["untyped_ids"] == ["R8"]
    assert "R9" not in result["grouping"]
    assert data == records()
    assert result["metrics"]["diagnostics"]["function_allocation"]["status_counts"] == {"proposed": 3}


def test_invalid_responses_and_missing_state():
    data = records()
    def model(_cfg, stage, payload):
        if stage == "function_group":
            return {"items": [{"id": "R1", "group": "R1"},
                              {"id": "R2", "group": "R99"},
                              {"id": "R3", "group": "R3"},
                              {"id": "R3", "group": "R3"}]}
        return {"items": [{"id": "R1", "category": "target", "actor": "Locker Inventory",
                           "reason": "Wrong actor", "state_refs": ["R5"]}]}
    with patch.object(analysis, "_json", side_effect=model):
        result = run(data)
    assert result["grouping"] == {"R1": "grouped", "R2": "invalid_group", "R3": "duplicate_response"}
    assert result["allocations"]["R1"]["status"] == "unsupported_assignment"
    assert all(row["category"] == "uncertain" for row in result["allocations"].values())
    for refs in (["R999"], ["R6"], ["R4", "R4"], "R4", []):
        def bad_refs(_cfg, stage, payload):
            if stage == "function_group":
                return {"items": [{"id": r["id"], "group": "R1"} for r in payload["items"]]}
            return {"items": [{"id": "R1", "category": "target", "actor": CONTEXT["target"],
                               "reason": "Bad reference", "state_refs": refs}]}
        with patch.object(analysis, "_json", side_effect=bad_refs):
            result = run(data)
        assert result["allocations"]["R1"]["status"] in {"invalid_response", "unsupported_assignment"}
        assert result["allocations"]["R2"]["status"] == "missing_response"
    no_state = {rid: row for rid, row in data.items() if row["kind"] != "current_state"}
    with patch.object(analysis, "_json", return_value={
        "items": [{"id": rid, "group": "R1"} for rid in ("R1", "R2", "R3")]
    }) as llm:
        result = run(no_state)
    assert llm.call_count == 1
    assert all(row["status"] == "no_state_evidence" for row in result["allocations"].values())
    with patch.object(analysis, "_json", side_effect=draft.DraftError("timeout")):
        result = run(data)
    assert set(result["grouping"].values()) == {"batch_error"}
    assert len(result["allocations"]) == 3 and not result["groups"]


def test_prompt_contract():
    for lang in ("ru", "en"):
        prompts = default_prompts(lang)
        assert '"group"' in prompts["draft_function_group"]
        assert all(key in prompts["draft_function_allocation"]
                   for key in ("state_refs", "category", "actor", "reason", *analysis.CATEGORIES))


if __name__ == "__main__":
    test_group_and_allocate()
    test_invalid_responses_and_missing_state()
    test_prompt_contract()
    print("ИТОГ: functional grouping, evidence-linked proposals and explicit unresolved decisions")

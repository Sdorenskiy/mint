"""Synthetic offline regressions for the function-scoped registry view."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint.ui.draft_review_view import (review_view, evidence_rows, review_snapshot, load_review_snapshot,
                                       update_review_selection, review_request_export)


def fixture():
    records = {f"R{i}": {"id": f"R{i}", "source": "source.md", "section": "1",
                           "quote": f"Synthetic requirement {i}", "kind": "functional"}
               for i in range(1, 10)}
    records["R9"]["kind"] = "uncertain"
    records["R8"]["kind"] = "definition"
    decisions = {
        "R1": {"function": "C1", "status": "model_supported", "change": "new",
               "state_refs": ["F1", "F2"], "reference_refs": ["F1"], "dossier_refs": ["F2"]},
        "R2": {"function": "C2", "status": "model_supported", "change": "new"},
        "R3": {"function": "C1", "status": "applicability_supported", "change": "unknown"},
        "R4": {"function": "system_wide", "status": "model_supported", "change": "explicit"},
        "R5": {"status": "missing_evidence", "change": "unknown"},
        "R6": {"status": "wrong_actor", "change": "unknown"},
        "R7": {"function": "C1", "status": "model_supported", "change": "already_supported"},
    }
    evidence = {"F1": {"source": "source.md", "section": "2", "quote": "Same passage"},
                "F2": {"source": "source.md", "section": "2", "quote": "Same passage"}}
    result = {"requirements": records, "decisions": decisions,
              "groups": [{"id": "G1", "function": "Load", "requirement_ids": ["R1", "R3", "R7"]},
                         {"id": "G2", "function": "Store", "requirement_ids": ["R2"]},
                         {"id": "G3", "function": "System", "requirement_ids": ["R4"]}],
              "approved_profile": [{"id": "C1", "name": "Load"}, {"id": "C2", "name": "Store"}],
              "selected_functions": ["C1"], "function_links": {"R1": ["C1", "C2"], "R2": ["C1", "C2"], "R5": ["C1"]},
              "state_evidence": evidence, "linked_by_need": {"R1": {"items": [{"id": "F1", **evidence["F1"]}]}},
              "metrics_registry": {}, "dossiers": {}, "diagnostics": {}, "dispositions": {}, "issues": [], "questions": []}
    return result


def test_scope():
    result = fixture()
    before = copy.deepcopy(result)
    view = review_view(result)
    assert list(view["sections"]) == ["C1"]
    assert view["sections"]["C1"][0]["ids"] == ["R1", "R3", "R7"]
    assert view["sections"]["C1"][0]["ready"] == ["R1"]
    assert view["sections"]["C1"][0]["context"] == ["R7"]
    assert view["cross"][0]["ready"] == ["R4"]
    assert view["outside"][0]["ids"] == ["R2"]
    assert view["candidates"] == ["R5"]
    assert view["unallocated"] == ["R6", "R9"]
    assert result == before
    result["selected_functions"] = []
    empty = review_view(result)
    assert not empty["sections"] and len(empty["outside"]) == 2
    result["selected_functions"] = ["C1", "C2"]
    both = review_view(result)
    assert [r for groups in both["sections"].values() for g in groups for r in g["ids"]] == ["R1", "R3", "R7", "R2"]
    assert not both["outside"]


def test_review_selection_and_requests():
    ready = ["R1", "R2", "R3"]
    assert update_review_selection(ready, ["R1", "R3", "R99"], ["R1", "R2"], ["R2", "R99"]) == ["R2", "R3"]
    assert update_review_selection(ready, ["R2", "R3"], ["R3"], []) == ["R2"]
    result = fixture()
    before = copy.deepcopy(result)
    exported = json.loads(review_request_export(result, {"R2": "C1", "R5": "C1", "R6": "C1",
                                                         "R1": "C1", "R9": "C2", "R99": "C1"}))
    assert exported["requires_verification"] is True
    assert [r["requirement_id"] for r in exported["requests"]] == ["R2", "R5", "R6"]
    assert exported["requests"][0]["quote"] == result["requirements"]["R2"]["quote"]
    assert result == before


def test_evidence_and_snapshot():
    result = fixture()
    prepared = {"context": {"target": "Fixture"}, "spans": {}, "secret": "not exported"}
    rows = evidence_rows("R1", prepared, result)
    assert len(rows) == 2 and rows[1]["ids"] == ["F1", "F2"]
    assert set(rows[1]["roles"]) == {"state", "reference", "dossier"}
    result["state_evidence"]["F2"]["table_context"] = {"occurrence": 2}
    assert len(evidence_rows("R1", prepared, result)) == 3
    raw = review_snapshot(prepared, result)
    assert b"not exported" not in raw and b"input_identity" not in raw
    loaded_prepared, loaded = load_review_snapshot(raw)
    assert loaded == result and loaded_prepared["context"] == prepared["context"]
    assert review_view(loaded) == review_view(result)
    for bad in (b"", b"[]", b'{"format":"unknown"}'):
        try:
            load_review_snapshot(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid snapshot accepted")


if __name__ == "__main__":
    test_scope()
    test_review_selection_and_requests()
    test_evidence_and_snapshot()
    print("OK: selected-function view, independent cross-cutting/candidate buckets, evidence deduplication, inert snapshot")

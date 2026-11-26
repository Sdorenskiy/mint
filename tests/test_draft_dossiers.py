"""Synthetic regression checks for additive retrieval and private expert export."""
import json
import sys
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import draft_target_analysis as target
from mint import draft_function_analysis as function
from mint.draft_dossiers import collect_dossiers, merge_dossier_quotes, summarize_dossiers, FACETS
from mint.draft_derivation import _assessment_verdict
from mint.draft_references import ReferenceMap
from mint.draft_registry_workbook import registry_workbook, regression_snapshot, compare_registries
from mint.draft_pilot_report import target_registry_export
from mint.i18n import use_lang
from openpyxl import load_workbook


def config(tmp):
    return SimpleNamespace(kb_path=Path(tmp) / "kb", log_path=Path(tmp) / "logs",
                           llm_model="test", max_tokens=1800, llm_context_tokens=12000, chars_per_token=2.5)


def test_additive_and_privacy():
    docs = [("a.md", "# 1 Need\nExisting duty.\nMessage categories: letters and numbers."),
            ("b.md", "# 2 Objective\nRate: 15 messages per second.")]
    spans, _ = target._map_sources(docs, {})
    refs = ReferenceMap(docs, spans)
    profile = {"C1": {"id": "C1", "name": "Messaging", "description": "Exchange", "refs": ["F1"]}}
    evidence = SimpleNamespace(spans=spans, find=lambda *a, **k: ["F1", "F2"])
    calls = []
    def model(cfg, stage, payload):
        calls.append(stage)
        rows = []
        if "data_categories" in payload["facets"]:
            rows = [{"span_id": "F1", "facet": "data_categories", "quote": "Message categories: letters and numbers."},
                    {"span_id": "F1", "facet": "data_categories", "quote": "invented"},
                    {"span_id": "F999", "facet": "data_categories", "quote": "foreign"}]
        if "performance" in payload["facets"]:
            rows = [{"span_id": "F2", "facet": "performance", "quote": "Rate: 15 messages per second."}]
        return {"items": rows}
    with TemporaryDirectory() as tmp, use_lang("en"):
        cfg = config(tmp)
        dossiers, counts = collect_dossiers(cfg, evidence, refs, profile, {"target": "Relay"}, lambda *_: None, model)
        assert counts["invalid_quotes"] == 2
        assert dossiers["C1"]["facets"]["data_categories"]["status"] == "found_partial"
        assert dossiers["C1"]["facets"]["performance"]["status"] == "found"
        assert set(dossiers["C1"]["facets"]) == set(FACETS)
        initial = {"id": "R1", "source": "a.md", "section": "1 Need", "quote": "Existing duty.",
                   "source_spans": []}
        records = {"R1": initial}
        assert merge_dossier_quotes(records, dossiers, spans, docs) == 2
        assert records["R1"] is initial and initial["quote"] == "Existing duty."
        assert merge_dossier_quotes(records, dossiers, spans, docs) == 0
        assert len(records) == 3
        counts2 = summarize_dossiers(dossiers, {}, {}, [])
        assert counts2["unresolved_facts"] == 2
        calls.clear()
        _, cached = collect_dossiers(cfg, evidence, refs, profile, {"target": "Relay"}, lambda *_: None, model)
        assert cached["cache_hits"] == 5 and len(calls) == 1
        safe = target_registry_export({}, {"diagnostics": {"dossiers": dict(counts)}})
        assert "letters" not in json.dumps(safe) and "foreign" not in json.dumps(safe)
        safe_priority = target_registry_export({}, {"diagnostics": {"dossier_priority":
            {"data_categories_found_partial": 1, "security_not_found": 1, "private source": 9}}})
        assert safe_priority["diagnostics"]["dossier_priority"]["data_categories_found_partial"] == 1
        assert safe_priority["diagnostics"]["dossier_priority"]["security_not_found"] == 1
        assert "private source" not in json.dumps(safe_priority)


def test_strict_quality_and_batch():
    good = {"supported": True, "correct_actor": True, "no_new_decisions": True, "reason": "ok"}
    assert _assessment_verdict({}, good) == "model_supported"
    assert _assessment_verdict({"quality_gate": True}, good) == "assessment_incomplete"
    strict = {**good, "complete": True, "unambiguous": True, "verifiable": True}
    assert _assessment_verdict({"quality_gate": True}, strict) == "model_supported"
    assert _assessment_verdict({"quality_gate": True}, {**strict, "complete": False}) == "needs_review"
    with TemporaryDirectory() as tmp:
        cfg = config(tmp)
        records = {"R" + str(i): {"id": "R" + str(i), "source": "a.md", "section": "A", "quote": "duty",
                                   "kind": "functional", "source_role": "need"} for i in range(1, 5)}
        decisions = {rid: {"status": "proposed", "state_refs": []} for rid in records}
        yes = {"correct_actor": True, "change_supported": True, "conditions_preserved": True, "reason": "ok"}
        items = [{"id": rid, **yes} for rid in ("R1", "R2", "R2", "R3", "R99")]
        with patch.object(function, "_json", return_value={"items": items}) as ask:
            stats = target._verify_decisions(cfg, decisions, records, {}, {"target": "Relay"}, lambda *_: None)
            assert ask.call_count == 1 and stats["batches"] == 1
        assert decisions["R1"]["status"] == decisions["R3"]["status"] == "model_supported"
        assert decisions["R2"]["status"] == decisions["R4"]["status"] == "needs_review"


def test_workbook_and_comparison():
    prepared = {"hashes": {"a.md": "hash"}, "context": {"target": "Relay"}, "roles": {}}
    source = {"id": "R1", "source": "a.md", "section": "A", "quote": "=SUM(1,2)", "kind": "functional",
              "source_spans": [{"source": "a.md", "section": "A", "fragment": 1, "revision": "mdhash", "quote": "=SUM(1,2)"}]}
    proposal = {"id": "P1", "text": "=HYPERLINK(\"https://invalid.example\")", "actor": "Relay", "kind": "functional",
                "assessment": "model_supported", "group": "G1", "need_refs": ["R1"], "state_refs": [],
                "constraint_refs": [], "reason": "synthetic"}
    result = {"requirements": {"R1": source}, "state_evidence": {}, "proposals": [proposal],
              "groups": [{"id": "G1", "function": "Messaging"}], "decisions": {},
              "dispositions": {"R1": "model_covered"}, "metrics_registry": {}}
    with use_lang("en"):
        wb = load_workbook(BytesIO(registry_workbook(prepared, result)))
        assert "Source records" in wb.sheetnames and "Traceability" in wb.sheetnames
        assert "Function characteristics" in wb.sheetnames
        assert wb["Source records"]["D2"].value == source["quote"]
        assert wb["Source records"]["D2"].data_type == "s"
        assert wb["Proposals"]["E2"].data_type == "s"
        assert wb["Traceability"]["F2"].value == source["quote"]
    baseline = regression_snapshot(prepared, result)
    assert compare_registries(baseline, baseline)["retained_accepted"] == 1
    changed = regression_snapshot(prepared, {**result, "proposals": [], "dispositions": {"R1": "needs_review"}})
    delta = compare_registries(baseline, changed)
    assert delta["missing_accepted"] == [proposal["text"]]
    assert delta["retained_records"] == 1 and delta["changed_dispositions"] == 1
    try:
        compare_registries(baseline, {**changed, "identity": "other"})
        raise AssertionError("incompatible sources accepted")
    except ValueError:
        pass


if __name__ == "__main__":
    test_additive_and_privacy()
    test_strict_quality_and_batch()
    test_workbook_and_comparison()
    print("ИТОГ: additive function evidence, strict review, independent batch verdicts, private workbook and regression")

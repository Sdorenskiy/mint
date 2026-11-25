"""Offline contract tests for pre-decomposition review. Fictional data only."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint.draft_target_review import summarize_needs, review_scope, MAX_NOTE
from mint.draft_registry_workbook import registry_identity, registry_workbook
from mint.draft_pilot_report import target_registry_export
from mint.template_draft import DraftError
from mint.i18n import use_lang
from io import BytesIO
from openpyxl import load_workbook

def source(rid, quote):
    return {"id": rid, "source": "fictional.md", "section": "Need", "quote": quote,
            "kind": "functional", "source_role": "need"}

records = {"R1": source("R1", "Transfer reservation identifiers."),
           "R2": source("R2", "Transfer 20 messages per second."),
           "R3": source("R3", "Unrelated system handles invoices."),
           "R4": source("R4", "Existing acknowledgement.")}
groups = [{"id": "G1", "function": "Exchange", "requirement_ids": ["R1", "R2", "R4"]}]
decisions = {"R1": {"change": "new", "status": "model_supported"},
             "R2": {"change": "change", "status": "model_supported"},
             "R3": {"change": "external", "status": "model_supported"},
             "R4": {"change": "already_supported", "status": "model_supported"}}
collected = {"groups": groups, "requirements": records, "decisions": decisions}

def test_summary_contract():
    cfg = SimpleNamespace(max_tokens=1800, llm_context_tokens=12000, chars_per_token=2.5)
    context = {"target": "Relay"}
    events = []
    def emit(*args):
        events.append(args)
    good = {"text": "Transfer reservation identifiers at 20 messages per second.",
            "need_refs": ["R1", "R2"], "evidence_refs": []}
    def ask(cfg, stage, payload):
        assert stage == "target_summary"
        assert {r["id"] for r in payload["needs"]} == {"R1", "R2"}
        return good
    rows, counts = summarize_needs(cfg, groups, records, decisions, {}, context, emit, ask)
    assert rows["G1"][0]["text"] == good["text"] and counts == {"draft": 1}
    assert ("target_summary_done", 1) in events
    for reply in ({**good, "need_refs": ["R1"]}, {**good, "need_refs": ["R1", "R2", "R3"]},
                  {**good, "need_refs": ["R1", "R1", "R2"]},
                  {**good, "evidence_refs": ["F999"]}, {**good, "text": "Transfer 999 messages per second."},
                  {**good, "text": ""}):
        rows, counts = summarize_needs(cfg, groups, records, decisions, {}, context, emit,
                                      lambda *_: reply)
        assert counts == {"invalid": 1} and rows["G1"][0]["text"] == ""
        assert rows["G1"][0]["need_refs"] == ["R1", "R2"]
    def failed(*_):
        raise DraftError("synthetic failure")
    rows, counts = summarize_needs(cfg, groups, records, decisions, {}, context, emit, failed)
    assert counts == {"error": 1} and rows["G1"][0]["need_refs"] == ["R1", "R2"]

def test_scope_contract():
    included, review = review_scope(collected)
    assert review["mode"] == "automatic" and review["included"] == ["R1", "R2"]
    assert included[0]["requirement_ids"] == ["R1", "R2", "R4"]
    included, review = review_scope(collected, ["R1"], {"G1": "Preserve exact data categories."})
    assert included[0]["requirement_ids"] == ["R1", "R4"]
    assert review["excluded"] == ["R2"] and review["mode"] == "expert"
    assert groups[0]["requirement_ids"] == ["R1", "R2", "R4"]
    assert review_scope(collected, [])[1]["excluded"] == ["R1", "R2"]
    for selection, notes in [(["R3"], {}), (["R4"], {}), (["R999"], {}), ([], {"G1": "note"}),
                             (["R1"], {"G9": "note"}), (["R1"], {"G1": "x"*(MAX_NOTE+1)}),
                             (None, {"G1": "note"})]:
        try:
            review_scope(collected, selection, notes)
        except ValueError:
            pass
        else:
            raise AssertionError((selection, notes))

def test_exports():
    prep = {"hashes": {}, "context": {"target": "Relay"}, "roles": {}}
    note = "=PRIVATE-EXPERT-NOTE"
    result = {**collected, "state_evidence": {}, "proposals": [], "questions": [],
              "dispositions": {"R1": "awaiting_decomposition", "R2": "expert_excluded",
                               "R3": "external", "R4": "already_supported"},
              "summaries": {"G1": [{"text": "=PRIVATE-SUMMARY", "status": "draft",
                                    "need_refs": ["R1", "R2"], "evidence_refs": []}]},
              "review": {"mode": "expert", "included": ["R1"], "excluded": ["R2"], "notes": {"G1": note}},
              "phase": "collected", "diagnostics": {"summaries": {"draft": 1},
                 "review_scope": {"included": 1, "excluded": 1, "notes": 1}}}
    safe = target_registry_export(prep, result)
    assert safe["phase"] == "collected" and safe["diagnostics"]["review_scope"]["excluded"] == 1
    raw = json.dumps(safe)
    assert "PRIVATE" not in raw and "R1" not in raw
    with use_lang("en"):
        wb = load_workbook(BytesIO(registry_workbook(prep, result)))
        ws = wb["Consolidated needs"]
        assert ws["D2"].value == "=PRIVATE-SUMMARY" and ws["D2"].data_type == "s"
        assert ws["I2"].value == note and ws["I2"].data_type == "s"
    assert registry_identity(prep, result) != registry_identity(prep, {**result, "review": {}})

if __name__ == "__main__":
    test_summary_contract()
    test_scope_contract()
    test_exports()
    print("ИТОГ: bounded summaries, source fallback, explicit scope, private review export")

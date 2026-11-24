"""V2 report regression: preserve dispositions and never export private text."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint.draft_pilot_report import diagnostic_export, review_rows


def test_report():
    secret = "PRIVATE_SOURCE_987"
    records = [{"id": f"R{i}", "source": secret, "section": secret, "quote": secret,
                "kind": kind, "source_role": "mixed"} for i, kind in enumerate(
                    ("functional", "functional", "nonfunctional", "current_state", "open_question", "uncertain"), 1)]
    result = {"requirements": records, "used": {"R1", "R4"},
              "section_dispositions": {"R1": "model_covered", "R2": "coverage_gap"},
              "derivation": {"cross_cutting_ids": ["R3"], "open_question_ids": ["R5"],
                             "untyped_ids": ["R6"], "generated_questions": [{"question": secret}]},
              "results": [{"text": secret}], "issues": [secret], "docx": b"private",
              "metrics": {"total_seconds": 2.5, "run_id": secret,
                          "stages": {"extract": {"llm_calls": 2, "llm_seconds": 1, secret: secret},
                                     secret: {"llm_calls": 99}},
                          "diagnostics": {"extraction": {"cache_hits": 1, secret: secret},
                                          "pilot_section": {"source_read_errors": 1}}}}
    result["analysis"] = {"grouping": {"R1": "grouped", "R2": secret},
                          "allocations": {"R1": {"status": "proposed", "category": "target", "reason": secret},
                                          "R2": {"status": secret, "category": secret}}}
    rows = review_rows(result)
    assert [r["disposition"] for r in rows] == [
        "model_covered", "coverage_gap", "cross_cutting_ids", "linked_evidence",
        "open_question_ids", "untyped_ids"]
    exported = diagnostic_export(result)
    assert exported["allocation_status_counts"] == {"proposed": 1, "other": 1}
    assert exported["grouping_status_counts"] == {"grouped": 1, "other": 1}
    assert exported["records"] == 6 and exported["linked_records"] == 2
    assert exported["inserted_paragraphs"] == 1
    assert exported["source_read_errors"] == 1 and exported["extraction"]["cache_hits"] == 1
    assert exported["stages"]["extract"]["llm_calls"] == 2
    assert secret not in json.dumps(exported)
    result["section_dispositions"]["R2"] = secret
    result["metrics"]["total_seconds"] = secret
    assert secret not in json.dumps(diagnostic_export(result))
    assert diagnostic_export(result)["disposition_counts"]["other"] == 1
    assert diagnostic_export({})["records"] == 0


if __name__ == "__main__":
    test_report()
    print("ИТОГ: V2 report dispositions and sanitized export")

"""Synthetic V3 regressions, no network, no actual work documents."""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import draft_atomic as atomic
from mint.kb import source_path
from mint.template_draft import DraftError

CLAUSE = "Records are transferred from Desk to Relay monthly, without conversion."
TABLE = "| Rate | 20 | msg/s |"
HEADER = "| Metric | Value | Unit |"


def candidate(quote=CLAUSE, **fields):
    return {"quote": quote, "fields": fields}


def test_contract():
    span = {"text": CLAUSE}
    good = candidate(action="are transferred", source_party="Desk", destination_party="Relay",
                     timing="monthly", constraint="without conversion")
    result, status = atomic._validated_candidate(good, span)
    assert status == "accepted" and span["text"][result["start"]:result["end"]] == CLAUSE
    assert "actor" not in result["fields"]
    for raw, code in (
        (candidate(actor="invented"), "invalid_field"),
        (candidate(action=42), "invalid_shape"),
        (candidate(foo="Records"), "invalid_shape"),
        (candidate(), "empty_fields"),
        (candidate("Records are sent.", action="sent"), "invalid_quote"),
        (candidate(action=""), "invalid_field"),
    ):
        assert atomic._validated_candidate(raw, span) == (None, code)
    assert atomic._validated_candidate(good, {"text": CLAUSE + "\n" + CLAUSE}) == (None, "ambiguous_quote")
    table = {"text": HEADER + "\n" + TABLE, "table_context": {"header": HEADER}}
    metric = candidate(TABLE, metric_subject="Rate", metric_value="20", metric_unit="msg/s")
    assert atomic._validated_candidate(metric, table)[1] == "accepted"
    assert atomic._validated_candidate(candidate(TABLE, metric_subject="Rate", metric_value="20"), table)[1] == "invalid_metric"
    assert atomic._validated_candidate(candidate(TABLE, metric_subject="Rate", metric_value="200", metric_unit="msg/s"), table)[1] == "invalid_field"
    assert atomic._validated_candidate(candidate(HEADER + "\n" + TABLE, metric_subject="Rate", metric_value="20",
                                                 metric_unit="msg/s"), table)[1] == "invalid_metric"


def test_sample_and_privacy():
    with TemporaryDirectory() as tmp:
        cfg = SimpleNamespace(kb_path=Path(tmp) / "kb", log_path=Path(tmp) / "logs", llm_model="fixture",
                              max_tokens=1800, llm_context_tokens=16000, chars_per_token=2.5)
        path = source_path(cfg, "private_source.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Flow\n" + CLAUSE + "\n# Other\nExternal duty.", encoding="utf-8")
        prepared = atomic.prepare_atomic_sources(cfg, ["private_source.md"])
        assert len(prepared["spans"]) == 2
        selected = next(iter(prepared["spans"]))
        events = []
        def fake(cfg, stage, payload):
            assert stage == "atomic_extract" and payload["text"] == CLAUSE
            valid = candidate(action="are transferred", source_party="Desk", destination_party="Relay")
            return {"items": [valid, candidate(actor="invented"), valid]}
        with patch.object(atomic, "_json", side_effect=fake) as ask:
            result = atomic.extract_atomic_sample(cfg, prepared, [selected], lambda *e: events.append(e))
            assert ask.call_count == 1
            assert atomic.extract_atomic_sample(cfg, prepared, [selected])["counts"]["accepted"] == 1
            assert ask.call_count == 2
        assert result["counts"]["accepted"] == result["counts"]["invalid_field"] == result["counts"]["duplicate"] == 1
        assert result["fragments"][0]["status"] == "partial"
        assert len(result["fragments"]) == 1 and result["fragments"][0]["facts"][0]["id"] == selected + ".1"
        assert ("atomic_extract_total", 1) in events and ("atomic_extract_done", 1) in events
        report = atomic.atomic_diagnostics(result)
        assert report["expert_review"] is None and report["counts"]["accepted"] == 1
        for secret in ("private_source", "Desk", "Relay", selected, "fixture"):
            assert secret not in json.dumps(report)
        with patch.object(atomic, "_json", side_effect=DraftError("private error")):
            fail = atomic.extract_atomic_sample(cfg, prepared, [selected])
        assert fail["counts"]["batch_error"] == 1 and fail["counts"]["fragments_processed"] == 0
        path.write_text("Changed", encoding="utf-8")
        with patch.object(atomic, "_json") as ask:
            try:
                atomic.extract_atomic_sample(cfg, prepared, [selected])
                raise AssertionError("stale original accepted")
            except DraftError:
                pass
            assert not ask.called


if __name__ == "__main__":
    test_contract()
    test_sample_and_privacy()
    print("ИТОГ: V3 strict structure, exact evidence, bounded selected scope, cold run and safe diagnostics")

"""Synthetic V3 regressions: numbered sources, whole scan, no network."""
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


def candidate(first=1, last=1, **fields):
    return {"first": first, "last": last, "fields": fields}


def test_contract():
    span = {"text": CLAUSE + "\r\n" + CLAUSE}
    good = candidate(2, 2, action="are transferred", source_party="Desk", destination_party="Relay",
                     timing="monthly", constraint="without conversion")
    result, status = atomic._validated_candidate(good, span)
    assert status == "accepted" and span["text"][result["start"]:result["end"]] == CLAUSE
    assert result["start"] == len(CLAUSE) + 2 and "actor" not in result["fields"]
    for raw, code in (
        (candidate(actor="invented"), "invalid_field"),
        (candidate(action=42), "invalid_shape"),
        (candidate(foo="Records"), "invalid_shape"),
        (candidate(), "empty_fields"),
        (candidate(1, 3, action="are transferred"), "invalid_range"),
        (candidate(2, 1, action="are transferred"), "invalid_range"),
        (candidate(True, 1, action="are transferred"), "invalid_shape"),
        (candidate(action=""), "invalid_field"),
    ):
        assert atomic._validated_candidate(raw, span) == (None, code)
    assert atomic._validated_candidate(candidate(1, 2, action="are transferred"),
                                       span, atomic._line_parts(span["text"])[1:])[1] == "invalid_range"
    table = {"text": HEADER + "\n" + TABLE, "table_context": {"header": HEADER}}
    metric = candidate(2, 2, metric_subject="Rate", metric_value="20", metric_unit="msg/s")
    assert atomic._validated_candidate(metric, table)[1] == "accepted"
    assert atomic._validated_candidate(candidate(2, 2, metric_subject="Rate", metric_value="20"), table)[1] == "invalid_metric"
    assert atomic._validated_candidate(candidate(2, 2, metric_subject="Rate", metric_value="200", metric_unit="msg/s"), table)[1] == "invalid_field"
    assert atomic._validated_candidate(candidate(1, 2, metric_subject="Rate", metric_value="20",
                                                 metric_unit="msg/s"), table)[1] == "invalid_range"
    assert atomic._validated_candidate(candidate(1, 1, object="Metric"), table)[1] == "invalid_range"


    # Synthetic regression: two table sizes, formatted headers, grouped
    # numbers, decimal comma and conditional measurement boundaries.
    header = "| **Показатель** | **Значение** | **Единица** | **Условия** |"
    process = [
        ("Размер набора A", "250 000", "записей", "Один регион и период"),
        ("Размер набора B", "500 000", "записей", "Один регион и период"),
        ("Время процесса", "4", "ч", "Не более в штатном режиме"),
        ("Время приёма", "60", "с", "После получения полного пакета"),
        ("Доступность", "99,5", "%", "За месяц без согласованных работ"),
        ("Хранение событий", "90", "суток", "Не менее"),
        ("Параллельная нагрузка", "12", "пакетов", "Одновременно"),
    ]
    component = [
        ("Размер пакета A", "250 000", "записей", "Не менее"),
        ("Размер пакета B", "500 000", "записей", "Не менее"),
        ("Технический приём", "60", "с", "Не более"),
        ("Доставка пакета", "30", "мин", "При доступном получателе"),
        ("Время ответа", "2", "с", "При 20 одновременных запросах"),
        ("Доступность интерфейса", "99,5", "%", "За календарный месяц"),
        ("Параллельный приём", "12", "пакетов", "Одновременно"),
        ("Хранение событий", "90", "суток", "Не менее"),
        ("Хранение сведений", "30", "суток", "Календарные дни"),
    ]
    for rows in (process, component):
        lines = [header, "| --- | --- | --- | --- |"] + [
            "| " + " | ".join(row) + " |" for row in rows]
        span = {"text": "\n".join(lines), "table_context": {"header": header,
                 "separator": lines[1]}}
        for n, (subject, value, unit, condition) in enumerate(rows, 3):
            raw = candidate(n, n, metric_subject=subject, metric_value=value,
                            metric_unit=unit, condition=condition)
            fact, status = atomic._validated_candidate(raw, span)
            assert status == "accepted", (subject, status)
            assert fact["quote"] == lines[n - 1]
            assert span["text"][fact["start"]:fact["end"]] == fact["quote"]
            assert fact["fields"]["condition"] == condition


def test_scope_and_privacy():
    with TemporaryDirectory() as tmp:
        cfg = SimpleNamespace(kb_path=Path(tmp) / "kb", log_path=Path(tmp) / "logs", llm_model="fixture",
                              max_tokens=1800, llm_context_tokens=16000, chars_per_token=2.5)
        path = source_path(cfg, "private_source.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(f"# Section {i}\n{CLAUSE}" for i in range(atomic.MAX_SAMPLE + 2)), encoding="utf-8")
        prepared = atomic.prepare_atomic_sources(cfg, ["private_source.md"])
        assert len(prepared["spans"]) == atomic.MAX_SAMPLE + 2
        selected = next(iter(prepared["spans"]))
        events = []
        def fake(cfg, stage, payload):
            assert stage == "atomic_extract" and payload["parts"] == [{"n": 1, "text": CLAUSE}]
            valid = candidate(action="are transferred", source_party="Desk", destination_party="Relay")
            return {"items": [valid, candidate(actor="invented"), valid]}
        with patch.object(atomic, "_json", side_effect=fake) as ask:
            full = atomic.extract_atomic_sample(cfg, prepared, progress=lambda *e: events.append(e))
            assert ask.call_count == atomic.MAX_SAMPLE + 2
            assert full["scope"] == "all" and full["counts"]["fragments_attempted"] == len(prepared["spans"])
            assert full["counts"]["partial_fragments"] == len(prepared["spans"])
            result = atomic.extract_atomic_sample(cfg, prepared, [selected])
            assert ask.call_count == atomic.MAX_SAMPLE + 3
        assert result["scope"] == "sample"
        assert result["counts"]["accepted"] == result["counts"]["invalid_field"] == result["counts"]["duplicate"] == 1
        assert result["fragments"][0]["status"] == "partial"
        assert len(result["fragments"]) == 1 and result["fragments"][0]["facts"][0]["id"] == selected + ".1"
        assert ("atomic_extract_total", atomic.MAX_SAMPLE + 2) in events
        assert ("atomic_extract_done", atomic.MAX_SAMPLE + 2) in events
        report = atomic.atomic_diagnostics(result)
        assert report["expert_review"] is None and report["counts"]["accepted"] == 1
        assert report["category_counts"]["interactions"] == report["category_counts"]["participants"] == 1
        for secret in ("private_source", "Desk", "Relay", selected, "fixture"):
            assert secret not in json.dumps(report)
        with patch.object(atomic, "_json", side_effect=DraftError("private error")):
            fail = atomic.extract_atomic_sample(cfg, prepared, [selected])
        assert fail["counts"]["batch_error"] == 1 and fail["counts"]["fragments_failed"] == 1
        with patch.object(atomic, "_json", return_value={"items": []}):
            empty = atomic.extract_atomic_sample(cfg, prepared, [selected])
        assert empty["counts"]["empty_response"] == 1 and empty["counts"]["fragments_complete"] == 1
        path.write_text("Changed", encoding="utf-8")
        with patch.object(atomic, "_json") as ask:
            try:
                atomic.extract_atomic_sample(cfg, prepared, [selected])
                raise AssertionError("stale original accepted")
            except DraftError:
                pass
            assert not ask.called


def test_bounded_recovery():
    from collections import Counter
    cfg = SimpleNamespace(max_tokens=1800, llm_context_tokens=16000, chars_per_token=2.5)
    span = {"text": "Desk transfers records.\nRelay stores records.", "section": "Fixture"}
    counts = Counter()
    first = candidate(actor="Desk")
    second = candidate(2, 2, actor="Relay")
    with patch.object(atomic, "_json", side_effect=[{"items": [first] * 12},
                      {"items": [first]}, {"items": [second]}]) as ask:
        facts, status = atomic._extract_fragment(cfg, span, counts)
    assert ask.call_count == 3 and status == "partial"
    assert counts["recovery_attempted"] == 1 and counts["recovery_added"] == 1
    assert counts["accepted"] == 2 and {f["first"] for f in facts} == {1, 2}
    assert ask.call_args.args[2]["parts"] == [{"n": 2, "text": "Relay stores records."}]


if __name__ == "__main__":
    test_contract()
    test_scope_and_privacy()
    test_bounded_recovery()
    print("ИТОГ: V3 whole-document scan, numbered evidence, bounded recovery, categories and safe diagnostics")

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


def test_structured_metric_tables():
    from collections import Counter
    cfg = SimpleNamespace(max_tokens=1800, llm_context_tokens=16000, chars_per_token=2.5)
    header = "| **Показатель** | **Значение** | **Единица** | **Условия** |"
    separator = "| --- | --- | --- | --- |"
    # Synthetic data with independently scoped process and component tables.
    for section, rows in (
        ("Process", [
            ("Размер A", "250 000", "записей", "Один регион и период"),
            ("Размер B", "500 000", "записей", "Один регион и период"),
            ("Консолидация", "4", "ч", "Не более; полный пакет"),
            ("Приём", "60", "с", "Не более"),
            ("Доступность", "99,5", "%", "За месяц"),
            ("Хранение событий", "90", "суток", "Не менее"),
            ("Параллельная нагрузка", "12", "пакетов", "Одновременно"),
        ]),
        ("Component", [
            ("Размер A", "250 000", "записей", "Не менее"),
            ("Размер B", "500 000", "записей", "Не менее"),
            ("Приём", "60", "с", "Полный пакет"),
            ("Доставка", "30", "мин", "Без ожидания зависимости"),
            ("Ответ", "2", "с", "При 20 запросах"),
            ("Доступность", "99,5", "%", "Без согласованных работ"),
            ("Параллельный приём", "12", "пакетов", "Одновременно"),
            ("Хранение событий", "90", "суток", "Не менее"),
            ("Хранение сведений", "30", "суток", "Календарные дни"),
        ]),
    ):
        lines = [header, separator] + ["| " + " | ".join(row) + " |" for row in rows]
        span = {"section": section, "text": "\r\n".join(lines),
                "table_context": {"header": header, "separator": separator}}
        counts = Counter()
        with patch.object(atomic, "_json") as ask:
            facts, status = atomic._extract_fragment(cfg, span, counts)
        assert not ask.called and status == "processed"
        assert counts["accepted"] == counts["metric_table_rows"] == len(rows)
        assert counts["metric_table_fragments"] == 1
        for i, (fact, row) in enumerate(zip(facts, rows), 3):
            assert fact["first"] == fact["last"] == i
            assert fact["quote"] == lines[i - 1]
            assert span["text"][fact["start"]:fact["end"]] == fact["quote"]
            assert fact["origin"] == "structured_table"
            assert tuple(fact["fields"][k] for k in (*atomic.METRIC_KEYS, "condition")) == row
    # Continuation chunks need not repeat the header. Reordered columns work.
    header_en = "| Unit | **Metric** | Value |"
    span = {"section": "Continuation", "text": "| ms | Latency | 25 |",
            "table_context": {"header": header_en}}
    with patch.object(atomic, "_json") as ask:
        facts, status = atomic._extract_fragment(cfg, span, Counter())
    assert not ask.called and status == "processed"
    assert facts[0]["fields"] == {"metric_subject": "Latency", "metric_value": "25", "metric_unit": "ms"}
    for bad in ("| A | 10–20 | ms | bounded |", "| A | 10 | | bounded |",
                "| A | 10 | ms | bounded | extra |", "Free text",
                "| A | 10 | - | bounded |"):
        span = {"section": "Fallback", "text": header + "\n" + separator + "\n"
                + "| Valid | 2 | ms | bounded |\n" + bad,
                "table_context": {"header": header, "separator": separator}}
        counts = Counter()
        with patch.object(atomic, "_json", return_value={"items": []}) as ask:
            facts, status = atomic._extract_fragment(cfg, span, counts)
        assert ask.call_count == 1 and counts["metric_table_fallbacks"] == 1
        assert counts["metric_table_rows"] == 0 and not facts
    # Ambiguous/other tables never become deterministic metric candidates.
    for header in ("| Metric | Value | Value | Unit |", "| Field | Description |"):
        span = {"section": "Other", "text": "| A | 10 | 20 | ms |",
                "table_context": {"header": header}}
        with patch.object(atomic, "_json", return_value={"items": []}) as ask:
            atomic._extract_fragment(cfg, span, Counter())
        assert ask.call_count == 1


def test_assertion_extraction():
    from collections import Counter
    cfg = SimpleNamespace(max_tokens=1800, llm_context_tokens=16000, chars_per_token=2.5)
    first = "System A stores records for 30 days."
    second = "System B must not modify records."
    span = {"section": "Fixture", "text": first + " " + second}
    def item(text, first=1, last=1):
        return {"first": first, "last": last, "text": text}
    counts = Counter()
    with patch.object(atomic, "_json", return_value={"items": [item(first), item(second),
            item(first), item("System B must modify records.")]}) as ask:
        facts, status = atomic._extract_fragment(cfg, span, counts, mode="assertions")
    assert ask.call_args.args[1] == "atomic_assertions"
    assert status == "partial" and counts["invalid_field"] == counts["duplicate"] == 1
    assert [fact["quote"] for fact in facts] == [first, second]
    assert counts["accepted"] == 2
    for fact in facts:
        assert not fact["fields"] and fact["origin"] == "assertion"
        assert span["text"][fact["start"]:fact["end"]] == fact["quote"]
    assert facts[0]["end"] < facts[1]["start"]
    assert atomic._validated_assertion(item(first, 1, 2), span)[1] == "invalid_range"
    assert atomic._validated_assertion({"first": True, "last": 1, "text": first}, span)[1] == "invalid_shape"
    assert atomic._validated_assertion(candidate(actor="System A"), span)[1] == "invalid_shape"
    assert atomic._validated_assertion(item("yst"), span)[1] == "invalid_field"
    assert atomic._validated_assertion(item(""), span)[1] == "invalid_field"
    repeated = {"text": first + " " + first}
    assert atomic._validated_assertion(item(first), repeated)[1] == "invalid_field"
    repeated_lines = {"text": first + "\r\n" + first}
    fact, status = atomic._validated_assertion(item(first, 2, 2), repeated_lines)
    assert status == "accepted" and fact["start"] == len(first) + 2
    cross = {"text": "Do not deliver\r\n  until accepted.\r\nOther."}
    fact, status = atomic._validated_assertion(item("Do not deliver until accepted.", 1, 2), cross)
    assert status == "accepted" and fact["quote"] == "Do not deliver\r\n  until accepted."
    assert cross["text"][fact["start"]:fact["end"]] == fact["quote"]
    # A table row is selected by number, without reproducing text or guessing cells.
    header = "| Field | Description |"
    table = {"section": "Fields", "text": header + "\n| --- | --- |\n| A | Required |",
             "table_context": {"header": header, "separator": "| --- | --- |"}}
    for n in (1, 2):
        assert atomic._validated_assertion({"first": n, "last": n}, table)[1] == "invalid_range"
    fact, status = atomic._validated_assertion({"first": 3, "last": 3}, table)
    assert status == "accepted" and fact["quote"] == "| A | Required |"
    assert atomic._validated_assertion(item("A", 3, 3), table)[1] == "invalid_field"
    assert atomic._validated_assertion(item("| A | Required |", 3, 3), table)[1] == "accepted"
    # Both modes reuse deterministic metric extraction unchanged.
    metric = {"section": "Metrics", "text": TABLE, "table_context": {"header": HEADER}}
    with patch.object(atomic, "_json") as ask:
        left = atomic._extract_fragment(cfg, metric, Counter(), mode="slots")
        right = atomic._extract_fragment(cfg, metric, Counter(), mode="assertions")
    assert left == right and not ask.called
    assert left[0][0]["origin"] == "structured_table"
    # Recovery keeps the chosen contract, including when narrowing the window.
    split = {"section": "Fixture", "text": first + "\n" + second}
    with patch.object(atomic, "_json", side_effect=[{"items": [item(first)] * 12},
                     {"items": [item(first)]}, {"items": [item(second, 2, 2)]}]) as ask:
        recovered, status = atomic._extract_fragment(cfg, split, Counter(), mode="assertions")
    assert status == "partial" and len(recovered) == 2
    assert all(call.args[1] == "atomic_assertions" for call in ask.call_args_list)
    # The safe export identifies the mode, but does not imply that categories
    # absent from an unclassified result have zero recall.
    diagnostic = atomic.atomic_diagnostics({"mode": "assertions", "fragments": [
        {"facts": facts + left[0]}], "counts": {"accepted": 3},
        "metrics": {"stages": {"atomic_assertions": {"llm_calls": 1, "llm_seconds": 2},
                               "secret": {"llm_calls": 9}}}})
    assert diagnostic["mode"] == "assertions"
    assert diagnostic["category_counts"] == {"metrics": 1}
    assert set(diagnostic["stages"]) == {"atomic_assertions"}
    assert first not in json.dumps(diagnostic)


def test_preserve_table_rows_and_context():
    from collections import Counter
    cfg = SimpleNamespace(max_tokens=1800, llm_context_tokens=16000, chars_per_token=2.5)
    specs = [
        ("Revision history", ["Revision", "Description"], 1, True),
        ("Terms", ["Term", "Definition"], 4, True),
        ("Participants", ["Party", "Responsibility"], 4, False),
        ("Recipient data", ["Field", "Description", "Required"], 6, False),
        ("Payment data", ["Field", "Description", "Required"], 5, False),
        ("Revision history", ["Version", "Description"], 1, True),
        ("Components", ["System", "Role"], 4, False),
        ("Links", ["From", "To", "Purpose"], 3, False),
        ("Contracts", ["From", "To", "Format", "Protocol"], 6, False),
        ("Envelope", ["Attribute", "Description", "Required"], 6, False),
    ]
    total = 0
    for section, headers, n, context in specs:
        header = "| " + " | ".join("**" + h + "**" for h in headers) + " |"
        sep = "| " + " | ".join("---" for _ in headers) + " |"
        data = ["| " + " | ".join(f"value {i}-{j}" for j in range(len(headers))) + " |"
                for i in range(n)]
        span = {"section": section, "text": "\r\n".join([header, sep, *data]),
                "table_context": {"header": header, "separator": sep}}
        counts = Counter()
        with patch.object(atomic, "_json") as ask:
            rows, status = atomic._extract_fragment(cfg, span, counts, mode="assertions")
        assert not ask.called and status == "processed"
        assert len(rows) == n and counts["ordinary_table_rows"] == n
        assert counts["accepted"] == n and not counts["uncertain_table_rows"]
        for i, row in enumerate(rows):
            assert row["quote"] == data[i] == span["text"][row["start"]:row["end"]]
            assert row["first"] == row["last"] == i + 3
            assert row["origin"] == "table_row" and not row["fields"]
            assert row["table_row"]["headers"] == ["**" + h + "**" for h in headers]
            assert row["table_row"]["values"] == [f"value {i}-{j}" for j in range(len(headers))]
            assert atomic._record_role(span, row) == ("context" if context else "candidate")
        total += n
    assert total == 40
    header = "| A | B | C |"
    data = [r"| alpha \| beta | x | yes |", "| | x | yes |",
            "| alpha | x ||", "| alpha | x |", "unparsed cell"]
    span = {"section": "Fields", "text": "\n".join(data),
            "table_context": {"header": header}}
    with patch.object(atomic, "_json") as ask:
        rows, status = atomic._extract_fragment(cfg, span, Counter(), mode="assertions")
    assert not ask.called and status == "partial" and len(rows) == len(data)
    assert rows[0]["table_row"]["values"] == [r"alpha \| beta", "x", "yes"]
    assert rows[1]["table_row"]["values"] == ["", "x", "yes"]
    assert rows[2]["table_row"]["values"] == ["alpha", "x", ""]
    assert all(r["record_role"] == "unresolved" for r in rows[1:])
    assert all(r["quote"] == line for r, line in zip(rows, data))
    assert atomic.fact_in_group(rows[1], "unresolved") and not atomic.fact_in_group(rows[1], "all")
    span = {"section": "Fields", "text": "| a | b | c |", "table_context": {"header": "| A | A | C |"}}
    rows, status = atomic._extract_fragment(cfg, span, Counter(), mode="assertions")
    assert status == "partial" and rows[0]["record_role"] == "unresolved"
    span = {"section": "Metrics", "text": "| Latency | 10–20 | ms |",
            "table_context": {"header": "| Metric | Value | Unit |"}}
    with patch.object(atomic, "_json", return_value={"items": []}) as ask:
        rows, status = atomic._extract_fragment(cfg, span, Counter(), mode="assertions")
        atomic._extract_fragment(cfg, span, Counter(), mode="slots")
    assert ask.call_count == 1 and status == "partial" and not rows[0]["fields"]
    assert rows[0]["record_role"] == "unresolved"
    span = {"fragment": 1, "section": "", "text": "**PROJECT**\n\nDocument title"}
    for quote in ("**PROJECT**", "Document title"):
        assert atomic._record_role(span, {"quote": quote}) == "context"
    span = {"fragment": 2, "section": "ФУНКЦИОНАЛЬНЫЕ ТРЕБОВАНИЯ",
            "text": "Название документа\nОбозначение: FT-01\nРедакция 1.0\nСтатус: согласован\nСистема хранит данные."}
    for quote in ("Название документа", "Обозначение: FT-01", "Редакция 1.0", "Статус: согласован"):
        assert atomic._record_role(span, {"quote": quote}) == "context"
    assert atomic._record_role(span, {"quote": "Система хранит данные."}) == "candidate"
    for quote in ("Версия пакета обязательна.", "На дату обследования обмен ручной.",
                  "Алгоритм шифрования уточняется.", "Повтор не создаёт новых записей."):
        assert atomic._record_role({"section": "1. Scope"}, {"quote": quote}) == "candidate"
    assert atomic._record_role({"section": "Scope"}, {"quote": "Условный пример кода: X."}) == "context"


def test_diagnostic_trace_and_literal_recovery():
    from collections import Counter
    cfg = SimpleNamespace(max_tokens=1800, llm_context_tokens=16000, chars_per_token=2.5)
    span = {"id": "private-id", "section": "private-section", "text": "System A stores records.\nSystem B does not modify records."}
    valid = {"first": 1, "last": 1, "text": "System A stores records."}
    invalid = {"first": 2, "last": 2, "text": "private-secret"}
    second = {"first": 2, "last": 2, "text": "System B does not modify records."}
    budget = {"events": 0, "extended": True, "private_events": 0,
              "private_chars": 0, "private_omitted": 0}
    trace = {"windows": 0, "rejections": [], "private": [], "budget": budget}
    counts = Counter()
    with patch.object(atomic, "_json", side_effect=[{"items": [valid, invalid]},
                     {"items": [valid]}, {"items": [second]}]) as ask:
        facts, status = atomic._extract_fragment(cfg, span, counts, mode="assertions", trace=trace)
    assert ask.call_count == 3 and status == "partial" and len(facts) == 2
    assert counts["recovery_attempted"] == counts["recovery_added"] == 1
    assert trace["rejections"][0]["code"] == "invalid_field"
    assert trace["rejections"][0]["field"] == "text"
    assert trace["rejections"][0]["cause"] == "not_literal"
    assert json.loads(trace["private"][0]["candidate_json"]) == invalid
    result = {"mode": "assertions", "fragments": [dict(span, facts=facts)],
              "counts": dict(counts), "fragment_diagnostics": [
                  {"status": status, "structure": "text", "windows": trace["windows"],
                   "counts": dict(counts), "seconds": 1.2,
                   "rejections": trace["rejections"] + [
                       {"code": "private-secret", "field": "private-field", "cause": "private-error"},
                       {"code": "invalid_field", "field": "private-field", "cause": "private-error",
                        "candidate_json": "private-secret"}]}],
              "private_diagnostics": {"fragments": [{"fragment": "private-id", "rejections": trace["private"]}],
                                      "omitted": 0}}
    safe = atomic.atomic_diagnostics(result)
    assert safe["fragment_diagnostics"][0]["fragment"] == 1
    assert safe["fragment_diagnostics"][0]["rejections"][0]["cause"] == "not_literal"
    assert "private-" not in json.dumps(safe)
    private = atomic.atomic_private_diagnostics(result)
    assert private["fragments"][0]["text"] == span["text"]
    assert json.loads(private["fragments"][0]["rejections"][0]["candidate_json"]) == invalid
    budget["extended"] = False
    trace["private"].clear()
    atomic._record_rejection(trace, counts, "invalid_payload", raw={"secret": "private-secret"})
    assert not trace["private"]
    budget["extended"] = True
    budget["private_events"] = atomic.MAX_PRIVATE_EVENTS
    atomic._record_rejection(trace, counts, "invalid_field", raw=invalid)
    assert budget["private_omitted"] == 1 and not trace["private"]
    budget["events"] = atomic.MAX_TRACE_EVENTS
    atomic._record_rejection(trace, counts, "batch_error")
    assert counts["trace_omitted"] == 1
    assert atomic.atomic_private_diagnostics({"fragments": []}) is None


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
        assert result["mode"] == report["mode"] == "slots"
        assert "private_diagnostics" not in result
        assert report["fragment_diagnostics"][0]["rejections"][0]["field"] == "actor"
        assert report["fragment_diagnostics"][0]["rejections"][0]["cause"] == "not_literal"
        with patch.object(atomic, "_json", side_effect=fake):
            detailed = atomic.extract_atomic_sample(cfg, prepared, [selected], extended=True)
        assert atomic.atomic_private_diagnostics(detailed)["fragments"][0]["fragment"] == selected
        assert atomic.atomic_diagnostics(detailed)["fragment_diagnostics"][0]["rejections"][0]["code"] == "invalid_field"
        assert "invented" not in json.dumps(atomic.atomic_diagnostics(detailed))
        with patch.object(atomic, "_json", return_value={"items": [{"first": 1, "last": 1, "text": CLAUSE}]}) as ask:
            simple = atomic.extract_atomic_sample(cfg, prepared, [selected], mode="assertions")
        assert simple["mode"] == "assertions" and ask.call_args.args[1] == "atomic_assertions"
        assert simple["fragments"][0]["facts"][0]["quote"] == CLAUSE
        assert simple["fragments"][0]["facts"][0]["id"] == selected + ".1"
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
    test_structured_metric_tables()
    test_assertion_extraction()
    test_preserve_table_rows_and_context()
    test_diagnostic_trace_and_literal_recovery()
    test_scope_and_privacy()
    test_bounded_recovery()
    print("ИТОГ: V3 whole-document scan, numbered evidence, bounded recovery, categories and safe diagnostics")

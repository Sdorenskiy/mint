"""Requirement → edit chat handoff and stale after-approval evidence."""
import io
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from docx import Document

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import document_edit as edit
from mint import draft_traceability as trace

CONTEXT = {"target": "Платформа А", "objective": "Обмен",
           "scope": "Передача сообщений", "participants": "Платформа Б"}


def test_stale_evidence_and_safe_handoff():
    result = {"requirements": [
        {"id": "R1", "source": "basis.md", "section": "4.1", "quote": "Платформа А отправляет.",
         "applicability": {"category": "target", "actor": "А", "reason": "А отправляет"}},
        {"id": "R2", "source": "basis.md", "section": "4.2", "quote": "Платформа Б подтверждает.",
         "applicability": {"category": "interaction", "actor": "Б", "reason": "Б подтверждает"}},
    ], "section_plan": {"7.1": {"selected_ids": ["R1"]}}, "results": [
        {"section": "7.1", "field": "Сервис", "kind": "field",
         "text": "Платформа А отправляет.", "status": "unchecked",
         "refs": ["R1"], "confirmed_refs": ["R1"]},
    ]}
    rows = trace.build_traceability(result)
    assert rows[0]["coverage"] == "output_anchor"
    revised = trace.mark_stale_after_edits(rows, {"7.1"})
    assert revised[0]["coverage"] == "stale_after_edit"
    assert revised[0]["stale_sections"] == ["7.1"]
    assert revised[1]["coverage"] == "external"
    assert trace.trace_counts(revised)["anchored"] == 0
    assert trace.trace_counts(revised)["pending"] == 1
    assert trace.mark_stale_after_edits(rows, set())[0]["coverage"] == "output_anchor"
    assert rows[0]["coverage"] == "output_anchor"  # original metadata preserved
    assert "дополни" in trace.chat_request_for_requirement(rows[0])
    external_request = trace.chat_request_for_requirement(rows[1])
    assert "правильного исполнителя" in external_request
    assert "Не переносить чужую обязанность" in external_request
    assert "Платформа Б подтверждает." in external_request


def test_chat_reuses_scope_and_proposal_checks():
    doc = Document()
    doc.add_heading("7.1 Обмен", 1)
    doc.add_paragraph("Платформа А отправляет.")
    stream = io.BytesIO()
    doc.save(stream)
    original = stream.getvalue()
    target = next(t for t in edit.list_targets(original) if t["kind"] == "paragraph")
    requirements = [
        {"id": "R1", "source": "basis.md", "section": "4.1", "quote": "Платформа А отправляет.",
         "applicability": {"category": "target", "actor": "А", "reason": "А отправляет"}},
        {"id": "R2", "source": "basis.md", "section": "4.2", "quote": "Платформа Б подтверждает.",
         "applicability": {"category": "interaction", "actor": "Б", "reason": "Б подтверждает"}},
        {"id": "R3", "source": "basis.md", "section": "4.3", "quote": "Платформа В хранит данные.",
         "applicability": {"category": "other", "actor": "В", "reason": "Другая платформа"}},
    ]
    cfg = SimpleNamespace(max_tokens=1500, llm_context_tokens=10000, chars_per_token=2.5)
    response = {"text": "Платформа А отправляет.", "refs": ["R1"],
                "coverage": {"R1": "Платформа А отправляет."}, "reason": "Без изменений"}
    with patch.object(edit, "_json", return_value=response) as mocked:
        suggestion = edit.propose_edit(cfg, original, target["id"], "Уточни обмен",
                                       requirements, context=CONTEXT)
    payload = mocked.call_args.args[2]
    assert payload["document_context"]["target"] == "Платформа А"
    assert [r["id"] for r in payload["requirements"]] == ["R1"]
    assert [r["id"] for r in payload["external_context"]] == ["R2"]
    assert suggestion["coverage_confirmed"] == ["R1"]
    assert edit.digest(original) == suggestion["doc_sha256"]
    assert "Платформа Б" not in suggestion["text"]


def test_long_edit_history_stays_stale_after_undo_limit():
    """Eleven changes with ten undo snapshots must not restore stale evidence."""
    state = {"docx": b"v0", "versions": [], "changes": []}
    for index in range(1, 12):
        edit.record_accepted_version(state, f"v{index}".encode(), "7.1 Обмен",
                                     f"p:{index}", max_undo=10)
    assert len(state["versions"]) == 10
    assert len(state["changes"]) == 11
    rows = trace.build_traceability({
        "requirements": [{"id": "R1", "source": "basis.md", "section": "4",
                          "quote": "Платформа А отправляет."}],
        "section_plan": {" 7.1  Обмен ": {"selected_ids": ["R1"]}},
        "results": [{"section": " 7.1  Обмен ", "field": "Функции",
                     "text": "Платформа А отправляет.", "status": "unchecked",
                     "refs": ["R1"], "confirmed_refs": ["R1"]}],
    })
    assert trace.mark_stale_after_edits(rows, {s for s, _ in state["changes"]})[0][
        "coverage"] == "stale_after_edit"
    for _ in range(10):
        assert edit.undo_accepted_version(state)
    assert state["docx"] == b"v1"
    assert len(state["changes"]) == 1
    assert not edit.undo_accepted_version(state)
    assert trace.mark_stale_after_edits(rows, {s for s, _ in state["changes"]})[0][
        "coverage"] == "stale_after_edit"


def test_explicit_source_focus_is_not_lost_or_misclassified():
    doc = Document()
    doc.add_heading("7.1 Обмен", 1)
    doc.add_paragraph("Платформа А отправляет.")
    original = io.BytesIO()
    doc.save(original)
    target = next(t for t in edit.list_targets(original.getvalue())
                  if t["kind"] == "paragraph")
    reqs = [
        {"id": "R1", "source": "basis.md", "section": "4.1",
         "quote": "Платформа А отправляет.",
         "applicability": {"category": "target", "actor": "А", "reason": "А отправляет"}},
        {"id": "R2", "source": "basis.md", "section": "4.2",
         "quote": "Платформа Б подтверждает.",
         "applicability": {"category": "interaction", "actor": "Б", "reason": "Б подтверждает"}},
    ]
    cfg = SimpleNamespace(max_tokens=1500, llm_context_tokens=10000, chars_per_token=2.5)
    response = {"text": "Платформа А отправляет.", "refs": ["R1"],
                "coverage": {"R1": "Платформа А отправляет."}}
    # Simulate retrieval missing every requirement: explicit selection still wins.
    with patch.object(edit, "_candidates", return_value=[]), patch.object(
            edit, "_json", return_value=response) as mocked:
        proposal = edit.propose_edit(cfg, original.getvalue(), target["id"],
                                     "Уточнить отправку", reqs, context=CONTEXT,
                                     focus_requirement_id="R1")
    payload = mocked.call_args.args[2]
    assert [item["id"] for item in payload["requirements"]] == ["R1"]
    assert payload["focused_requirement"]["id"] == "R1"
    assert proposal["refs"] == ["R1"]

    # External obligation remains visible for review but cannot become evidence.
    with patch.object(edit, "_candidates", return_value=[]), patch.object(
            edit, "_json", return_value={"text": "Платформа А отправляет.",
                                        "refs": ["R2"], "coverage": {}}) as mocked:
        external = edit.propose_edit(cfg, original.getvalue(), target["id"],
                                     "Проверь, относится ли пункт к А", reqs,
                                     context=CONTEXT, focus_requirement_id="R2")
    assert mocked.call_args.args[2]["focused_requirement"]["id"] == "R2"
    assert mocked.call_args.args[2]["requirements"] == []
    assert external["refs"] == []
    try:
        edit.propose_edit(cfg, original.getvalue(), target["id"],
                          "Проверь пункт", reqs, context=CONTEXT,
                          focus_requirement_id="R999")
    except edit.DraftError:
        pass
    else:
        raise AssertionError("Unknown selected requirement must be rejected")


if __name__ == "__main__":
    test_stale_evidence_and_safe_handoff()
    test_chat_reuses_scope_and_proposal_checks()
    test_long_edit_history_stays_stale_after_undo_limit()
    test_explicit_source_focus_is_not_lost_or_misclassified()
    print("ИТОГ: переход из требования в чат, запрет чужих обязанностей и устаревшие связи")

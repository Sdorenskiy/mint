"""Bidirectional traceability shows true output anchors separately from candidates."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint.draft_traceability import (
    build_traceability, by_word_section, by_basis_document, trace_counts,
)


def test_two_directions_and_nonclaims():
    requirements = [
        {"id": "R1", "source": "basis_a.docx", "section": "1", "quote": "А отправляет",
         "applicability": {"category": "target", "actor": "Платформа А", "reason": "А отправляет"}},
        {"id": "R2", "source": "basis_a.docx", "section": "2", "quote": "А повторяет",
         "applicability": {"category": "target", "actor": "Платформа А", "reason": "А повторяет"}},
        {"id": "R3", "source": "basis_b.docx", "section": "3", "quote": "А сохраняет",
         "applicability": {"category": "shared", "actor": "Все участники", "reason": "Общее"}},
        {"id": "R4", "source": "basis_b.docx", "section": "4", "quote": "Б подтверждает",
         "applicability": {"category": "interaction", "actor": "Платформа Б", "reason": "Б подтверждает"}},
        {"id": "R5", "source": "basis_b.docx", "section": "5", "quote": "Платформа В",
         "applicability": {"category": "other", "actor": "В", "reason": "Другая платформа"}},
        {"id": "R6", "source": "basis_a.docx", "section": "6", "quote": "Неясная обязанность",
         "applicability": {"category": "uncertain", "actor": "", "reason": "Не указан исполнитель"}},
        {"id": "R7", "source": "basis_a.docx", "section": "7", "quote": "А обрабатывает"},
    ]
    result = {"requirements": requirements, "results": [
        {"section": "7.1", "kind": "field", "field": "Функции", "status": "unchecked",
         "text": "А отправляет", "refs": ["R1", "R2"], "confirmed_refs": ["R1"]},
        {"section": "6.1", "kind": "table", "field": "Таблица", "status": "manual",
         "text": "А сохраняет", "refs": ["R3"], "confirmed_refs": []},
    ], "section_plan": {
        "7.1": {"selected_ids": ["R1", "R2", "R7"]},
        "6.1": {"selected_ids": ["R3"]},
    }}
    rows = build_traceability(result)
    indexed = {row["id"]: row for row in rows}
    assert len(rows) == 7
    assert indexed["R1"]["coverage"] == "output_anchor"
    assert indexed["R1"]["anchored"][0]["section"] == "7.1"
    assert indexed["R2"]["coverage"] == "cited_without_anchor"
    assert indexed["R3"]["coverage"] == "cited_without_anchor"
    assert indexed["R4"]["coverage"] == "external"
    assert indexed["R5"]["coverage"] == "external"
    assert indexed["R6"]["coverage"] == "scope_uncertain"
    assert indexed["R7"]["coverage"] == "candidate_only"
    assert "7.1" in by_word_section(rows, result)
    assert set(row["id"] for row in by_word_section(rows, result)["7.1"]) == {"R1", "R2", "R7"}
    assert set(by_basis_document(rows, ["basis_a.docx", "basis_b.docx"])) == {
        "basis_a.docx", "basis_b.docx"}
    assert len(by_basis_document(rows)["basis_b.docx"]) == 3
    assert trace_counts(rows) == {"extracted": 7, "anchored": 1, "pending": 4, "external": 2}
    assert "Применимость" not in str(result.get("results")[0])  # no fabricated independent audit


def test_invalid_ref_and_old_result_are_safe():
    result = {"requirements": [{"id": "R1", "source": "source.md", "section": "A",
                                 "quote": "Сервис обрабатывает запрос"}],
              "results": [{"field": "Текст", "text": "Сервис обрабатывает запрос",
                           "refs": ["R999"], "status": "unchecked"}],
              "section_plan": {}}
    rows = build_traceability(result)
    assert rows[0]["coverage"] == "not_selected"
    assert rows[0]["anchored"] == []


if __name__ == "__main__":
    test_two_directions_and_nonclaims()
    test_invalid_ref_and_old_result_are_safe()
    print("ИТОГ: две стороны просмотра, реальные текстовые якоря, сомнения и внешние платформы")

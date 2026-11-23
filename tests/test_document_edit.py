"""Offline regression of the document chat's controlled Word edits.

The LLM is mocked; no confidential document or external service is used.
"""
import io
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from docx import Document
from docx.oxml import OxmlElement

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import document_edit as edit
from mint.template_draft import DraftError


def blob(doc):
    stream = io.BytesIO()
    doc.save(stream)
    return stream.getvalue()


def sample():
    doc = Document()
    doc.add_paragraph("Титульный лист — заполняется человеком")
    doc.add_heading("7.1 Функции сервиса", 1)
    p = doc.add_paragraph("Сервис принимает заявку.")
    p.runs[0].bold = True
    doc.add_paragraph("Сервис отправляет уведомление.")
    doc.add_heading("8 Справочник", 1)
    table = doc.add_table(rows=3, cols=2)
    table.cell(0, 0).text = "Термин"
    table.cell(0, 1).text = "Определение"
    table.cell(1, 0).text = "СЗ"
    table.cell(1, 1).text = "Сервис заявок"
    table.cell(2, 0).text = "АС"
    table.cell(2, 1).text = "Аналитическая система"
    doc.add_heading("9 Служебные ссылки", 1)
    doc.add_paragraph("Не трогать [12].")
    protected = doc.add_paragraph("Текст с защищённой ссылкой")
    protected._p.append(OxmlElement("w:hyperlink"))
    return blob(doc)


REQ = [{"id": "R1", "source": "approved_basis.md", "section": "7.1",
        "quote": "Сервис принимает заявку и помещает её в очередь при недоступности получателя."}]


def expect_error(func, *args):
    try:
        func(*args)
    except DraftError:
        return
    raise AssertionError("unsafe or stale edit unexpectedly succeeded")


def test_sections_proposals_and_acceptance():
    initial = sample()
    original_sha = edit.digest(initial)
    targets = edit.list_targets(initial)
    main = next(row for row in targets if row["kind"] == "section"
                and "7.1" in row["section"])
    assert main["text"] == "Сервис принимает заявку.\nСервис отправляет уведомление."
    assert next(row for row in targets if row["kind"] == "cell"
                and row["text"] == "Сервис заявок")
    assert not any(row["kind"] == "cell" and row["text"] == "Определение" for row in targets)
    assert not any("Текст с защищённой ссылкой" in row["text"] for row in targets)

    cfg = SimpleNamespace(max_tokens=2000, llm_context_tokens=16384, chars_per_token=2.5)
    response = {"text": "Сервис принимает заявку.\n"
                        "При недоступности получателя заявка ставится в очередь.",
                "refs": ["R1"],
                "coverage": {"R1": "При недоступности получателя заявка ставится в очередь."},
                "reason": "Добавлена обработка недоступности"}
    with patch.object(edit, "_json", return_value=response) as call:
        proposal = edit.propose_edit(
            cfg, initial, main["id"], "Добавь очередь при сбое получателя", REQ,
            [{"role": "user", "content": "Это обработка заявок"}])
    assert call.call_args.args[1] == "edit"
    assert call.call_args.args[2]["original"] == main["text"]
    assert call.call_args.args[2]["conversation"][0]["role"] == "user"
    assert edit.digest(initial) == proposal["doc_sha256"]
    assert proposal["refs"] == ["R1"] and proposal["coverage_confirmed"] == ["R1"]
    assert proposal["sources"][0]["source"] == "approved_basis.md"
    assert not proposal["warnings"]
    assert "-Сервис отправляет уведомление." in edit.proposal_diff(proposal)
    assert "+При недоступности" in edit.proposal_diff(proposal)
    assert Document(io.BytesIO(initial)).paragraphs[2].text == "Сервис принимает заявку."
    accepted = edit.apply_edit(initial, proposal)
    assert accepted != initial
    doc = Document(io.BytesIO(accepted))
    lines = [p.text for p in doc.paragraphs]
    assert "Сервис принимает заявку." in lines
    assert "При недоступности получателя заявка ставится в очередь." in lines
    assert "Сервис отправляет уведомление." not in lines
    assert doc.paragraphs[0].text == "Титульный лист — заполняется человеком"
    assert doc.tables[0].cell(1, 1).text == "Сервис заявок"
    assert "Не трогать [12]." in lines
    assert doc.paragraphs[2].runs[0].bold
    expect_error(edit.apply_edit, accepted, proposal)  # stale proposal
    expect_error(edit.apply_edit, initial, {**proposal, "target_id": "s:9999"})
    expect_error(edit.apply_edit, initial, {**proposal, "text": ""})
    assert edit.digest(initial) == original_sha  # the original bytes are immutable


def test_cell_and_single_paragraph():
    initial = sample()
    targets = edit.list_targets(initial)
    cell = next(row for row in targets if row["kind"] == "cell"
                and row["text"] == "Аналитическая система")
    proposal = {"target_id": cell["id"], "original": cell["text"],
                "doc_sha256": edit.digest(initial), "text": "Система аналитики"}
    final = edit.apply_edit(initial, proposal)
    doc = Document(io.BytesIO(final))
    assert doc.tables[0].cell(2, 1).text == "Система аналитики"
    assert doc.tables[0].cell(1, 1).text == "Сервис заявок"
    expect_error(edit.apply_edit, initial, {**proposal, "text": "Недопустимо\nдве строки"})
    heading_id = "p:1"
    expect_error(edit.apply_edit, initial, {**proposal, "target_id": heading_id})
    body_paragraph = next(t for t in targets if t["kind"] == "paragraph"
                          and "Не трогать [12]" in t["text"])
    single = edit.apply_edit(initial, {"target_id": body_paragraph["id"],
                                      "original": body_paragraph["text"],
                                      "doc_sha256": edit.digest(initial),
                                      "text": "Новая формулировка [12]."})
    assert "Новая формулировка [12]." in [p.text for p in Document(io.BytesIO(single)).paragraphs]
    assert "Не трогать [12]." in [p.text for p in Document(io.BytesIO(initial)).paragraphs]


def test_unconfirmed_sources_and_errors():
    initial = sample()
    target = next(t for t in edit.list_targets(initial) if t["kind"] == "paragraph"
                  and "принимает заявку" in t["text"])
    cfg = SimpleNamespace(max_tokens=1500, llm_context_tokens=12000, chars_per_token=2.5)
    with patch.object(edit, "_json", return_value={"text": "Заявки хранятся 100 суток.",
                                                     "refs": ["R1"], "coverage": {}}):
        proposal = edit.propose_edit(cfg, initial, target["id"], "Сделай срок 100 суток", REQ)
    assert len(proposal["warnings"]) == 2  # missing output anchor + unsupported number
    with patch.object(edit, "_json", return_value={"text": "Понятнее", "refs": [], "coverage": {}}):
        editorial = edit.propose_edit(cfg, initial, target["id"], "Сделай проще", REQ)
    assert any("No source" in warning for warning in editorial["warnings"])
    with patch.object(edit, "_json", return_value={"text": "", "refs": []}):
        expect_error(edit.propose_edit, cfg, initial, target["id"], "Сделай проще", REQ)
    expect_error(edit.propose_edit, cfg, initial, target["id"], " ", REQ)
    expect_error(edit.propose_edit, cfg, initial, "p:9999", "Исправь", REQ)
    expect_error(edit.propose_edit, cfg, initial, target["id"], "a" * 3001, REQ)


if __name__ == "__main__":
    test_sections_proposals_and_acceptance()
    test_cell_and_single_paragraph()
    test_unconfirmed_sources_and_errors()
    print("ИТОГ: чат предлагает, пользователь принимает, Word сохраняет структуру, таблицы и ссылочные поля")

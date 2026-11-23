"""Word draft usability: title, long instructions, context, rows and comments.

Fictional-only data, no real document or external LLM requests.
"""
import io
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from docx import Document
from docx.shared import RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import template_draft as draft
from mint.i18n import set_lang

set_lang("ru")


def bytes_of(doc):
    stream = io.BytesIO()
    doc.save(stream)
    return stream.getvalue()


def template():
    doc = Document()
    doc.add_paragraph("Согласование: [Укажите ФИО]")
    doc.add_heading("7.1 Функциональные требования", 1)
    p = doc.add_paragraph("[Содержание раздела должно раскрывать")
    p.runs[0].font.color.rgb = RGBColor(0, 0, 255)
    for i in range(12):
        doc.add_paragraph(f"функции и условия {i + 1}")
    doc.add_paragraph("и обработку ошибок.]")
    p = doc.add_paragraph("Целью обработки является ")
    span = p.add_run("[Укажите цель]")
    span.font.color.rgb = RGBColor(200, 0, 0)
    p.add_run(" на основании [12].")
    doc.add_paragraph("Постоянный текст с настоящей ссылкой [12].")
    doc.add_heading("8 Сокращения и термины", 1)
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Сокращение"
    table.cell(0, 1).text = "Расшифровка"
    table.cell(1, 0).text = "[Укажите сокращение]"
    table.cell(1, 1).text = "[Укажите расшифровку]"
    doc.add_heading("9 Календарный план", 1)
    table = doc.add_table(rows=2, cols=3)
    for i, title in enumerate(("Работа", "Срок", "Результат")):
        table.cell(0, i).text = title
    for i, cell_text in enumerate(("[Укажите работу]", "[Укажите срок]", "[Укажите результат]")):
        table.cell(1, i).text = cell_text
    p = doc.add_paragraph("Пример заполнения:")
    p.runs[0].font.color.rgb = RGBColor(0, 176, 80)
    sample = doc.add_table(rows=2, cols=2)
    sample.cell(0, 0).text = "Работа"
    sample.cell(0, 1).text = "Срок"
    sample.cell(1, 0).text = "Пример"
    sample.cell(1, 1).text = "999 дней"
    doc.add_heading("10 Дополнительные сведения", 1)
    doc.add_paragraph("[Укажите неизвестный реквизит]")
    return doc


def model(_cfg, stage, payload):
    if stage == "layout":
        # Deliberately omit long 7.1: deterministic fallback must still fill it.
        rows = [{"id": b["id"], "target": "[Укажите цель]", "purpose": "Цель обработки"}
                for b in payload["blocks"] if "[Укажите цель]" in b["text"]]
        rows += [{"id": b["id"], "target": "[Укажите неизвестный реквизит]", "purpose": "Неизвестный реквизит"}
                 for b in payload["blocks"] if "[Укажите неизвестный реквизит]" in b["text"]]
        return {"fields": rows, "fixed": []}
    if stage == "extract":
        return {"requirements": [{"quote": line} for line in payload["text"].splitlines() if line.strip()]}
    if stage == "rows":
        heads = payload["columns"]
        rid = payload["requirements"][0]["id"]
        if "Сокращение" in heads:
            return {"rows": [
                {"cells": ["СЗ", "Сервис заявок"], "refs": [rid], "coverage": {rid: "Сервис заявок"}},
                {"cells": ["СЗ", "Сервис заявок"], "refs": [rid], "coverage": {rid: "Сервис заявок"}},
                {"cells": ["СЗ\\nАК", "Сервис заявок\\nАналитический комплекс"],
                 "refs": [rid], "coverage": {rid: "Сервис заявок"}},
            ]}
        if "Результат" in heads:
            return {"rows": [{"cells": ["Настройка уведомлений", "", ""], "refs": [rid],
                              "coverage": {rid: "Настройка уведомлений"}}]}
        return {"rows": []}
    if stage == "fill":
        field = payload["field"]
        if "Содержание раздела" in field:
            assert "обработку ошибок" in payload["paragraph"]
            assert payload["full_block"]
            return {"status": "filled", "text": "Сервис заявок регистрирует заявки.\\n"
                     "При недоступности получателя сообщение ставится в очередь.",
                    "refs": [r["id"] for r in payload["requirements"][:2]], "coverage": {
                        r["id"]: ("Сервис заявок" if i == 0 else "сообщение ставится в очередь")
                        for i, r in enumerate(payload["requirements"][:2])}}
        if field == "Цель обработки":
            assert payload["before"].endswith("является ")
            assert payload["after"] == " на основании [12]."
            return {"status": "filled", "text": "регистрация заявок",
                    "refs": [payload["requirements"][0]["id"]],
                    "coverage": {payload["requirements"][0]["id"]: "регистрация заявок"}}
        return {"status": "missing", "text": "", "refs": [], "reason": "Неизвестный реквизит"}
    if stage == "check":
        assert payload["norms"] == []
        return {"supported": True, "status": "unchecked", "ref": ""}
    raise AssertionError(stage)


def test_usable_draft():
    original = bytes_of(template())
    with TemporaryDirectory() as root:
        cfg = SimpleNamespace(kb_path=Path(root), max_query_chars=900, max_tokens=1800,
                              llm_context_tokens=12000, chars_per_token=2.5)
        source = draft.source_path(cfg, "fiction.md")
        source.parent.mkdir(exist_ok=True)
        source.write_text("# Обработка заявок\nСервис заявок регистрирует заявки.\n"
                          "При недоступности получателя сообщение ставится в очередь.\n"
                          "Настройка уведомлений использует сокращение СЗ: Сервис заявок.\n",
                          encoding="utf-8")
        with patch.object(draft, "_json", side_effect=model), patch.object(
                draft, "search_parent_child", return_value=([], [])):
            result = draft.create_draft(original, cfg, ["fiction.md"])
    output = Document(io.BytesIO(result["docx"]))
    assert output.paragraphs[0].text == "Согласование: [Укажите ФИО]"
    texts = [p.text for p in output.paragraphs]
    assert "Сервис заявок регистрирует заявки." in texts
    assert "При недоступности получателя сообщение ставится в очередь." in texts
    assert any("Целью обработки является регистрация заявок на основании [12]." == x for x in texts)
    assert "Постоянный текст с настоящей ссылкой [12]." in texts
    assert not any("функции и условия" in x or "обработку ошибок.]" in x for x in texts)
    assert not any("Пример заполнения" in x for x in texts)
    assert not any("[Укажите неизвестный реквизит]" in x for x in texts)
    assert "Неизвестный реквизит" in " ".join(result["issues"])
    assert len(output.tables) == 2  # example table removed
    glossary, schedule = output.tables
    assert len(glossary.rows) == 2 and glossary.cell(1, 0).text == "СЗ"
    assert glossary.cell(1, 1).text == "Сервис заявок"
    assert len(schedule.rows) == 2 and schedule.cell(1, 0).text == "Настройка уведомлений"
    assert schedule.cell(1, 1).text == "" and schedule.cell(1, 2).text == ""
    assert not list(output.comments), "No absent-wiki or missing-placeholder comment storm"
    paragraph = next(p for p in output.paragraphs if p.text.startswith("Целью обработки"))
    filled = [run for run in paragraph.runs if run.text == "регистрация заявок"]
    assert len(filled) == 1 and filled[0].font.color.rgb is None
    assert any(r["status"] == "missing" for r in result["results"])
    assert len(result["used"]) > 0


def test_verbatim_norm_and_public_refs():
    text = "Сервис сохраняет журнал 30 суток."
    norm = {"N1": {"id": "N1", "source": "policy.md", "section": "2.1", "quote": text}}
    cfg = SimpleNamespace(max_query_chars=1000)
    with patch.object(draft, "_wiki", return_value=norm), patch.object(
            draft, "_json", return_value={
                "supported": True, "status": "conflict", "ref": "N1",
                "quote": text, "claim_quote": text, "scope_quote": text,
                "applicability": "applicable", "applicability_reason": "Норма действует",
                "reason": "Норма N1 нарушена"}):
        status, detail = draft._verify(cfg, text, [], {}, None, [], [])
        assert status == "checked" and not detail
    other = "Сервис сохраняет журнал 10 суток."
    with patch.object(draft, "_wiki", return_value=norm), patch.object(
            draft, "_json", return_value={
                "supported": True, "status": "conflict", "ref": "N1",
                "quote": text, "claim_quote": other, "scope_quote": other,
                "applicability": "applicable", "applicability_reason": "Норма действует",
                "reason": "Норма N1 нарушена"}):
        status, detail = draft._verify(cfg, other, [], {}, None, [], [])
        assert status == "conflict" and "policy.md" in detail and "N1" not in detail


if __name__ == "__main__":
    test_usable_draft()
    test_verbatim_norm_and_public_refs()
    print("ИТОГ: большой раздел, титул, цвет, грамматический контекст, таблицы, примеры и N1")

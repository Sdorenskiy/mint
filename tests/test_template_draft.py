"""Word drafting from a template or completed example, with fake model responses."""
import io
import json
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


def to_bytes(doc):
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def add_table(doc, rows):
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    for result, values in zip(table.rows, rows):
        for cell, text in zip(result.cells, values):
            cell.text = text
    return table


def mock_model(system, user, *_args, **_kwargs):
    data = json.loads(user)
    if "blocks" in data:
        result = {"fields": []}
        for block in data["blocks"]:
            text = block["text"]
            if "[Указывается режим]" in text:
                result["fields"].append({"id": block["id"], "target": "[Указывается режим]", "purpose": "Режим"})
            if text.startswith("[Указываются сроки"):
                result["fields"].append({"id": block["id"], "target": text, "purpose": "Срок"})
    elif "source" in data:
        result = {"requirements": [{"quote": line} for line in data["text"].splitlines() if line]}
    elif "columns" in data:
        result = {"rows": [{"cells": ["Настройка", "7 дней"], "refs": ["R1"]},
                           {"cells": ["Проверка", ""], "refs": ["R2"]},
                           {"cells": ["Неподтвержденный срок", "90 дней"], "refs": ["R1"]}]}
    elif "field" in data:
        result = ({"status": "filled", "text": "хранение 7 дней", "refs": ["R1"]}
                  if data["field"] != "Срок" else {"status": "missing", "text": "", "refs": []})
    else:
        assert "evidence" in data
        conflict = "7 дней" in data["claims"]
        result = {"supported": True, "status": "conflict" if conflict else "unchecked",
                  "ref": "N1", "quote": "минимум 30 дней", "reason": "7 дней меньше минимума"}
    return json.dumps(result)


def mock_search(query, cfg, **kwargs):
    assert kwargs["exclude_sources"] == ["basis.md"]
    return [{"source": "norm.md", "path": "Хранение", "block": "Предусмотреть хранение минимум 30 дней."}], []


def test_draft():
    doc = Document()
    doc.add_heading("Требования", 1)
    p = doc.add_paragraph("Обязательный текст. ")
    p.runs[0].bold = True
    p.add_run("[Указывается ")
    p.add_run("режим]")
    p.add_run(". Конец.")
    doc.add_paragraph("[Указываются сроки")
    doc.add_paragraph("с учетом условий.]")
    add_table(doc, [["Работа", "Срок"], ["[Указывается работа]", "[Указывается срок]"]])
    p = doc.add_paragraph("ПРИМЕР:")
    p.runs[0].font.color.rgb = RGBColor(0, 176, 80)
    add_table(doc, [["Работа", "Срок"], ["Пример", "90 дней"]])
    original = to_bytes(doc)
    with TemporaryDirectory() as folder:
        cfg = SimpleNamespace(kb_path=Path(folder), max_query_chars=1000, max_tokens=1500)
        path = draft.source_path(cfg, "basis.md")
        path.parent.mkdir(exist_ok=True)
        path.write_text("# Работы\nНастройка предусматривает хранение 7 дней.\nПроверка входит в работы.",
                        encoding="utf-8")
        with patch.object(draft, "ask_llm", mock_model), patch.object(draft, "search_parent_child", mock_search):
            result = draft.create_draft(original, cfg, ["basis.md"])
            output = Document(io.BytesIO(result["docx"]))
            assert output.paragraphs[0].text == "Требования"
            assert output.paragraphs[1].runs[0].bold
            assert output.paragraphs[1].text.startswith("Обязательный текст. хранение 7 дней. Конец.")
            assert "Противоречие с вики" in output.paragraphs[1].text
            assert "Требуется уточнение" in output.paragraphs[2].text
            assert not output.paragraphs[3].text
            assert len(output.tables) == 1 and len(output.tables[0].rows) == 3
            assert "Настройка" in output.tables[0].cell(1, 0).text
            assert output.tables[0].cell(1, 1).text == "7 дней"
            assert "Уточнить" in output.tables[0].cell(2, 1).text
            assert any("норм" in c.text.lower() or "norm.md" in c.text for c in output.comments)
            assert result["used"] == {"R1", "R2"}
            assert any("требует проверки" in x for x in result["issues"])
            assert len(Document(io.BytesIO(original)).tables) == 2

            example = Document()
            example.add_heading("Работы", 1)
            example.add_paragraph("Старый проект. Срок 90 дней.")
            example.add_heading("Параметры", 2)
            add_table(example, [["Работа", "Срок"], ["Старый проект", "90 дней"]])
            result = draft.create_draft(to_bytes(example), cfg, ["basis.md"], example=True)
            output = Document(io.BytesIO(result["docx"]))
            assert [(p.text, p.style.name) for p in output.paragraphs if p.style.name.startswith("Heading")] == [
                ("Работы", "Heading 1"), ("Параметры", "Heading 2")]
            assert "Старый проект" not in output.element.xml and "90 дней" not in output.element.xml
            assert len(output.tables[0].rows) == 3

        with patch.object(draft, "ask_llm", return_value="не JSON"):
            result = draft.create_draft(original, cfg, ["basis.md"])
            assert result["issues"] and not result["used"]

    print("ИТОГ: оба режима, таблицы, следы источников, конфликт, пропуск и сбой проверены")


if __name__ == "__main__":
    test_draft()

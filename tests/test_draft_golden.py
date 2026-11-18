"""Synthetic golden cases for template section planning and Word fidelity.

All source data are fictional; expected statements are authored before model stubs.
The model is deliberately mocked so CI tests remain deterministic and offline.
"""
import io
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from docx import Document
from docx.shared import Cm, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import template_draft as draft
from mint.i18n import set_lang

set_lang("ru")

FACTS = (
    "Сервис заявок должен сохранять журнал операций не менее 30 суток.",
    "Сервис заявок должен подтверждать получение сообщения не позднее 3 секунд.",
    "При недоступности получателя сообщение должно помещаться в очередь повторной доставки.",
)
MISSING = "Укажите утверждённую дату завершения разработки"


def data(doc):
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def template():
    doc = Document()
    doc.add_heading("7.1 Требования к дорабатываемым функциям", level=1)
    p = doc.add_paragraph("[Укажите требования к функции обработки заявок]")
    p.style = "Normal"
    label = doc.add_paragraph("Постоянный текст, который нельзя изменять.")
    label.runs[0].bold = True
    doc.add_heading("9 Календарный план", level=1)
    table = doc.add_table(rows=2, cols=2)
    table.autofit = False
    table.columns[0].width = Cm(0.9)
    table.columns[1].width = Cm(8)
    table.cell(0, 0).text = "№"
    table.cell(0, 1).text = "Работа"
    table.cell(1, 0).text = "[Укажите номер]"
    table.cell(1, 1).text = "[Укажите работу]"
    table.cell(1, 0).paragraphs[0].runs[0].font.color.rgb = RGBColor(0, 0, 200)
    return doc


def fake_model(_cfg, stage, payload):
    if stage == "layout":
        return {"fields": [
            {"id": b["id"], "target": "[Укажите требования к функции обработки заявок]",
             "purpose": "функциональные требования к обработке заявок"}
            for b in payload["blocks"] if "[Укажите требования к функции" in b["text"]
        ] + [{"id": b["id"], "target": "[Укажите номер]", "purpose": "Номер строки"}
             for b in payload["blocks"] if b["text"] == "[Укажите номер]"],
            "fixed": []}
    if stage == "extract":
        return {"requirements": [{"quote": line} for line in payload["text"].splitlines()
                                 if line and not line.startswith("#")]}
    if stage == "rows":
        # Not a row-prototype test: the model correctly finds no justified plan.
        return {"rows": []}
    if stage == "fill":
        if "функциональные" in payload["field"]:
            candidates = {r["quote"]: r["id"] for r in payload["requirements"]}
            assert all(quote in candidates for quote in FACTS), "section plan dropped a source-backed fact"
            return {"status": "filled", "text": "\n".join(FACTS),
                    "refs": [candidates[q] for q in FACTS]}
        return {"status": "missing", "text": "", "refs": []}
    if stage == "check":
        # Source grounding succeeds; absence of wiki norms is not an error.
        return {"supported": True, "status": "unchecked", "ref": "", "quote": "", "reason": ""}
    raise AssertionError(stage)


def test_golden_section_and_word():
    original = template()
    before = data(original)
    with TemporaryDirectory() as folder:
        cfg = SimpleNamespace(kb_path=Path(folder), max_query_chars=1000, max_tokens=1500,
                              llm_context_tokens=16384, chars_per_token=2.5)
        path = draft.source_path(cfg, "fictional_basis.md")
        path.parent.mkdir(exist_ok=True)
        # Distractors are deliberately inserted before the relevant statements.
        distractors = [f"Договор поставки канцелярских товаров содержит пункт {i} о закупках."
                       for i in range(220)]
        path.write_text("# Прочие сведения\n" + "\n".join(distractors) +
                        "\n# Функции обработки заявок\n" + "\n".join(FACTS), encoding="utf-8")
        with patch.object(draft, "_json", side_effect=fake_model), patch.object(
                draft, "search_parent_child", return_value=([], [])):
            result = draft.create_draft(before, cfg, ["fictional_basis.md"])
        after = Document(io.BytesIO(result["docx"]))
        block = after.paragraphs[1].text
        assert all(fact in block for fact in FACTS), block
        assert "Требуется" not in after.element.xml and "Проверка по вики" not in after.element.xml
        assert after.paragraphs[2].runs[0].bold
        assert after.paragraphs[2].text == "Постоянный текст, который нельзя изменять."
        assert len(after.tables) == 1
        assert len(after.tables[0].rows) == 2
        assert "[Укажите номер]" in after.tables[0].cell(1, 0).text  # never invent unknown data
        assert "[Требуется" not in after.tables[0].cell(1, 0).text
        assert before != result["docx"]
        assert after.tables[0].cell(1, 0)._tc.tcPr.xml == original.tables[0].cell(1, 0)._tc.tcPr.xml
        assert any(r["status"] == "missing" for r in result["results"])
        assert len(result["used"]) == 3
        assert result["section_plan"] and any(set(result["used"]) <= set(info["selected_ids"])
                                              for info in result["section_plan"].values())
        assert "metrics" in result and "total_seconds" in result["metrics"]

        def partial_fill(cfg_, stage, payload):
            answer = fake_model(cfg_, stage, payload)
            if stage == "fill" and answer.get("status") == "filled":
                answer["text"] = "\n".join(FACTS[:2])
                answer["refs"] = answer["refs"][:2]
            return answer

        with patch.object(draft, "_json", side_effect=partial_fill), patch.object(
                draft, "search_parent_child", return_value=([], [])):
            partial = draft.create_draft(before, cfg, ["fictional_basis.md"])
        omitted_id = next(req["id"] for req in partial["requirements"] if req["quote"] == FACTS[2])
        assert omitted_id not in partial["used"]
        assert any(omitted_id in ids for ids in partial["unresolved_candidates"].values())
        # A candidate is not automatically an applicable obligation or a verified omission.
        assert not any(r.get("status") == "missing_requirement" for r in partial["results"])


def test_no_model_uses_for_docx_remarks():
    doc = Document()
    doc.add_paragraph("Статический текст")
    p = doc.add_paragraph()
    draft._note(doc, p, "Требуется уточнение", "Нет сведений")
    assert not p.text.strip()
    assert "Требуется уточнение" not in p.text
    assert any("Нет сведений" in c.text for c in doc.comments)


if __name__ == "__main__":
    test_golden_section_and_word()
    test_no_model_uses_for_docx_remarks()
    print("ИТОГ: эталонный раздел, цитаты, неподтвержденные поля, таблица и оформление проверены")

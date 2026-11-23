"""Offline checks: inferred subject is explicitly confirmed and grounds retrieval."""
import io
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from docx import Document

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import document_context as ctx
from mint import template_draft as draft


def _bytes(doc):
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _template():
    doc = Document()
    doc.add_paragraph("Задание на развитие Платформы А")
    doc.add_heading("1 Цель", 1)
    doc.add_paragraph("Платформа А взаимодействует с платформами Б и В.")
    doc.add_heading("7 Функции", 1)
    doc.add_paragraph("[Укажите функции платформы А]")
    return _bytes(doc)


def test_infer_and_confirm():
    template = _template()
    captured = {}

    def answer(cfg, stage, payload):
        assert stage == "context"
        captured.update(payload)
        return {"target": "Платформа А", "objective": "Развитие интеграции",
                "scope": "Передача сообщений", "participants": "Б, В",
                "confidence": "high", "reason": "Заголовок титульного листа"}

    with patch.object(ctx, "_json", side_effect=answer):
        proposed = ctx.infer_context(SimpleNamespace(), template,
                                     ["Требования Б.md", "Общие требования В.docx"])
    assert proposed["target"] == "Платформа А"
    assert "Задание на развитие Платформы А" in captured["template"]["front_matter"]
    assert captured["selected_source_names"][0] == "Требования Б.md"
    assert proposed["reason"].startswith("Заголовок")
    approved = ctx.confirm_context({**proposed, "scope": "Передача и повторная доставка"})
    assert approved["target"] == "Платформа А"
    assert approved["scope"] != proposed["scope"]
    assert ctx.context_search_terms(approved).startswith("Платформа А")
    assert "confidence" not in approved
    try:
        ctx.confirm_context({"target": "    "})
    except draft.DraftError:
        pass
    else:
        raise AssertionError("ambiguous context cannot be silently confirmed")


def test_context_reaches_draft_without_changing_sources():
    original = _template()
    approved = ctx.confirm_context({"target": "Платформа А", "objective": "Обмен",
                                    "scope": "Отправка сообщений", "participants": "Платформа Б"})
    seen = {}
    with TemporaryDirectory() as folder:
        cfg = SimpleNamespace(kb_path=Path(folder), max_query_chars=500, max_tokens=1600,
                              llm_context_tokens=12000, chars_per_token=2.5)
        path = draft.source_path(cfg, "wide_basis.md")
        path.parent.mkdir(exist_ok=True)
        path.write_text("# Платформа Б\nПлатформа Б принимает сообщения.\n"
                        "# Платформа А\nПлатформа А отправляет сообщения.", encoding="utf-8")

        def model(_cfg, stage, payload):
            if stage == "layout":
                return {"fields": [{"id": b["id"], "target": b["text"],
                                    "purpose": "Функции платформы А"}
                                   for b in payload["blocks"] if b["text"].startswith("[Укажите")],
                        "fixed": []}
            if stage == "extract":
                return {"requirements": [{"quote": value} for value in payload["text"].splitlines()
                                         if value.strip()]}
            if stage == "rows":
                return {"rows": []}
            if stage == "fill":
                seen.update(payload)
                return {"status": "filled", "text": "Платформа А отправляет сообщения.",
                        "refs": [r["id"] for r in payload["requirements"]
                                 if "А отправляет" in r["quote"]],
                        "coverage": {r["id"]: "Платформа А отправляет сообщения."
                                     for r in payload["requirements"] if "А отправляет" in r["quote"]}}
            if stage == "check":
                return {"supported": True, "status": "unchecked"}
            raise AssertionError(stage)

        with patch.object(draft, "_json", side_effect=model), patch.object(
                draft, "search_parent_child", return_value=([], [])):
            result = draft.create_draft(original, cfg, ["wide_basis.md"], context=approved)
    assert seen["document_context"]["target"] == "Платформа А"
    assert "scope" in seen["document_context"]
    assert result["document_context"] == approved
    assert "Платформа А отправляет" in result["requirements"][-1]["quote"]
    assert "Платформа А отправляет" in Document(io.BytesIO(result["docx"])).paragraphs[-1].text


if __name__ == "__main__":
    test_infer_and_confirm()
    test_context_reaches_draft_without_changing_sources()
    print("ИТОГ: контекст предложен по шаблону, подтверждён пользователем и передан в генератор")

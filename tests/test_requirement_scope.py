"""Offline checks that broad multi-platform bases do not become target obligations."""
import io
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from docx import Document

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import template_draft as draft
from mint import requirement_scope as scope

CONTEXT = {"target": "Платформа А", "objective": "Интеграция", "scope": "Отправка данных",
           "participants": "Платформа Б"}


def test_scope_classification_and_fail_closed():
    reqs = {f"R{i}": {"id": f"R{i}", "source": "broad.md", "section": "Интеграция",
                      "quote": value} for i, value in enumerate([
        "Платформа А передаёт сообщение Б.",
        "Платформа Б подтверждает получение.",
        "Каждая участвующая платформа обеспечивает защиту канала.",
        "Платформа В хранит события 90 суток.",
        "Участник сохраняет доступность сервиса.",
    ], 1)}
    rows = [
        {"id": "R1", "category": "target", "actor": "Платформа А", "reason": "А передаёт"},
        {"id": "R2", "category": "interaction", "actor": "Платформа Б", "reason": "Б подтверждает"},
        {"id": "R3", "category": "shared", "actor": "Все", "reason": "Каждая участвующая платформа"},
        {"id": "R4", "category": "other", "actor": "Платформа В", "reason": "В хранит"},
        # R5 intentionally omitted: do not invent its applicability.
    ]
    with patch.object(scope, "_json", return_value={"items": rows}):
        issues = []
        result = scope.classify(SimpleNamespace(), reqs, CONTEXT, issues, lambda *_: None)
    direct, interactions = scope.partition(result, CONTEXT)
    assert set(direct) == {"R1", "R3"}
    assert set(interactions) == {"R2"}
    assert scope.category_of(result["R4"]) == "other"
    assert scope.category_of(result["R5"]) == "uncertain"
    assert any("1 требований" in x for x in issues)
    assert scope.partition(reqs, None)[0] == reqs  # old tests/callers
    with patch.object(scope, "_json", side_effect=draft.DraftError("invalid JSON")):
        failed = scope.classify(SimpleNamespace(), reqs, CONTEXT, [], lambda *_: None)
    assert all(scope.category_of(v) == "uncertain" for v in failed.values())


def test_target_draft_never_uses_other_platform_requirements():
    doc = Document()
    doc.add_heading("7 Функции Платформы А", 1)
    doc.add_paragraph("[Укажите функции Платформы А]")
    buf = io.BytesIO()
    doc.save(buf)
    with TemporaryDirectory() as directory:
        cfg = SimpleNamespace(kb_path=Path(directory), max_query_chars=1000,
                              max_tokens=1800, llm_context_tokens=12000, chars_per_token=2.5)
        path = draft.source_path(cfg, "multiplatform.md")
        path.parent.mkdir(exist_ok=True)
        path.write_text("# Функции\nПлатформа А отправляет сообщения.\n"
                        "Платформа Б подтверждает приём.\n"
                        "Платформа В хранит данные 90 суток.", encoding="utf-8")
        seen = {}

        def model(_cfg, stage, payload):
            if stage == "layout":
                return {"fields": [{"id": b["id"], "target": b["text"], "purpose": "Функции А"}
                                   for b in payload["blocks"] if "Укажите функции" in b["text"]],
                        "fixed": []}
            if stage == "extract":
                return {"requirements": [{"quote": line} for line in payload["text"].splitlines()
                                         if line.strip()]}
            if stage == "scope":
                return {"items": [{"id": r["id"],
                                   "category": ("target" if "А отправляет" in r["quote"] else
                                                "interaction" if "Б подтверждает" in r["quote"] else "other"),
                                   "actor": "Платформа А" if "А отправляет" in r["quote"] else "Внешняя",
                                   "reason": "А отправляет" if "А отправляет" in r["quote"] else
                                             "Обязанность внешней платформы"}
                                  for r in payload["requirements"]]}
            if stage == "fill":
                seen.update(payload)
                assert len(payload["requirements"]) == 1
                assert "А отправляет" in payload["requirements"][0]["quote"]
                assert "Б подтверждает" in payload["external_context"][0]["quote"]
                key = payload["requirements"][0]["id"]
                return {"status": "filled", "text": "Платформа А отправляет сообщения.",
                        "refs": [key], "coverage": {key: "Платформа А отправляет сообщения."}}
            if stage == "check":
                assert "Платформа В" not in payload["claims"]
                return {"supported": True, "status": "unchecked"}
            if stage == "rows":
                return {"rows": []}
            raise AssertionError(stage)

        with patch.object(draft, "_json", side_effect=model), patch.object(
                scope, "_json", side_effect=model), patch.object(
                draft, "search_parent_child", return_value=([], [])):
            result = draft.create_draft(buf.getvalue(), cfg, ["multiplatform.md"], context=CONTEXT)
    assert seen and len(result["requirements"]) == 3
    assert result["scope_counts"] == {"target": 1, "shared": 0, "interaction": 1, "other": 1, "uncertain": 0}
    assert "Платформа В" not in Document(io.BytesIO(result["docx"])).paragraphs[-1].text
    assert len(result["used"]) == 1


def test_missing_actor_cannot_be_confirmed():
    requirements = {f"R{idx}": {"id": f"R{idx}", "source": "basis.md",
                                "section": "1", "quote": "Обязанность " + str(idx)}
                    for idx in range(1, 5)}
    answers = [
        {"id": "R1", "category": "target", "actor": "", "reason": "Целевая обязанность"},
        {"id": "R2", "category": "shared", "actor": "  ", "reason": "Общее требование"},
        {"id": "R3", "category": "interaction", "actor": "", "reason": "Внешняя сторона"},
        {"id": "R4", "category": "target", "actor": "Платформа А", "reason": "А выполняет"},
    ]
    issues = []
    with patch.object(scope, "_json", return_value={"items": answers}):
        classified = scope.classify(SimpleNamespace(), requirements, CONTEXT,
                                    issues, lambda *_: None)
    assert {key for key, item in classified.items()
            if scope.category_of(item) == "uncertain"} == {"R1", "R2", "R3"}
    assert scope.category_of(classified["R4"]) == "target"
    assert set(scope.partition(classified, CONTEXT)[0]) == {"R4"}
    assert any("3 требований" in issue for issue in issues)


if __name__ == "__main__":
    test_scope_classification_and_fail_closed()
    test_target_draft_never_uses_other_platform_requirements()
    test_missing_actor_cannot_be_confirmed()
    print("ИТОГ: сохранены роли внешних участников и не допущен перенос чужих обязанностей")

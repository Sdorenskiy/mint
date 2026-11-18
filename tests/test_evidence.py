"""Synthetic, deterministic checks for the shared proof contract.

No external model calls and no confidential source documents.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mint import evidence
from mint import template_draft as draft
from mint import audit
from mint.i18n import set_lang
set_lang("ru")

CLAIM = "Система Портал-2 обрабатывает персональные данные. Журналы операций хранятся 20 суток."
NORM = "Для систем, обрабатывающих персональные данные, журналы операций хранятся не менее 30 суток."
OTHER = "Система Архив хранит журналы операций не менее 90 суток."


def proposal(**changes):
    v = {"status": "conflict", "ref": "N1", "claim_quote": "Журналы операций хранятся 20 суток.",
         "norm_quote": NORM, "reason": "20 меньше обязательного минимума 30",
         "applicability": "applicable",
         "applicability_reason": "Портал-2 обрабатывает персональные данные"}
    return {**v, **changes}


def test_evidence():
    ok = evidence.verify_comparison(CLAIM, NORM, proposal())
    assert ok["status"] == "conflict", ok
    assert evidence.verify_comparison(CLAIM, NORM, proposal(
        applicability="different_scope", norm_quote=NORM))["status"] == "unchecked"
    assert evidence.verify_comparison(CLAIM, NORM, proposal(
        applicability="unclear"))["status"] == "uncertain"
    assert evidence.verify_comparison(CLAIM, NORM, proposal(
        applicability_reason=""))["status"] == "uncertain"
    assert evidence.verify_comparison(CLAIM, NORM, proposal(
        norm_quote=OTHER))["status"] == "uncertain"
    assert evidence.verify_comparison(CLAIM, NORM, proposal(
        claim_quote="Таблица 12 из другого документа"))["status"] == "uncertain"

    # No difference other than a local table identifier: not a semantic clash.
    table_claim = "План работ представлен в таблице 7."
    table_norm = "План работ представлен в таблице 3."
    assert evidence.only_table_number_diff(table_claim, table_norm)
    assert evidence.verify_comparison(table_claim, table_norm, {
        "status": "conflict", "ref": "N1", "claim_quote": table_claim,
        "norm_quote": table_norm, "reason": "номера различаются",
        "applicability": "applicable", "applicability_reason": "общий план"})["status"] == "unchecked"

    norms = ("=== ИСТОЧНИК: Регламент_ИБ.docx | Раздел в начале фрагмента: 2.1 ===\n" + NORM +
             "\n=== ИСТОЧНИК: Описание_Архива.md | Раздел в начале фрагмента: Логи ===\n" + OTHER)
    assert evidence.quoted(NORM, evidence.source_context(norms, "Регламент_ИБ.docx"))
    assert not evidence.quoted(OTHER, evidence.source_context(norms, "Регламент_ИБ.docx"))
    assert evidence.source_reference("Замечание [Источник: Регламент_ИБ.docx, 2.1]") == ("Регламент_ИБ.docx", "2.1")
    assert evidence.source_reference("Внутреннее несоответствие") is None
    assert evidence.source_context(norms, "НетТакогоФайла") == ""


def test_draft_uses_common_proof():
    cfg = SimpleNamespace()
    norms = {"N1": {"id": "N1", "source": "Регламент_ИБ.docx", "section": "2.1", "quote": NORM}}
    reqs = {"R1": {"id": "R1", "source": "Основание.md", "section": "1", "quote": CLAIM}}
    base = {"supported": True, "status": "conflict", "ref": "N1",
            "claim_quote": proposal()["claim_quote"], "quote": NORM,
            "reason": proposal()["reason"], "applicability": "applicable",
            "applicability_reason": proposal()["applicability_reason"]}
    issues = []
    with patch.object(draft, "_wiki", return_value=norms), patch.object(draft, "_json", return_value=base):
        status, detail = draft._verify(cfg, CLAIM, ["R1"], reqs, None, issues, ["Основание.md"])
    assert status == "conflict" and "Регламент_ИБ.docx" in detail
    with patch.object(draft, "_wiki", return_value=norms), patch.object(
            draft, "_json", return_value={**base, "applicability": "different_scope"}):
        status, _ = draft._verify(cfg, CLAIM, ["R1"], reqs, None, issues, ["Основание.md"])
    assert status == "unchecked"
    with patch.object(draft, "_wiki", return_value=norms), patch.object(
            draft, "_json", return_value={**base, "supported": False, "support_reason": "Добавлена новая обязанность"}):
        status, _ = draft._verify(cfg, CLAIM, ["R1"], reqs, None, issues, ["Основание.md"])
    assert status == "manual"  # Independent source-grounding check overrides wiki.


def test_audit_uses_common_proof():
    norms = "=== ИСТОЧНИК: Регламент_ИБ.docx | 2.1 ===\n" + NORM
    finding = {"severity": "СРЕДНИЙ", "text":
               "Хранение журналов не соответствует требованиям [Источник: Регламент_ИБ.docx, 2.1]",
               "quote": "", "part": 1}
    answer = [{"n": 1, "verdict": "ОСТАВИТЬ", "severity": "СРЕДНИЙ",
               "quote": proposal()["claim_quote"], "text": finding["text"],
               "norm_quote": NORM, "comparison": "conflict", "reason": proposal()["reason"],
               "applicability": "applicable",
               "applicability_reason": proposal()["applicability_reason"]}]
    with patch.object(audit, "ask_llm", return_value=json.dumps(answer, ensure_ascii=False)):
        kept, dropped = audit.critique_findings(CLAIM, norms, [finding], SimpleNamespace())
    assert not dropped
    assert kept[0]["evidence"]["status"] == "conflict"
    answer[0]["norm_quote"] = OTHER
    with patch.object(audit, "ask_llm", return_value=json.dumps(answer, ensure_ascii=False)):
        kept, _ = audit.critique_findings(CLAIM, norms, [finding], SimpleNamespace())
    assert kept[0]["evidence"]["status"] == "uncertain"

    # Confirm that both source references survive a same-remedy merge.
    left = {"severity": "СРЕДНИЙ",
            "text": "Недостаточный срок [Источник: Регламент А.docx, 1]", "quote": ""}
    right = {"severity": "СРЕДНИЙ",
             "text": "Недостаточный срок [Источник: Регламент Б.docx, 2]", "quote": ""}
    audit._absorb(left, right)
    assert "Регламент А.docx" in left["text"] and "Регламент Б.docx" in left["text"]


if __name__ == "__main__":
    test_evidence()
    test_draft_uses_common_proof()
    test_audit_uses_common_proof()
    print("ИТОГ: общие доказательства, применимость, чужие источники, номера таблиц, ссылки и аудит")

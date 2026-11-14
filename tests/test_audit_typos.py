"""[integration/unit] Optional language checks, report filtering and conservative typo deduplication."""
import os
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness

W = harness.make_project(prefix="mint_typos_")
os.environ.update(MINT_CONFIG=str(W / "config.yaml"), LOG_DIR=str(W / "logs"), KB_DIR=str(W / "kb"),
                  LLM_API_URL="http://127.0.0.1:9/v1", MINT_LANG="ru")
app = harness.load_mint(W, include_ui=False)
from mint import audit, deep_checks, audit_store

cfg, _ = app.load_settings()
check = harness.Checker()
check(cfg.audit_typos is False, "language checks are off by default")
(W / "config.yaml").write_text("audit_typos: true\n", encoding="utf-8")
loaded, notes = app.load_settings()
check(loaded.audit_typos and "audit_typos" in loaded.explicit_fields, "persistent YAML setting is recognised")
cfg = replace(cfg, audit_summary_max=0, use_self_critique=False, audit_merge_duplicates=False, audit_passes=1)
md = "# 1. Назначение\n\nДокумент описывает хранение журналов событий в соотвествии с требованиями."
typo = '- [НИЗКИЙ] Опечатка: «соотвествии» → «соответствии»'
technical = '- [СРЕДНИЙ] 1: Не указан срок хранения журналов событий.'


def deep_reply(system, *args, **kwargs):
    if "ТОЛЬКО JSON-массив" in system:
        return "[]"
    return typo if "Найди в тексте явные опечатки" in system else "Часть чистая"


def finding(text, section="1"):
    return {"severity": "НИЗКИЙ", "text": text, "quote": "", "sections": [section], "origins": [section]}


try:
    for enabled in (False, True):
        with patch.object(audit, "ask_llm", return_value=typo + "\n" + technical), \
             patch.object(deep_checks, "ask_llm", side_effect=deep_reply) as calls:
            res = app.run_audit(md, "test.md", replace(cfg, audit_typos=enabled), use_wiki=False,
                               deep=True, retry_failed=False)
        language_calls = [c for c in calls.call_args_list if "Найди в тексте явные опечатки" in c.args[0]]
        check(bool(language_calls) == enabled, f"language requests follow the toggle: {enabled}")
        check(any("ТОЛЬКО JSON-массив" in c.args[0] for c in calls.call_args_list), "other deep checks still run")
        check(any("срок хранения" in f["text"] for f in res["findings"]), "technical finding retained")
        check(bool(res["typos"]) == enabled, f"typo result follows toggle: {enabled}")
        check(("соотвествии" in res["report"]) == enabled, f"report follows toggle: {enabled}")
        if not enabled:
            check(all(not audit.is_typo(f) for f in res["findings"] + res["unverified"]), "all exported findings filtered")
            saved = audit_store.load_audit(cfg, audit_store.save_audit(cfg, res, "test.md"))
            check("соотвествии" not in saved["report"] and all(not audit.is_typo(f) for f in saved["result"]["findings"]),
                  "saved report and findings remain filtered")
    alternate = typo + '\n- [НИЗКИЙ] Опечатка: «соотвествии» → «соответствия»'
    with patch.object(audit, "ask_llm", return_value=alternate):
        res = app.run_audit(md, "test.md", replace(cfg, audit_typos=True), use_wiki=False, deep=False, retry_failed=False)
    check(len(res["typos"]) == 2, "different corrections survive the whole assembly pipeline")
    exact = audit.clean_typos([finding("Опечатка: пропущена буква в слове название", "a"),
                              finding("Опечатка: пропущена буква в слове название", "b")])
    check(len(exact) == 1 and exact[0]["sections"] == ["a", "b"], "exact duplicates without arrows merge with locations")
    pair = '«ошбка» → «ошибка»'
    merged = audit.clean_typos([finding(pair, "a"), finding(pair, "b")])
    check(len(merged) == 1 and merged[0]["origins"] == ["a", "b"], "same correction keeps both origins")
    cases = [(pair, '«ошбка» → «ошибки»'),
             (pair + '; «тес» → «тест»', pair + '; «кодд» → «код»'),
             ('«все» → «всё»', '«все» → «все»'),
             ('«москва» → «Москва»', '«москва» → «москва»')]
    for a, b in cases:
        check(len(audit.clean_typos([finding(a), finding(b)])) == 2, f"distinct corrections retained: {a} / {b}")
finally:
    shutil.rmtree(W, ignore_errors=True)
check.finish()

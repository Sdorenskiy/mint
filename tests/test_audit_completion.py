"""[integration] Incomplete checks must not result in automatic document approval."""
import os
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness

W = harness.make_project(prefix="mint_audit_completion_")
os.environ.update(LLM_API_URL="http://127.0.0.1:9/v1", LLM_MODEL="completion-test", MINT_LANG="ru",
                  MINT_CONFIG=str(W / "none.yaml"), LOG_DIR=str(W / "logs"), KB_DIR=str(W / "kb"))
app = harness.load_mint(W, include_ui=False)
from mint import audit, deep_checks, audit_store
from mint.i18n import use_lang

cfg, _ = app.load_settings()
cfg = replace(cfg, llm_retries=1, audit_summary_max=0, audit_passes=1,
              use_self_critique=False, audit_merge_duplicates=False)
md = "# 1. Назначение\n\nДокумент описывает порядок хранения журналов событий системы."
check = harness.Checker()


def run(reply="Часть чистая", deep=False, deep_reply="Часть чистая", checklist=None):
    with patch.object(audit, "ask_llm", return_value=reply), patch.object(deep_checks, "ask_llm", return_value=deep_reply):
        return app.run_audit(md, "test.md", cfg, use_wiki=False, retry_failed=False, deep=deep, checklist=checklist)


try:
    for text in ("", " ", "ok", "Часть чистая\n\n⚠️ Ответ обрезан: test", "Часть чистая\n\n⚠️ Answer truncated: test"):
        res = run(text)
        check(res["completion"]["status"] == "incomplete" and res["failed_sections"],
              f"invalid/partial section is incomplete: {text!r}")
        check("ДОКУМЕНТ СОГЛАСОВАН" not in res["report"], "no false approval")
    res = run(deep=True, deep_reply="❌ [ТАЙМАУТ]")
    check(not res["failed_sections"] and res["completion"]["failed"] > 0
          and res["completion"]["status"] == "incomplete", "deep failure counts even when main sections succeeded")
    check("ПРОВЕРЕНО НЕ ПОЛНОСТЬЮ" in res["report"], "report explicitly incomplete")
    aid = audit_store.save_audit(cfg, res, "test.md")
    saved = audit_store.load_audit(cfg, aid)
    check(saved["result"]["completion"] == res["completion"], "completeness survives saving and reopening")
    with patch.object(audit, "ask_llm", return_value="Часть чистая"), patch.object(deep_checks, "ask_llm", side_effect=lambda system, *a, **kw: "[]" if "ТОЛЬКО JSON-массив" in system else "Часть чистая"):
        fixed = app.recheck_failed_sections(res, "test.md", cfg)
    check(fixed["completion"]["status"] == "complete", "successful recheck recomputes completeness")
    for kind in ("focus", "checklist", "systems"):
        state = {"results": [{"failed": False}], kind: [{"failed": True}]}
        check(audit.audit_completion(state)["failed"] == 1, f"{kind} failure included")
    state = {"results": [{"failed": False}], "passes": [{"results": [{"failed": True}], "deep": []}], "deep_skipped": 2}
    coverage = audit.audit_completion(state)
    check(coverage == {"status": "incomplete", "total": 4, "completed": 1, "failed": 1, "skipped": 2},
          "additional passes and skipped tasks included")
    check(audit.audit_completion({"sections": ["a", "b"], "results": [{"failed": False}]})["skipped"] == 1,
          "missing planned section is not silently counted complete")
    from mint.ui import theme
    for lang in ("ru", "en"):
        with use_lang(lang):
            complete = run()
            stamp = theme.audit_verdict_html([], 0, 1)
            check("Согласовано" not in stamp and "Approved" not in stamp, f"{lang}: UI does not approve document")
            check("mint-verdict--incomplete" in theme.audit_verdict_html([], 1, 1), f"{lang}: incomplete UI stamp")
        check(complete["completion"]["status"] == "complete", f"{lang}: complete checks counted")
        check("ДОКУМЕНТ СОГЛАСОВАН" not in complete["report"] and "DOCUMENT APPROVED" not in complete["report"],
              f"{lang}: automatic checks do not approve document")
    for raw in ("bad json", "", "[{}]", "[1]", "[]"):
        task = {"kind": "claims", "system_key": "deep_claims_system", "user": "test", "sections": ["x"], "title": "Claims"}
        with patch.object(deep_checks, "ask_llm", return_value=raw):
            entry = deep_checks.run_task(task, cfg)
        check(entry["failed"] == (raw != "[]"), f"claims JSON validation: {raw!r}")
finally:
    shutil.rmtree(W, ignore_errors=True)
check.finish()

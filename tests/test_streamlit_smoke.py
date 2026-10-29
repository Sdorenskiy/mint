"""Смоук-тест страницы MINT на настоящем Streamlit (streamlit.testing.v1.AppTest), без браузера:
страница открывается, чат отвечает, кнопки 👍/👎 и комментарий работают, «Новый чат» есть всегда и очищает историю,
сохранённый аудит открывается из «📂 Мои аудиты» и замечания размечаются, профиль меняет критерии и набор промптов,
консультант отвечает со схемой в своём разговоре, документ удаляется из базы с подтверждением.

Запуск из корня проекта:  python tests/test_streamlit_smoke.py
Если настоящий Streamlit не установлен, тест пропускается (на GitHub он установлен).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402
import mock_server  # noqa: E402

CHILD = r'''
import json, traceback
from streamlit.testing.v1 import AppTest

res = {"errors": []}


def has_button(at, key):
    try:
        at.button(key=key)
        return True
    except Exception:
        return False


def errors(at):
    return [str(e.message) + "\n" + "\n".join(str(x) for x in (e.stack_trace or [])[-10:]) for e in at.exception]


try:
    at = AppTest.from_file("app.py", default_timeout=120)
    at.run()
    res["errors"] += errors(at)
    res["titles"] = [str(m.value) for m in at.markdown if "mint-wordmark" in str(m.value)]
    res["theme"] = any("mint-theme-anchor" in str(m.value) for m in at.markdown)
    res["tabs"] = len(at.tabs)
    res["new_chat_empty"] = has_button(at, "chat_clear_btn")
    if not at.exception:
        at.chat_input[0].set_value("Какие требования к журналам?").run()
        res["errors"] += errors(at)
        res["new_chat_after_answer"] = has_button(at, "chat_clear_btn")
        msgs = at.session_state["messages"]
        res["messages"] = len(msgs)
        res["answer"] = msgs[-1]["content"][:200] if msgs else ""
        aid = msgs[-1].get("id") if msgs else None
        if aid:
            at.button(key=f"fb_up_chat_{aid}").click().run()
            res["errors"] += errors(at)
            at.text_input(key=f"fb_text_chat_{aid}").set_value("Комментарий из смоук-теста").run()
            at.button(key=f"fb_send_chat_{aid}").click().run()
            res["errors"] += errors(at)
        at.button(key="chat_clear_btn").click().run()
        res["errors"] += errors(at)
        res["messages_after_clear"] = len(at.session_state["messages"])
        # переключение языка настоящим виджетом
        at.selectbox(key="ui_lang").set_value("en").run()
        res["errors"] += errors(at)
        res["titles_en"] = [str(m.value) for m in at.markdown if "mint-wordmark" in str(m.value)]
        res["tabs_en"] = [str(t.label) for t in at.tabs]
        at.chat_input[0].set_value("How long are logs kept?").run()
        res["errors"] += errors(at)
        res["answer_en"] = at.session_state["messages"][-1]["content"][:200]
        # сохранённый аудит: открыть из «Моих аудитов» и разметить замечания настоящими виджетами
        at.selectbox(key="ui_lang").set_value("ru").run()
        from mint.audit_store import load_audit, save_audit
        from mint.config import load_settings
        cfg_, _ = load_settings()
        f1 = {"severity": "КРИТИЧНЫЙ", "text": "Не указан срок хранения журналов", "quote": "", "sections": ["2. Журналы"],
              "origins": ["s1"]}
        f2 = {"severity": "СРЕДНИЙ", "text": "Шаг 2 не связан с шагом 3", "quote": "", "sections": ["3. Процесс"],
              "origins": ["deep:step#1"], "source": "deep", "check": "step"}
        aid_ = save_audit(cfg_, {"findings": [f1, f2], "by_section": [("2. Журналы", [f1]), ("3. Процесс", [f2])],
                                 "report": "# ЭКСПЕРТНОЕ ЗАКЛЮЧЕНИЕ\n", "log_md": "# Лог\n", "failed_sections": [],
                                 "sections": 2, "special": "", "focus": "", "prompts": "p"}, "Пример.md")
        at.run()
        at.selectbox(key="tab2_saved_pick").set_value(aid_).run()
        at.button(key="tab2_saved_open").click().run()
        res["errors"] += errors(at)
        res["reopened"] = bool(at.session_state["tab2_reopened"])
        rows_ = at.session_state["tab2_rows"]
        k0, k1 = (f"rv::{aid_}::{rows_[i]['key']}" for i in (0, 1))
        at.radio(key=k0 + "::v").set_value("ok").run()
        at.radio(key=k1 + "::v").set_value("wrong").run()
        res["errors"] += errors(at)
        at.selectbox(key=k1 + "::r").set_value("present").run()
        at.text_input(key=k0 + "::c").set_value("согласен").run()
        res["errors"] += errors(at)
        res["marks"] = load_audit(cfg_, aid_)["review"]["marks"]
        res["keys"] = [rows_[0]["key"], rows_[1]["key"]]
        at.run()
        res["radio_after"] = [at.radio(key=k0 + "::v").value, at.radio(key=k1 + "::v").value]
        res["errors"] += errors(at)
        # профиль: по умолчанию архитектурный (промпты до профилей); выбран универсальный — его критерии в поле
        from mint.prompts import profile_audit_focus
        res["focus_expect"] = [profile_audit_focus("architecture", "ru"), profile_audit_focus("general", "ru")]
        res["focus_default"] = at.text_area(key="tab2_user_focus").value
        at.chat_input[0].set_value("Какие требования к журналам?").run()
        res["errors"] += errors(at)
        res["arch_prompts"] = at.session_state["messages"][-1].get("prompts", "")
        at.selectbox(key="mint_profile").set_value("general").run()
        res["errors"] += errors(at)
        res["focus_general"] = at.text_area(key="tab2_user_focus").value
        # документы в базе: число документов и векторов, список; удаление: выбрать → «Удалить выбранные» →
        # подтвердить (настоящие виджеты и колбэки)
        from mint.kb import list_kb_documents, process_and_add_to_kb
        from mint.limits import resolve_model_limits, resolve_settings
        cfg_kb, _ = resolve_settings(cfg_, resolve_model_limits(cfg_, {}, None, {}), {})
        for name_, text_ in (("Памятка_А.md", "# Памятка А\n\n## 1. Хранение\n\nФайлы хранятся 30 дней.\n"),
                             ("Памятка_Б.md", "# Памятка Б\n\n## 1. Доступ\n\nДоступ выдаёт администратор.\n")):
            res["indexed"] = res.get("indexed", []) + [process_and_add_to_kb(name_, text_.encode("utf-8"), cfg_kb)[0]]
        at.run()
        res["errors"] += errors(at)
        res["metrics"] = [[str(m.label), str(m.value)] for m in at.metric]
        res["docs_list"] = [str(m.value) for m in at.markdown if str(m.value).startswith('<ul class="mint-kbdocs"')]
        # консультант: своё поле ввода и свой разговор; ход работы (st.status), ответ, «Что нашёл в вики»
        at.chat_input(key="consult_field").set_value("Нарисуй схему: как хранятся файлы и кто выдаёт доступ").run()
        res["errors"] += errors(at)
        cm_ = at.session_state["consult_messages"]
        res["consult"] = {"n": len(cm_), "kind": cm_[-1].get("kind") if cm_ else None,
                          "diagrams": len(cm_[-1].get("diagrams") or []) if cm_ else 0,
                          "error": cm_[-1].get("error") if cm_ else True,
                          "shown": any("📄 Как устроено сейчас" in str(m.value) for m in at.markdown),
                          "found": any("Что нашёл в вики" in str(e.label) for e in at.expander),
                          "chat_untouched": len(at.session_state["messages"])}
        at.button(key="consult_clear_btn").click().run()
        res["errors"] += errors(at)
        res["consult"]["after_clear"] = len(at.session_state["consult_messages"])
        doc_ = "Памятка_А.md"
        res["docs_before"] = len(list_kb_documents(cfg_)[0])
        at.multiselect(key="kb_del_pick").set_value([doc_]).run()
        at.button(key="kb_del_ask").click().run()
        res["errors"] += errors(at)
        res["del_confirm"] = any("Удалить из базы документов: 1?" in str(w.value) for w in at.warning)
        at.button(key="kb_del_yes").click().run()
        res["errors"] += errors(at)
        res["docs_after"] = len(list_kb_documents(cfg_)[0])
        res["del_gone"] = doc_ not in list_kb_documents(cfg_)[0]
        res["del_pick_after"] = list(at.multiselect(key="kb_del_pick").value)
        res["alerts"] = [str(s.value)[:120] for s in at.success]     # эмодзи в начале Streamlit выносит в значок
        res["del_msg"] = any("Удалено из базы: Памятка_А.md" in a for a in res["alerts"])
except Exception:
    res["errors"].append(traceback.format_exc())
print("RESULT" + json.dumps(res, ensure_ascii=False))
'''


def clean_env(extra):
    """Окружение без заглушек: настоящий Streamlit; faiss — настоящий или заглушка, если его нет."""
    paths = [str(extra["PROJECT"])] + ([] if harness.REAL_FAISS else [str(harness.TESTS / "fallback")])
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH",)}
    env.update({k: str(v) for k, v in extra.items() if k != "PROJECT"})
    env.update({"PYTHONPATH": os.pathsep.join(paths), "PYTHONUTF8": "1"})
    return env


probe = subprocess.run([sys.executable, "-c", "import streamlit.testing.v1"], env=clean_env({"PROJECT": harness.ROOT}),
                       capture_output=True, text=True)
if probe.returncode != 0:
    print("  — настоящий Streamlit не установлен: смоук-тест страницы пропущен")
    print("\nИТОГ: пропущено (нет Streamlit)")
    sys.exit(0)

W = harness.make_project(prefix="mint_smoke_", extra_files=("app.py", ".streamlit"))
(W / "smoke_child.py").write_text(CHILD, encoding="utf-8")
srv = mock_server.start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/v1"
env = clean_env({
    "PROJECT": W, "LLM_API_URL": BASE, "EMBED_API_URL": BASE + "/embeddings", "RERANK_API_URL": BASE + "/rerank",
    "LLM_MODEL": "test-llm", "EMBED_MODEL": "emb-model", "RERANK_MODEL": "rr-model", "LLM_API_KEY": "k",
    "KB_DIR": W / "kb", "LOG_DIR": W / "logs", "MINT_CONFIG": W / "none.yaml", "GLOSSARY_PATH": W / "none.json", "MINT_LANG": "ru",
})
check = harness.Checker()
r = subprocess.run([sys.executable, "smoke_child.py"], cwd=W, env=env, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=600)
line = next((x for x in r.stdout.splitlines() if x.startswith("RESULT")), None)
res = json.loads(line[6:]) if line else {"errors": [r.stdout[-2000:] + r.stderr[-3000:]]}
ver = subprocess.run([sys.executable, "-c", "import streamlit; print(streamlit.__version__)"], env=env,
                     capture_output=True, text=True).stdout.strip()
print(f"  Streamlit {ver}")

# ошибки — одной строкой: на GitHub в аннотацию попадают только строки с «✗», и трассировка видна целиком
check(not res["errors"], "страница и действия без исключений", " ⏎ ".join(res["errors"]).replace("\n", " ⏎ ")[-3000:])
check(any("MINT" in t for t in res.get("titles", [])) and res.get("theme"), f"шапка MINT и стили на странице: {str(res.get('titles'))[:200]}")
check(res.get("tabs") == 4, f"четыре вкладки: {res.get('tabs')}")
check(res.get("new_chat_empty") and res.get("new_chat_after_answer"),
      "«Новый чат» есть всегда: в пустом чате и сразу после первого ответа")
cons = res.get("consult") or {}
check(cons.get("n") == 2 and cons.get("kind") == "diagram" and cons.get("diagrams") == 1 and not cons.get("error")
      and cons.get("shown") and cons.get("found") and cons.get("after_clear") == 0,
      f"«Консультант»: ответ со схемой, «Что нашёл в вики», «Новый разговор»: {cons}")
metrics = dict(map(tuple, res.get("metrics") or []))
docs_list = (res.get("docs_list") or [""])[0]
check(res.get("indexed") == [True, True] and metrics.get("Документов") == "2" and docs_list.count("<li") == 2
      and "Памятка_<wbr>Б.md" in docs_list and "Векторов" in metrics,
      f"боковая панель: число документов и векторов, список документов: {metrics}, {res.get('indexed')}")
check(res.get("messages") == 2 and res.get("answer"), f"чат ответил: {res.get('answer', '')[:80]!r}")
fb = W / "logs" / "feedback.jsonl"
rows = [json.loads(x) for x in fb.read_text(encoding="utf-8").splitlines()] if fb.exists() else []
check([x.get("rating") for x in rows] == ["up", "comment"], f"оценка и комментарий записаны: {[x.get('rating') for x in rows]}")
check(res.get("messages_after_clear") == 0, "«Новый чат» очищает историю")
check(any("An intelligent RAG system" in t for t in res.get("titles_en", [])) and "📋 Document review" in res.get("tabs_en", [])
      and "🧠 Consultant" in res.get("tabs_en", []),
      "переключатель языка: интерфейс на английском", f"{str(res.get('titles_en'))[-200:]}, {res.get('tabs_en')}")
check(str(res.get("answer_en", "")).startswith("Answer from the context"), f"чат на английском: {res.get('answer_en')!r}")
k0, k1 = res.get("keys") or ("", "")
check(res.get("reopened") and res.get("marks") == {k0: {"verdict": "ok", "comment": "согласен"},
                                                   k1: {"verdict": "wrong", "reason": "present"}},
      f"сохранённый аудит открывается, отметки и причина сохраняются: {res.get('marks')}")
check(res.get("radio_after") == ["ok", "wrong"], f"отметки не сбрасываются после перерисовки: {res.get('radio_after')}")
check(res.get("focus_expect") and [res.get("focus_default"), res.get("focus_general")] == res["focus_expect"],
      "профиль: по умолчанию архитектурные критерии, выбран универсальный — его критерии")
check(res.get("del_confirm") and res.get("del_gone") and res.get("docs_after") == res.get("docs_before", 0) - 1
      and res.get("del_pick_after") == [] and res.get("del_msg"),
      f"удаление документа: подтверждение, документ удалён, выбор очищен, сообщение "
      f"({res.get('docs_before')} → {res.get('docs_after')}, {res.get('del_confirm')}, {res.get('del_pick_after')}, "
      f"{res.get('alerts')})")
check(res.get("arch_prompts") == "ru-8fd10871",
      f"профиль по умолчанию — набор промптов до профилей: {res.get('arch_prompts')}")

if os.environ.get("GITHUB_ACTIONS") == "true" and not check.fails:   # видно в интерфейсе GitHub и через API
    print(f"::notice title=Смоук-тест страницы::Streamlit {ver}: страница, чат, 👍 и комментарий, «Новый чат», "
          "переключение на английский, разбор замечаний сохранённого аудита, удаление документа — без ошибок")
srv.shutdown()
shutil.rmtree(W, ignore_errors=True)
check.finish()

"""Запросы к языковой модели и сбои: выключатель рассуждений (без привязки к модели), свои параметры запроса,
шлюз, который их не принимает, распознавание рассуждений, сообщение о таймауте; аудит — повторная проверка
разделов, на которых модель не ответила, и время каждого раздела.

Запуск из корня проекта:  python tests/test_llm_requests.py
"""
import os
import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402
import mock_server  # noqa: E402

W = harness.make_project(prefix="mint_llm_")
srv = mock_server.start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/v1"
os.environ.update({
    "LLM_API_URL": BASE, "EMBED_API_URL": BASE + "/embeddings", "RERANK_API_URL": "",
    "LLM_MODEL": "test-llm", "EMBED_MODEL": "emb-model", "KB_DIR": str(W / "kb"), "LOG_DIR": str(W / "logs"),
    "MINT_CONFIG": str(W / "config.yaml"), "GLOSSARY_PATH": str(W / "none.json"), "MINT_LANG": "ru",
})
os.chdir(W)
app = harness.load_mint(W, include_ui=False)
check = harness.Checker()
STATE = mock_server.STATE


def chats():
    return [p for m, path, p in STATE["requests"] if path.endswith("/chat/completions") and p]


print("1. [unit] Свои параметры запроса: разбор и проверка")
base, _ = app.load_settings()
ok = replace(base, llm_extra_body='{"top_p": 0.5, "chat_template_kwargs": {"foo": 1}}')
check(app.extra_body(ok) == {"top_p": 0.5, "chat_template_kwargs": {"foo": 1}} and not app.extra_body_error(ok),
      "JSON-объект разобран")
bad = replace(base, llm_extra_body="{top_p: 0.5")
check(app.extra_body(bad) == {} and "не JSON" in app.extra_body_error(bad)
      and any(lvl == "warning" and "не JSON" in t for lvl, t in app.check_settings(bad)),
      "неверный JSON — не отправляется, предупреждение в настройках")
check("должен быть объектом" in app.extra_body_error(replace(base, llm_extra_body="[1, 2]"))
      and "model" in app.extra_body_error(replace(base, llm_extra_body='{"model": "x", "top_p": 1}')),
      "не объект и поля, которые задаёт MINT, — объяснение")

print("2. [unit] Настройки: config.yaml (словарём) и .env")
(W / "config.yaml").write_text("models:\n  llm_no_reasoning: true\n  llm_extra_body:\n    top_p: 0.7\n", encoding="utf-8")
cfg_y, notes = app.load_settings()
check(cfg_y.llm_no_reasoning and app.extra_body(cfg_y) == {"top_p": 0.7} and not notes,
      f"в config.yaml — выключатель и параметры словарём: {cfg_y.llm_extra_body!r} {notes}")
os.environ.update({"LLM_NO_REASONING": "0", "LLM_EXTRA_BODY": '{"top_k": 20}'})
cfg_e, _ = app.load_settings()
check(not cfg_e.llm_no_reasoning and app.extra_body(cfg_e) == {"top_k": 20}, "окружение / .env важнее config.yaml")
for k in ("LLM_NO_REASONING", "LLM_EXTRA_BODY"):
    del os.environ[k]
(W / "config.yaml").unlink()

cfg, _ = app.load_settings()
cfg, _ = app.resolve_settings(cfg, app.resolve_model_limits(cfg, {}, None, {}), {})

print("3. [интеграция] Выключатель рассуждений и свои параметры в запросе")
STATE["requests"].clear()
app.ask_llm("Ты помощник.", "Привет", cfg)
check("chat_template_kwargs" not in chats()[-1], "по умолчанию лишних полей нет — как настроено на сервере")
app.ask_llm("Ты помощник.", "Привет", replace(cfg, llm_no_reasoning=True))
check(chats()[-1].get("chat_template_kwargs") == {"enable_thinking": False, "thinking": False},
      f"выключатель — стандартный параметр шаблона чата: {chats()[-1].get('chat_template_kwargs')}")
app.ask_llm("Ты помощник.", "Привет", replace(cfg, llm_no_reasoning=True,
                                               llm_extra_body='{"top_p": 0.5, "chat_template_kwargs": {"foo": 1}}'))
last = chats()[-1]
check(last.get("top_p") == 0.5 and last.get("chat_template_kwargs") == {"enable_thinking": False, "thinking": False,
                                                                        "foo": 1},
      f"свои параметры добавлены и объединены с выключателем: {last}")

print("4. [интеграция] Шлюз не принимает выключатель — повтор без него, запоминается")
strict = replace(cfg, llm_model="strict-gw", llm_no_reasoning=True)
STATE["requests"].clear()
ans = app.ask_llm("Ты помощник.", "Привет", strict)
sent = [("chat_template_kwargs" in p) for p in chats()]
check(not ans.startswith("❌") and sent == [True, False], f"ответ получен со второй попытки без выключателя: {sent}")
STATE["requests"].clear()
app.ask_llm("Ты помощник.", "Ещё вопрос", strict)
check([("chat_template_kwargs" in p) for p in chats()] == [False], "следующий запрос — сразу без выключателя")

print("5. [интеграция] Модель рассуждает: распознаётся, таймаут подсказывает, что сделать")
think = replace(cfg, llm_model="think-model", llm_timeout=1, llm_retries=1)
check(not app.model_reasons(think), "до первого ответа — неизвестно")
check(not app.ask_llm("Ты помощник.", "Привет", think).startswith("❌") and app.model_reasons(think),
      "по полю reasoning_content понятно, что модель рассуждает")
STATE["think_seconds"] = 2.5
msg = app.ask_llm("Ты помощник.", "Привет", think)
check(msg.startswith("❌ [ТАЙМАУТ MINT]") and "Модель рассуждает" in msg and "max_tokens" not in msg,
      f"таймаут: что увеличить и что выключить: {msg}")
t0 = time.time()
fast = app.ask_llm("Ты помощник.", "Привет", replace(think, llm_no_reasoning=True))
check(not fast.startswith("❌") and time.time() - t0 < 1.5, "с выключенными рассуждениями — ответ сразу")
STATE["think_seconds"] = 0
plain_to = app.timeout_message(cfg, "test-llm", 90)
check("Если модель рассуждает" in plain_to and "90" in plain_to, "без признаков рассуждений — подсказка с «если»")

print("6. [интеграция] Аудит: раздел, на котором модель не ответила, проверяется ещё раз")
md = ("# 1. Общие положения\n\nПередача ПДн между подсистемами описана в общих чертах без деталей.\n\n"
      "# 2. Бизнес-процесс\n\nЗАМЕДЛЕНИЕ. Описание целевого бизнес-процесса представления сведений.\n\n"
      "# 3. Надёжность\n\nВремя восстановления сервиса не указано в явном виде для всех режимов.\n")
acfg = replace(cfg, llm_timeout=1, llm_retries=1, audit_map_size=150, use_self_critique=False)
STATE["slow_words"] = {"ЗАМЕДЛЕНИЕ": 2.0}
events = []
res = app.run_audit(md, "ТЗ.md", acfg, use_wiki=False, deep=False, on_progress=lambda e, **d: events.append((e, d)))
retry = [d for e, d in events if e == "retry"]
part2 = next(e for e in res["log"] if "ЗАМЕДЛЕНИЕ" in e["preview"])
check(res["sections"] == 3 and retry and retry[0]["n"] == 1 and retry[0]["timeout"] == app.retry_timeout(acfg)
      and app.retry_timeout(acfg) == 180, f"повтор одного раздела с таймаутом {app.retry_timeout(acfg)} с: {retry}")
check(not res["failed_sections"] and not part2["failed"] and part2["attempts"] == 2 and part2["seconds"] >= 1.9,
      f"после повтора все разделы проверены: попыток {part2['attempts']}, {part2['seconds']:.1f} с")
check("проверен с 2-й попытки" in res["log_md"] and "Таймаут ответа LLM, с" in res["log_md"]
      and "Рассуждения модели" in res["log_md"] and all(e.get("seconds") is not None for e in res["log"]),
      "в логе — время каждого раздела, повтор, таймаут и выключатель рассуждений")
check(app.retry_timeout(replace(cfg, llm_timeout=400)) == 600, "потолок таймаута повтора — 600 с")

print("7. [интеграция] Аудит без автоповтора и перепроверка непроверенных разделов")
res = app.run_audit(md, "ТЗ.md", acfg, use_wiki=False, retry_failed=False, deep=False)
check(len(res["failed_sections"]) == 1 and "НЕ УДАЛОСЬ ПРОВЕРИТЬ" in res["report"]
      and "ТАЙМАУТ" in res["failed_sections"][0][2], "без повтора — раздел в списке непроверенных")
before = len(res["findings"])
res2 = app.recheck_failed_sections(res, "ТЗ.md", acfg)
check(not res2["failed_sections"] and "НЕ УДАЛОСЬ ПРОВЕРИТЬ" not in res2["report"] and len(res2["findings"]) >= before
      and res2["log"][1]["attempts"] == 2, "перепроверка: раздел проверен, заключение собрано заново")
STATE["slow_words"] = {}

print("8. [интеграция] Автоповтор — только когда он может помочь")
STATE["requests"].clear()
down = replace(acfg, llm_url="http://127.0.0.1:9/v1", llm_retries=1)          # шлюз недоступен
events = []
res = app.run_audit(md, "ТЗ.md", down, use_wiki=False, deep=False, on_progress=lambda e, **d: events.append(e))
check(len(res["failed_sections"]) == 3 and "retry" not in events,
      "ни один раздел не проверен (шлюз недоступен) — без автоповтора, чтобы не удваивать ожидание")
print("9. [интеграция] Шлюз отвечает 429: общая пауза сколько просит шлюз, на 429 попыток больше")
import threading  # noqa: E402
c1 = replace(cfg, llm_retries=1, llm_timeout=5)
r0 = app.rate_limit_stats()
STATE["rate_limit"] = {"left": 2, "retry_after": "1"}
t0 = time.time()
ans = app.ask_llm("Ты помощник", "Привет", c1)
took = time.time() - t0
r1 = app.rate_limit_stats()
check(not ans.startswith("❌") and r1["count"] - r0["count"] == 2 and 1.8 <= took < 6,
      f"два ответа 429 при llm_retries=1 — запрос всё равно выполнен, пауза по Retry-After: {took:.1f} с, {ans[:60]}")
STATE["rate_limit"] = {"left": 1, "retry_after": "2"}
times = {}


def call(name):
    t = time.time()
    times[name] = (app.ask_llm("Ты помощник", "Привет, " + name, c1), time.time() - t)


a = threading.Thread(target=call, args=("a",))
a.start()
time.sleep(0.3)
b = threading.Thread(target=call, args=("b",))
b.start()
a.join()
b.join()
check(times["b"][1] >= 1.2 and STATE["rate_limit"]["hits"] == 1 and not times["b"][0].startswith("❌"),
      f"пока идёт пауза после 429, другие запросы ждут, а не добивают лимит: {times['b'][1]:.1f} с")
STATE["rate_limit"] = {"left": 10, "retry_after": "0"}
ans = app.ask_llm("Ты помощник", "Привет", c1)
check(ans.startswith("❌") and "после 4 попыток (HTTP 429)" in ans and STATE["rate_limit"]["left"] == 6,
      f"лимит не отпускает — после 4 попыток ошибка: {ans}")
STATE["rate_limit"] = {"left": 1, "retry_after": "0.5"}
res = app.run_audit(md, "ТЗ.md", acfg, use_wiki=False, deep=False)
STATE.pop("rate_limit")
check(not res["failed_sections"] and "**Шлюз просил реже (HTTP 429):** 1 раз, общие паузы" in res["log_md"],
      "в логе аудита видно, сколько раз шлюз просил реже")
res = app.run_audit(md, "ТЗ.md", acfg, use_wiki=False, deep=False)
check("Шлюз просил реже" not in res["log_md"], "не просил — строки нет")
srv.shutdown()
os.chdir(harness.ROOT)
shutil.rmtree(W, ignore_errors=True)
check.finish()

"""Аудит без шума: ответ потоком с обрывом (длина, зацикливание, шлюз без потока), повторы внутри ответа и потолок
замечаний, самокритика и сведение повторов пачками, мелкое и опечатки отдельно, параллельные разделы и время по
часам, ссылки на нормы, итог сверки с эталоном, нормы по разделам в режиме «весь документ».

Запуск из корня проекта:  python tests/test_audit_noise.py
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

W = harness.make_project(prefix="mint_noise_")
srv = mock_server.start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/v1"
os.environ.update({
    "LLM_API_URL": BASE, "EMBED_API_URL": BASE + "/embeddings", "RERANK_API_URL": "",
    "LLM_MODEL": "test-llm", "EMBED_MODEL": "emb-model", "KB_DIR": str(W / "kb"), "LOG_DIR": str(W / "logs"),
    "MINT_CONFIG": str(W / "none.yaml"), "GLOSSARY_PATH": str(W / "none.json"), "MINT_LANG": "ru",
})
os.chdir(W)
app = harness.load_mint(W, include_ui=False)
check = harness.Checker()
STATE = mock_server.STATE
cfg, _ = app.load_settings()
cfg = replace(cfg, llm_context_tokens=32768, llm_timeout=20, llm_retries=1)


def chats():
    return [p for m, path, p in STATE["requests"] if path.endswith("/chat/completions") and p]


print("1. [unit] Зацикливание и оборванный ответ")
cycle = "\n".join(f"- [НИЗКИЙ] 5.2: не указано, как проверяются требования к разделу 4.{i}" for i in range(1, 4))
check(app.answer_loops(cycle * 3) and not app.answer_loops(cycle), "три повтора одной строки — зацикливание; один раз — нет")
import json  # noqa: E402
pretty = json.dumps([{"n": i, "verdict": "ОСТАВИТЬ", "severity": "СРЕДНИЙ", "found": [i, i + 3], "topic": "участники и роли",
                      "comment": f"замечание {i}: подтверждается текстом главы"} for i in range(1, 10)], ensure_ascii=False, indent=2)
same_obj = "\n".join(['{"topic": "сроки и время", "claim": "файлы хранятся один год на файловом ресурсе"}'] * 3)
check(not app.answer_loops(pretty) and app.answer_loops(same_obj),
      "JSON с переносами строк («\"verdict\": \"ОСТАВИТЬ\",» у каждого объекта) — не зацикливание; один и тот же объект трижды — да")
check(app._trim_cut(cycle + "\n" + cycle + "\n- [НИЗКИЙ] оборв", "loop") == cycle, "без повторов и недописанной строки")

print("2. [интеграция] Ответ потоком: обрыв зацикливания и длинного ответа")
STATE["requests"].clear()
STATE["stream_aborted"] = 0
t0 = time.time()
ans = app.ask_llm("s", "проверь", replace(cfg, llm_model="loop-model"), guard=True)
took = time.time() - t0
lines = [ln for ln in ans.split("\n") if ln.strip()]
check(chats()[-1].get("stream") is True and len(lines) == 5 and len(set(lines)) == 5 and took < 3,
      f"зациклившийся ответ оборван: строк {len(lines)}, {took:.1f} с (полный ответ — 1500 строк)")
time.sleep(0.3)
check(STATE["stream_aborted"] >= 1, "соединение закрыто — шлюз перестаёт генерировать")
ans_long = app.ask_llm("s", "проверь", replace(cfg, llm_model="long-model"), max_tokens=100, guard=True)
check(len(ans_long) < 3000 and ans_long.startswith("- [СРЕДНИЙ] 1.1:") and ans_long.count("\n") >= 3,
      f"ответ далеко за лимитом длины оборван: {len(ans_long)} симв.")
plain = app.ask_llm("s", "проверь", replace(cfg, llm_model="loop-model"))
check(len(plain) > 50000 and "stream" not in chats()[-1], "без guard (чат) — обычный запрос, как раньше")
check(not app.ask_llm("s", "проверь", replace(cfg, llm_model="loop-model", llm_stream=False), guard=True)
      .startswith("❌") and "stream" not in chats()[-1], "llm_stream выключен — обычный запрос")

print("3. [интеграция] Шлюз без потока")
STATE["requests"].clear()
a1 = app.ask_llm("Ты помощник.", "Привет", replace(cfg, llm_model="stream-strict"), guard=True)
a2 = app.ask_llm("Ты помощник.", "Привет", replace(cfg, llm_model="stream-strict"), guard=True)
sent = [bool(p.get("stream")) for p in chats()]
check(not a1.startswith("❌") and not a2.startswith("❌") and sent == [True, False, False],
      f"шлюз отклонил поток — повтор обычным запросом, дальше сразу обычный: {sent}")
check(app.ask_llm("Ты помощник.", "Привет", replace(cfg, llm_model="nostream-model"), guard=True).startswith("Ответ"),
      "шлюз, который поток молча игнорирует, — обычный ответ разбирается")
think = replace(cfg, llm_model="think-model")
app.ask_llm("Ты помощник.", "Привет", think, guard=True)
check(app.model_reasons(think), "рассуждения в потоке тоже замечаются")

print("4. [unit] Повторы в ответе и потолок замечаний")
items = app.parse_findings("- [СРЕДНИЙ] Не указан сервис шага 6.2\n- [НИЗКИЙ] Не указан сервис шага 6.2\n"
                           "- [КРИТИЧНЫЙ] Шаг 9 противоречит границам\n- [СРЕДНИЙ]   не указан сервис шага 6.2.")
check(len(items) == 2, f"одно и то же замечание — один раз: {items}")
fs = [{"severity": sv, "text": f"замечание {i}"} for i, sv in enumerate(["НИЗКИЙ", "КРИТИЧНЫЙ", "СРЕДНИЙ", "НИЗКИЙ",
                                                                         "КРИТИЧНЫЙ"])]
kept, over = app.cap_findings(fs, 3)
check(over == 2 and [f["text"] for f in kept] == ["замечание 1", "замечание 2", "замечание 4"],
      "сверх потолка: сначала критичные, порядок ответа сохранён")

print("5. [интеграция] Самокритика и сведение повторов пачками")
STATE["requests"].clear()
many = [{"severity": "СРЕДНИЙ", "text": f"Замечание номер {i} про раздел {i} с подробностями", "category": None,
         "quote": ""} for i in range(32)]
kept, dropped = app.critique_findings("Глава документа.", "", many, cfg)
crit = [c for c in chats() if "Старший Контролер" in c["messages"][0]["content"]]
check(len(crit) == 3 and len(kept) + len(dropped) == 32 and dropped,
      f"32 замечания — три запроса самокритики по ≤15, вердикт у каждого: {len(crit)}, {len(kept)}+{len(dropped)}")
calls = []


def fake_merge(system, user, cfg_, **kw):
    calls.append(user)
    return "[[1, 2]]"


orig = app.ask_llm
app.ask_llm = fake_merge
big = [{"severity": "НИЗКИЙ", "text": f"Замечание {i}: " + "длинный текст " * 30, "sections": [f"раздел {i % 4}"],
        "category": None, "quote": ""} for i in range(120)]
merged, groups, err = app.merge_duplicate_findings(big, cfg)
app.ask_llm = orig
check(len(calls) >= 3 and groups >= 3 and len(merged) < 120 and not err,
      f"длинный список сводится пачками (+ общий проход, если влезает): запросов {len(calls)}, групп {groups}")

print("6. [unit] Мелкое и опечатки — отдельно от главного")
F = lambda sev, text, **kw: {"severity": sev, "text": text, "category": None, "quote": "", "sections": [], **kw}  # noqa: E731
mixed = [F("СРЕДНИЙ", "2.2.3, шаг 4: не описано, как файл попадает в платформу"),
         F("НИЗКИЙ", "Указать, каким образом обеспечивается обработка файлов большого объёма"),
         F("НИЗКИЙ", "«политой» → «политикой»", check="language"),
         F("НИЗКИЙ", "Опечатка в слове «соотвествии»"),
         F("НИЗКИЙ", "Таблица 4.2: не заполнено поле"),
         F("НИЗКИЙ", "Разделы без текста", source="check")]
main, minor, typos = app.split_minor_findings(mixed)
check([f["text"][:10] for f in main] == ["2.2.3, шаг", "Таблица 4.", "Разделы бе"] and len(minor) == 1 and len(typos) == 2,
      "главное (с местом), мелкое без места, опечатки")
rep = app.build_final_report("x.docx", app.group_by_section(main, {}), [], 2, minor=minor, typos=typos)
check(rep.index("ЗАМЕЧАНИЯ ПО РАЗДЕЛАМ") < rep.index("МЕЛКИЕ И ОБЩИЕ ЗАМЕЧАНИЯ (1)") < rep.index("ОПЕЧАТКИ И ГРАММАТИКА (2)"),
      "в заключении мелкое и опечатки — после главного")

print("7. [интеграция] Разделы параллельно, время по часам")
md = "\n\n".join(f"## {i} Раздел\n\nТекст раздела {i}. ЖДАТЬ{i}" for i in range(1, 5))
STATE["slow_words"] = {f"ЖДАТЬ{i}": 0.6 for i in range(1, 5)}
t0 = time.time()
res = app.run_audit(md, "Д.md", replace(cfg, audit_map_size=60, use_self_critique=False, audit_parallel=4,
                                         audit_merge_duplicates=False), use_wiki=False, deep=False)
took = time.time() - t0
STATE["slow_words"] = {}
check(res["sections"] == 4 and took < 2.0 and [e["part"] for e in res["log"]] == [1, 2, 3, 4],
      f"4 раздела по 0,6 с одновременно — {took:.1f} с; лог по порядку разделов")
check("**Время аудита (по часам), с:**" in res["log_md"] and "сумма по разделам" in res["log_md"],
      "в логе — время по часам и сумма по разделам")

print("8. [интеграция] Ссылки на нормы проверяются")


def fake_audit(system, user, cfg_, **kw):
    if "Старший Контролер" in system or "редактор заключения" in system:
        return "[]"
    return ("- [СРЕДНИЙ] 1: срок хранения не согласован с нормой [Источник: Регламент_ИБ.docx, 2.1 Хранение]\n"
            "- [СРЕДНИЙ] 1: нарушено требование [Источник: Фантом.docx, 9.9]")


norms = "=== ИСТОЧНИК: Регламент_ИБ.docx | Раздел в начале фрагмента: 2.1 Хранение ===\n## 2.1 Хранение\n\nЖурналы — 3 года."
orig_norms = app.build_norms_context
app.ask_llm, app.build_norms_context = fake_audit, (lambda *a, **k: (norms, ["Регламент_ИБ.docx › 2.1 Хранение"]))
res = app.run_audit("## 1 Хранение\n\nЖурналы хранятся год.", "Д.md", replace(cfg, use_self_critique=False), deep=False)
app.ask_llm, app.build_norms_context = orig, orig_norms
check([f["text"][:20] for f in res["findings"] if "Регламент_ИБ" in f["text"]] and
      [u["unverified"] for u in res["unverified"]] == [["[Источник: Фантом.docx, 9.9]"]],
      f"ссылка на приложенную норму — в заключении, на чужой файл — «не подтверждено»: {res['unverified']}")

print("9. [интеграция] Сверка: сколько всего замечаний и сколько к эталону")
cmp = app.compare_with_reference({"findings": mixed}, "Шаг 4 не описано как файл попадает в платформу\nНет резервного копирования",
                                 cfg)
md_cmp = app.reference_markdown(cmp, "x.docx", cfg)
check(cmp["audit_total"] == 6 and cmp["matched"] >= 1 and "**Замечаний в заключении:** 6; из них к эталону относятся" in md_cmp,
      f"итог сверки — с числом замечаний: {cmp['audit_total']}, {cmp['matched']}")

print("10. [интеграция] Весь документ одним запросом: нормы — по каждому разделу")
queries = []
orig_search = app.search_parent_child


def fake_search(query, cfg_, **kw):
    queries.append(query)
    return [], []


app.search_parent_child = fake_search
long_md = "\n\n".join(f"## {i} Раздел\n\n" + f"Требования раздела {i}. " * 40 for i in range(1, 6))
res_w = app.run_audit(long_md, "Д.md", replace(cfg, audit_map_size=1000, use_self_critique=False), deep=False, whole=True)
app.search_parent_child = orig_search
parts_n = len(app.split_document_parts(app.compact_markdown_tables(long_md), 1000))
check(res_w["document_mode"] == "whole" and parts_n >= 3 and len(queries) >= parts_n
      and any(q.startswith("## 3 Раздел") for q in queries), f"нормы ищутся по разделам: запросов {len(queries)}")

print("11. [unit] Замечание о пункте другой части документа")
two = ("## Содержание\n\n1.1.\tНазначение\t3\n\n2.1.\tОписание\t5\n\n2.2.\tТребования\t6\n\n"
       "## 1 Общие\n\n### 1.1 Назначение\n\n" + "Текст назначения. " * 30 + "\n\n"
       "## 2 Процесс\n\n### 2.1 Описание\n\n" + "Текст описания. " * 30 + "\n\n2.1.1. Требование к обмену.\n\n"
       "### 2.2 Требования\n\n" + "Текст требований. " * 30)
known = app.text_clauses(two)
check({"1", "1.1", "2", "2.1", "2.1.1", "2.2"} <= known, f"пункты документа — заголовки и нумерованные абзацы: {sorted(known)}")
p1 = {"text": two.split("## 2 Процесс")[0], "spans": [(0, "1 Общие")]}
own1 = app.part_clauses(p1)
check(own1 == {"1", "1.1"}, f"строки содержания — не пункты части: {sorted(own1)}")
cases = {"2.1, шаг 4: не описано": "2.1", "п. 2.1.1: противоречие": "2.1.1", "1.1: цель не ясна": None,
         "152-ФЗ не учтён": None, "шаг 2 → шаг 3: разрыв": None, "9.9: пункт нормы": None, "Раздел 2.2: пусто": "2.2"}
got = {t: app.foreign_clause(t, own1, known) for t in cases}
check(got == cases, f"чужой пункт — только известный документу и не из этой части: {got}")
own4 = {"2.2.3"}
known4 = {"2", "2.2", "2.2.3", "2.2.4", "2.2.4.1"}
check(app.foreign_clause("2.2: модель процесса", own4, known4) is None
      and app.foreign_clause("2.2.4.1: требование", own4, known4) == "2.2.4.1",
      "объемлющий раздел — свой, соседний подпункт — чужой")

print("12. [интеграция] Проверка раздела: чужие пункты отсеиваются, лимит — 10 в запросе")
STATE["requests"].clear()
STATE["section_reply"] = ("- [СРЕДНИЙ] 1.1: цель документа описана неполно, не указан заказчик\n"
                          "- [КРИТИЧНЫЙ] 2.1, шаг 4: не описано, кто передаёт файл дальше по процессу\n"
                          "- [СРЕДНИЙ] 2.2: требования к обмену не согласованы с описанием процесса")
res_c = app.run_audit(two, "Д.md", replace(cfg, audit_map_size=600, use_self_critique=False,
                                            audit_merge_duplicates=False), use_wiki=False, deep=False)
STATE.pop("section_reply")
by_part = {e["part"]: e for e in res_c["log"]}
toc_part, first = by_part[1], by_part[2]
check(len(res_c["log"]) == 4 and "1.1: цель" in first["report"] and "2.1, шаг 4" not in first["report"]
      and any("о пункте 2.1" in d for d in first["dropped"]),
      f"в части с разделом 1 оставлен свой пункт, чужие — в «Отклонено»: {first['dropped']}")
check(len(toc_part["dropped"]) == 3, f"у части без своих пунктов (содержание) чужие все: {toc_part['dropped']}")
last = by_part[max(by_part)]
check("2.2: требования" in last["report"] and "1.1: цель" not in last["report"], "в своей части замечание осталось")
sys_of = lambda p: next((m["content"] for m in p.get("messages") or [] if m["role"] == "system"), "")  # noqa: E731
sec_prompts = [sys_of(p) for p in chats() if "эксперт-аудитор" in sys_of(p)]
check(sec_prompts and all("не больше 10 замечаний" in x for x in sec_prompts), "в запросе проверки раздела — не больше 10")
rep_c = res_c["report"]
check(rep_c.index("### 1.1 Назначение") < rep_c.index("### 2.1 Описание") < rep_c.index("### 2.2 Требования")
      and "АРХИТЕКТУРН" not in rep_c and "# ЭКСПЕРТНОЕ ЗАКЛЮЧЕНИЕ" in rep_c and rep_c.count("2.2: требования") == 1,
      f"заключение — по разделам документа в его порядке, раздел — по пункту в начале замечания: {rep_c[:900]}")
log_c = res_c["log_md"]
check("**Отклонено:**" in log_c and "о пункте 2.1: его проверяет своя часть документа" in log_c, "в логе — причина отсева")

print("13. [unit] Группировка по разделам")
G = lambda sev, text, secs: {"severity": sev, "text": text, "quote": "", "sections": secs}  # noqa: E731
groups = app.group_by_section([G("НИЗКИЙ", "а", ["2 Б"]), G("КРИТИЧНЫЙ", "б", ["2 Б"]), G("СРЕДНИЙ", "в", []),
                               G("СРЕДНИЙ", "г", ["3 В", "1 А"])], {"1 А": 0, "2 Б": 1, "3 В": 2})
check([(h, [f["text"] for f in fs]) for h, fs in groups] == [("1 А", ["г"]), ("2 Б", ["б", "а"]),
                                                             (app.GENERAL_SECTION, ["в"])],
      f"порядок документа, критичные первыми, без раздела — в конце: {groups}")
rep_g = app.build_final_report("x.docx", groups, [], 3)
check("г — *также: 3 В*" in rep_g and "### Документ в целом" in rep_g and "1. 🔥" not in rep_g.split("### 2 Б")[0],
      "у замечания из нескольких разделов — «также», нумерация сквозная")

srv.shutdown()
os.chdir(harness.ROOT)
shutil.rmtree(W, ignore_errors=True)
check.finish()

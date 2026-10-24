"""Качество аудита: части по разделам, документ целиком в проверке раздела, ответы на «особое внимание»,
проверки без модели (сокращения, ссылки и цифры), подпункты замечаний, сведение повторов.

Документ в тесте выдуманный: функциональные требования с таблицей сокращений, процессом из таблицы операций и
требованиями к нему в разных разделах.

Запуск из корня проекта:  python tests/test_audit_quality.py
"""
import os
import shutil
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402
import mock_server  # noqa: E402

W = harness.make_project(prefix="mint_audit_q_")
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


def chats():
    return [p for m, path, p in STATE["requests"] if path.endswith("/chat/completions") and p]


def padded(rows):
    """Таблица, выровненная пробелами и чёрточками, как её выгружает Docling."""
    w = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    line = lambda r: "| " + " | ".join(c.ljust(w[i]) for i, c in enumerate(r)) + " |"  # noqa: E731
    return "\n".join([line(rows[0]), "|" + "|".join("-" * (x + 2) for x in w) + "|"] + [line(r) for r in rows[1:]])


ABBR = padded([["№ п/п", "Аббревиатура", "Расшифровка"],
               ["1.", "ХРО", "Хранилище отчётов"],
               ["2.", "ПИ", "Платформа интеграции"],
               ["3.", "ЛКП", "Личный кабинет поставщика"],
               ["4.", "ОКР", "Отдел контроля рисков"]])
STEPS = padded([["№ п/п", "Операция", "Описание операции", "Исполнитель", "Информационный сервис"]]
               + [[f"{i}.", f"Операция {i}", f"Шаг {i}: отчётная форма ОФ передаётся дальше по цепочке обработки "
                   f"поставщиков и проверяется на полноту", "ПИ" if i % 2 else "ХРО", "ЛКП"] for i in range(1, 9)])
DOC = f"""|  | УТВЕРЖДАЮ |
|--|-----------|
|  | Заказчик  |

# Функциональные требования

## 1 Общие положения

### 1.1 Назначение документа

Документ описывает требования к приёму отчётов поставщиков. Владелец — Служба отчётности (СО).

### 1.2 Аббревиатуры и сокращения

{ABBR}

## 2 Описание бизнес-процесса

### 2.1 Описание целевого процесса

{STEPS}

2.1.4 Отчётные формы ОФ шифруются на сертификат поставщика и хранятся в ХРО один год.

## 3 Требования к производительности

Показатели приведены в таблице 3.1: не более 50 Мб в сутки, время обработки — до 30 мин. Работа по МСК.
Алгоритм шифрования данных при передаче между подсистемами — ГОСТ 34.12.

## 4 Требования к документированию

Документация — по закону 99-ФЗ.
"""

print("1. [unit] Таблицы без выравнивания")
compact = app.compact_markdown_tables(ABBR)
check(len(compact) < len(ABBR) * 0.8 and "| 1. | ХРО | Хранилище отчётов |" in compact
      and compact.split("\n")[1] == "| --- | --- | --- |", f"выравнивание убрано, текст ячеек цел: {len(ABBR)} → {len(compact)}")
check(app.compact_markdown_tables("текст | не таблица") == "текст | не таблица"
      and app.compact_markdown_tables("| a \\| b | c |") == "| a \\| b | c |", "обычный текст и экранированная черта не трогаются")
md = app.compact_markdown_tables(DOC)

print("2. [unit] Части по разделам")
parts = app.split_document_parts(md, 1200)
proc = next(p for p in parts if "2.1 Описание целевого процесса" in p["text"])
check("| 8. | Операция 8" in proc["text"] and "2.1.4 Отчётные формы" in proc["text"] and len(proc["text"]) > 1200,
      f"раздел процесса (до 1,5 лимита) — одной частью с таблицей и требованиями: {len(proc['text'])} симв.")
check(all(not p["text"].rstrip().endswith(("## 2 Описание бизнес-процесса", "## 3 Требования к производительности"))
          for p in parts), "заголовок без текста не остаётся в конце части")
small = app.split_document_parts(md, 500)
cont = [p for p in small if p["text"].startswith("(продолжение таблицы")]
check(cont and all("| № п/п | Операция |" in p["text"] and p["continued"] for p in cont)
      and all(p["path"].endswith("2.1 Описание целевого процесса") for p in cont),
      f"большая таблица режется по строкам: шапка повторена, пометка «продолжение», раздел известен ({len(cont)})")
check(any("строки с " in p["text"] for p in cont) and "| 8. | Операция 8" in "".join(p["text"] for p in small),
      "в пометке — с какой строки продолжение; строки не потеряны")
p3 = next(p for p in parts if "Требования к производительности" in p["text"])
pos = p3["text"].index("99-ФЗ")
check(app.section_label(app.part_path_at(p3, pos)) == "4 Требования к документированию",
      f"раздел по месту в части: {app.part_path_at(p3, pos)}")
outline = app.document_outline(app.document_blocks(md))
check(outline.split("\n")[:3] == ["Функциональные требования", "  1 Общие положения", "    1.1 Назначение документа"],
      f"оглавление с отступами: {outline[:80]!r}")
check(not any(b["level"] for b in app.document_blocks("```\n# комментарий в коде\n```")), "«#» в блоке кода — не заголовок")

print("3. [unit] Подпункты остаются в своём замечании")
draft = ("- [СРЕДНИЙ] Перевод взаимодействия не раскрыт. Однако в главе не описано:\n"
         "  - что именно переводится;\n  - сроки и этапы перехода;\n"
         "- [НИЗКИЙ] Опечатка в разделе 4\n- Отдельное замечание без тега с заглавной буквы\n"
         "- [КРИТИЧНЫЙ] Не указаны получатели:\n- Участник А\n- Поставщик")
items = app.parse_findings(draft)
check(len(items) == 4 and items[0].endswith("не описано: что именно переводится; сроки и этапы перехода;")
      and items[3].endswith("Не указаны получатели: Участник А; Поставщик"),
      f"список внутри замечания — к замечанию; отдельное без тега — отдельно: {items}")
check(app.parse_findings("- первое\n- второе") == ["- первое", "- второе"], "без тегов — как раньше, по строкам")
qwen = [app.finding_from_line(x) for x in app.parse_findings(
    "- [КРИТИЧНЫЙ] шаг 3 → шаг 4:   передача между системами не описана.\u2028"
    "шаг 3 → шаг 4: [СРЕДНИЙ] неясно, кто расшифровывает файл.\r"
    "2.2.4.4. [НИЗКИЙ] нет шага расшифрования.\n\nИтог: замечаний три.")]
check([(f["severity"], f["text"]) for f in qwen] == [
    ("КРИТИЧНЫЙ", "шаг 3 → шаг 4: передача между системами не описана."),
    ("СРЕДНИЙ", "шаг 3 → шаг 4: неясно, кто расшифровывает файл."),
    ("НИЗКИЙ", "2.2.4.4. нет шага расшифрования.")],
      f"тег после метки, без «-», и любой перевод строки (\\r, разделитель строк) — отдельные замечания: {qwen}")
check(len(app.parse_findings("- [СРЕДНИЙ] Не описано:\n  - кто передаёт;\nИтог по разделу: всё остальное в порядке.")) == 1,
      "строка без тега и без знака списка — не замечание")

J = app.extract_json
check(J('Сверка [эталон] ниже:\n```json\n[{"n": 1, "found": [3]}, {"n": 2, "found": []},]\n```') ==
      [{"n": 1, "found": [3]}, {"n": 2, "found": []}], "JSON: скобки в тексте до ответа, обёртка, висячая запятая")
check(J('{"n": 1, "found": [3]}\n{"n": 2, "found": [5, 7]}') == [{"n": 1, "found": [3]}, {"n": 2, "found": [5, 7]}]
      and J('[{"n": 1, "found": [3]}, {"n": 2, "fou') == [{"n": 1, "found": [3]}]
      and J('{"n": 1, "found": [30, 38]}') == [{"n": 1, "found": [30, 38]}],
      "JSON: объекты без массива, оборванный ответ — целые объекты; номера внутри объекта — не ответ целиком")
check(J("[[1, 4], [2, 7, 9]]") == [[1, 4], [2, 7, 9]] and J("Повторов нет: []") == []
      and J('Ответ: {"found": true, "quote": "a [b] } c"}', kind="object") == {"found": True, "quote": "a [b] } c"}
      and J("не могу ответить") is None, "JSON: группы сведения, пустой массив, объект со скобками в строке, нет JSON")

print("4. [unit] Сокращения без расшифровки")
checks = app.check_abbreviations(app.document_blocks(md))
undef = next((f for f in checks if "без расшифровки" in f["text"]), None)
check(undef and "ОФ (×9" in undef["text"] and "впервые — «2.1 Описание целевого процесса»" in undef["text"]
      and "ХРО" not in undef["text"] and "СО" not in undef["text"] and "МСК" not in undef["text"]
      and "УТВЕРЖДАЮ" not in undef["text"] and undef["severity"] == "СРЕДНИЙ",
      f"используется без расшифровки: {undef and undef['text']}")
unused = next((f for f in checks if "которых нет в тексте" in f["text"]), None)
check(unused and "ОКР" in unused["text"] and "ХРО" not in unused["text"], f"расшифровано, но не используется: {unused}")
check(not any("ОФ" in f["text"] for f in app.check_abbreviations(app.document_blocks(md), known="ОФ, ПИ")),
      "свои общеизвестные сокращения (audit_known_abbreviations) не отмечаются")
check(not app.check_abbreviations(app.document_blocks("# Т\n\nТекст про ГОСТ и РФ и ХРО.")) and
      app.check_abbreviations(app.document_blocks("## Сокращения\n\nОФ — отчётная форма\n\n## Текст\n\nРОП/ПФ и ОФ"))[0]
      ["text"].count("РОП/ПФ (×1") == 1,
      "без раздела сокращений и при одном-двух сокращениях — без замечания; «РОП/ПФ» — одно сокращение")
TECH = ("# Руководство\n\n## Обозначения и сокращения\n\nОФ — отчётная форма\n\n## 1 Доступ\n\nПодключение по SSH и NTP, "
        "порты TCP/UDP, ОС Astra Linux SE 1.7. Тест выполняется заранее; отметка «нет» — доступа нет. Важно: ОФ хранится в ЗКС.\n\n"
        "| Группа | Сервер | Тест | Доступ |\n|---|---|---|---|\n| CORP\\Admins-OS | srv01.CORP.local | ТЕСТ | НЕТ |\n"
        "| CORP\\Users | srv02.CORP.local | ТЕСТ | НЕТ |\n\nСм. ОРГ.10.0.ТЗ.2, index=OSLOG; ВАЖНО: в ЗКС.\n")
tech = " | ".join(f["text"] for f in app.check_abbreviations(app.document_blocks(TECH)))
check("ЗКС (×2" in tech and not any(x in tech for x in ("CORP", "НЕТ", "ТЕСТ", "SSH", "NTP", "TCP/UDP", "ТЗ", "OSLOG",
                                                          "ОРГ", "ВАЖНО", "SE")),
      f"не сокращения: части имён серверов и учётных записей, кода документа и названия продукта (Linux SE), слова "
      f"заглавными буквами, общеизвестные SSH, NTP, TCP/UDP; ЗКС без расшифровки — отмечено: {tech}")

print("4а. [unit] Повторы в кусках одного длинного раздела (таблица на десятки строк)")
parts_r = [{"path": "A", "continued": False}, {"path": "B", "continued": False}, {"path": "B", "continued": True},
           {"path": "B", "continued": True}, {"path": "C", "continued": True}]
check(app.section_runs(parts_r) == {1: 1, 2: 1, 3: 1}, f"куски раздела B — одна серия: {app.section_runs(parts_r)}")
fa = {"severity": "СРЕДНИЙ", "text": "В таблице нет правил передачи журналов из портала в подсистему мониторинга",
      "quote": "", "part": 3, "origins": ["part2"], "run": 1, "sections": ["B"]}
fb = {"severity": "КРИТИЧНЫЙ", "text": "Таблица не содержит правил для передачи журналов портала в подсистему "
      "мониторинга — нарушение схемы", "quote": "", "part": 4, "origins": ["part3"], "run": 1, "sections": ["B"]}
st_ = {}
merged = app.collect_unique_findings([fa, fb], stats=st_)
check(len(merged) == 1 and merged[0]["severity"] == "КРИТИЧНЫЙ" and merged[0]["origins"] == ["part2", "part3"]
      and st_.get("run_merged") == 1, f"один недостаток своими словами в двух кусках таблицы — одно замечание: {merged}")
check(len(app.collect_unique_findings([fa, {**fb, "run": None}])) == 2
      and len(app.collect_unique_findings([fa, {**fb, "part": 3, "origins": ["part2"]}])) == 2,
      "в разных разделах и в одном ответе модели такие замечания не склеиваются")

print("5. [unit] Ссылки и цифры в замечаниях сверяются с документом и нормами")
src = app._norm_src(md + "\n=== ИСТОЧНИК: Регламент_обмена.docx ===\nЛимит сообщения — 100 Мб; квота — 2 Гб.")
check(app.unverified_refs("Лимит 4 Гб/мес (Таблица №5 ВП)", src) == ["Таблица №5", "4 Гб"],
      f"таблицы и цифры нет ни в документе, ни в нормах: {app.unverified_refs('Лимит 4 Гб/мес (Таблица №5 ВП)', src)}")
check(not app.unverified_refs("По таблице 3.1 объём 50 Мб; по 99-ФЗ; лимит 100 Мб, за год ≈ 18 250 Мб", src),
      "есть в документе и нормах; вычисленное моделью («≈ …») не проверяется")
check(app.unverified_refs("Нарушен п. 7.7.7 и 999-ФЗ", src) == ["п. 7.7.7", "999-ФЗ"], "пункт и акт, которых нет")
check(not app.unverified_refs("Нарушен п. 7.7.7", src, check_clauses=False), "без нумерации разделов пункты не проверяются")

print("6. [unit] Сведение повторов моделью")
F = lambda sev, text, sec, **kw: {"severity": sev, "text": text, "category": None, "quote": "", "sections": [sec], **kw}  # noqa: E731
fs = [F("СРЕДНИЙ", "Бизнес-процесс передачи данных не описан", "1.4"),
      F("НИЗКИЙ", "Срок хранения журналов не указан", "4.3"),
      F("КРИТИЧНЫЙ", "Не описан процесс передачи: участники, шаги и форматы", "2.1", unverified=["Таблица №5"]),
      F("СРЕДНИЙ", "Процесс передачи данных не раскрыт: кто инициатор и получатель", "4.8", focus_item=0)]
calls = []


def fake_llm(system, user, cfg, **kw):
    calls.append(user)
    return "[[1, 3, 4], [2, 99], [1, 2]]"


orig_llm = app.ask_llm
app.ask_llm = fake_llm
merged, groups, err = app.merge_duplicate_findings(fs, app.load_settings()[0])
app.ask_llm = orig_llm
rep = merged[0]
check(groups == 1 and len(merged) == 2 and not err and "(1.4)" in calls[0] and "[КРИТИЧНЫЙ]" in calls[0],
      f"группа из трёх сведена; номер вне списка и повтор номера — пропущены: {groups}, {len(merged)}")
check(rep["severity"] == "КРИТИЧНЫЙ" and rep["sections"] == ["4.8", "1.4", "2.1"] and not rep.get("unverified")
      and rep["focus_item"] == 0 and rep["text"].startswith("Процесс передачи данных не раскрыт"),
      f"остаётся подтверждённая формулировка, критичность — наибольшая, разделы — всех: {rep}")
app.ask_llm = lambda *a, **k: "не JSON"
same, g2, err2 = app.merge_duplicate_findings(fs, app.load_settings()[0])
app.ask_llm = orig_llm
check(same == fs and g2 == 0 and err2, "неразборчивый ответ — замечания как были, причина в логе")
check("разделы: 4.8; 1.4; 2.1" in app.finding_display(rep), "в заключении — разделы, где повторялось замечание")

# один ответ модели — разные проблемы: не сливаются, даже если модель их сгруппировала
same_answer = [F("СРЕДНИЙ", "шаг 3 → шаг 4: не описано, как платформа получает файл от портала", "2.2.3", origins=["deep3"]),
               F("СРЕДНИЙ", "шаг 3 → шаг 4: неясно, может ли платформа обработать зашифрованный файл и на чей "
                            "сертификат он зашифрован", "2.2.3", origins=["deep3"]),
               F("КРИТИЧНЫЙ", "Не описано, на чей сертификат зашифрован файл на шаге 4", "2.2.3", origins=["part3"]),
               F("НИЗКИЙ", "«соотвествии» → «соответствии»", "4.3", check="language", origins=["deep9"])]
calls.clear()
app.ask_llm = lambda system, user, cfg_, **kw: calls.append(user) or "[[1, 2, 3]]"
out, g3, err3 = app.merge_duplicate_findings(same_answer, app.load_settings()[0])
app.ask_llm = lambda *a, **k: "[[1, 2]]"
out2, g4, _e = app.merge_duplicate_findings(same_answer, app.load_settings()[0])
app.ask_llm = orig_llm
texts = [f["text"] for f in out]
check(g3 == 1 and len(out) == 3 and texts[1].startswith("Не описано, на чей сертификат") and out[1]["origins"] == [
    "part3", "deep3"] and texts[0].endswith("как платформа получает файл от портала"),
      f"группа из трёх: из двух замечаний одного вопроса глубокой проверки в группу вошло одно, второе осталось: {texts}")
check("соотвествии" not in calls[0] and calls[0].count("\n") == 3 and out[-1]["text"] == "«соотвествии» → «соответствии»",
      "опечатки модели на сведение не передаются и остаются в списке")
check(g4 == 0 and out2 == same_answer, "группа только из одного ответа — не группа, замечания как были")
typos_in = [F("НИЗКИЙ", "«в соотвествии с регламентом обмена» → «в соответствии с регламентом обмена»", "4.3",
              check="language", origins=["deep9"]),
            F("НИЗКИЙ", "«В соотвествии с регламентом обмена» → «в соответствии с регламентом обмена»", "4",
              origins=["part4"]),
            F("НИЗКИЙ", "«подготовленным исполнителем» → «подготовленным исполнителем» (нет ошибки)", "5.2",
              check="language"),
            F("НИЗКИЙ", "«3.4.\tПриёмка работ» → «3.4. Приёмка работ» (это не ошибка текста)", "5.3",
              check="language"),
            F("НИЗКИЙ", "«согласованным с заказчиком» → «согласованным с заказчиком» (ошибок нет) — фактически "
                        "ошибка: «подготовленном и согласованным» → «подготовленном и согласованном»", "5.1",
              check="language"),
            F("НИЗКИЙ", "«в системе не\u00a0предполагается» → «в системе не предполагается» "
                        "(лишний неразрывный пробел)", "4.3", check="language"),
            F("НИЗКИЙ", '"recieve the file" → "receive the file"', "2", check="language")]
clean = app.clean_typos(typos_in)
check([f["text"][:12] for f in clean] == ["«в соотвеств", "«согласованн", "«в системе н", '"recieve the']
      and clean[0]["sections"] == ["4.3", "4"] and clean[0]["origins"] == ["deep9", "part4"],
      f"опечатки: одна фраза — одна строка; «ошибки нет» при одинаковых вариантах — убрано; вторая пара, "
      f"неразрывный пробел и английские кавычки — остаются: {[f['text'][:12] for f in clean]}")
check(app.is_typo(typos_in[1]) and not app.is_typo(F("НИЗКИЙ", "Таблица 4.2: не заполнено поле", "4.5")),
      "опечатка — по паре «как написано» → «как правильно» или проверке языка")
long_same = "«" + "очень длинная фраза документа " * 12 + "» → «" + "очень длинная фраза документа " * 12 + "» (ошибок нет)"
check(app.clean_typos([F("НИЗКИЙ", long_same, "1", check="language")]) == [],
      "«ошибок нет» убирается и у длинной фразы (длиннее 200 символов)")

no_problem = ["В сведениях заявлен результат для потребителя, и он передаётся на шаге 9, что соответствует. "
              "Проблем нет по этому пункту.",
              "Утверждения относятся к разным предметам, поэтому противоречий между ними нет.",
              "Значения совпадают — это уточнение, а не противоречие. Противоречий не выявлено.",
              "Result of step 1 is used on step 2 as described. There are no contradictions here."]
real = ["Противоречий в цифрах нет, но годовой объём не сходится с суточным.",
        "Не описан механизм решения проблем с доставкой файлов. Нет механизма решения проблем с доставкой.",
        "Проблемы с доставкой файлов нет описания механизма повторной отправки.",
        "Это не противоречит требованию напрямую, но порядок доставки требует уточнения.",
        "Есть ли у получателя ключ? Противоречий с требованием нет?",
        "There is no step that sends the summary file to the recipient."]
check(all(app.is_no_problem(t) for t in no_problem) and not any(app.is_no_problem(t) for t in real),
      f"«проблем нет» последней фразой — не замечание; с «но», вопросом или о реальном отсутствии — замечание: "
      f"{[t[:30] for t in no_problem if not app.is_no_problem(t)] + [t[:30] for t in real if app.is_no_problem(t)]}")

order = {"2.2.3": 0, "4.3": 1}
fs_sec = [F("КРИТИЧНЫЙ", "Одна проверка, критичное", "2.2.3", origins=["part3"]),
          F("СРЕДНИЙ", "Три проверки, среднее", "2.2.3", origins=["part3", "deep2", "focus0"]),
          F("НИЗКИЙ", "Две проверки, низкое", "2.2.3", origins=["deep4", "deep5"]),
          F("СРЕДНИЙ", "Проверка без модели", "4.3", source="check")]
grouped = app.group_by_section(fs_sec, order)
check([f["text"][:5] for f in grouped[0][1]] == ["Три п", "Две п", "Одна "] and app.corroboration(fs_sec[3]) == 1,
      "внутри раздела — сначала найденные несколькими проверками, затем по критичности")
rep_sec = app.build_final_report("x.docx", grouped, [], 2)
check("Три проверки, среднее — *нашли проверок: 3*" in rep_sec and "Одна проверка, критичное\n" in rep_sec,
      "в заключении видно, сколько проверок нашли замечание (если больше одной)")
line = app.merge_log_line([fs_sec[1], fs_sec[0]], [fs_sec[2]])
check(line.startswith("Оставлено: «Три проверки") and "влито: «Одна проверка" in line
      and "отдельно (тот же ответ модели): «Две проверки" in line, f"строка лога о группе сведения: {line}")

# разные шаги процесса — разные замечания, даже если модель свела их в одну группу (так терялось «на шаге 3 получатель
# не может прочитать файл»: его слили с замечанием о шаге 4 → 5)
steps_in = [F("СРЕДНИЙ", "шаг 1 → шаг 2: файл зашифрован на сертификат конечного получателя, а размещается у "
                         "посредника", "2.1", origins=["deep1"]),
            F("СРЕДНИЙ", "шаг 2 → шаг 3: посредник получает файл, зашифрованный на чужой сертификат, — прочитать "
                         "его не может", "2.1", origins=["deep2"]),
            F("СРЕДНИЙ", "2.1, шаги 3→4: неясно, расшифровывает ли посредник файл перед отправкой", "2.1",
              origins=["part2"]),
            F("КРИТИЧНЫЙ", "Шаг 4 → Шаг 5: не описано, как получатель расшифровывает файл и формирует ответный", "2.1",
              origins=["deep4"]),
            F("СРЕДНИЙ", "Нет шага расшифрования файлов получателя", "2.1", origins=["deep9"])]
merge_log = []
app.ask_llm = lambda *a, **k: "[[1, 2, 3, 4, 5]]"
out_s, g_s, _e = app.merge_duplicate_findings(steps_in, app.load_settings()[0], log=merge_log)
app.ask_llm = orig_llm
texts_s = [f["text"][:11] for f in out_s]
check(g_s == 1 and len(out_s) == 3 and out_s[2]["text"].startswith("Шаг 4 → Шаг 5")
      and set(out_s[2]["origins"]) == {"deep4", "part2", "deep9"} and texts_s[:2] == ["шаг 1 → шаг", "шаг 2 → шаг"],
      f"модель свела замечания о разных шагах: о шагах 1 → 2 и 2 → 3 остались отдельно, 3 → 4 и без шага — влиты в "
      f"4 → 5: {texts_s}")
check(merge_log and "отдельно (другой шаг процесса): «шаг" in merge_log[0]
      and all(t in merge_log[0].split("другой шаг процесса")[1] for t in ("«шаг 1 → шаг 2", "«шаг 2 → шаг 3")),
      f"в логе — что оставлено отдельно из-за другого шага: {merge_log[:1]}")
check(sorted(app.finding_steps("2.2.3, шаги 8–9 ↔ 2.1, 2.2.4.4: нет шага")) == ["8", "9"]
      and sorted(app.finding_steps("step 3 → step 4: missing")) == ["3", "4"]
      and not app.finding_steps("2.2.4.4: нет шага") and not app.finding_steps("Не описан процесс шага 3")
      and app.steps_conflict("шаг 2 → шаг 3: а", "Шаг 4 → Шаг 5: б")
      and not app.steps_conflict("2.1, шаг 6.2: а", "2.1, шаги 6.2–7.1: б"),
      "[unit] шаги — из метки места в начале замечания; общий шаг — можно сводить")
near = [F("СРЕДНИЙ", "шаг 2 → шаг 3: получатель не может прочитать файл, зашифрованный на чужой сертификат", "2.1"),
        F("СРЕДНИЙ", "шаг 3 → шаг 4: получатель не может прочитать файл, зашифрованный на чужой сертификат", "2.1"),
        F("СРЕДНИЙ", "шаг 5 → шаг 6: получатель не может прочитать файл, зашифрованный на чужой сертификат", "2.1")]
check(len(app.collect_unique_findings(near)) == 2,
      "склейка по словам тоже не сводит разные шаги (2 → 3 и 5 → 6), соседние с общим шагом — сводит")

print("7. [unit] Документ целиком — если помещается в окно модели")
cfg0, _ = app.load_settings()
cfg0 = replace(cfg0, llm_context_tokens=32768, chars_per_token=2.5)
check(app.document_mode(md, parts, cfg0) == "full", "32k токенов — документ целиком")
check(app.document_mode(md, parts, replace(cfg0, llm_context_tokens=6000)) == "outline", "маленькое окно — оглавление")
check(app.document_mode(md, parts, replace(cfg0, audit_full_document=False)) == "outline", "выключено в настройках — оглавление")
check(app.document_mode(md, parts[:1], cfg0) == "single", "документ в одну часть — без справки")

print("8. [интеграция] Аудит: документ целиком, особое внимание, сокращения, сведение повторов")
cfg = replace(cfg0, audit_map_size=1200, use_self_critique=False, llm_timeout=5)
STATE["requests"].clear()
STATE["merge_reply"] = "[[1, 2], [4, 5]]"
events = []
res = app.run_audit(DOC, "ФТ.docx", cfg, special="Всё ли понятно по процессу передачи отчётов?", use_wiki=False,
                    on_progress=lambda e, **d: events.append(e))
STATE.pop("merge_reply")
sec_calls = [c for c in chats() if "ОБЯЗАТЕЛЬНЫЕ ФОКУСЫ" in c["messages"][0]["content"]]
users = [c["messages"][-1]["content"] for c in sec_calls]
check(res["document_mode"] == "full" and len(sec_calls) == res["sections"] >= 3
      and all("ДОКУМЕНТ ЦЕЛИКОМ" in u and "| 8. | Операция 8" in u for u in users),
      f"каждая часть проверяется вместе с документом целиком: частей {res['sections']}")
check(any(u.split("--- КОНЕЦ ДОКУМЕНТА ---")[1].lstrip().startswith(
    "Расположение главы в документе: Функциональные требования → 2 Описание бизнес-процесса") for u in users),
      "у части — расположение в документе (после документа, перед проверяемой главой)")
check(all("на каждый пункт отдельно отвечает проверка по всему документу" in c["messages"][0]["content"] for c in sec_calls),
      "в проверке раздела «особое внимание» только направляет внимание")
focus_calls = [c for c in chats() if "Пользователь отметил пункт" in c["messages"][0]["content"]]
check(len(focus_calls) == 1 and "ДОКУМЕНТ ЦЕЛИКОМ" in focus_calls[0]["messages"][-1]["content"]
      and len(res["focus_answers"]) == 1 and res["focus_answers"][0]["answer"].startswith("частично"),
      "на пункт особого внимания — один ответ по всему документу")
rep_md = res["report"]
check("ОТВЕТЫ НА ПУНКТЫ ОСОБОГО ВНИМАНИЯ" in rep_md and rep_md.index("ОТВЕТЫ НА ПУНКТЫ") < rep_md.index("ЗАМЕЧАНИЯ ПО РАЗДЕЛАМ")
      and "**1. Всё ли понятно по процессу передачи отчётов?**" in rep_md,
      "ответы на особое внимание — перед перечнем замечаний")
check(any(f.get("source") == "check" and "ОФ (" in f["text"] for f in res["findings"]) and "ОФ (" in rep_md,
      "замечание о сокращениях — в заключении")
merge_calls = [c for c in chats() if "редактор заключения аудита" in c["messages"][0]["content"]]
check(len(merge_calls) == 1 and "merge" in events and "Объединено групп повторов: 1" in res["log_md"],
      f"повторы сведены моделью одним запросом: {events}")
check("Группы повторов:" in res["log_md"] and "отдельно (тот же ответ модели)" in res["log_md"]
      and "← влито: «шаг 3 → шаг 4" in res["log_md"], "в логе — состав групп сведения")
check("— *нашли проверок: 3*" in rep_md, "замечание, которое нашли три части документа, — с пометкой в заключении")
raw_ = res["state"]["raw"]
labels_ = [r["label"] for r in raw_]
check(len(raw_) == len(chats()) and any(lb.startswith("Часть 1/") for lb in labels_) and "Особое внимание 1" in labels_
      and "Сведение повторов" in labels_ and all(r["answer"] and r["system"] for r in raw_),
      f"каждый запрос аудита и ответ модели записаны, с подписью проверки: {len(raw_)} из {len(chats())}")
raw_file = app.raw_answers_markdown(res, "ФТ.docx")
part_answer = next(r["answer"] for r in raw_ if r["label"].startswith("Часть 1/") and "ОБЯЗАТЕЛЬНЫЕ ФОКУСЫ" in r["system"])
check(raw_file.startswith("# Сырые ответы модели: ФТ.docx") and f"**Запросов:** {len(raw_)}" in raw_file
      and part_answer in raw_file and "[… документ целиком — " in raw_file and DOC not in raw_file
      and raw_file.count("**Ответ модели**") == len(raw_),
      "файл сырых ответов: ответ модели слово в слово, документ целиком в запросах — пометкой")
long_ = app._raw_clip("начало " + "х" * 9000 + " конец вопроса", "")
check(long_.startswith("начало ") and long_.endswith(" конец вопроса") and "[… пропущено " in long_ and len(long_) < 3300,
      "длинный запрос — началом и концом")
check(sum("алгоритм шифрования" in f["text"] or "времени отклика" in f["text"] for f in res["findings"]) == 2
      and sum("из портала в платформу" in f["text"] or "из кабинета в платформу" in f["text"]
              for f in res["findings"]) == 1,
      "замечания одного ответа модели не сливаются, повтор из другого ответа — сливается")
check(events[:2] == ["sections", "checks"] and events.count("focus_answer") == 1 and events[-2:] == ["merge", "summary"],
      f"ход аудита: {events}")
check("## 🎯 Особое внимание: «Всё ли понятно" in res["log_md"] and "## Проверки без модели" in res["log_md"]
      and "**Документ в проверке раздела:** целиком" in res["log_md"], "в логе — ответ на пункт, проверки и режим")
check(all(f.get("sections") is not None for f in res["findings"]), "у замечаний — раздел документа")

print("9. [интеграция] Документ не помещается: оглавление и сверка «не описано» с другими разделами")
small_cfg = replace(cfg, llm_context_tokens=6000, audit_merge_duplicates=False)
STATE["requests"].clear()
STATE["absence_reply"] = ('{"found": true, "quote": "Алгоритм шифрования данных при передаче между подсистемами", '
                         '"reason": "есть"}')
res2 = app.run_audit(DOC, "ФТ.docx", small_cfg, use_wiki=False)
STATE.pop("absence_reply")
users2 = [c["messages"][-1]["content"] for c in chats() if "ОБЯЗАТЕЛЬНЫЕ ФОКУСЫ" in c["messages"][0]["content"]]
absence = [c for c in chats() if "отсутствие чего утверждает замечание" in c["messages"][0]["content"]]
check(res2["document_mode"] == "outline" and all("ОГЛАВЛЕНИЕ ДОКУМЕНТА" in u and "ДОКУМЕНТ ЦЕЛИКОМ" not in u for u in users2),
      "документ не помещается — к частям прилагается оглавление")
dropped = [d for e in res2["log"] for d in e["dropped"]]
left = [e for e in res2["log"] if "Не указан алгоритм шифрования" in e["report"]]
check(absence and any("есть в другом разделе документа" in d for d in dropped)
      and len(left) == 1 and "Алгоритм шифрования данных при передаче" in res2["state"]["sections"][left[0]["part"] - 1],
      f"«не указано» снято там, где это есть в другом разделе ({len(absence)} сверок); осталось в разделе, где "
      f"это написано, — его снимает самокритика")
check(not [c for c in chats() if "редактор заключения аудита" in c["messages"][0]["content"]]
      and "Выключено в настройках" in res2["log_md"], "сведение повторов выключено — запроса нет")

print("10. [интеграция] Ответ на пункт особого внимания не получен — повтор")
STATE["fail_words"] = {"ТРАНСПОРТ": 1}
res3 = app.run_audit(DOC, "ФТ.docx", replace(cfg, llm_retries=1), special="ТРАНСПОРТ: нужны ли доработки?", use_wiki=False)
STATE["fail_words"] = {}
fa = res3["focus_answers"][0]
check(not fa["failed"] and fa["attempts"] == 2 and "ОТВЕТЫ НА ПУНКТЫ" in res3["report"],
      f"после сбоя шлюза ответ получен со 2-й попытки: {fa['attempts']}")
check(app.focus_points("Первое; второе\nТретье? Четвёртое?") == ["Первое", "второе", "Третье?", "Четвёртое?"],
      "пункты — через «;», с новой строки или вопросами")
fa_only = [{"item": "Процесс", "failed": False, "answer": "", "report": ""}]
f_only = [{"severity": "СРЕДНИЙ", "text": "Шаг 4 без исполнителя", "sections": [], "focus_item": 0}]
r_only = app.build_final_report("x.docx", [], [], 3, focus_answers=fa_only, focus_findings=f_only)
check("Шаг 4 без исполнителя" in r_only and "Замечаний по пункту нет" not in r_only and "ТРЕБУЕТ ДОРАБОТКИ" in r_only,
      "модель не написала «Ответ:», но дала замечания — замечания в блоке, вывод «требует доработки»")

print("11. [интеграция] Весь документ одним запросом — для сравнения с проверкой по разделам")
STATE["requests"].clear()
ev_w = []
res_w = app.run_audit(DOC, "ФТ.docx", replace(cfg, use_self_critique=True), use_wiki=False, deep=False, whole=True,
                      on_progress=lambda e, **d: ev_w.append((e, d)))
sec_w = [c for c in chats() if "ОБЯЗАТЕЛЬНЫЕ ФОКУСЫ" in c["messages"][0]["content"]]
crit_w = [c for c in chats() if "Старший Контролер" in c["messages"][0]["content"]]
check(res_w["sections"] == 1 and res_w["document_mode"] == "whole" and len(sec_w) == 1
      and "| 8. | Операция 8" in sec_w[0]["messages"][-1]["content"] and "1.2 Аббревиатуры" in sec_w[0]["messages"][-1]["content"]
      and "ДОКУМЕНТ ЦЕЛИКОМ" not in sec_w[0]["messages"][-1]["content"],
      "одна проверка — весь документ, без отдельной справки")
check(sec_w[0]["max_tokens"] == app.WHOLE_MAX_TOKENS and crit_w and crit_w[0]["max_tokens"] == app.WHOLE_MAX_TOKENS
      and "весь документ одним запросом" in res_w["log_md"], "длинный ответ — и у проверки, и у самокритики; режим в логе")
check(all(f.get("sections") is not None for f in res_w["findings"]), "у замечаний — разделы документа")
STATE["requests"].clear()
res_wd = app.run_audit(DOC, "ФТ.docx", cfg, use_wiki=False, deep=True, whole=True)
claims_w = [d for d in res_wd["deep"] if d["check"] == "claims"]
check(res_wd["document_mode"] == "whole" and len(claims_w) == len(app.split_document_parts(DOC, cfg.audit_map_size)) > 1,
      f"весь документ одним запросом + глубокая проверка: утверждения и опечатки — по разделам ({len(claims_w)})")
ev_small = []
res_s = app.run_audit(DOC, "ФТ.docx", replace(cfg, llm_context_tokens=5000), use_wiki=False, deep=False, whole=True,
                      on_progress=lambda e, **d: ev_small.append(e))
check("whole_too_big" in ev_small and res_s["document_mode"] != "whole" and res_s["sections"] > 1,
      "не помещается в окно — проверка по разделам и предупреждение")

print("12. [интеграция] Несколько проходов; «Главное»; ответ на пункт с замечаниями других проверок")
STATE["requests"].clear()
ev_p = []
STATE["summary_reply"] = ('[{"n": 2, "gist": "Суть второго замечания одной строкой"}, {"n": 99, "gist": "нет такого"}, '
                          '{"n": 2, "gist": "повтор"}, {"n": 1, "gist": "Суть первого"}]')
res_p = app.run_audit(DOC, "ФТ.docx", replace(cfg, audit_passes=2), special="Всё ли понятно по процессу передачи отчётов?",
                      use_wiki=False, on_progress=lambda e, **d: ev_p.append((e, d)))
STATE.pop("summary_reply")
labels_p = [r["label"] for r in res_p["state"]["raw"]]
sec_p = [(c, r) for c, r in zip(chats(), res_p["state"]["raw"]) if "ОБЯЗАТЕЛЬНЫЕ ФОКУСЫ" in c["messages"][0]["content"]]
first = [c for c, r in sec_p if not r["label"].startswith("Проход 2")]
second = [c for c, r in sec_p if r["label"].startswith("Проход 2 · Часть ")]
check(len(first) == len(second) == res_p["sections"] and all(c["temperature"] == cfg.temperature for c in first)
      and all(c["temperature"] >= app.PASS_TEMPERATURE for c in second),
      f"второй проход — те же разделы, температура не ниже {app.PASS_TEMPERATURE}: {len(first)} + {len(second)}")
deep2 = [lb for lb in labels_p if lb.startswith("Проход 2 · ") and not lb.startswith("Проход 2 · Часть ")]
check(deep2 and any("шаг" in lb for lb in deep2) and not any("Утверждения" in lb or "Опечатки" in lb for lb in deep2),
      f"глубокая проверка во втором проходе — процесс и цифры, без утверждений и опечаток: {len(deep2)}")
check([d["n"] for e, d in ev_p if e == "pass"] == [2] and len(res_p["state"]["passes"]) == 1,
      "событие о проходе и его результаты в состоянии аудита")
twice = [f for f in res_p["findings"] if any(o.endswith("#p2") for o in f.get("origins") or [])
         and any("#p" not in o for o in f.get("origins") or [])]
check(twice and "проходов — 2)*" in res_p["report"], "одно и то же из двух проходов — одно замечание с пометкой о проходах")
check("**Проходов проверки (audit_passes):** 2" in res_p["log_md"] and "## Проходы 2–2" in res_p["log_md"]
      and "### Проход 2: разделов — " in res_p["log_md"], "в логе — число проходов и что дал второй")
focus_p = [c for c in chats() if "Пользователь отметил пункт" in c["messages"][0]["content"]]
fu = focus_p[0]["messages"][-1]["content"] if focus_p else ""
check(focus_p and "УЖЕ НАЙДЕННЫЕ ДРУГИМИ ПРОВЕРКАМИ" in fu and "алгоритм шифрования" in fu.split("УЖЕ НАЙДЕННЫЕ")[1]
      and "«из документа не ясно»" in focus_p[0]["messages"][0]["content"]
      and "только с дословной цитатой" in focus_p[0]["messages"][0]["content"],
      "ответ на пункт — после проверок, с их замечаниями; можно ответить «из документа не ясно»")
sum_calls = [c for c in chats() if "блок «Главное»" in c["messages"][0]["content"]]
rep_p = res_p["report"]
summ = res_p["summary"]
main_lines = rep_p.split("ЗАМЕЧАНИЯ ПО РАЗДЕЛАМ")[1].split("\n")
line_of = lambda k: next((ln for ln in main_lines if ln.startswith(f"{k}. ")), "")  # noqa: E731
check(len(sum_calls) == 1 and "Главное" in labels_p and [it["ref"] for it in summ] == ["№2", "№1"]
      and [it["gist"] for it in summ] == ["Суть второго замечания одной строкой", "Суть первого"]
      and all(it["finding"]["text"] in line_of(it["ref"][1:]) for it in summ),
      f"«Главное» — выбор модели; номер ведёт на то же замечание ниже: {[it['ref'] for it in summ]}")
check("## ⭐ ГЛАВНОЕ" in rep_p and rep_p.index("ГЛАВНОЕ") < rep_p.index("ОТВЕТЫ НА ПУНКТЫ") < rep_p.index("ЗАМЕЧАНИЯ ПО РАЗДЕЛАМ")
      and "1. 🔥 Суть второго замечания одной строкой → **№2**" in rep_p.replace("⚠️", "🔥").replace("📝", "🔥")
      and "Выбрано моделью: 2 из " in res_p["log_md"], "блок «Главное» — в начале заключения, указатели на номера")
STATE["requests"].clear()
STATE["summary_reply"] = "Не могу выбрать"
res_f = app.run_audit(DOC, "ФТ.docx", cfg, use_wiki=False, deep=False)
STATE.pop("summary_reply")
res_0 = app.run_audit(DOC, "ФТ.docx", replace(cfg, audit_summary_max=0), use_wiki=False, deep=False)
calls_0 = [c for c in chats() if "блок «Главное»" in c["messages"][0]["content"]]
check(res_f["summary"] and all(it["finding"]["severity"] != "НИЗКИЙ" for it in res_f["summary"])
      and "найденные несколькими проверками и критичные" in res_f["report"] and "Не выбрано моделью" in res_f["log_md"],
      "модель не выбрала — «Главное» по подтверждению и критичности")
check(len(calls_0) == 1 and "ГЛАВНОЕ" not in res_0["report"] and not res_0["summary"]
      and "audit_summary_max = 0" in res_0["log_md"] and len(res_0["findings"]) == len(res_f["findings"]),
      "«Главное» выключено — запроса и блока нет; число замечаний то же")

ans_, rest_ = app._split_answer("Ответ: Частично. Процесс описан не полностью.\n"
                                "- 2.1, шаги 6.2–7.1: не указан информационный сервис у шагов контроля\n"
                                "- 2.1, шаг 9: файл направляется не тому получателю, что в требованиях\n"
                                "**Итого**")
pf_ = app._point_findings(rest_, 0, "focus")
check(ans_ == "Частично. Процесс описан не полностью." and len(pf_) == 2
      and all(f["severity"] == "СРЕДНИЙ" for f in pf_) and pf_[1]["text"].startswith("2.1, шаг 9"),
      "[unit] ответ на пункт без тегов критичности: пункты списка — замечания, а не абзац ответа")
ans2_, rest2_ = app._split_answer("Ответ: да — всё описано:\n- шаги 1–3 в таблице 2.1\n- [НИЗКИЙ] 2.1: опечатка в шаге 2")
check(ans2_.startswith("да — всё описано") and "шаги 1–3" in ans2_ and len(app._point_findings(rest2_, 0, "focus")) == 1,
      "[unit] с тегами — как раньше: пункты до первого тега — пояснение ответа")

print("13. [интеграция] Аудит с рассуждениями модели")
STATE["requests"].clear()
res_r = app.run_audit(DOC, "ФТ.docx", replace(cfg, audit_reasoning=True, llm_no_reasoning=True, max_tokens=1000),
                      use_wiki=False, deep=False)
calls_r = chats()
check(calls_r and all((c.get("chat_template_kwargs") or {}).get("enable_thinking") is True
                      and c["max_tokens"] == 1000 + app.REASONING_EXTRA_TOKENS for c in calls_r),
      "все запросы аудита — с включателем рассуждений и запасом длины ответа")
check("включены для аудита (audit_reasoning)" in res_r["log_md"]
      and app.audit_cfg(replace(cfg, audit_reasoning=True, llm_timeout=60)).llm_timeout == app.REASONING_TIMEOUT,
      "в логе — рассуждения включены; таймаут не меньше 300 с")
STATE["requests"].clear()
app.ask_llm("Вопрос", "Текст", replace(cfg, audit_reasoning=True, llm_no_reasoning=True))
check((chats()[-1].get("chat_template_kwargs") or {}).get("enable_thinking") is False,
      "вне аудита (чат) рассуждения выключены, как в настройках")
store_ = []
with app.record_answers(store_), app.answer_label("Проход 2"), app.answer_label("Часть 1/3"):
    app.ask_llm("Вопрос", "Текст", cfg)
check([r["label"] for r in store_] == ["Проход 2 · Часть 1/3"], "[unit] подписи сырых ответов вкладываются")
crit_text = app.prompt_text("critique_system")
check("детали реализации" in crit_text and "опираясь на то, чего в документе нет" in crit_text,
      "самокритика не удаляет пробелы процесса как «детали реализации» и по догадкам")

srv.shutdown()
os.chdir(harness.ROOT)
shutil.rmtree(W, ignore_errors=True)
check.finish()

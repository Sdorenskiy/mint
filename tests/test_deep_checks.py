"""Глубокая проверка аудита (mint/deep_checks.py) и сверка с эталоном: таблицы операций, требования и границы
процесса, цифры, оформление без модели, утверждения и противоречия, опечатки; параллельные вопросы, лимит,
повтор после сбоя; эталон.

Документ в тесте выдуманный.

Запуск из корня проекта:  python tests/test_deep_checks.py
"""
import os
import shutil
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402
import mock_server  # noqa: E402

W = harness.make_project(prefix="mint_deep_")
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


STEPS = "\n".join(f"| {i}. | Операция {i} | {d} | {who} | {inp} | {out} | {svc} |" for i, d, who, inp, out, svc in [
    (1, "Поставщик формирует отчётную форму", "Поставщик", "Данные учёта", "Отчётная форма", "Система поставщика"),
    (2, "Поставщик размещает форму в кабинете", "Поставщик", "Отчётная форма", "Форма размещена", "ЛКП"),
    (3, "Форма доставлена в кабинет", "ЛКП", "Отчётная форма", "Форма получена", "ЛКП"),
    (4, "Платформа передаёт форму в хранилище", "ПИ", "Отчётная форма", "Форма в хранилище", "ХРО"),
    (5, "Служба проверяет форму", "Служба отчётности", "Отчётная форма", "Результат проверки", "ХРО")])
DOC = f"""# Функциональные требования

Содержание

1. Общие положения 2

1.1. Назначение 2

2. Процесс 3

2.1. Описание процесса 3

3. Прочие требования 5

3.1. Требования к хранению 5

## 1 Общие положения

### 1.1 Назначение

Документ описывает приём отчётов поставщиков.

## 2 Процесс

| Наименование процесса | Приём отчётов |
| --- | --- |
| Участники и информационные сервисы | Поставщик, Служба отчётности; ЛКП, ПИ, ХРО |
| Границы бизнес-процесса | С момента формирования отчётной формы до направления итогового отчёта поставщику |

### 2.1 Описание процесса

| № п/п | Операция | Описание операции | Исполнитель | Входные данные | Результаты | Информационный сервис |
| --- | --- | --- | --- | --- | --- | --- |
{STEPS}

2.1.4. Отчётные формы шифруются на сертификат поставщика.

2.1.5. Результат проверки направляется поставщику не позднее следующего рабочего дня.

### 2.2 Модель целевого процесса

## 3 Прочие требования

### 3.1 Требования к хранению

| Характеристика | Значение |
| --- | --- |
| Средний объём передаваемой информации за сутки | 10 Мб |
| Объём передаваемой информации за год | 200 Гб |
| Регламентирующие документы | |

Информация содержит персональные данные поставщиков.

### 3.2 Требования к безопасности

В соотвествии с политикой персональные данные не обрабатываются.

| № п/п | Документ | Описание требований |
| --- | --- | --- |
| 1. | Положение о хранении | |
| 2. | Регламент доступа | |

3.4 Приёмочные испытания

Испытания длятся пять рабочих дней.

## 4 Журнал изменений

| Дата | Автор | Версия |
| --- | --- | --- |
|  |  |  |
"""
blocks = app.document_blocks(DOC)

print("1. [unit] Таблица операций и сведения о процессе")
tables = app.find_process_tables(blocks)
check(len(tables) == 1 and len(tables[0]["rows"]) == 5 and tables[0]["path"].endswith("2.1 Описание процесса"),
      f"найдена одна таблица операций из 5 шагов: {[(t['path'], len(t['rows'])) for t in tables]}")
t = tables[0]
st3 = app.step_text(t["header"], t["rows"][2], 2)
check(st3.startswith("Шаг 3: Операция: Операция 3; Описание операции: Форма доставлена") and "Информационный сервис: ЛКП" in st3,
      f"шаг одной строкой с названиями колонок: {st3}")
info, reqs = app.process_info(blocks, t)
check(any(x.startswith("Границы бизнес-процесса:") for x in info) and len(reqs) == 2 and reqs[0].startswith("2.1.4."),
      f"сведения (границы, участники) и требования после таблицы: {info}, {reqs}")
check(not app.find_process_tables(app.document_blocks("| Показатель | Значение |\n|---|---|\n| a | 1 |")),
      "таблица «показатель — значение» — не процесс")
procs = app.find_processes(blocks)
check([(p["kind"], len(p["steps"])) for p in procs] == [("table", 5)] and procs[0]["steps"][2][1] == st3,
      f"документ с таблицей операций — один процесс, пункты «2.1.4.» после таблицы — не список шагов: "
      f"{[(p['kind'], p['path']) for p in procs]}")

print("1а. [unit] Процесс списком шагов, абзацами «Шаг N» и подразделами «Шаг N»")
LIST_DOC = """# Технические требования

## 2 Процесс

### 2.1 Порядок обмена

Участники процесса: Поставщик, Служба отчётности.

Обмен выполняется в следующем порядке:

1. Поставщик формирует отчётную форму в своей системе.
2. Поставщик размещает форму в личном кабинете портала.
    - форма подписывается электронной подписью поставщика
3. Платформа интеграции передаёт форму в хранилище данных.
4. Служба отчётности проверяет форму и формирует результат.

Отчётные формы шифруются на сертификат поставщика.

### 2.2 Требования к процессу

Результат проверки направляется поставщику не позднее следующего рабочего дня.
"""
lb = app.document_blocks(LIST_DOC)
lp = app.find_processes(lb)
check(len(lp) == 1 and lp[0]["kind"] == "list" and [n for n, _s in lp[0]["steps"]] == ["1", "2", "3", "4"]
      and lp[0]["steps"][1][1] == "Шаг 2: Поставщик размещает форму в личном кабинете портала.; форма подписывается "
                                   "электронной подписью поставщика",
      f"нумерованный список после «в следующем порядке:» — шаги процесса, подпункт — к своему шагу: {lp}")
l_info, l_reqs = app.process_info(lb, lp[0])
check(l_info == ["Участники процесса: Поставщик, Служба отчётности."]
      and l_reqs == ["Отчётные формы шифруются на сертификат поставщика.",
                     "Результат проверки направляется поставщику не позднее следующего рабочего дня."],
      f"сведения о процессе текстом и требования — после списка и в разделе «Требования к процессу»: {l_info}, {l_reqs}")
check(app.process_summary(lp) == "«2.1 Порядок обмена» — список, шагов: 4", f"строка лога: {app.process_summary(lp)}")
l_tasks = app.build_deep_tasks(lb, app.split_document_parts(LIST_DOC, 1500))
l_kinds = Counter(x["kind"] for x in l_tasks)
s34 = next((x for x in l_tasks if x["title"] == "Процесс «2.1 Порядок обмена»: шаг 3 → шаг 4"), None)
check(l_kinds["boundary"] == 1 and l_kinds["step"] == 3 and l_kinds["requirement"] == 2 and s34
      and "--- ШАГИ ПРОЦЕССА (раздел «2.1 Порядок обмена») ---" in s34["user"]
      and "Шаг 1: Поставщик формирует" in s34["user"], f"по списку — те же вопросы, что по таблице: {dict(l_kinds)}")

STEP_PARAS = ("# ТЗ\n\n## 3 Сценарий подачи заявки\n\nШаг 1. Пользователь открывает форму заявки на портале.\n\n"
              "Шаг 2. Портал проверяет заполнение полей и сохраняет заявку.\n\n"
              "Шаг 3 — Система согласования направляет заявку руководителю.\n\n"
              "- Шаг 4: Руководитель согласует заявку, портал уведомляет пользователя.\n")
sp = app.find_processes(app.document_blocks(STEP_PARAS))
check(len(sp) == 1 and [s for _n, s in sp[0]["steps"]] == [
    "Шаг 1: Пользователь открывает форму заявки на портале.",
    "Шаг 2: Портал проверяет заполнение полей и сохраняет заявку.",
    "Шаг 3: Система согласования направляет заявку руководителю.",
    "Шаг 4: Руководитель согласует заявку, портал уведомляет пользователя."],
      f"абзацы «Шаг N. …», «Шаг N — …», «- Шаг N: …» — шаги процесса: {sp}")

STEP_HEADS = ("# ТЗ\n\n## 4 Описание процесса\n\n### 4.1 Шаг 1. Формирование файла\n\nПоставщик формирует файл и "
              "подписывает его.\n\n### 4.2 Шаг 2. Передача файла\n\nФайл передаётся через платформу интеграции.\n\n"
              "1. Платформа принимает файл и проверяет его формат.\n2. Платформа направляет файл в хранилище "
              "получателя.\n3. Хранилище подтверждает получение файла платформе.\n\n"
              "#### 4.2.1 Протокол\n\nИспользуется протокол обмена файлами.\n\n### 4.3 Шаг 3. Приём файла\n\nСлужба отчётности принимает файл и проверяет подпись.\n\n"
              "## 5 Требования к процессу\n\nФайл расшифровывается получателем перед проверкой подписи.\n")
hb = app.document_blocks(STEP_HEADS)
hp = app.find_processes(hb)
check(len(hp) == 1 and hp[0]["kind"] == "headings" and len(hp[0]["steps"]) == 3
      and hp[0]["steps"][1][1].startswith("Шаг 2: Передача файла: Файл передаётся через платформу интеграции. "
                                          "1. Платформа принимает файл")
      and hp[0]["steps"][1][1].endswith("Используется протокол обмена файлами.")
      and app.process_info(hb, hp[0])[1] == ["Файл расшифровывается получателем перед проверкой подписи."],
      f"подразделы «Шаг N» — шаги (с текстом подразделов, без отдельного процесса из списка внутри шага): {hp}")

not_process = {
    "список требований": "## 2 Описание процесса\n\n1. Система должна хранить файлы не менее пяти лет.\n"
                         "2. Система должна шифровать файлы при передаче.\n3. Доступ к файлам должен быть по ролям.\n",
    "участники": "## 1 Общие сведения\n\nУчастники взаимодействия:\n\n- Поставщик — формирует и направляет отчётные "
                 "формы в срок.\n- Служба отчётности — проверяет формы и направляет результат.\n- Платформа интеграции — "
                 "обеспечивает доставку сообщений участникам.\n",
    "термины": "## 1.2 Термины и определения\n\n1. Отчётная форма — документ установленного образца с данными.\n"
               "2. Поставщик — организация, которая направляет отчётные формы.\n3. Хранилище — система хранения "
               "данных отчётности за все годы.\n",
    "свойства без признака процесса": "## 3 Особенности\n\nСистема обладает следующими свойствами\n\n- Поддерживает "
                                      "работу с большим числом пользователей.\n- Позволяет выгружать отчёты в "
                                      "нескольких форматах.\n- Сохраняет историю изменений каждой записи.\n",
    "короткий перечень": "## 2 Порядок работы\n\n1. Вход.\n2. Поиск.\n3. Выгрузка.\n",
}
wrong = {k: app.find_processes(app.document_blocks("# ТЗ\n\n" + v)) for k, v in not_process.items()}
check(not any(wrong.values()), f"не процесс: требования, участники, термины, свойства, перечень названий: "
                               f"{ {k: len(v) for k, v in wrong.items()} }")
bullets = app.find_processes(app.document_blocks(
    "# ТЗ\n\n## 3 Приём отчётов\n\nПроцесс включает следующие действия:\n\n- поставщик выгружает отчёт из учётной "
    "системы и подписывает его;\n- портал принимает отчёт и проверяет электронную подпись;\n- хранилище сохраняет "
    "отчёт и уведомляет службу отчётности.\n"))
check(len(bullets) == 1 and [n for n, _s in bullets[0]["steps"]] == ["1", "2", "3"],
      "маркированный список после «Процесс включает следующие действия:» — шаги 1–3")

print("2. [unit] Цифры: показатели и расчёты программы")
facts = app.extract_quantities(blocks)
check([(f["value"], f["period"], f["stat"]) for f in facts] == [("10 Мб", "day", "avg"), ("200 Гб", "year", None)],
      f"показатели с периодом и видом: {[(f['value'], f['period'], f['stat']) for f in facts]}")
calc = app.quantity_calculations(facts)
check(len(calc) == 1 and "× 365 = 3,56 Гб" in calc[0] and "больше в 56,1 раза" in calc[0],
      f"сутки × 365 против года считает программа: {calc}")
mx = [{"label": "Макс. за сутки", "value": "4 Гб", "bytes": 4 * 2 ** 30, "period": "day", "stat": "max", "section": "a"},
      {"label": "За год", "value": "200 Гб", "bytes": 200 * 2 ** 30, "period": "year", "stat": None, "section": "b"}]
check(not app.quantity_calculations(mx), "максимум за сутки × 365 больше годового — не расхождение")

print("3. [unit] Оформление без модели")
fmt = {f["text"].split(":")[0]: f for f in app.check_formatting(blocks)}
texts = " | ".join(f["text"] for f in fmt.values())
check("«3.4 Приёмочные испытания»" in texts and "1.1. Назначение" not in texts.split("обычным текстом")[1].split("|")[0],
      f"пункт текстом вместо заголовка; строки содержания не в счёт: {texts[:200]}")
check("«3.2 Требования к безопасности»" in texts.split("нет в содержании:")[1].split("|")[0],
      "раздел есть в документе, но нет в содержании")
check("Таблица в разделе «4 Журнал изменений» не заполнена" in texts
      and "не заполнено: «Регламентирующие документы»" in texts
      and "не заполнены колонки: «Описание требований»" in texts,
      "пустая таблица, пустое поле и пустая колонка")
check("Разделы без текста" not in texts, "раздел «Модель…» без текста не отмечается: там обычно только схема")
check("Разделы без текста: «2 Пусто»" in " ".join(f["text"] for f in app.check_formatting(app.document_blocks(
    "# Т\n\n## 1 Текст\n\nАбзац.\n\n## 2 Пусто\n\n## 3 Ещё\n\nАбзац."))), "пустой раздел")
check(not app.check_formatting(app.document_blocks("## Приложение. Реестр\n\n| № | Комментарий |\n|---|---|\n| 1 | |")),
      "шаблоны в приложении не отмечаются")
gap_doc = ("## 2.1 Процесс\n\n| № | Операция | Исполнитель | Входные данные | Результаты | Сервис |\n|---|---|---|---|---|---|\n"
           "| 1. | Приём | Портал | Форма | Получена | ЛКП |\n| 2. | Проверка | Служба | Форма | Итог |  |\n"
           "| 3. | Отправка | Служба | Итог | Отправлен | ЛКП |")
check(any("шаг 2 — «Сервис»" in f["text"] for f in app.check_formatting(app.document_blocks(gap_doc))),
      "шаг таблицы операций без сервиса")
bold_doc = ("# Записка\n\n## Содержание\n\n**1.\tОбщие положения\t3**\n\n1.1.\tНазначение\t3\n\n1.2.\tСокращения\t3\n\n1.3.\tТермины\t4\n\n"
            "**2.\tПроцесс\t5**\n\n2.1.\tОписание\t5\n\n**Приложение. Реестр вопросов*\t9**\n\n"
            "## 1 Общие положения\n\n### 1.1 Назначение\n\nТекст.\n\n### 1.2 Сокращения\n\nТекст.\n\n### 1.3 Термины\n\nТекст.\n\n"
            "## 2 Процесс\n\n### 2.1 Описание\n\n| **№** | **Операция** | **Исполнитель** | **Входные данные** | "
            "**Результаты** | **Сервис** |\n|---|---|---|---|---|---|\n| 1. | Приём | Портал | Форма | Получена | ЛКП |\n"
            "| 2. | Проверка | Служба | Форма | Итог |  |\n| 3. | Отправка | Служба | Итог | Отправлен | ЛКП |\n\n"
            "## Приложение. Реестр вопросов*\n\nТекст.")
bold = " | ".join(f["text"] for f in app.check_formatting(app.document_blocks(bold_doc)))
app_doc = ("# Руководство\n\n## Содержание\n\n1 Общие положения 3\n\n2 Ресурсы 4\n\nПриложение А Структура каталогов 12\n\n"
           "Таблица А.1 – Пример структуры каталога 13\n\nПриложение Б Перечень событий 14\n\n## 1 Общие положения\n\nТекст.\n\n"
           "## 2 Ресурсы\n\n| № | Имя сервера | Домен | Описание |\n|---|---|---|---|\n| Зона эксплуатации |  |  |  |\n"
           "|  | srv-01 | .corp.example | Сервер БД |\n|  | srv-02 | .corp.example | Сервер приложений |\n"
           "| Зона тестирования |  |  |  |\n|  | srv-03 | .test.example | Сервер БД |\n\n"
           "## Структура каталогов\n\nТекст.\n\n## Перечень событий\n\nТекст.\n")
app_fmt = " | ".join(f["text"] for f in app.check_formatting(app.document_blocks(app_doc)))
check("содержани" not in app_fmt and "не заполнены колонки" not in app_fmt,
      f"«Приложение А» из нумерации Word и подписи таблиц в содержании — не расхождение; колонки с пустым «№» и "
      f"строками зон — заполнены: {app_fmt}")
check("содержани" not in bold and "шаг 2 — «Сервис»" in bold and "**" not in bold,
      f"строки содержания и шапка таблицы жирным — не ложные расхождения, в замечаниях без звёздочек: {bold[:300]}")

print("4. [unit] Задачи для модели: состав, лимит, противоречия")
parts = app.split_document_parts(DOC, 1500)
tasks = app.build_deep_tasks(blocks, parts)
kinds = Counter(x["kind"] for x in tasks)
check(kinds["boundary"] == 1 and kinds["step"] == 4 and kinds["requirement"] == 2 and kinds["numbers"] == 1
      and kinds["claims"] == kinds["language"] == len(parts), f"вопросы по процессу, цифрам и частям: {dict(kinds)}")
step34 = next(x for x in tasks if x["kind"] == "step" and "шаг 3 → шаг 4" in x["title"])
check("Границы бизнес-процесса" in step34["user"] and "2.1.4. Отчётные формы шифруются" in step34["user"]
      and step34["user"].split("--- ПРОВЕРЯЕМЫЙ ПЕРЕХОД ---")[1].count("Шаг ") == 2,
      "в вопросе о переходе — сведения, требования, вся таблица и проверяемая пара шагов")
kept, skipped = app.limit_tasks(tasks, 6)
check(skipped == len(tasks) - 6 and [x["kind"] for x in kept] == ["boundary", "step", "step", "step", "step", "requirement"],
      f"при лимите первыми идут вопросы о процессе: {[x['kind'] for x in kept]}")
conf = app.conflict_tasks([("категория данных", "содержит ПД", "3.1"), ("Категория данных", "ПД не обрабатываются", "3.2"),
                           ("хранение", "год", "3.1"), ("выдуманная тема", "x", "3.2"), ("хранение", "год", "3.1")])
check(len(conf) == 1 and "«3.1»: содержит ПД" in conf[0]["user"] and "«3.2»: ПД не обрабатываются" in conf[0]["user"],
      "сравниваются утверждения одной темы; тема вне списка и одно утверждение (повтор) — нет")

print("5. [интеграция] Аудит с глубокой проверкой")
cfg, _ = app.load_settings()
cfg = replace(cfg, llm_context_tokens=32768, audit_map_size=1500, use_self_critique=False, audit_parallel=3)
STATE["requests"].clear()
events = []
res = app.run_audit(DOC, "ФТ.md", cfg, use_wiki=False, deep=True, on_progress=lambda e, **d: events.append(e))
texts = [f["text"] for f in res["findings"]]
expect = {"шаг 3 → шаг 4": "переход между шагами", "нет шага расшифрования": "требование без шага",
          "итогового отчёта потребителю": "границы процесса", "обработка ПД не предполагается": "противоречие разделов",
          "объём за сутки и за год": "цифры", "«соотвествии» → «соответствии»": "опечатка"}
for needle, what in expect.items():
    check(any(needle in x for x in texts), f"в заключении — {what}")
check(any("3.4 Приёмочные испытания" in x for x in texts) and any("Журнал изменений" in x for x in texts),
      "в заключении — замечания об оформлении")
deep_calls = [c for c in chats() if "эксперт-аудитор" in c["messages"][0]["content"]
              and "ОБЯЗАТЕЛЬНЫЕ ФОКУСЫ" not in c["messages"][0]["content"]]
check(len(res["deep"]) == len(tasks) + 1 and events.count("deep") == 2 and events.count("deep_task") == len(res["deep"])
      and len(deep_calls) >= 8, f"вопросы глубокой проверки и сравнение утверждений: {len(res['deep'])}")
check("## Глубокая проверка" in res["log_md"] and "### Процесс «2.1 Описание процесса»: шаг 3 → шаг 4" in res["log_md"]
      and "_Глубокая проверка: вопросов модели:" in res["report"], "в логе — каждый вопрос, в заключении — итог")
check(any("«соотвествии»" in f["text"] for f in res["typos"]) and "Опечатки — без модели: было" in res["log_md"],
      "опечатки сводятся без модели — в логе это видно")
f34 = next(f for f in res["findings"] if "шаг 3 → шаг 4" in f["text"])
check(f34["sections"] == ["2.1 Описание процесса"] and f34["source"] == "deep", "у замечания — раздел таблицы операций")
check("**Процесс в документе (глубокая проверка):** «2.1 Описание процесса» — таблица, шагов: 5" in res["log_md"],
      "в шапке лога — какой процесс нашла глубокая проверка")

print("5а. [интеграция] Аудит документа, где процесс описан списком")
res_list = app.run_audit(LIST_DOC, "ТТ.md", cfg, use_wiki=False, deep=True)
fl = [f for f in res_list["findings"] if "шаг 3 → шаг 4" in f["text"]]
check(fl and fl[0]["sections"] == ["2.1 Порядок обмена"]
      and any("нет шага расшифрования" in f["text"] for f in res_list["findings"])
      and "**Процесс в документе (глубокая проверка):** «2.1 Порядок обмена» — список, шагов: 4" in res_list["log_md"]
      and "### Процесс «2.1 Порядок обмена»: шаг 3 → шаг 4" in res_list["log_md"],
      "переход между шагами и требование без шага — найдены и в процессе, описанном списком")
res_none = app.run_audit("# Записка\n\n## 1 Общее\n\nТекст записки без процесса.\n", "З.md", cfg, use_wiki=False,
                         deep=True)
check("**Процесс в документе (глубокая проверка):** не найден: шаги процесса ищутся в таблицах операций" in
      res_none["log_md"], "процесса нет — в логе сказано, где MINT его искал")

print("6. [интеграция] Параллельные вопросы: язык сеанса передаётся, результат как при последовательных")
STATE["requests"].clear()
seq = app.run_tasks(tasks[:6], replace(cfg, audit_parallel=1), parallel=1)
par = app.run_tasks(tasks[:6], cfg, parallel=3)
check([e["report"] for e in seq] == [e["report"] for e in par], "параллельно — те же ответы и в том же порядке")
app.set_lang("en")
STATE["requests"].clear()
en_tasks = app.build_deep_tasks(blocks, parts)[:4]
app.run_tasks(en_tasks, cfg, parallel=3)
app.set_lang("ru")
check(chats() and all("Section is clean" in c["messages"][0]["content"] for c in chats()),
      "в потоках — промпты на языке сеанса (английский)")

print("7. [интеграция] Лимит вопросов и повтор после сбоя")
res_l = app.run_audit(DOC, "ФТ.md", replace(cfg, audit_deep_max_calls=5), use_wiki=False, deep=True)
check(len(res_l["deep"]) == 5 and "пропущено по лимиту: " in res_l["log_md"]
      and "пропущено по лимиту: 0" not in res_l["log_md"], f"лимит соблюдён: {len(res_l['deep'])}")
STATE["fail_words"] = {"Операция 5": 2}
res_f = app.run_audit(DOC, "ФТ.md", replace(cfg, llm_retries=1, audit_deep_max_calls=8), use_wiki=False, deep=True)
STATE["fail_words"] = {}
retried = [e for e in res_f["deep"] if e["attempts"] == 2]
check(retried and not any(e["failed"] for e in res_f["deep"]), f"вопрос, на который шлюз не ответил, задан ещё раз: {len(retried)}")
res_off = app.run_audit(DOC, "ФТ.md", cfg, use_wiki=False, deep=False)
check(not res_off["deep"] and "**Глубокая проверка:** выключена" in res_off["log_md"], "выключена — вопросов нет")

print("7а. [интеграция] Модель заполняет шаблон — в заключении не больше двух замечаний на переход")
step = next(t for t in tasks if t["kind"] == "step")
STATE["step_reply"] = ("- [НИЗКИЙ] шаг 1 → шаг 2: наименования файла на шагах не совпадают дословно\n"
                       "- [СРЕДНИЙ] шаг 1 → шаг 2: не описано, как файл попадает от отправителя в систему приёма\n"
                       "- [НИЗКИЙ] шаг 1 → шаг 2: неясно, проверяется ли формат файла на этом шаге\n"
                       "- [КРИТИЧНЫЙ] шаг 1 → шаг 2: файл зашифрован на сертификат другого участника — получатель "
                       "не сможет его прочитать")
e_step = app.run_task(step, cfg)
STATE.pop("step_reply")
check([f["severity"] for f in e_step["findings"]] == ["СРЕДНИЙ", "КРИТИЧНЫЙ"]
      and "Сверх лимита (в заключение не вошли)" in e_step["report"] and "дословно" in e_step["report"],
      f"переход: 4 замечания — оставлены 2 самых критичных в порядке ответа, остальные видны в логе: "
      f"{[f['severity'] for f in e_step['findings']]}")
check(app.DEEP_KIND_MAX["step"] == 2 and app.DEEP_KIND_MAX["requirement"] == 2 and app.DEEP_KIND_MAX["boundary"] == 3
      and app.DEEP_KIND_MAX["conflict"] == 2, "лимиты по видам вопросов: переход 2, требование 2, границы 3, противоречия 2")

print("8. [unit + интеграция] Сверка с эталоном")
check(app.parse_reference("1. Непонятно по процессу:\nчто дальше после шага 3\n- Нет шага расшифрования\nкоротко\n\n") ==
      ["Непонятно по процессу: что дальше после шага 3", "Нет шага расшифрования", "коротко"],
      "эталон: по пункту на строку, продолжение после двоеточия — к пункту")
cmp = app.compare_with_reference(res, "Переход шаг 3 → шаг 4: как отчётная форма попадает в платформу\n"
                                      "Нет резервного копирования хранилища", cfg)
check(cmp["total"] == 2 and cmp["found"] == 1 and cmp["missed"] == 1 and cmp["rows"][0]["found"]
      and not cmp["error"], f"найдено одно из двух эталонных замечаний: {cmp}")
md = app.reference_markdown(cmp, "ФТ.md", cfg)
check("**найдено:** 1 из 2" in md and "| 1 | Переход шаг 3" in md and "❌ не найдено" in md, "итог сверки — таблицей")
REF4 = ("Переход шаг 3 → шаг 4: как отчётная форма попадает в платформу\nНет резервного копирования хранилища\n"
        "Нет шага расшифрования\nОбъём за сутки и за год не согласованы")
STATE["requests"].clear()
STATE["reference_garble"] = 1
cmp_b = app.compare_with_reference(res, REF4, cfg)
ref_calls = [c for c in chats() if "сверяешь результат аудита с эталоном" in c["messages"][0]["content"]]
check(cmp_b["total"] == 4 and cmp_b["found"] == 3 and cmp_b["missed"] == 1 and not cmp_b["error"]
      and len(ref_calls) == 3, f"ответ не по формату — эталон сверяется пачками по 3 пункта: запросов {len(ref_calls)}, "
                               f"найдено {cmp_b['found']}, ошибка «{cmp_b['error']}»")
STATE["reference_garble"] = 5
cmp_x = app.compare_with_reference(res, REF4, cfg)
STATE["reference_garble"] = 0
check(cmp_x["found"] == 0 and "ответ модели не разобран: «Сверка [эталон]" in cmp_x["error"],
      f"не разобрано и пачками — в ошибке видно начало ответа модели: {cmp_x['error']}")
REF9 = "\n".join([REF4] * 3).replace("Нет резервного", "Нет резервного")
STATE["requests"].clear()
STATE["reference_style"] = "pretty"
cmp_p = app.compare_with_reference(res, REF9, cfg)
STATE.pop("reference_style")
ref_calls = [c for c in chats() if "сверяешь результат аудита с эталоном" in c["messages"][0]["content"]]
check(cmp_p["total"] == 12 and cmp_p["found"] == 9 and cmp_p["missed"] == 3 and not cmp_p["error"] and len(ref_calls) == 1,
      f"JSON с переносами строк и вердиктом «✅ найдено» — один запрос, не принят за зацикливание: "
      f"запросов {len(ref_calls)}, найдено {cmp_p['found']}, не найдено {cmp_p['missed']}, «{cmp_p['error']}»")
STATE["requests"].clear()
STATE["reference_only"] = 2
cmp_o = app.compare_with_reference(res, REF4, cfg)
ref_calls = [c for c in chats() if "сверяешь результат аудита с эталоном" in c["messages"][0]["content"]]
check(cmp_o["found"] == 3 and cmp_o["missed"] == 1 and not cmp_o["error"] and len(ref_calls) == 2
      and "3. Нет шага расшифрования" in ref_calls[1]["messages"][-1]["content"]
      and "1. Переход" not in ref_calls[1]["messages"][-1]["content"],
      f"модель ответила на 2 пункта из 4 — остальные переспрошены отдельно: запросов {len(ref_calls)}")
check([app.reference_verdict(x) for x in ("✅ найдено", "Partially", "Не найдено", "Да", "НАЙДЕНО|ЧАСТИЧНО|НЕТ")]
      == ["found", "partial", "missed", "found", "unknown"], "вердикт сверки в любом виде; шаблон из промпта — не вердикт")
raw_d = res["state"]["raw"]
check(any(r["label"] == "Процесс «2.1 Описание процесса»: шаг 3 → шаг 4" and "отчётная форма" in r["answer"] for r in raw_d)
      and any(r["label"] == "Сверка с эталоном" for r in raw_d),
      "в сырых ответах — вопросы глубокой проверки с подписью и запросы сверки с эталоном")
check(app.compare_with_reference(res, "  \n", cfg)["error"] and
      app.compare_with_reference({"findings": []}, "Что-то важное", cfg)["missed"] == 1,
      "пустой эталон — подсказка; замечаний нет — всё «не найдено»")

srv.shutdown()
os.chdir(harness.ROOT)
shutil.rmtree(W, ignore_errors=True)
check.finish()

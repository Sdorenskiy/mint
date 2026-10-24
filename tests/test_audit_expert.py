"""Экспертные материалы аудита: чек-листы по типам документов, документы базы «учитывать всегда» (правила
экспертов) и карточки систем — подключаются по упоминаниям, вопрос «что документ требует от системы».

Все документы в тесте выдуманные: «Система А», «Шлюз Б», «Участник А» — нейтральные имена.

Запуск из корня проекта:  python tests/test_audit_expert.py
"""
import os
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402
import mock_server  # noqa: E402

W = harness.make_project(prefix="mint_expert_", extra_files=("checklists.example.yaml", "checklists.example.en.yaml"))
srv = mock_server.start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/v1"
os.environ.update({
    "LLM_API_URL": BASE, "EMBED_API_URL": BASE + "/embeddings", "RERANK_API_URL": "",
    "LLM_MODEL": "test-llm", "EMBED_MODEL": "emb-model", "KB_DIR": str(W / "kb"), "LOG_DIR": str(W / "logs"),
    "MINT_CONFIG": str(W / "none.yaml"), "GLOSSARY_PATH": str(W / "none.json"), "MINT_LANG": "ru",
})
os.environ.pop("MINT_CHECKLISTS", None)
os.chdir(W)
app = harness.load_mint(W, include_ui=False)
check = harness.Checker()
STATE = mock_server.STATE
cfg, _ = app.load_settings()
cfg = replace(cfg, llm_context_tokens=32768, llm_timeout=20, llm_retries=1, audit_deep=False,
              audit_merge_duplicates=False, use_self_critique=False, parent_size=700, parent_overlap=50,
              child_size=300, child_overlap=30)


def chats():
    return [p for m, path, p in STATE["requests"] if path.endswith("/chat/completions") and p]


def msg(p, role):
    return next((m["content"] for m in p.get("messages") or [] if m["role"] == role), "")


DOC = """# ТЕХНИЧЕСКОЕ ЗАДАНИЕ
на создание портала отчётности поставщиков

## 1 Общие положения

### 1.1 Назначение

Портал отчётности принимает отчётные формы поставщиков и передаёт их в Систему А для обработки и хранения.

### 1.2 Сокращения

| Сокращение | Расшифровка |
| --- | --- |
| ОФ | Отчётная форма |

## 2 Требования к взаимодействию

### 2.2 Приём файлов

Портал передаёт файлы ОФ в Систему А через REST API сразу после проверки формата.

### 2.3 Объём

Размер одного файла ОФ — до 500 Мб. Файлы передаются ежедневно.

### 2.4 Хранение

Система А хранит принятые файлы ОФ 5 лет и выдаёт их по запросу аудитора.

## 3 Защита информации

Файлы ОФ шифруются на сертификат портала и передаются через Шлюз Б по защищённому каналу.

## 4 Этапы работ

Этап 1 — проектирование, этап 2 — разработка, этап 3 — испытания.
"""

RULES = """# Правила экспертов

## КРИПТ-01. Шифрование — на сертификат получателя

Когда применяется: данные на каком-либо шаге передаются в зашифрованном виде.
Правило: Участник А шифрует данные на сертификат участника Б, который будет их расшифровывать. Для каждого
шага, где участник получает зашифрованные данные, должно быть указано, на чей сертификат они зашифрованы и кто,
где их расшифровывает. Типичная ошибка: получатель «принимает» данные, зашифрованные на чужой сертификат, —
прочитать их он не может. Ключ шифрования хранится только у получателя, передача ключа по почте запрещена.

## ХРАН-01. Срок хранения файлов

Когда применяется: документ задаёт срок хранения файлов или архива.
Правило: срок хранения файлов должен совпадать со сроком, который обеспечивает система хранения; если документ
требует срок дольше, чем умеет система, — нужно указать доработку системы или другое хранилище. Срок хранения
указывается в годах, вместе с порядком удаления файлов по окончании срока и ответственным за удаление архива.
"""

CARD_A = """# Карточка системы «Система А»

Названия: Система А, СА, System A
Актуально на: 10.2026

## Что умеет сейчас

Приём файлов через REST API, размер файла — не больше 100 Мб. Обработка отчётных форм по расписанию.

## Ограничения

Файлы хранятся 1 год, затем удаляются автоматически.

## Планы

Файлы до 1 Гб — 2 квартал 2027 года.
"""

CARD_B = """# Карточка системы «Шлюз Б»

Названия: Шлюз Б

## Что умеет сейчас

Передача файлов по защищённому каналу, шифрование на сертификат получателя.
"""

REG = """# Регламент обмена

## 1 Общие требования

Обмен файлами между системами выполняется по защищённому каналу с контролем целостности.
"""

print("1. [unit] Чек-листы: образец, свой файл, тип документа по названию")
cl = app.load_checklists()
check(cl["source"] == "example" and cl["common"] and len(cl["types"]) >= 4,
      f"своего файла нет — образец: общих пунктов {len(cl['common'])}, типов {len(cl['types'])}")
t, word = app.detect_document_type(DOC, "проект.docx", cl)
check(t and t["name"] == "Техническое задание" and word == "техническое задание",
      f"«ТЕХНИЧЕСКОЕ ЗАДАНИЕ» в начале — тип «Техническое задание» ({t and t['name']}, «{word}»)")
t2, _ = app.detect_document_type("# Протокол испытаний\n\nпо программе испытаний", "x.md", cl)
check(t2 and t2["name"] == "Протокол испытаний", "одно начало у двух слов («протокол», «протокол испытаний») — "
      "побеждает более длинное")
t3, w3 = app.detect_document_type("# Записка\n\nтекст", "Функциональные_требования_v2.docx", cl)
check(t3 and t3["name"] == "Функциональные требования", f"тип по имени файла: {t3 and t3['name']} («{w3}»)")
check(app.detect_document_type("# Записка\n\nПросто текст.", "a.md", cl) == (None, ""), "тип не найден — None")
REF_DOC = ("# Руководство по эксплуатации\n\nРазработано по требованиям документа «Портал отчётности. Техническое задание "
           "на развитие» (шифр 1.2.ТЗ.2).\n\nДокумент разработан на основании технического задания на создание портала "
           "отчётности поставщиков и требований к защите информации, утверждённых заказчиком в установленном порядке.\n")
check(app.detect_document_type(REF_DOC, "руководство.docx", cl) == (None, ""),
      "«Техническое задание» в кавычках и «на основании технического задания» в длинной фразе — ссылки на другой "
      "документ, не тип")
t4, _ = app.detect_document_type("| Утверждаю |  |\n|---|---|\n|  | ТЕХНИЧЕСКОЕ ЗАДАНИЕ |\n\nТекст.", "x.docx", cl)
check(t4 and t4["name"] == "Техническое задание", "название в ячейке таблицы титульного листа — тип найден")
items = app.checklist_items(cl, t)
check(items[:len(cl["common"])] == cl["common"] and len(items) == len(cl["common"]) + len(t["items"]),
      "пункты: общие, затем пункты типа")
own = {"common": ["Пункт для всех"], "types": [{"name": "Записка", "match": "служебная записка; записка",
                                                "items": "- Первый\n- Второй"}]}
path = app.save_checklists(own)
cl2 = app.load_checklists()
check(Path(path).resolve() == (W / "checklists.yaml").resolve() and cl2["source"] == "file" and cl2["types"][0]["match"] == [
    "служебная записка", "записка"] and cl2["types"][0]["items"] == ["Первый", "Второй"],
      "свой файл checklists.yaml рядом с программой: строки и «;» превращаются в списки")
check("в репозиторий не попадает" in (W / "checklists.yaml").read_text(encoding="utf-8"),
      "в своём файле — подсказка о формате")
(W / "checklists.yaml").unlink()

print("2. [unit] Карточки систем: названия и упоминания")
names = app.card_names(CARD_A, "Карточка_Система_А.md")
check(names[:3] == ["Система А", "СА", "System A"], f"названия из строки «Названия:» и заголовка: {names}")
check(app.card_names("# Карточка системы «Платформа данных»\n\nтекст", "x.md") == ["Платформа данных"],
      "без строки «Названия:» — название из заголовка в кавычках")
check(app.card_names("просто текст", "Карточка_Шлюз.md") == ["Шлюз"], "без заголовка — имя файла")
pat = app.names_pattern(names)
n = app.count_mentions(pat, "Передаёт в Систему А; Системой А принято; СА хранит. Система Альфа и «са» — нет; "
                            "System A works. САМ — нет.")
check(n == 4, f"упоминания с окончаниями и сокращение как написано: {n} из 4")
check(app.card_names("# Карточка системы «Система А»\n\nНазвания: Система А, СА Актуально на: 10.2026", "x.md")[:2]
      == ["Система А", "СА"], "строки карточки склеились при разборе — названия до следующей подписи «…:»")
check(app.count_mentions(app.names_pattern(["Платформа данных"]), "в платформе данных и Платформу Данных") == 2,
      "название из нескольких слов — с окончаниями и без учёта регистра")

print("3. [интеграция] База: правила «учитывать всегда» и карточки")
for name, text in (("Правила_экспертов.md", RULES), ("Карточка_Система_А.md", CARD_A),
                   ("Карточка_Шлюз_Б.md", CARD_B), ("Регламент_обмена.md", REG)):
    ok, m = app.process_and_add_to_kb(name, text.encode("utf-8"), cfg)
    check(ok, f"{name} в базе", m)
check(app.load_expert_materials(cfg) is None, "ролей не задано — материалов нет, аудит как раньше")
app.save_roles(cfg, always=["Правила_экспертов.md", "Карточка_Шлюз_Б.md"],
               cards=["Карточка_Система_А.md", "Карточка_Шлюз_Б.md", "Нет_такого.md"])
roles = app.load_roles(cfg)
check(roles["always"] == ["Правила_экспертов.md"] and "Карточка_Шлюз_Б.md" in roles["cards"],
      "документ — либо правило, либо карточка (карточка важнее)")
mat = app.load_expert_materials(cfg)
check(mat and [d["source"] for d in mat.always] == ["Правила_экспертов.md"]
      and [d["source"] for d in mat.cards] == ["Карточка_Система_А.md", "Карточка_Шлюз_Б.md"],
      "документа, которого нет в базе, нет и в материалах")
pins = app.select_pinned(mat, "Портал передаёт файлы в Систему А", 100000)
srcs = {it["source"] for it in pins}
check(srcs == {"Правила_экспертов.md", "Карточка_Система_А.md"} and all("=== ИСТОЧНИК:" in it["block"] for it in pins),
      f"правила — всегда, карточка — только упомянутой системы: {sorted(srcs)}")
check(any(it["short"].startswith("📌") for it in pins) and any(it["short"].startswith("🗂️") for it in pins),
      "в источниках видно: 📌 правило, 🗂️ карточка")
small = app.select_pinned(mat, "Срок хранения файлов архива в годах", 650)
text_small = "\n".join(it["block"] for it in small)
check("ответственным за удаление архива" in text_small and "Типичная ошибка" not in text_small,
      "не помещается — самые близкие к тексту фрагменты правил", text_small[:300])
check(app.select_pinned(mat, "текст", 0) == [] and app.select_pinned(None, "текст", 1000) == [],
      "лимит 0 или нет материалов — ничего")

print("4. [интеграция] Аудит: правила и карточки в проверке, чек-лист, требования к системе")
STATE["requests"].clear()
events = []
acfg = replace(cfg, audit_map_size=500)
res = app.run_audit(DOC, "ТЗ_портал.md", acfg, special="", use_wiki=True,
                    on_progress=lambda e, **d: events.append((e, d)),
                    checklist=["Для каждой роли описано, что она делает", "Все сокращения расшифрованы",
                               "Указаны сроки этапов работ"], doc_type="Техническое задание")
sec_prompts = [p for p in chats() if "ПРОВЕРЯЕМАЯ ГЛАВА ДОКУМЕНТА" in msg(p, "user")]
check(len(sec_prompts) >= 2, f"документ разбит на части: {len(sec_prompts)}")
check(all("ПРАВИЛА ЭКСПЕРТОВ И КАРТОЧКИ СИСТЕМ" in msg(p, "system") and "Правила_экспертов.md" in msg(p, "system")
          for p in sec_prompts), "правила экспертов — в каждой проверке раздела")
with_b = [p for p in sec_prompts if "Шлюз Б" in msg(p, "user").split("ПРОВЕРЯЕМАЯ ГЛАВА ДОКУМЕНТА")[-1]]
without_b = [p for p in sec_prompts if p not in with_b]
check(with_b and all("Карточка_Шлюз_Б.md" in msg(p, "system") for p in with_b)
      and all("Карточка_Шлюз_Б.md" not in msg(p, "system") for p in without_b),
      "карточка «Шлюз Б» — только в проверке раздела, где он упоминается")
dup = [p for p in sec_prompts if msg(p, "system").count("=== ИСТОЧНИК: Правила_экспертов.md") > len(
    [1 for b in msg(p, "system").split("ПРАВИЛА ЭКСПЕРТОВ")[1].split("НОРМАТИВНЫЕ ФРАГМЕНТЫ")[0].split("=== ИСТОЧНИК:")
     if b.strip().startswith("Правила_экспертов.md")])]
check(not dup, "фрагменты правил не повторяются среди найденных норм")
cl_prompts = [p for p in chats() if "по одному пункту чек-листа" in msg(p, "system")]
check(len(cl_prompts) == 3 and all("для документов типа «Техническое задание»" in msg(p, "system") for p in cl_prompts)
      and all("ПРАВИЛА ЭКСПЕРТОВ" in msg(p, "system") for p in cl_prompts),
      "каждый пункт чек-листа — отдельный вопрос, с типом документа и правилами")
verdicts = [e["verdict"] for e in res["checklist_answers"]]
check(verdicts == ["no", "yes", "partial"], f"ответы разобраны: {verdicts}")
rep = res["report"]
check("**Тип документа**: Техническое задание" in rep and "## ✅ ЧЕК-ЛИСТ «Техническое задание»" in rep
      and "Да — 1, частично — 1, нет — 1" in rep and "❌ **1. Для каждой роли" in rep, "блок чек-листа в заключении")
cl_f = [f for f in res["findings"] if f.get("point_kind") == "checklist"]
check(len(cl_f) == 2 and "роль «Оператор»" in rep.split("## ✅ ЧЕК-ЛИСТ")[1].split("## 🧩")[0],
      f"замечания по пунктам — под своими пунктами и в списке замечаний: {len(cl_f)}")
card_prompts = [p for p in chats() if "карточкой системы" in msg(p, "system")]
check(len(card_prompts) == 1 and "«Система А»" in msg(card_prompts[0], "system")
      and "Файлы хранятся 1 год" in msg(card_prompts[0], "user"),
      "вопрос о системе — только по «Системе А» (упомянута 4 раза; «Шлюз Б» — 1 раз), с текстом карточки")
sa = res["system_answers"][0]
check([c for c, _t in sa["statuses"]] == ["have", "change", "conflict"] and sa["mentions"] >= 2 and len(sa["findings"]) == 1,
      f"статусы и замечание разобраны: {sa['statuses']}")
block = rep.split("## 🧩 ЧТО ДОКУМЕНТ ТРЕБУЕТ ОТ СИСТЕМ")[1].split("## 📋")[0]
check(block.index("⛔ противоречие") < block.index("🛠️ нужна доработка") < block.index("✅ есть")
      and "Карточка_Система_А.md" in block and "**Замечания:**" in block,
      "блок о системах: сначала противоречия и доработки")
check(any(e == "points" and d["checklist"] == 3 and d["systems"] == ["Система А"] for e, d in events)
      and sum(1 for e, _d in events if e == "checklist_answer") == 3
      and sum(1 for e, _d in events if e == "system_answer") == 1, "события хода работы для интерфейса")
log = res["log_md"]
check("✅ Чек-лист: «Все сокращения расшифрованы»" in log and "🧩 Система «Система А»" in log
      and "Карточка_Система_А.md (Система А, СА, System A)" in log and "Правила_экспертов.md" in log,
      "лог: ответы на пункты, правила и карточки с найденными названиями")
check(any(s.startswith("📌 Правила_экспертов.md") for e in res["log"] for s in e["sources"]),
      "в источниках раздела видно правило экспертов")

print("5. [интеграция] Без базы знаний и без вопроса о системах")
STATE["requests"].clear()
res2 = app.run_audit(DOC, "ТЗ_портал.md", acfg, use_wiki=False, checklist=["Указаны сроки этапов работ"])
check(not any("ПРАВИЛА ЭКСПЕРТОВ" in msg(p, "system") for p in chats()) and not res2["system_answers"]
      and "## ✅ ЧЕК-ЛИСТ\n" in res2["report"], "без базы — ни правил, ни карточек; чек-лист без типа работает")
STATE["requests"].clear()
res3 = app.run_audit(DOC, "ТЗ_портал.md", replace(acfg, audit_systems=False), use_wiki=True)
check(not res3["system_answers"] and "## 🧩" not in res3["report"]
      and any("Карточка_Система_А.md" in msg(p, "system") for p in chats()),
      "audit_systems выключен — вопроса нет, а карточка в проверке разделов осталась")

print("6. [интеграция] Повтор пункта чек-листа после сбоя")
STATE["requests"].clear()
STATE["fail_words"]["СБОЙНЫЙ"] = 1
res4 = app.run_audit(DOC, "ТЗ_портал.md", acfg, use_wiki=True, retry_failed=False, systems=False,
                     checklist=["СБОЙНЫЙ пункт про сроки этапов"])
check(res4["checklist_answers"][0]["failed"] and "ответ не получен — 1" in res4["report"],
      "пункт без ответа — в заключении отмечен")
res5 = app.recheck_failed_sections(res4, "ТЗ_портал.md", acfg)
e5 = res5["checklist_answers"][0]
check(not e5["failed"] and e5["attempts"] == 2 and e5["verdict"] == "partial", "перепроверка получила ответ")
STATE["fail_words"].clear()

print("7. [unit] Ответ на пункт: формы ответа")
check([app.checklist_verdict(x) for x in ("Да — есть", "нет.", "Частично: да", "не относится", "Partially", "N/A",
                                          "данные есть", "")] == ["yes", "no", "partial", "na", "partial", "na",
                                                                  "unknown", "unknown"],
      "да / нет / частично / не относится — по первому слову, «данные» — не «да»")

print("8. [интеграция] Черновик карточки системы по базе знаний")
STATE["requests"].clear()
progress_ = []
card = app.draft_system_card("Система А", cfg, aliases=["СисА"], on_progress=lambda d, t, e: progress_.append((d, t)))
card_calls = [c for c in chats() if "составить карточку системы" in msg(c, "system")]
md_ = card["markdown"]
check(len(card_calls) == len(app.CARD_SECTIONS) and progress_[-1] == (len(app.CARD_SECTIONS), len(app.CARD_SECTIONS))
      and all("ФРАГМЕНТЫ БАЗЫ ЗНАНИЙ" in msg(c, "user") and "=== ИСТОЧНИК:" in msg(c, "user") for c in card_calls),
      f"по вопросу на раздел карточки, каждый — с найденными фрагментами базы: {len(card_calls)}")
check(md_.startswith("# Карточка системы «Система А»") and "\nНазвания: Система А, СисА, СА, System A\n" in md_
      and app.card_names(md_, "Карточка_Система_А.md")[:2] == ["Система А", "СисА"],
      "заголовок и «Названия:» — как у карточки, которую узнаёт аудит; варианты из базы добавлены")
check("⚠️ ЧЕРНОВИК" in md_ and "## Что умеет сейчас" in md_ and "### Лимиты и объёмы" in md_
      and "- размер файла — не больше 100 Мб [Источник:" in md_,
      "черновик по шаблону: разделы и факты со ссылкой на источник")
plans_ = md_.split("## Что в планах и к какому сроку")[1].split("\n## ")[0]
check("Нет в базе — заполнит эксперт" in plans_ and "Что в планах и к какому сроку" in card["gaps"],
      "«нет в базе» — пробел для эксперта")
check(card["unconfirmed"] == 1 and "обработка по расписанию [Источник: Выдуманный_документ.md] ⚠️ проверьте" in md_,
      "ссылка на файл, которого нет среди найденных фрагментов, — с пометкой «проверьте»")
src_part = md_.split("## Источники")[1]
src_lines = [ln for ln in src_part.splitlines() if ln.startswith("- ")]
check("## Источники, по которым собран черновик" in md_ and "Карточка_Система_А.md" in src_part
      and len(src_lines) == len(set(src_lines)) and "итог" not in src_part and "rerank" not in src_part
      and app.source_name("📄 Ф.docx › 1 Раздел (итог 0.0443 · dense #1 · rerank 0.20 (не учтён))") == "Ф.docx › 1 Раздел",
      f"в конце — источники без повторов и баллов поиска: {src_lines[:4]}")
STATE["fail_words"]["защищает данные"] = 5
card2 = app.draft_system_card("Система А", replace(cfg, llm_retries=1), on_progress=None)
STATE["fail_words"].clear()
check(card2["failed"] == ["Защита данных"] and "_Не получено:" in card2["markdown"],
      f"сбой модели на разделе — пометка в черновике, остальное собрано: {card2['failed']}")
try:
    app.draft_system_card("  ", cfg)
    check(False, "пустое название — ошибка")
except ValueError:
    check(True, "пустое название — ошибка")
for k_ in ("card_section_system", "card_section_user"):
    check(app.prompt_text(k_, "en") and "{{" not in app.prompt_text(k_, "ru")[:5], f"промпт {k_} — на двух языках")

print("9. [интеграция] Документы-основания: ссылки документа → документы базы → в каждой проверке")
TZ = ("# Портал отчётности. Техническое задание на развитие\n\nШифр: ОРГ.10.0.123.ТЗ.5\n\n## 4 Требования\n\n"
      "### 4.2 Требования к журналированию\n\n4.2.1.14 Журналы и события безопасности компонентов портала передаются в "
      "подсистему мониторинга; в систему анализа событий их передаёт подсистема мониторинга.\n\n"
      "### 4.3 Требования к хранению\n\nОтчёты хранятся пять лет.\n")
TZ_OLD = TZ.replace("ОРГ.10.0.123.ТЗ.5", "ОРГ.10.0.123.ТЗ.3")
NOTE = ("# Пояснительная записка\n\nЗаписка разработана в соответствии с документом ОРГ.10.0.123.ТЗ.5.\n\n"
        "## 1 Общие сведения\n\nПортал принимает отчёты.\n")
for name, text in (("ТЗ_портал_отчётности.md", TZ), ("ТЗ_старое.md", TZ_OLD), ("Пояснительная_записка.md", NOTE)):
    ok, m = app.process_and_add_to_kb(name, text.encode("utf-8"), cfg)
    check(ok, f"{name} в базе", m)
GUIDE = ("# Руководство по эксплуатации портала\n\nДокумент разработан в соответствии с требованиями документов:\n\n"
         "- «Портал отчётности. Техническое задание на развитие» (ОРГ.10.0.123.ТЗ.5) по договору № 1;\n"
         "- «Регламент обмена файлами между системами» (ОРГ.1.2.3.РГ.1).\n\n## 1 Журналирование\n\n"
         "Журналы сервера приложений передаются агентом напрямую в систему анализа событий.\n\n"
         "## Ссылочные документы\n\n| № | Документ |\n|---|---|\n| 1 | Порядок согласования эскизов интерфейса |\n")
refs = app.basis_references(GUIDE)
check([(r["title"], r["code"]) for r in refs] == [
    ("Портал отчётности. Техническое задание на развитие", "ОРГ.10.0.123.ТЗ.5"),
    ("Регламент обмена файлами между системами", "ОРГ.1.2.3.РГ.1"), ("Порядок согласования эскизов интерфейса", "")],
      f"ссылки с титула (название и шифр) и из «Ссылочных документов»: {refs}")
found = app.find_basis_documents(refs, cfg, exclude=["Руководство.md"])
check([(d["source"], d["by"]) for d in found["docs"]] == [("ТЗ_портал_отчётности.md", "code"),
                                                          ("Регламент_обмена.md", "title")]
      and [r["title"] for r in found["missing"]] == ["Порядок согласования эскизов интерфейса"],
      f"по шифру — сам ТЗ (не старая редакция и не записка, которая на него ссылается); по названию — регламент; "
      f"чего нет в базе — в «нет в базе»: {found}")
STATE["requests"].clear()
ev_b = []
res_b = app.run_audit(GUIDE, "Руководство.md", replace(cfg, audit_map_size=3000), use_wiki=True, systems=False,
                      on_progress=lambda e, **d: ev_b.append(e))
maps = [c for c in chats() if "ДОКУМЕНТЫ-ОСНОВАНИЯ" in msg(c, "system")]
check(maps and "4.2.1.14 Журналы и события безопасности" in msg(maps[0], "system") and "basis" in ev_b
      and "📎 ТЗ_портал_отчётности.md" in res_b["log_md"]
      and "**Документы-основания (audit_basis_docs):** ТЗ_портал_отчётности.md (по шифру" in res_b["log_md"]
      and "в базе нет: «Порядок согласования эскизов интерфейса»" in res_b["log_md"],
      "требование документа-основания — в проверке раздела отдельным блоком; в логе — какие найдены и каких нет")
STATE["requests"].clear()
res_m = app.run_audit(GUIDE, "Руководство.md", cfg, use_wiki=True, systems=False, basis=[])
res_o = app.run_audit(GUIDE, "Руководство.md", replace(cfg, audit_basis_docs=False), use_wiki=True, systems=False)
check(not any("ДОКУМЕНТЫ-ОСНОВАНИЯ" in msg(c, "system") for c in chats())
      and "**Документы-основания (audit_basis_docs):** найдены, но сняты вручную: ТЗ_портал_отчётности.md (по шифру"
      in res_m["log_md"]
      and "**Документы-основания (audit_basis_docs):** выключено" in res_o["log_md"],
      "сняты в интерфейсе или выключены в настройках — без документов-оснований; в логе — что MINT нашёл сам",
      res_m["log_md"][:1500])
res_h = app.run_audit(GUIDE, "Руководство.md", cfg, use_wiki=True, systems=False,
                      basis=["ТЗ_старое.md", "ТЗ_портал_отчётности.md"])
check("ТЗ_старое.md (выбран вручную); ТЗ_портал_отчётности.md (по шифру" in res_h["log_md"],
      "в логе: добавленный в интерфейсе — «выбран вручную», оставленный из найденных — как он найден")

print("10. [unit] Документы-основания: документ того же семейства, который ссылается на то же ТЗ, — не основание")
SVC_TZ = "# Сервис уведомлений. Техническое задание на развитие\n\n## 1 Общие сведения\n\nСервис рассылает уведомления.\n"
SVC_ADMIN = ("# Руководство администратора\n\nРуководство разработано в соответствии с требованиями документов: "
             "«Сервис уведомлений. Техническое задание на развитие» (ОРГ.9.9.ТЗ.7).\n\n## 1 Установка\n\n"
             "Установка выполняется с дистрибутива.\n")
for name, text in (("ТЗ_сервис_уведомлений.md", SVC_TZ), ("Руководство_администратора_сервиса.md", SVC_ADMIN)):
    ok, m = app.process_and_add_to_kb(name, text.encode("utf-8"), cfg)
    check(ok, f"{name} в базе", m)
ref_svc = [{"title": "Сервис уведомлений. Техническое задание на развитие", "code": "ОРГ.9.9.ТЗ.7"}]
found_svc = app.find_basis_documents(ref_svc, cfg)
check([(d["source"], d["by"]) for d in found_svc["docs"]] == [("ТЗ_сервис_уведомлений.md", "title")],
      "шифра нет в начале ТЗ (в PDF он бывает в колонтитуле) — по названию находится само ТЗ, а не руководство, "
      f"которое на это ТЗ ссылается: {found_svc['docs']}")

print("11. [unit] Фрагменты документов-оснований: без сокращений и терминов, доля каждому документу, близость по смыслу")
PS = {
    "a0": {"source": "Общее_ТЗ.pdf", "heading_path": "Обозначения и сокращения",
           "text": "ИМ — информация мониторинга; ОМ — подсистема мониторинга; СУБД — система управления базами "
                   "данных; журналы событий; агент сбора журналов; система анализа событий."},
    "a1": {"source": "Общее_ТЗ.pdf", "heading_path": "4 Требования → 4.2.3 Требования к импортозамещению",
           "text": "Используются СУБД, журналы событий, агент сбора журналов, ОС и веб-серверы отечественного "
                   "производства. " * 6},
    "a2": {"source": "Общее_ТЗ.pdf", "heading_path": "4 Требования → 4.1.6 Требования к эргономике",
           "text": "Интерфейс удобен пользователю. " * 8},
    "b0": {"source": "Частное_ТЗ.pdf", "heading_path": "Термины и определения",
           "text": "ИМ — информация мониторинга; журналы СУБД; агент сбора журналов."},
    "b1": {"source": "Частное_ТЗ.pdf", "heading_path": "4.1.8 Требования к защите информации",
           "text": "ИМ и события безопасности передаются в подсистему ОМ; в систему анализа событий их передаёт ОМ."},
}
ORDER = {p: i for i, p in enumerate(PS)}
docs_ab = [{"source": "Общее_ТЗ.pdf", "ids": ["a0", "a1", "a2"], "chars": 0},
           {"source": "Частное_ТЗ.pdf", "ids": ["b0", "b1"], "chars": 0}]
SECTION = ("Журналы СУБД собираются агентом сбора журналов и передаются напрямую в систему анализа событий; "
           "события безопасности и ИМ")
mat = app.ExpertMaterials(PS, ORDER, docs_ab, [], kind="basis")
picked = [it["id"] for it in app.select_pinned(mat, SECTION, 500)]
check("a0" not in picked and "b0" not in picked and "b1" in picked,
      f"сокращения и термины не берутся; частный документ получает свою долю бюджета: {picked}")
vec = {"a1": app.np.array([[1.0, 0.0]], dtype="float32"), "a2": app.np.array([[0.0, 1.0]], dtype="float32"),
       "b1": app.np.array([[0.6, 0.8]], dtype="float32")}
mat_v = app.ExpertMaterials(PS, ORDER, docs_ab[:1], [], kind="basis", vectors=vec)
one = [it["id"] for it in app.select_pinned(mat_v, "Квартальная отчётность", 250,
                                             query_vec=app.np.array([0.0, 1.0], dtype="float32"))]
none = app.select_pinned(mat_v, "Квартальная отчётность", 250)
check(one == ["a2"] and none == [], f"близость по смыслу: общих слов нет, а ближайший по вектору фрагмент берётся: "
                                    f"{one}; без вектора — ничего: {none}")

check.finish()

"""Промпты моделей (mint/prompts/*.yaml): русская и английская версии согласованы, подстановки заполняются,
версия набора меняется вместе с текстами, а формат ответа, который разбирает код, в промптах на месте. Свои
правки (prompts.yaml и правки сеанса): что можно править, что не применяется и почему, запас окна модели.

Запуск из корня проекта:  python tests/test_prompts.py
"""
import json
import re
import shutil
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402

WORK = harness.make_project(prefix="mint_prompts_")
app = harness.load_mint(WORK, include_ui=False)
from mint import citations, prompts as P  # noqa: E402
from mint.i18n import use_lang  # noqa: E402

check = harness.Checker()

print("1. [unit] Файлы промптов: одни и те же ключи и подстановки на двух языках")
ru, en = P.default_prompts("ru"), P.default_prompts("en")
check(len(ru) >= 30 and set(ru) == set(en), f"ключей {len(ru)}; только в ru: {sorted(set(ru) - set(en))}, "
                                            f"только в en: {sorted(set(en) - set(ru))}")
diff = {k: (P.placeholders(ru[k]), P.placeholders(en[k])) for k in ru
        if k in en and set(P.placeholders(ru[k])) != set(P.placeholders(en[k]))}
check(not diff, "подстановки {{…}} совпадают", str(diff))
check(all(v.strip() and v == v.rstrip("\n") for d in (ru, en) for v in d.values()),
      "тексты не пустые и без пустых строк в конце (их добавляет код)")
cyr = [k for k, v in en.items() if re.search(r"[А-Яа-яЁё]{3,}", v)]
check(not cyr, "в en.yaml нет русского текста", str(cyr))
RULE_RE = re.compile(r"(?m)^\s*(?:\d+[.)]|-)\s")
rules = {k: (len(RULE_RE.findall(ru[k])), len(RULE_RE.findall(en[k]))) for k in ru if k in en}
drift = {k: v for k, v in rules.items() if v[0] != v[1]}
check(not drift, "правил (пунктов списка) в каждом промпте поровну на двух языках — правило не добавлено только в "
                 "одну версию", str(drift))

print("2. [unit] Подстановки")
check(P.fill("a {{x}} b {{y}}", {"x": "{{y}}", "y": 1}) == "a {{y}} b 1",
      "подставленный текст (документ, вопрос) не разбирается повторно")
try:
    P.fill("{{x}}", {})
    check(False, "незаданная подстановка — ошибка")
except KeyError:
    check(True, "незаданная подстановка — ошибка")
check(P.placeholders("{{a}} {{b}} {{a}}") == ["a", "b"], "список подстановок")

print("3. [unit] Сборка промптов на двух языках")
for lang in ("ru", "en"):
    with use_lang(lang):
        built = {
            "chat": P.chat_system_prompt(), "user": P.chat_user_content("ctx", "q", "A", "q2"),
            "audit": P.audit_map_prompt(P.norms_block("N"), P.default_audit_focus(), "S"),
            "critique": app._critique_user_content("SEC", "", "1. x", "S"),
            "review": P.review_prompt(""), "lowconf": P.low_confidence_note(),
        }
        left = {k: P.placeholders(v) for k, v in built.items() if P.placeholders(v)}
        check(not left, f"{lang}: все подстановки заполнены", str(left))
        check(P.chat_system_prompt() == (P.CHAT_SYSTEM_PROMPT_EN if lang == "en" else P.CHAT_SYSTEM_PROMPT),
              f"{lang}: константа по умолчанию = собранный промпт")

print("4. [unit] Версия набора промптов")
v_ru, v_en = P.prompts_version("ru"), P.prompts_version("en")
check(re.fullmatch(r"ru-[0-9a-f]{8}", v_ru) and re.fullmatch(r"en-[0-9a-f]{8}", v_en), f"формат: {v_ru}, {v_en}")
with use_lang("en"):
    check(P.prompts_version() == v_en, "по умолчанию — язык интерфейса")
cached = P.default_prompts("ru")                # тексты профиля читаются один раз — правим их в кэше
saved = dict(cached)
cached["chat_system"] += " "
check(P.prompts_version("ru") != v_ru, "любая правка текста меняет версию")
cached.clear()
cached.update(saved)
check(P.prompts_version("ru") == v_ru, "те же тексты — та же версия")

print("5. [unit] Формат ответа, который разбирает код, есть в промптах")
for lang, d in (("ru", ru), ("en", en)):
    with use_lang(lang):
        sev = ("[КРИТИЧНЫЙ]", "[СРЕДНИЙ]", "[НИЗКИЙ]") if lang == "ru" else ("[CRITICAL]", "[MEDIUM]", "[LOW]")
        audit_p = P.audit_map_prompt("", "f")
        check(("не больше 10 замечаний" if lang == "ru" else "at most 10 findings") in audit_p
              and ("30" in P.audit_map_prompt("", "f", max_findings=30)), f"{lang}: лимит замечаний подставляется")
        check(all(s in audit_p for s in sev) and any(c in audit_p.lower() for c in app.CLEAN_PHRASES)
              and all(app._SEV_RE.search(s) for s in sev),
              f"{lang}: теги критичности и фраза «раздел чистый» — те, что понимает разбор черновика")
        crit = P.critique_system()
        verdicts = re.search(r'"verdict": "([^"]+)"', crit).group(1).split("|")
        check('"category"' not in crit, f"{lang}: самокритика не просит тему замечания")
        check(verdicts[1].upper().startswith(("УДАЛ", "DROP")) and not verdicts[0].upper().startswith(("УДАЛ", "DROP")),
              f"{lang}: вердикты самокритики: {verdicts}")
        check(all(f'"{f}"' in crit for f in ("n", "verdict", "severity", "quote", "text", "reason")),
              f"{lang}: поля JSON самокритики")
        rev = P.review_prompt("")
        statuses = re.search(r'"status": "([^"]+)"', rev).group(1).split("|")
        src_ = "Данные шифруются по ГОСТ на всех каналах."
        labels = [app.parse_verification(json.dumps({"status": s, "quote": src_, "comment": ""}), src_)[0]
                  for s in statuses]
        check(len(statuses) == 3 and labels[0].startswith("✅") and labels[1].startswith("⚠️")
              and labels[2].startswith("❌"), f"{lang}: статусы контроля исправлений разбираются: {labels}")
        chat_p = P.chat_system_prompt()
        example = re.search(r"\[(?:Источник|Source): [^\]]+\]", chat_p)
        check(example and citations._CITE_RE.search(example.group(0)),
              f"{lang}: формат ссылки из промпта чата понимает проверка ссылок")
        block = P.render("context_block", header="f.docx | x", body="text")
        check(citations._BLOCK_RE.search(block), f"{lang}: разметка источника в контексте понятна проверке ссылок")
        mark = P.low_confidence_note().split("—")[0].strip()
        check(mark.rstrip() in chat_p, f"{lang}: пометка «уверенность низкая» названа в промпте чата: {mark!r}")
        check(chat_p.count(d["chat_no_info"]) == 2, f"{lang}: фраза «информации нет» — в промпте чата")

print("6. [unit] Свои правки: prompts.yaml, правки сеанса, проверка, запас окна модели")
import os  # noqa: E402
os.environ["PROMPTS_PATH"] = str(WORK / "my_prompts.yaml")
pfile = WORK / "my_prompts.yaml"
base_chat = P.default_text("chat_system", "ru")
check(P.check_text("chat_system", "ru", base_chat) == [] and P.check_text("context_block", "ru", "x")
      and P.check_text("no_such_key", "ru", "x") and P.check_text("chat_system", "ru", "  "),
      "умолчание проходит проверку; разметку, несуществующий ключ и пустой текст править нельзя")
bad = P.check_text("audit_system", "ru", P.default_text("audit_system", "ru").replace("{{focus}}", "{{fokus}}")
                   .replace("[НИЗКИЙ]", "[МАЛЫЙ]"))
check(len(bad) == 3 and "{{focus}}" in bad[0] and "{{fokus}}" in bad[1] and "[НИЗКИЙ]" in bad[2],
      f"нет подстановки, неизвестная подстановка, нет части формата: {bad}")
for key in P.EDITABLE:
    for lang in ("ru", "en"):
        parts, _need = P.format_parts(key, lang)
        if any(part not in P.default_text(key, lang) for part in parts):
            check(False, f"обязательная часть формата есть в умолчании: {lang}.{key}")
check(all(k in ru for k in P.EDITABLE) and set(P.FORMAT_PARTS) <= set(P.EDITABLE)
      and set(P.MEASURED_BY_ANSWERS) <= set(P.EDITABLE), "правимые ключи и их формат — из набора промптов")
v0 = P.prompts_version("ru")
P.save_custom("chat_system", "ru", base_chat + "\n9. Кратко.")
data, problems = P.custom_file_prompts()
check(pfile.exists() and data["ru"]["chat_system"]["base"] and not problems and P.custom_status("ru") == {"chat_system": "file"}
      and P.prompts_version("ru") != v0 and P.prompts_version("en") == P.prompts_version("en"),
      "сохранённая правка читается из файла, версия меняется")
with P.defaults_only():
    check(P.prompt_text("chat_system", "ru") == base_chat and P.prompts_version("ru") == v0, "defaults_only — умолчания")
check(P.CHAT_SYSTEM_PROMPT == P.chat_system_prompt("ru").replace("\n9. Кратко.", ""),
      "константы — тексты по умолчанию, а не правки")
P.set_session_prompts({"ru": {"chat_no_info": "Сведений нет", "audit_system": "сломано", "context_block": "x"}})
check(P.custom_status("ru") == {"chat_system": "file", "chat_no_info": "session"} and "Сведений нет" in P.chat_system_prompt("ru")
      and P.prompt_text("audit_system", "ru") == P.default_text("audit_system", "ru"),
      "правка сеанса действует поверх файла; неверная правка сеанса и разметка не применяются")
P.set_session_prompts(None)
P.remove_custom("chat_system", "ru")
check(P.custom_status("ru") == {} and P.prompts_version("ru") == v0 and "chat_system" not in pfile.read_text(encoding="utf-8"),
      "«вернуть умолчание» убирает правку из файла")
pfile.write_text("ru:\n  chat_system: без формата\n  nope: x\nde:\n  a: b\nen:\n  chat_no_info: |-\n    Nothing found\n",
                 encoding="utf-8")
data, problems = P.custom_file_prompts()
check(data == {"en": {"chat_no_info": {"text": "Nothing found", "base": None}}} and len(problems) == 3,
      f"файл, написанный вручную: верная правка применяется, неверные пропущены с объяснением: {problems}")
check(P.file_has("chat_system", "ru") and not P.file_has("audit_system", "ru"), "запись в файле видна и неверная")
P.save_custom("chat_no_info", "ru", "Сведений нет")
after = pfile.read_text(encoding="utf-8")
check(all(s in after for s in ("без формата", "nope: x", "de:", "Nothing found", "Сведений нет"))
      and P.custom_status("ru") == {"chat_no_info": "file"} and P.custom_status("en") == {"chat_no_info": "file"},
      "сохранение одной правки не теряет остального в файле, и неверных записей тоже")
P.remove_custom("chat_system", "ru")
check(not P.file_has("chat_system", "ru") and "nope: x" in pfile.read_text(encoding="utf-8"),
      "«вернуть умолчание» убирает и неверную запись этого промпта")
pfile.write_text("ru: [не словарь", encoding="utf-8")
check(P.custom_file_prompts()[0] == {} and P.custom_file_prompts()[1], "битый prompts.yaml — умолчания и предупреждение")
try:
    P.save_custom("chat_no_info", "ru", "Сведений нет")
    check(False, "битый prompts.yaml не перезаписывается")
except ValueError as e:
    check(pfile.read_text(encoding="utf-8") == "ru: [не словарь" and "my_prompts.yaml" in str(e),
          f"битый prompts.yaml не перезаписывается: {e}")
pfile.unlink()
lim = app.resolve_model_limits(replace(app.DEFAULTS, llm_context_tokens=8192), {}, None, {"llm_context_tokens": 8192})
c1, _ = app.resolve_settings(app.DEFAULTS, lim, {"top_k": 5})
with use_lang("ru"):
    P.set_session_prompts({"ru": {"chat_system": base_chat + "\n" + "Подробное правило. " * 150,
                                  "audit_system": P.default_text("audit_system", "ru") + "\n" + "Правило. " * 300}})
    c2, _ = app.resolve_settings(app.DEFAULTS, lim, {"top_k": 5})
    P.set_session_prompts(None)
check(c2.smart_truncate_chars < c1.smart_truncate_chars and c2.audit_context_max_chars < c1.audit_context_max_chars,
      f"длинная правка промпта уменьшает место под фрагменты: чат {c1.smart_truncate_chars} → {c2.smart_truncate_chars}, "
      f"нормы аудита {c1.audit_context_max_chars} → {c2.audit_context_max_chars}")

print("7. [unit] Профили: «Архитектура и ИТ-решения» (по умолчанию, промпты до профилей слово в слово) и универсальный")
check(set(P.PROFILES) == {"general", "architecture"} and P.DEFAULT_PROFILE == "architecture"
      and P.get_profile() == "architecture" and app.DEFAULTS.profile == "architecture",
      "профили; по умолчанию — архитектурный (и в config)")
# Версии наборов промптов MINT до появления профилей (21.0): профиль архитектуры должен давать тот же набор — тогда
# его результаты сравнимы с прежними, а для архитектурной проверки ничего не меняется
OLD_VERSIONS = {"ru": "ru-8fd10871", "en": "en-9c3500f7"}
HEAD_LINES = {"chat_system": 2, "audit_system": 2, "audit_focus_answer_system": 1, "audit_checklist_system": 1,
              "critique_system": 1, "review_system": 1}       # остальное в них — правила, общие с <язык>.yaml
FREE = {"chat_no_info", "condense_system", "paraphrase_system", "question_gen_system", "audit_no_norms",
        "audit_focus_default", "audit_focus_generic"}          # короткие тексты — отличаются целиком
for lang in ("ru", "en"):
    over = P.profile_overrides("architecture", lang)
    with P.use_profile("general"):
        base = P.default_prompts(lang)
    check(set(over) <= set(base) and set(over) <= set(HEAD_LINES) | FREE, f"{lang}: профиль меняет только известные ключи",
          str(sorted(set(over) - set(HEAD_LINES) - FREE)))
    check(all(not P.check_text(k, lang, v) for k, v in over.items() if k in P.EDITABLE),
          f"{lang}: тексты профиля — с подстановками и форматом ответа умолчания")
    drift = [k for k in over if k in HEAD_LINES
             and over[k].split("\n")[HEAD_LINES[k]:] != base[k].split("\n")[HEAD_LINES[k]:]]
    check(not drift, f"{lang}: правила в текстах профиля те же, что в {lang}.yaml (отличаются только роли)", str(drift))
    with P.use_profile("architecture"), P.defaults_only():
        check(P.prompts_version(lang) == OLD_VERSIONS[lang],
              f"{lang}: профиль «Архитектура и ИТ-решения» — набор промптов до профилей ({P.prompts_version(lang)})")
        arch = P.default_prompts(lang)
        check("Архитектурн" in arch["critique_system"] or "Architecture Board" in arch["critique_system"],
              f"{lang}: самокритика архитектуры — роль архитектурного комитета")
        check(P.get_profile() == "architecture" and P.default_audit_focus(lang) == over["audit_focus_default"],
              f"{lang}: критерии профиля")
    with P.use_profile("general"):
        check(P.get_profile() == "general" and P.default_prompts(lang) == base, f"{lang}: универсальный профиль в блоке")
    check(P.get_profile() == "architecture" and P.default_prompts(lang) == {**base, **over},
          f"{lang}: после блока — снова профиль по умолчанию")
for lang, words in (("ru", r"архитект|корпоратив|ИИ-"), ("en", r"architect|corporate|AI ")):
    with P.use_profile("general"):
        narrow = sorted(k for k, v in P.default_prompts(lang).items() if re.search(words, v, re.I))
    check(not narrow, f"{lang}: в универсальном профиле нет узкой специализации", str(narrow))
with use_lang("ru"):
    gen, arch = P.profile_audit_focus("general"), P.profile_audit_focus("architecture")
    check(gen != arch and P.profile_audit_focus("нет такого") == arch and P.normalize_profile("x") == "architecture"
          and gen in P.audit_map_prompt("", gen) and P.DEFAULT_AUDIT_FOCUS == arch,
          "критерии профилей; неизвестный профиль — по умолчанию (архитектурный)")
    texts = P.all_profile_focus_texts()
    check(len(texts) == 4 and {gen, arch, P.DEFAULT_AUDIT_FOCUS, P.DEFAULT_AUDIT_FOCUS_EN} <= texts,
          "критерии всех профилей на двух языках — для замены нетронутого поля при смене профиля или языка")
    check(app.is_no_info_answer("В предоставленных документах информация отсутствует.")
          and app.is_no_info_answer("В предоставленных регламентах информация отсутствует."),
          "«информации нет» узнаётся в любом профиле")
    P.set_session_prompts({"ru": {"critique_system": P.default_text("critique_system", "ru") + "\nСвоё правило."}})
    with P.use_profile("architecture"):
        check(P.prompt_text("critique_system").endswith("Своё правило.") and P.custom_status("ru") == {"critique_system": "session"},
              "своя правка действует и в профиле")
    P.set_session_prompts(None)
check(P.set_profile("general") == "general" and P.get_profile() == "general"
      and P.set_profile("нет такого") == "architecture", "профиль сеанса: set_profile")
check(any("profile" in m for _, m in app.check_settings(replace(app.DEFAULTS, profile="legal")))
      and not any("profile" in m for _, m in app.check_settings(replace(app.DEFAULTS, profile="architecture"))),
      "неизвестный profile в config.yaml — предупреждение")

shutil.rmtree(WORK, ignore_errors=True)
check.finish()

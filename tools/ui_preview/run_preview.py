"""Скриншоты и запись анимаций интерфейса MINT на настоящем Streamlit — для проверки оформления.

Без сети и без моделей: шлюз моделей имитируется (tests/mock_server.py), Docling заменён заглушкой
(tests/stubs/docling), база знаний собирается из двух сгенерированных регламентов. Нужны streamlit,
playwright (с Chromium) и ffmpeg для GIF.

    python tools/ui_preview/run_preview.py --out preview
    python tools/ui_preview/run_preview.py --out preview/readme/en --readme --lang en   # снимки для README
    python tools/ui_preview/run_preview.py --out preview/sidebar --sidebar              # список документов, «Новый чат»

В папке --out: PNG экранов, motion.gif (загрузка страницы и ответ в чате), dom.txt — разметка ключевых
элементов (по ней проверяются селекторы mint/ui/assets/mint.css в текущей версии Streamlit).
На GitHub Actions (.github/workflows/ui-preview.yml) — только снимки для README (--readme): нейтральная демо-база
без отраслевых терминов. Полный набор экранов — локально.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
import mock_server  # noqa: E402

PORT = 8599
LANG = "ru"          # --lang en: английский интерфейс и подписи
README_MODE = False  # --readme: нейтральная база и документ без отраслевых терминов, только чат и аудит — для README
SIDEBAR_MODE = False  # --sidebar: нейтральная база из 14 документов — список документов, поиск, удаление, «Новый чат»


def L(text):
    """Подпись интерфейса на языке прогона: русский текст из кода → перевод из mint/i18n/en.py."""
    if LANG != "en":
        return text
    sys.path.insert(0, str(ROOT))
    from mint.i18n.en import EN
    return EN.get(text, text)


TEXT = {"ru": {"question": "Сколько хранятся журналы событий безопасности?"},
        "en": {"question": "How long are security event logs kept?"}}
README_TEXT = {
    "ru": {
        "question": "Сколько хранятся резервные копии?",
        "answer": ("Ежедневные резервные копии хранятся **30 дней**, ежемесячные — **один год** {r0}.\n\n"
                   "Восстановление из копии проверяется раз в квартал, а сервис восстанавливается не дольше чем за "
                   "четыре часа {r1}."),
        "findings": ("- [КРИТИЧНЫЙ] 1.3: резервные копии создаются еженедельно, а регламент требует ежедневного "
                     "копирования [Источник: Регламент_хранения_данных.docx, 1.1 Резервное копирование]\n"
                     "- [СРЕДНИЙ] 1.2: требование «быстро отвечать под нагрузкой» нельзя проверить — не указаны время "
                     "отклика и число одновременных пользователей [Источник: Уровни_сервиса.docx, 1.1 Время отклика]\n"
                     "- [НИЗКИЙ] 1.1: не указано, кто и как удаляет файлы после окончания срока хранения"),
        "keep": "ОСТАВИТЬ", "sev": ["КРИТИЧНЫЙ", "СРЕДНИЙ", "НИЗКИЙ"],
        "gist": "Резервные копии — еженедельно вместо ежедневно, как требует регламент",
    },
    "en": {
        "question": "How long are backups kept?",
        "answer": ("Daily backups are kept for **30 days**, monthly ones for **one year** {r0}.\n\n"
                   "Restoring from a backup is tested every quarter, and the service is restored within four hours "
                   "{r1}."),
        "findings": ("- [CRITICAL] 1.3: backups are made weekly, while the policy requires daily backups "
                     "[Source: Data_storage_policy.docx, 1.1 Backup]\n"
                     "- [MEDIUM] 1.2: the requirement \"respond quickly under load\" cannot be verified — no response "
                     "time or number of concurrent users is given [Source: Service_levels.docx, 1.1 Response time]\n"
                     "- [LOW] 1.1: it is not specified who deletes files after the retention period and how"),
        "keep": "KEEP", "sev": ["CRITICAL", "MEDIUM", "LOW"],
        "gist": "Backups are weekly instead of daily as the policy requires",
    },
}
SELECTORS = [
    '[data-testid="stDecoration"]', '[data-testid="stStatusWidget"]', '[data-testid="stHeader"]',
    '.stTabs [data-baseweb="tab-list"]', '[data-testid="stChatMessage"]', '[data-testid="stChatInput"]',
    '[data-testid="stExpander"]', '[data-testid="stProgress"]', '[data-testid="stFileUploaderDropzone"]',
    '[data-testid="stSpinner"]', '.stButton', '[data-testid="stSidebar"] [data-testid="stExpander"]',
    '.mint-hero', '.mint-verdict', '.mint-sources', '[data-testid="stDataFrame"]', '.mint-scorecard', '.mint-ladder',
    '.mint-steps', '[data-testid="stRadio"]', '[data-testid="stVerticalBlockBorderWrapper"]',
]


def nice_reply(original):
    """Ответ чата в предпросмотре похож на настоящий: со ссылками на источники из контекста."""
    def reply(system, user, max_tokens):
        if README_MODE:
            t = README_TEXT[LANG]
            if "эксперт-аудитор" in system or "expert reviewer" in system:      # проверка раздела
                return t["findings"]
            if "Старший Контролер" in system or "Senior Controller" in system:  # самокритика: всё верно
                import json
                import re
                draft = re.split(r"ЧЕРНОВИК ЗАМЕЧАНИЙ|DRAFT FINDINGS", user)[-1]
                n = len(re.findall(r"^\d+\.", draft, flags=re.M))
                return "```json\n" + json.dumps([{"n": i, "verdict": t["keep"], "severity": t["sev"][min(i, 3) - 1],
                                                   "quote": "", "text": "", "reason": "ok"} for i in range(1, n + 1)],
                                                  ensure_ascii=False) + "\n```"
        out = original(system, user, max_tokens)
        if README_MODE and out.startswith(("Ответ по контексту", "Answer from the context")):
            time.sleep(2.5)
            import re
            src = re.findall(r"=== (?:ИСТОЧНИК|SOURCE): ([^|=]+?)(?: \| (?:Раздел в начале фрагмента|Section at the start "
                             r"of the fragment): ([^|=]+?))?(?: \|[^=]*)? ===", user)
            word = "Источник" if LANG == "ru" else "Source"
            refs = [f"[{word}: {f.strip()}" + (f", {s.strip()}" if s else "") + "]" for f, s in src[:2]]
            return README_TEXT[LANG]["answer"].format(r0=refs[0] if refs else "", r1=refs[-1] if refs else "")
        if out.startswith("Answer from the context"):
            time.sleep(2.5)
            import re
            src = re.findall(r"=== SOURCE: ([^|=]+?)(?: \| Section at the start of the fragment: ([^|=]+?))?(?: \|[^=]*)? ===",
                             user)
            refs = [f"[Source: {f.strip()}" + (f", {s.strip()}" if s else "") + "]" for f, s in src[:2]]
            return ("Security event logs are kept for **at least three years**; access to them is restricted by role "
                    f"{refs[0] if refs else ''}.\n\nThe administrator checks log integrity every day, and backups are "
                    f"made daily {refs[-1] if refs else ''}.")
        if out.startswith("Ответ по контексту"):
            time.sleep(2.5)          # чтобы снимок «во время ответа» застал индикатор работы
            import re
            src = re.findall(r"=== ИСТОЧНИК: ([^|=]+?)(?: \| Раздел в начале фрагмента: ([^|=]+?))?(?: \|[^=]*)? ===", user)
            refs = [f"[Источник: {f.strip()}" + (f", {s.strip()}" if s else "") + "]" for f, s in src[:2]]
            return ("Журналы событий безопасности хранятся **не менее трёх лет**; доступ к ним разграничивается "
                    f"по ролям {refs[0] if refs else ''}.\n\nАдминистратор ежедневно проверяет целостность журналов, "
                    f"а резервные копии выполняются каждые сутки {refs[-1] if refs else ''}.")
        return out
    return reply


def make_docx(path, blocks):
    import docx
    d = docx.Document()
    for kind, text in blocks:
        if kind == "h1":
            d.add_heading(text, level=1)
        elif kind == "h2":
            d.add_heading(text, level=2)
        else:
            d.add_paragraph(text)
    d.save(path)
    return path


def build_base(work, env):
    """Два регламента в базе знаний — через те же функции, что и кнопка «Добавить в базу»."""
    docs = work / "docs"
    docs.mkdir()
    a = make_docx(docs / "Регламент_ИБ.docx", [
        ("h1", "Перечень сокращений"), ("p", "СЗИ — средства защиты информации;"), ("p", "ПДн — персональные данные."),
        ("h1", "1. Общие положения"),
        ("p", "Регламент задаёт требования к информационной безопасности автоматизированных систем: защите данных при "
              "передаче и хранении, журналированию событий, резервному копированию и управлению доступом. Требования "
              "обязательны для всех систем, которые обрабатывают ПДн или сведения ограниченного доступа."),
        ("h2", "1.1 Шифрование"),
        ("p", "При передаче ПДн между подсистемами применяется шифрование сертифицированными средствами. Ключи "
              "шифрования хранятся отдельно от данных и меняются не реже одного раза в год. Передача ПДн по открытым "
              "каналам без шифрования запрещена, включая тестовые среды с копиями рабочих данных."),
        ("h2", "1.2 Журналирование"),
        ("p", "Журналы событий безопасности хранятся не менее трёх лет. Доступ к журналам разграничивается по ролям. "
              "Администратор ежедневно проверяет целостность журналов и сообщает об отклонениях в службу безопасности "
              "в течение одного рабочего дня."),
        ("h2", "1.3 Управление доступом"),
        ("p", "Учётные записи создаются по заявке руководителя и блокируются в день увольнения сотрудника. "
              "Привилегированный доступ выдаётся на срок не более тридцати дней и пересматривается при каждой смене "
              "роли. Пароли длиной не менее двенадцати символов меняются раз в девяносто дней."),
    ])
    b = make_docx(docs / "Регламент_SLA.docx", [
        ("h1", "1. Показатели надёжности"),
        ("p", "Время восстановления сервиса не превышает четырёх часов. Доступность системы — 99,9 % в месяц без "
              "учёта согласованных регламентных работ. Регламентные работы проводятся в выходные дни с 02:00 до 06:00 "
              "и объявляются пользователям не позднее чем за три рабочих дня."),
        ("h2", "1.1 Резервное копирование"),
        ("p", "Резервное копирование выполняется ежедневно в центре обработки данных. Копии хранятся тридцать дней, "
              "ежемесячные — один год. Восстановление из резервной копии проверяется раз в квартал на отдельном стенде "
              "с записью результата в журнал проверок."),
        ("h2", "1.2 Мониторинг"),
        ("p", "Мониторинг доступности выполняется каждые пять минут из двух независимых точек. Инцидент первого "
              "уровня регистрируется автоматически, дежурный инженер подключается в течение пятнадцати минут, "
              "а о продолжительности простоя сообщается в ежемесячном отчёте."),
    ])
    rules = make_docx(docs / "Правила_экспертов.docx", [
        ("h1", "Правила экспертов"),
        ("h2", "ШИФР-01. Шифрование — на сертификат получателя"),
        ("p", "Когда применяется: данные на каком-либо шаге передаются в зашифрованном виде. Правило: Участник А "
              "шифрует данные на сертификат участника Б, который будет их расшифровывать; для каждого шага указано, "
              "на чей сертификат зашифрованы данные и кто их расшифровывает."),
        ("h2", "ХРАН-01. Срок хранения"),
        ("p", "Когда применяется: документ задаёт срок хранения файлов. Правило: срок не больше того, что обеспечивает "
              "система хранения; иначе в документе указана доработка системы."),
    ])
    card = make_docx(docs / "Карточка_Система_А.docx", [
        ("h1", "Карточка системы «Система А»"),
        ("p", "Названия: Система А, СА"),
        ("p", "Актуально на: 10.2026"),
        ("h2", "Что умеет сейчас"), ("p", "Приём файлов через REST API, файл — не больше 100 Мб."),
        ("h2", "Ограничения"), ("p", "Файлы хранятся 1 год, затем удаляются."),
        ("h2", "Планы"), ("p", "Файлы до 1 Гб — 2 квартал 2027 года."),
    ])
    code = ("import sys; sys.path.insert(0, %r)\n"
            "from mint.devtools import load_namespace\n"
            "app = load_namespace(include_ui=False)\n"
            "cfg, _ = app.load_settings()\n"
            "cfg, _ = app.resolve_settings(cfg, app.resolve_model_limits(cfg, {}, None, {}), {})\n"
            "for p in %r:\n"
            "    ok, msg = app.process_and_add_to_kb(p.split('/')[-1], open(p, 'rb').read(), cfg)\n"
            "    print(ok, msg)\n"
            "app.save_roles(cfg, always=['Правила_экспертов.docx'], cards=['Карточка_Система_А.docx'])\n"
            ) % (str(ROOT), [str(a), str(b), str(rules), str(card)])
    subprocess.run([sys.executable, "-c", code], env=env, check=True, cwd=ROOT)
    spec = make_docx(work / "ТЗ_Сервис_обмена.docx", [
        ("h1", "1. Общие сведения"),
        ("p", "Система передаёт ПДн между подсистемами по внутренней сети и хранит журналы операций."),
        ("h2", "1.1 Производительность"), ("p", "Система должна быстро отвечать под нагрузкой."),
    ])
    EXPERT["spec"] = make_docx(work / "ТЗ_Портал_отчётности.docx", [
        ("h1", "Техническое задание на портал отчётности"),
        ("h2", "1. Назначение"),
        ("p", "Портал принимает отчётные формы поставщиков и передаёт их в Систему А через REST API."),
        ("h2", "2. Требования к хранению"),
        ("p", "Система А хранит файлы 5 лет. Размер файла — до 500 Мб."),
        ("h2", "3. Этапы работ"), ("p", "Проектирование, разработка, испытания."),
    ])
    spec_v2 = make_docx(work / "ТЗ_Сервис_обмена_v2.docx", [
        ("h1", "1. Общие сведения"),
        ("p", "Система передаёт ПДн между подсистемами; канал защищён шифрованием TLS 1.3."),
    ])
    return spec, spec_v2


def build_base_readme(work, env):
    """База для снимков README: два нейтральных регламента и документ на проверку — без отраслевых терминов."""
    docs = work / "docs"
    docs.mkdir()
    ru = LANG == "ru"
    a = make_docx(docs / ("Регламент_хранения_данных.docx" if ru else "Data_storage_policy.docx"), [
        ("h1", "1. Общие положения" if ru else "1. General provisions"),
        ("p", "Регламент задаёт правила хранения рабочих данных, резервного копирования и доступа к архиву для всех "
              "сервисов компании." if ru else
              "The policy sets the rules for storing working data, backups and access to the archive for all the "
              "company's services."),
        ("h2", "1.1 Резервное копирование" if ru else "1.1 Backup"),
        ("p", "Резервные копии создаются ежедневно в 02:00. Ежедневные копии хранятся 30 дней, ежемесячные — один "
              "год. Восстановление из копии проверяется раз в квартал." if ru else
              "Backups are made daily at 02:00. Daily copies are kept for 30 days, monthly copies for one year. "
              "Restoring from a backup is tested every quarter."),
        ("h2", "1.2 Журналы операций" if ru else "1.2 Operation logs"),
        ("p", "Журналы операций хранятся не менее трёх лет. Доступ к журналам выдаётся по ролям." if ru else
              "Operation logs are kept for at least three years. Access to the logs is granted by role."),
    ])
    b = make_docx(docs / ("Уровни_сервиса.docx" if ru else "Service_levels.docx"), [
        ("h1", "1. Показатели доступности" if ru else "1. Availability"),
        ("p", "Доступность сервиса — 99,9 % в месяц. Сервис восстанавливается не дольше чем за четыре часа." if ru
              else "Service availability is 99.9 % a month. The service is restored within four hours."),
        ("h2", "1.1 Время отклика" if ru else "1.1 Response time"),
        ("p", "Время отклика интерфейса — не более 2 секунд при нагрузке до 500 одновременных пользователей." if ru
              else "Interface response time is at most 2 seconds with up to 500 concurrent users."),
    ])
    code = ("import sys; sys.path.insert(0, %r)\n"
            "from mint.devtools import load_namespace\n"
            "app = load_namespace(include_ui=False)\n"
            "cfg, _ = app.load_settings()\n"
            "cfg, _ = app.resolve_settings(cfg, app.resolve_model_limits(cfg, {}, None, {}), {})\n"
            "for p in %r:\n"
            "    ok, msg = app.process_and_add_to_kb(p.split('/')[-1], open(p, 'rb').read(), cfg)\n"
            "    print(ok, msg)\n") % (str(ROOT), [str(a), str(b)])
    subprocess.run([sys.executable, "-c", code], env=env, check=True, cwd=ROOT)
    spec = make_docx(work / ("Описание_сервиса_обмена.docx" if ru else "Exchange_service_description.docx"), [
        ("h1", "1. Назначение" if ru else "1. Purpose"),
        ("p", "Сервис обмена принимает файлы от партнёров и передаёт их во внутренние системы компании." if ru else
              "The exchange service receives files from partners and passes them to the company's internal systems."),
        ("h2", "1.1 Хранение" if ru else "1.1 Storage"),
        ("p", "Полученные файлы хранятся в архиве сервиса десять лет." if ru else
              "Received files are kept in the service archive for ten years."),
        ("h2", "1.2 Производительность" if ru else "1.2 Performance"),
        ("p", "Сервис должен быстро отвечать под нагрузкой." if ru else "The service must respond quickly under load."),
        ("h2", "1.3 Резервное копирование" if ru else "1.3 Backup"),
        ("p", "Резервные копии архива создаются еженедельно." if ru else "Backups of the archive are made weekly."),
    ])
    return spec, spec


SIDEBAR_DOCS = ["Положение_о_резервном_копировании", "Пояснительная_записка_часть_1_Архитектура_решения",
                "Пояснительная_записка_часть_2_Развёртывание", "Описание_программного_обеспечения",
                "Стандарт_интеграции_сервисов", "Руководство_администратора_v3", "Методика_оценки_нагрузки",
                "Правила_именования_сервисов", "Порядок_вывода_из_эксплуатации", "Требования_к_мониторингу",
                "Регламент_обновления_версий", "Каталог_сервисов_2026"]


def add_sidebar_docs(work, env):
    """Ещё дюжина нейтральных документов (.md) — длинный список, как у пользователей."""
    folder = work / "more"
    folder.mkdir()
    paths = []
    for i, name in enumerate(SIDEBAR_DOCS):
        body = (f"# {name.replace('_', ' ')}\n\n## 1. Общие положения\n\nДокумент описывает порядок работы "
                f"номер {i + 1}: кто выполняет шаги, в какие сроки и как проверяется результат.\n\n"
                f"## 2. Порядок\n\nШаги выполняются по очереди; результат каждого шага записывается в журнал.\n")
        path = folder / f"{name}.md"
        path.write_text(body, encoding="utf-8")
        paths.append(str(path))
    code = ("import sys; sys.path.insert(0, %r)\n"
            "from mint.devtools import load_namespace\n"
            "app = load_namespace(include_ui=False)\n"
            "cfg, _ = app.load_settings()\n"
            "cfg, _ = app.resolve_settings(cfg, app.resolve_model_limits(cfg, {}, None, {}), {})\n"
            "for p in %r:\n"
            "    ok, msg = app.process_and_add_to_kb(p.split('/')[-1], open(p, 'rb').read(), cfg)\n"
            "    print(ok, msg)\n") % (str(ROOT), paths)
    subprocess.run([sys.executable, "-c", code], env=env, check=True, cwd=ROOT)


def build_base_en(work, env):
    """Английская база для снимков README: два регламента и документ на проверку."""
    docs = work / "docs"
    docs.mkdir()
    a = make_docx(docs / "Security_policy.docx", [
        ("h1", "Abbreviations"), ("p", "ISS — information security system;"), ("p", "PD — personal data."),
        ("h1", "1. General provisions"),
        ("p", "The policy sets information security requirements for automated systems: protection of data in transit "
              "and at rest, event logging, backup and access control. The requirements apply to every system that "
              "processes personal data or restricted information."),
        ("h2", "1.1 Encryption"),
        ("p", "Personal data transferred between subsystems is encrypted with certified tools. Encryption keys are "
              "stored separately from the data and are changed at least once a year."),
        ("h2", "1.2 Logging"),
        ("p", "Security event logs are kept for at least three years. Access to the logs is restricted by role. The "
              "administrator checks log integrity every day and reports deviations to the security service within "
              "one working day."),
    ])
    b = make_docx(docs / "Service_levels.docx", [
        ("h1", "1. Reliability"),
        ("p", "The service is restored within four hours. Availability is 99.9 % a month, excluding agreed "
              "maintenance windows announced at least three working days in advance."),
        ("h2", "1.1 Backup"),
        ("p", "Backups are made daily in the data centre. Copies are kept for thirty days, monthly copies for one "
              "year. Restoring from a backup is tested every quarter on a separate stand."),
    ])
    code = ("import sys; sys.path.insert(0, %r)\n"
            "from mint.devtools import load_namespace\n"
            "app = load_namespace(include_ui=False)\n"
            "cfg, _ = app.load_settings()\n"
            "cfg, _ = app.resolve_settings(cfg, app.resolve_model_limits(cfg, {}, None, {}), {})\n"
            "for p in %r:\n"
            "    ok, msg = app.process_and_add_to_kb(p.split('/')[-1], open(p, 'rb').read(), cfg)\n"
            "    print(ok, msg)\n") % (str(ROOT), [str(a), str(b)])
    subprocess.run([sys.executable, "-c", code], env=env, check=True, cwd=ROOT)
    spec = make_docx(work / "Specification_Exchange_service.docx", [
        ("h1", "1. General information"),
        ("p", "The system transfers personal data between subsystems over the internal network and keeps operation "
              "logs."),
        ("h2", "1.1 Performance"), ("p", "The system must respond quickly under load."),
        ("h2", "1.2 Storage"), ("p", "Personal data of applicants is stored in the archive subsystem."),
    ])
    return spec, spec


EXPERT = {}       # документ для сценария «знания эксперта» (собирается в build_base)
MERMAID_JS = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"


def readme_diagrams(browser, out, shots):
    """Схемы Mermaid из README.md и README.ru.md — так, как их нарисует GitHub: картинка или ошибка разбора."""
    import json
    import re
    for name in ("README.md", "README.ru.md"):
        blocks = re.findall(r"```mermaid\n(.*?)```", (ROOT / name).read_text(encoding="utf-8"), flags=re.S)
        for i, code in enumerate(blocks, 1):
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            try:
                page.set_content(f'<html><body style="background:#fff"><div id="d"></div><script src="{MERMAID_JS}">'
                                 '</script></body></html>')
                page.wait_for_function("() => window.mermaid", timeout=30000)
                err = page.evaluate("""async code => {
                    mermaid.initialize({startOnLoad: false});
                    try { const r = await mermaid.render('m', code); document.getElementById('d').innerHTML = r.svg;
                          return ''; } catch (e) { return String(e.message || e); }
                }""", code)
                if err:
                    shots.errors.append(f"===== mermaid {name} #{i}\n{err}")
                else:
                    page.locator("#d svg").screenshot(path=str(out / f"mermaid_{name.replace('.', '_')}_{i}.png"))
                shots.dom.append(f"mermaid {name} #{i}: {json.dumps(err or 'ok', ensure_ascii=False)}\n")
            except Exception as e:
                shots.errors.append(f"===== mermaid {name} #{i}\n{e}")
            finally:
                page.close()


def dom_dump(page, title):
    ids = page.evaluate("() => [...new Set([...document.querySelectorAll('[data-testid]')].map(e => e.dataset.testid))]")
    parts = [f"===== {title}", "testids: " + " ".join(sorted(ids))]
    for sel in SELECTORS:
        html = page.evaluate("s => { const e = document.querySelector(s); return e ? e.outerHTML : null; }", sel)
        parts.append(f"--- {sel}\n{(html or '(нет)')[:2500]}")
    return "\n".join(parts) + "\n"


def tall(page, path, height=2600):
    """Длинный снимок: прокручивается не документ, а внутренний контейнер Streamlit, поэтому full_page не
    помогает — окно на время снимка делается высоким."""
    size = page.viewport_size
    page.set_viewport_size({"width": size["width"], "height": height})
    time.sleep(1.2)
    page.screenshot(path=str(path))
    page.set_viewport_size(size)


README_VIEWPORT = {"width": 1100, "height": 1400}    # снимки для README: уже, чем экран, — крупнее текст на странице
README_CSS = ('[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"], '
              '[data-testid="stExpandSidebarButton"], [data-testid="stHeader"], .mint-src__meta '
              '{display: none !important;}')


def simplify(page):
    """Снимок для README — только суть: без боковой панели с настройками и служебной полосы Streamlit."""
    page.add_style_tag(content=README_CSS)
    time.sleep(0.8)


def clip_shot(page, path, top, bottom, pad=10):
    """Снимок полосы страницы от top до bottom (координаты окна) на всю ширину окна: поля небольшие, чтобы в кадр
    не попадали края соседних блоков (поле ввода чата, загрузчик)."""
    w = page.viewport_size["width"]
    y = max(0, top - pad)
    page.screenshot(path=str(path), clip={"x": 0, "y": y, "width": w, "height": bottom + pad - y})


def upload(page, label, path):
    """Файл в загрузчик с этой подписью (в боковой панели есть свой загрузчик — для базы знаний)."""
    box = page.locator('[data-testid="stFileUploader"]').filter(has_text=label)
    box.locator('input[type="file"]').set_input_files(str(path))


class Shots:
    """Сценарии предпросмотра: каждый со своим контекстом браузера; ошибка одного не останавливает остальные —
    в errors.txt пишется трассировка, рядом сохраняется снимок экрана в момент ошибки."""

    def __init__(self, browser, out):
        self.browser, self.out = browser, out
        self.dom, self.errors = [], []
        self.started, self.marks = {}, {}       # время начала сценария и отметки внутри — для нарезки видео

    def scenario(self, name, fn, readme=False, **ctx_args):
        size = {"viewport": README_VIEWPORT, "device_scale_factor": 2} if readme else {"viewport": {"width": 1440, "height": 900}}
        ctx = self.browser.new_context(**(size | ctx_args))
        self.started[name] = time.time()
        page = ctx.new_page()
        try:
            page.goto(f"http://localhost:{PORT}/")
            page.wait_for_selector(".mint-wordmark", timeout=60000)
            if readme:
                simplify(page)
            fn(page)
        except Exception:
            import traceback
            self.errors.append(f"===== {name}\n{traceback.format_exc()}")
            try:
                page.screenshot(path=str(self.out / f"error_{name}.png"), full_page=True)
                self.dom.append(dom_dump(page, f"ошибка: {name}"))
            except Exception:
                pass
        finally:
            ctx.close()

    def save(self):
        (self.out / "dom.txt").write_text("\n".join(self.dom), encoding="utf-8")
        (self.out / "errors.txt").write_text("\n".join(self.errors) or "нет ошибок\n", encoding="utf-8")


def run(out):
    from playwright.sync_api import sync_playwright
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="mint_preview_"))
    stub = work / "stub"
    stub.mkdir()
    shutil.copytree(ROOT / "tests" / "stubs" / "docling", stub / "docling")
    mock_server.chat_reply = nice_reply(mock_server.chat_reply)
    # «Главное» в начале заключения: модель-редактор выбирает два замечания
    mock_server.STATE["summary_reply"] = (
        '[{"n": 3, "gist": "' + README_TEXT[LANG]["gist"] + '"}]' if README_MODE else     # №3 — критичное
        '[{"n": 1, "gist": "The encryption algorithm for data transferred between subsystems is not specified"}]'
        if LANG == "en" else
        '[{"n": 2, "gist": "Не указан алгоритм шифрования при передаче между подсистемами"}, '
        '{"n": 1, "gist": "Сокращение используется без расшифровки"}]')
    srv = mock_server.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/v1"
    env = {**os.environ, "PYTHONPATH": str(stub), "PYTHONUTF8": "1", "LLM_API_URL": base,
           "EMBED_API_URL": base + "/embeddings", "RERANK_API_URL": base + "/rerank", "LLM_MODEL": "test-llm",
           "EMBED_MODEL": "emb-model", "RERANK_MODEL": "rr-model", "LLM_API_KEY": "k", "KB_DIR": str(work / "kb"),
           "LOG_DIR": str(work / "logs"), "MINT_CONFIG": str(work / "none.yaml"), "GLOSSARY_PATH": str(work / "none.json"),
           "MINT_LANG": LANG}
    if README_MODE:                     # без чек-листа: на снимке — только замечания по документу
        (work / "checklists.yaml").write_text("common: []\ntypes: []\n", encoding="utf-8")
        env["MINT_CHECKLISTS"] = str(work / "checklists.yaml")
        # без баллов поиска у источников и без строки глубокой проверки — на снимке только суть
        (work / "readme.yaml").write_text("show_source_details: false\naudit_deep: false\n", encoding="utf-8")
        env["MINT_CONFIG"] = str(work / "readme.yaml")
        spec, spec_v2 = build_base_readme(work, env)
        if SIDEBAR_MODE:
            add_sidebar_docs(work, env)
    else:
        spec, spec_v2 = build_base_en(work, env) if LANG == "en" else build_base(work, env)
    log = open(out / "streamlit.log", "w", encoding="utf-8")
    app = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", str(PORT),
                            "--server.headless", "true"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    videos = []
    try:
        import urllib.request
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://localhost:{PORT}/_stcore/health", timeout=2)
                break
            except Exception:
                time.sleep(1)
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception:           # Chromium для Playwright не скачался — Chrome, установленный в системе
                browser = p.chromium.launch(channel="chrome")
            shots = Shots(browser, out)

            def home(page):
                time.sleep(2.5)
                page.screenshot(path=str(out / "01_home.png"))
                shots.dom.append(dom_dump(page, "главная"))
                fonts = page.evaluate("() => [...document.fonts].map(f => f.family + ' ' + f.status)")
                shots.dom.append("fonts: " + ", ".join(fonts) + "\n")
                status = page.evaluate("async () => (await fetch('app/static/fonts/onest.woff')).status")
                shots.dom.append(f"static onest.woff: HTTP {status}\n")

            def chat(page):
                box = page.locator('[data-testid="stChatInput"] textarea')
                box.fill((README_TEXT if README_MODE else TEXT)[LANG]["question"])
                box.press("Enter")
                time.sleep(1.2)
                shots.dom.append(dom_dump(page, "во время ответа"))
                page.screenshot(path=str(out / "02_chat_working.png"), clip={"x": 0, "y": 0, "width": 1440, "height": 220})
                page.wait_for_function(
                    "() => document.querySelectorAll('[data-testid=\"stChatMessage\"]').length >= 2", timeout=60000)
                time.sleep(1.2)
                page.get_by_text(L("Использованные источники")).last.click()
                time.sleep(1.2)
                page.screenshot(path=str(out / "02_chat.png"))
                shots.dom.append(dom_dump(page, "ответ в чате"))
                if README_MODE:             # для README: шапка, вопрос, ответ со ссылками и источники — без поля ввода
                    top, bottom = page.evaluate("""() => {
                        const hero = document.querySelector('.mint-hero') || document.querySelector('.mint-wordmark');
                        const m = [...document.querySelectorAll('[data-testid="stChatMessage"]')].pop();
                        return [hero.getBoundingClientRect().top, m.getBoundingClientRect().bottom]; }""")
                    clip_shot(page, out / "readme_chat.png", top, bottom)

            def audit(page):
                page.get_by_role("tab", name=L("📋 Аудит документа")).click()
                time.sleep(0.8)
                settings = page.get_by_test_id("stTabs").get_by_text(L("⚙️ Настройки аудита"), exact=True)
                settings.click()
                time.sleep(1.2)
                shots.dom.append(dom_dump(page, "настройки аудита"))
                tall(page, out / "03_audit_settings.png", 2600)
                settings.click()
                time.sleep(0.8)
                upload(page, L("Загрузить документ на согласование (.docx, .pdf, .md, .txt)"), spec)
                page.get_by_text(L("Файл '{name}' готов к проверке.").split("' ")[-1].rstrip(".")).first.wait_for(
                    timeout=60000)
                page.get_by_role("button", name=L("🚀 Запустить аудит документа")).click()
                time.sleep(0.6)
                page.screenshot(path=str(out / "03_audit_running.png"))
                shots.dom.append(dom_dump(page, "аудит идёт"))
                page.wait_for_selector(".mint-verdict", timeout=180000)
                time.sleep(1.5)
                page.locator(".mint-verdict").scroll_into_view_if_needed()
                page.screenshot(path=str(out / "03_audit.png"))
                tall(page, out / "03_audit_full.png")
                if README_MODE:             # для README: заголовок, штамп, «Главное» и замечания — до конца замечаний
                    title = L("## 📄 Итоговое экспертное заключение").lstrip("# ")
                    page.evaluate("""t => { const h = [...document.querySelectorAll('h1, h2, h3')]
                        .find(e => e.innerText.includes(t)); h.scrollIntoView({block: 'start'}); }""", title)
                    time.sleep(1.0)
                    top, bottom = page.evaluate("""t => {
                        const h = [...document.querySelectorAll('h1, h2, h3')].find(e => e.innerText.includes(t));
                        const li = [...document.querySelectorAll('[data-testid="stMarkdownContainer"] li')]
                            .filter(e => e.innerText.includes('1.3:')).pop();
                        return [h.getBoundingClientRect().top, li.getBoundingClientRect().bottom]; }""", title)
                    clip_shot(page, out / "readme_audit.png", top, bottom)

            def review(page):
                page.get_by_role("tab", name="Контроль исправления замечаний").click()
                time.sleep(0.8)
                page.get_by_role("textbox", name="Ранее выданные замечания").fill(
                    "- [КРИТИЧНЫЙ] Не указано шифрование ПДн при передаче между подсистемами\n"
                    "- [СРЕДНИЙ] Требование к производительности сформулировано неизмеримо")
                page.keyboard.press("Control+Enter")
                upload(page, "Загрузить новую редакцию документа", spec_v2)
                time.sleep(1.5)
                page.get_by_role("button", name="Запустить контр-проверку").click()
                page.wait_for_selector(".mint-verdict", timeout=180000)
                time.sleep(1.5)
                page.locator(".mint-verdict").last.scroll_into_view_if_needed()
                page.screenshot(path=str(out / "04_review.png"))

            def top_geometry(page, title):
                # где верхняя полоса Streamlit и где шапка MINT: шапка не должна уходить под полосу
                g = page.evaluate("""() => {
                    const q = s => document.querySelector(s);
                    const r = el => { if (!el) return null; const b = el.getBoundingClientRect();
                                      return [Math.round(b.top), Math.round(b.bottom), Math.round(b.left)]; };
                    const h = q('[data-testid="stHeader"]') || q('header');
                    const sb = q('[data-testid="stSidebar"]');
                    return {header: r(h), header_bg: h && getComputedStyle(h).backgroundColor,
                            sidebar_expanded: sb && sb.getAttribute('aria-expanded'),
                            hero: r(q('.mint-hero')), wordmark: r(q('.mint-wordmark')),
                            expand_button: r(q('[data-testid="stExpandSidebarButton"], [data-testid="collapsedControl"]')),
                            container_padding_top: getComputedStyle(q('[data-testid="stMainBlockContainer"]')).paddingTop};
                }""")
                shots.dom.append(f"=== {title}: {g}\n")
                return g

            def collapsed(page):
                time.sleep(2.5)
                top_geometry(page, "панель открыта")
                page.screenshot(path=str(out / "01_top_expanded.png"), clip={"x": 0, "y": 0, "width": 1440, "height": 260})
                page.locator('[data-testid="stSidebar"]').hover()
                button = page.locator('[data-testid="stSidebarCollapseButton"] button, '
                                      '[data-testid="stSidebarHeader"] button').first
                button.click()
                time.sleep(1.5)
                g = top_geometry(page, "панель свёрнута")
                page.screenshot(path=str(out / "01_top_collapsed.png"), clip={"x": 0, "y": 0, "width": 1440, "height": 260})
                opaque = g["header_bg"] not in (None, "transparent", "rgba(0, 0, 0, 0)")
                assert not opaque or g["wordmark"][0] >= g["header"][1], f"шапка MINT уходит под полосу Streamlit: {g}"
                page.mouse.wheel(0, 400)
                time.sleep(0.8)
                top_geometry(page, "панель свёрнута, страница прокручена")

            def mobile(page):
                time.sleep(2.5)
                page.screenshot(path=str(out / "05_mobile.png"))

            def sidebar(page):
                """Документы в базе: число документов и векторов, список, поиск, удаление; «Новый чат» в шапке."""
                time.sleep(2.5)
                sb = page.locator('[data-testid="stSidebar"]')
                page.screenshot(path=str(out / "sidebar_chat_header.png"), clip={"x": 0, "y": 0, "width": 1440, "height": 320})
                head = sb.get_by_text(L("📁 Документы в базе"), exact=True)
                head.evaluate("e => e.scrollIntoView({block: 'start'})")
                time.sleep(0.8)
                sb.screenshot(path=str(out / "sidebar_docs.png"))
                shots.dom.append(dom_dump(page, "документы в базе"))
                find = sb.get_by_placeholder(L("🔎 Поиск по названию"))
                find.fill("записка 1")
                find.press("Enter")
                time.sleep(1.5)
                head.evaluate("e => e.scrollIntoView({block: 'start'})")
                sb.screenshot(path=str(out / "sidebar_search.png"))
                find.fill("")
                find.press("Enter")
                time.sleep(1.5)
                sb.get_by_text(L("🗑️ Удалить из базы"), exact=True).click()
                time.sleep(0.8)
                pick = sb.locator('[data-testid="stMultiSelect"]').filter(has_text=L("Документы")).first
                pick.locator("input").click()
                pick.locator("input").fill("Каталог")
                time.sleep(0.6)
                page.keyboard.press("Enter")
                time.sleep(0.6)
                page.keyboard.press("Escape")
                sb.get_by_text(L("Из базы удаляются фрагменты, векторы и сохранённый оригинал. Вернуть документ можно, "
                                 "только загрузив его заново.")).click()       # закрыть выпадающий список
                time.sleep(1.5)
                ask = sb.get_by_role("button", name=L("🗑️ Удалить выбранные ({n})").format(n=1))
                ask.wait_for(timeout=15000)
                ask.click()
                yes = sb.get_by_role("button", name=L("Удалить"), exact=True)
                yes.wait_for(timeout=15000)
                yes.scroll_into_view_if_needed()
                time.sleep(0.8)
                sb.screenshot(path=str(out / "sidebar_delete_confirm.png"))
                yes.click()
                time.sleep(2.0)
                head.evaluate("e => e.scrollIntoView({block: 'start'})")
                sb.screenshot(path=str(out / "sidebar_deleted.png"))
                shots.dom.append(dom_dump(page, "после удаления"))
                box = page.locator('[data-testid="stChatInput"] textarea')
                box.fill(README_TEXT[LANG]["question"])
                box.press("Enter")
                page.wait_for_function(
                    "() => document.querySelectorAll('[data-testid=\"stChatMessage\"]').length >= 2", timeout=60000)
                time.sleep(1.2)
                page.evaluate("() => window.scrollTo(0, 0)")
                page.screenshot(path=str(out / "sidebar_chat_after_answer.png"), clip={"x": 0, "y": 0, "width": 1440, "height": 520})

            shots.scenario("home", home)
            if SIDEBAR_MODE:                       # список документов на боковой панели и «Новый чат»
                shots.scenario("sidebar", sidebar, viewport={"width": 1440, "height": 1000}, device_scale_factor=2)
                browser.close()
                shots.save()
                return
            if README_MODE:                        # снимки для README: чат и аудит, схемы Mermaid
                shots.scenario("chat", chat, readme=True)
                shots.scenario("audit", audit, readme=True)
                readme_diagrams(browser, out, shots)
                browser.close()
                shots.save()
                return
            shots.scenario("collapsed", collapsed)
            shots.scenario("chat", chat, record_video_dir=str(work / "video"),
                           record_video_size={"width": 1440, "height": 900})
            videos = sorted((work / "video").glob("*.webm"))
            shots.scenario("audit", audit)
            shots.scenario("review", review)
            shots.scenario("mobile", mobile, viewport={"width": 390, "height": 844}, device_scale_factor=2)
            for extra in EXTRA_SCENARIOS:
                shots.scenario(extra.__name__, lambda page, f=extra: f(page, out, shots),
                               record_video_dir=str(work / "video" / extra.__name__),
                               record_video_size={"width": 1440, "height": 900})
                clip = sorted((work / "video" / extra.__name__).glob("*.webm"))
                mark = shots.marks.get(extra.__name__)
                if clip and mark and shutil.which("ffmpeg"):
                    start = max(0.0, mark - shots.started[extra.__name__] - 0.3)
                    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{start:.2f}", "-i", str(clip[0]),
                                    "-t", "5", "-vf", "fps=16,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen="
                                    "max_colors=160[p];[b][p]paletteuse=dither=bayer", str(out / f"{extra.__name__}.gif")],
                                   check=False)
            browser.close()
            shots.save()
        if videos and shutil.which("ffmpeg"):
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(videos[0]), "-t", "14", "-vf",
                            "fps=14,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=160[p];[b][p]paletteuse=dither=bayer",
                            str(out / "motion.gif")], check=False)
            shutil.copy(videos[0], out / "motion.webm")
    finally:
        app.terminate()
        srv.shutdown()
        log.close()


def quality(page, out, shots):
    """Проверка качества: настройки, таблица вопросов с фрагментом, результаты."""
    page.get_by_role("button", name="Открыть проверку качества").click()
    page.get_by_role("button", name="Составить вопросы").wait_for(timeout=30000)
    time.sleep(1.2)
    page.screenshot(path=str(out / "06_quality_setup.png"))
    page.get_by_role("button", name="Составить вопросы").click()
    page.get_by_text("Проверьте вопросы").wait_for(timeout=120000)
    time.sleep(2.0)
    shots.dom.append(dom_dump(page, "проверка качества: вопросы"))
    page.screenshot(path=str(out / "07_quality_review.png"))
    page.get_by_text("Фрагмент, по которому составлен вопрос").click()
    time.sleep(1.2)
    tall(page, out / "07_quality_review_full.png", 2000)
    page.get_by_role("button", name="Запустить проверку").click()
    page.wait_for_selector(".mint-scorecard", timeout=180000)
    shots.marks["quality"] = time.time()
    time.sleep(2.5)
    shots.dom.append(dom_dump(page, "проверка качества: результаты"))
    page.screenshot(path=str(out / "08_quality_results.png"))
    tall(page, out / "08_quality_results_full.png", 3200)


def prompts(page, out, shots):
    """Промпты: страница, правка без формата ссылки (ошибка), «Проверить правку» → проверка ответов чата."""
    page.get_by_role("button", name="Открыть промпты").click()
    page.get_by_role("button", name="Попробовать в сеансе").wait_for(timeout=30000)
    time.sleep(1.2)
    page.screenshot(path=str(out / "09_prompts.png"))
    box = page.get_by_role("textbox", name="Текст")
    text = box.input_value()
    box.fill(text.replace("[Источник: имя_файла, раздел]", "(источник)"))
    page.keyboard.press("Control+Enter")
    page.get_by_text("нет обязательной части формата").wait_for(timeout=30000)
    time.sleep(1.0)
    tall(page, out / "10_prompts_format_error.png", 1500)
    box.fill(text + "\n9. Отвечай кратко: не больше пяти предложений.")
    page.keyboard.press("Control+Enter")
    time.sleep(1.5)
    page.get_by_role("button", name="Проверить правку").click()
    page.get_by_role("button", name="Запустить проверку").wait_for(timeout=60000)
    time.sleep(1.0)
    page.get_by_role("button", name="Запустить проверку").click()
    page.wait_for_selector(".mint-answers", timeout=180000)
    shots.marks["prompts"] = time.time()
    time.sleep(2.5)
    shots.dom.append(dom_dump(page, "проверка правки промпта: результаты"))
    tall(page, out / "11_prompt_check_results.png", 3600)


def expert(page, out, shots):
    """Знания эксперта: правила и карточки в боковой панели, чек-лист по типу документа, блоки в заключении."""
    page.get_by_text("Для аудита: правила экспертов и карточки систем").click()
    time.sleep(1.2)
    page.get_by_text("Для аудита: правила экспертов и карточки систем").scroll_into_view_if_needed()
    page.screenshot(path=str(out / "12_kb_roles.png"))
    # черновик карточки системы по базе — отдельная страница вместо вкладок
    page.get_by_role("button", name="🗂️ Собрать черновик карточки системы по базе").click()
    page.get_by_text("🗂️ Черновик карточки системы").first.wait_for(timeout=30000)
    page.get_by_role("textbox", name="Система").fill("Система А")
    page.keyboard.press("Enter")
    time.sleep(1.0)
    page.get_by_role("button", name="🗂️ Собрать черновик", exact=True).click()
    page.get_by_text("Скачать черновик карточки").first.wait_for(timeout=120000)
    time.sleep(1.5)
    shots.dom.append(dom_dump(page, "черновик карточки системы"))
    tall(page, out / "15_card_draft.png", 3000)
    page.get_by_role("button", name="✕ Закрыть").click()
    time.sleep(1.0)
    page.get_by_role("tab", name="Аудит документа").click()
    time.sleep(0.8)
    upload(page, "Загрузить документ на согласование", EXPERT["spec"])
    page.get_by_text("готов к проверке").first.wait_for(timeout=60000)
    time.sleep(1.0)
    page.get_by_text("📋 Чек-лист:").click()
    time.sleep(1.2)
    shots.dom.append(dom_dump(page, "чек-лист по типу документа"))
    tall(page, out / "13_checklist.png", 1800)
    page.get_by_role("button", name="Запустить аудит документа").click()
    page.wait_for_selector(".mint-verdict", timeout=180000)
    shots.marks["expert"] = time.time()
    time.sleep(1.5)
    page.locator(".mint-verdict").scroll_into_view_if_needed()
    tall(page, out / "14_audit_expert_full.png", 3600)


def expert_review(page, out, shots):
    """Сохранённый аудит из «📂 Мои аудиты» (его сохранил сценарий audit) и разбор замечаний экспертом."""
    page.get_by_role("tab", name=L("📋 Аудит документа")).click()
    time.sleep(0.8)
    page.get_by_text(L("📂 Мои аудиты")).first.click()
    time.sleep(1.2)
    page.screenshot(path=str(out / "16_my_audits.png"))
    page.get_by_role("button", name=L("📂 Открыть")).click()
    page.wait_for_selector(".mint-verdict", timeout=60000)
    time.sleep(1.2)
    block = L("✍️ Разбор замечаний экспертом и «Мои замечания»")
    page.get_by_text(block).first.click()
    time.sleep(1.5)
    page.get_by_text(block).first.scroll_into_view_if_needed()
    shots.dom.append(dom_dump(page, "разбор замечаний экспертом"))
    page.screenshot(path=str(out / "17_expert_review.png"))
    tall(page, out / "17_expert_review_full.png", 3200)
    # варианты отметки — в переключателях карточек (в подсказке над ними те же слова)
    radios = page.locator('[data-testid="stRadio"]')
    radios.nth(0).get_by_text(L("❌ неверно"), exact=True).click()
    reason = page.locator('[data-testid="stSelectbox"]').filter(has_text=L("Причина: —").split(":")[0]).first
    reason.wait_for(timeout=30000)
    time.sleep(1.0)
    reason.click()
    page.get_by_role("option", name=L("в документе это есть")).click()
    time.sleep(1.5)
    radios.nth(1).get_by_text(L("✅ беру"), exact=True).click()
    time.sleep(1.5)
    shots.marks["expert_review"] = time.time()
    page.get_by_text(L("Размечено {m} из {n}: ✅ {ok} · ➖ {mi} · ❌ {w} · своих замечаний — {a}").split(" ")[0]).first \
        .scroll_into_view_if_needed()
    page.screenshot(path=str(out / "18_expert_review_marked.png"))
    tall(page, out / "18_expert_review_full.png", 3600)


EXTRA_SCENARIOS = [quality, prompts, expert, expert_review]     # дополнительные сценарии (page, out, shots)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="preview")
    ap.add_argument("--lang", default="ru", choices=["ru", "en"])
    ap.add_argument("--readme", action="store_true", help="снимки для README: нейтральная база, только чат и аудит")
    ap.add_argument("--sidebar", action="store_true",
                    help="с --readme: список документов на боковой панели (14 нейтральных документов) и «Новый чат»")
    args = ap.parse_args()
    LANG, README_MODE, SIDEBAR_MODE = args.lang, args.readme or args.sidebar, args.sidebar
    run(Path(args.out).resolve())

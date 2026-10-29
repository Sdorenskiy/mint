"""Регулярные выражения MINT не «зависают» на неудобном тексте: каждое из модуля пакета на длинных словах, рядах
точек, пробелов, табуляций (по 3000 знаков — длиннее строки документа не бывают) — быстрее секунды. Так ловится
перебор с экспоненциальным или кубическим ростом; квадратичный на таких длинах укладывается.

Повод: заголовок документа-основания из 40+ букв останавливал аудит на часы (no_requirements: под «*» стоял кусок,
который делил одно слово на части огромным числом способов). Плюс смысл исправленных выражений не изменился.

Запуск из корня проекта:  python tests/test_regex_speed.py
"""
import importlib
import os
import pkgutil
import random
import re
import signal
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402  (заглушки и пути — до импорта mint)

W = harness.make_project(prefix="mint_regex_")
app = harness.load_mint(W, include_ui=False)
check = harness.Checker()
LIMIT = 1.0                 # секунд на одно выражение и одну строку

ADVERSARIAL = {
    "длинное слово": "Требованиякобеспечениюинформационнойбезопасностипривзаимодействиикомпонентов",
    "длинный заголовок": "Требования к обеспечению информационной безопасности при взаимодействии компонентов системы",
    "заглавные": "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЭЮЯАБВГДЕЖЗИКЛМНОПР",
    "через одну": "АбВгДеЖзИкЛмНоПрСтУфХцЧшЩэЮяАбВгДеЖзИкЛмНоПр",
    "номера": "1.2.3.4.5.6.7.8.9.10.11.12.13.14.15.16.17.18.19.20.21.22.23.24.25.26 x",
    "точки": "." * 3000 + "x",
    "пробелы": " " * 3000 + "x",
    "табуляции": "\t" * 3000 + "x",
    "пробел-таб": "\t " * 1500 + "x",
    "таблица": "|" + " --- |" * 500 + "x",
    "дефисы": "-" * 3000 + "x",
    "буква-цифра": "a1" * 1500 + "!",
    "длинная строка": "слово " * 500 + "!",
    "звёздочки": "*" * 3000 + "x",
    "двоеточия": ": " * 1500 + "x",
}


def run_limited(fn, seconds):
    """fn() не дольше seconds: True — успел. POSIX — прерывание по таймеру; Windows — поток с ожиданием."""
    if hasattr(signal, "setitimer"):
        class Late(Exception):
            pass

        def late(*_a):
            raise Late()
        old = signal.signal(signal.SIGALRM, late)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        try:
            fn()
            return True
        except Late:
            return False
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
    t = threading.Thread(target=fn, daemon=True)
    t.start()
    t.join(seconds)
    return not t.is_alive()


print("1. [unit] Все выражения пакета mint на неудобном тексте — быстрее секунды")
import mint  # noqa: E402

patterns = {}
for info in pkgutil.walk_packages(mint.__path__, "mint."):
    if info.name.startswith("mint.ui"):
        continue
    mod = importlib.import_module(info.name)
    for name, value in vars(mod).items():
        if isinstance(value, re.Pattern):
            patterns[f"{info.name}.{name}"] = value
slow = []
for name, pat in sorted(patterns.items()):
    for label, text in ADVERSARIAL.items():
        def work(p=pat, s=text):
            p.search(s)
            list(p.finditer(s[:5000]))
        started = time.time()
        if not run_limited(work, LIMIT):
            slow.append(f"{name} — «{label}»: дольше {LIMIT} с")
        elif time.time() - started > LIMIT:
            slow.append(f"{name} — «{label}»: {time.time() - started:.1f} с")
check(len(patterns) > 50 and not slow, f"выражений проверено: {len(patterns)}, неудобных строк: {len(ADVERSARIAL)}",
      "; ".join(slow))

print("2. [unit] Исправленные выражения: смысл тот же")
nr = app.no_requirements
yes = ["Перечень сокращений", "1.2 Термины и определения", "А. Обозначения и сокращения", "Сокращения",
       "3) Нормативные ссылки", "Содержание", "Оглавление", "2.4. Ссылочные документы", "Лист регистрации изменений",
       "1 Terms and definitions", "Contents", "References", "ПРИЛОЖЕНИЕ А. перечень терминов"]
no = ["Требования к хранению", "2.1 Обозначения на схеме", "3.7.5 ТПС Внешний шлюз", "Определение состава работ",
      "Порядок обработки сокращённых сообщений", "1.2 Термины", ""]
check(all(nr(f"Документ → {h}") for h in yes), "разделы без требований узнаются (и последний уровень пути)",
      str([h for h in yes if not nr(h)]))
check(not any(nr(h) for h in no), "обычные разделы — не «без требований»", str([h for h in no if nr(h)]))
t0 = time.time()
long_heading = "Требования к обеспечению информационной безопасности при взаимодействии компонентов " * 3
res = []
done = run_limited(lambda: res.append(nr(long_heading)), LIMIT)
check(done and res == [False] and time.time() - t0 < 0.05, f"длинный заголовок — мгновенно ({time.time() - t0:.4f} с)")
sre = app._STATUS_RE
cases = {"- [ЕСТЬ] приём файлов через REST": ("ЕСТЬ", "приём файлов через REST"),
         "- **[ПРОТИВОРЕЧИЕ]** хранение 5 лет — в карточке: 1 год": ("ПРОТИВОРЕЧИЕ", "хранение 5 лет — в карточке: 1 год"),
         "1. [В ПЛАНАХ]: третья очередь": ("В ПЛАНАХ", "третья очередь"),
         "  * [unclear] - формат ответа": ("unclear", "формат ответа"),
         "[ДОРАБОТКА] файлы до 500 Мб": ("ДОРАБОТКА", "файлы до 500 Мб")}
got = {s: (m.group(1), m.group(2).strip()) if (m := sre.match(s)) else None for s in cases}
check(got == cases, "статусы карточки системы разбираются как раньше", str({k: v for k, v in got.items() if v != cases[k]}))
check(sre.match("Требований к системе нет") is None and sre.match("- [КРИТИЧНЫЙ] 2.4: x") is None,
      "не статус — не разбирается")
check(app.text_clauses("2.2.4.1. Пункт\n2.1 Название ........ 7\n3 Раздел\n" + "." * 50000 + "\n") == {"2.2.4.1", "3"},
      "номера пунктов: строки содержания пропускаются, длинный ряд точек — без задержки")


print("3. [unit] Новые выражения разбирают то же, что прежние (21.2), — на случайных строках из их «словаря»")
OLD = {   # как было в 21.2 (на коротких строках прежние выражения ещё быстры)
    "nr": re.compile(
        r"(?i)^\W*(?:[\dА-ЯA-Z]{1,3}[.)]?\s*)*(?:обозначени\w*\s+и\s+сокращени|перечень\s+(?:сокращени|обозначени|"
        r"терминов|ссылочн)|сокращени\w*\s*(?:и\s+обозначени\w*)?\s*$|термины\s+и\s+(?:определени|сокращени)|"
        r"определени\w*\s*$|ссылочн\w*\s+документ|нормативн\w*\s+ссылк|содержание\s*$|оглавление\s*$|"
        r"лист\s+регистрации|abbreviations|acronyms|terms\s+and\s+(?:definitions|abbreviations)|definitions\s*$|"
        r"(?:table\s+of\s+)?contents\s*$|references\s*$|normative\s+references)"),
    "toc": re.compile(r"(?:\t|\.{3,}|…)\s*\d{1,3}\**\s*$"),
    "answer": re.compile(r"^\s*\**\s*(?:Ответ|Answer)\s*\**\s*:\s*\**\s*(.*)$", re.IGNORECASE),
    "status": re.compile(r"^\s*(?:[-–—•*·]+|\d{1,2}[.)])?\s*\**\s*\[\s*(ЕСТЬ|В\s+ПЛАНАХ|ДОРАБОТКА|ПРОТИВОРЕЧИЕ|НЕЯСНО|HAVE|"
                         r"PLANNED|CHANGE|CONFLICT|UNCLEAR)\s*\]\s*\**\s*[:—–-]?\s*(.+)$", re.IGNORECASE),
    "info": re.compile(r"^\s*(?:[-–—•·*]\s+)?[*_]*([^:\n]{3,80}?)[*_]*\s*:\s*(\S.{5,})$"),
}
rnd = random.Random(7)


def sample(tokens, n, count):
    return ["".join(rnd.choice(tokens) for _ in range(rnd.randint(1, n))) for _ in range(count)]


def groups(m):
    return m.groups() if m else None


nr_tokens = ["1", "2.", "1.2", "3)", "А.", "A", "ё", " ", "\t", ".", ")", ",", "-", "«", "_", "Приложение ", "сокращения",
             "Сокращения", "и обозначения", "обозначения и сокращения", "перечень терминов", "Перечень ", "термины и определения",
             "определения", "Определение", "содержание", "Оглавление", "ссылочные документы", "нормативные ссылки",
             "лист регистрации", "Contents", "References", "terms and definitions", "Список ", "к "]
diff, skipped = [], 0
for s in sample(nr_tokens, 3, 3000):
    old_res = []
    if not run_limited(lambda s=s: old_res.append(bool(OLD["nr"].search(s))), 0.05):
        skipped += 1           # прежнее выражение само «зависло» — сравнивать не с чем
    elif old_res[0] != nr(s):
        diff.append(s)
check(not diff and skipped < 300, f"no_requirements: 3000 заголовков (прежнее не уложилось на {skipped})", str(diff[:5]))
diff = [s for s in sample(["Название", " ", "\t", ".", "...", "....", "…", "7", "123", "1234", "*", "\u00a0", "\u2003", "x"],
                          8, 20000) if bool(OLD["toc"].search(s)) != bool(app._TOC_TAIL_RE.search(s))]
check(not diff, "строки содержания: 20000 строк", str(diff[:5]))
diff = [s for s in sample([" ", "\t", "*", "**", "Ответ", "Answer", "ответ", ":", "да", "Нет", "x", "* x"], 7, 20000)
        if groups(OLD["answer"].match(s)) != groups(app._ANSWER_RE.match(s))]
check(not diff, "«Ответ:» в ответе модели: 20000 строк", str(diff[:5]))
diff = [s for s in sample([" ", "-", "–", "•", "*", "**", "-*", "* *", "1.", "12)", "[", "]", "[ЕСТЬ]", "ЕСТЬ", "В ПЛАНАХ",
                           "unclear", ":", "—", "текст", "x", "\t"], 8, 40000)
        if groups(OLD["status"].match(s)) != groups(sre.match(s))]
check(not diff, "статусы карточки системы: 40000 строк", str(diff[:5]))
from mint import deep_checks  # noqa: E402


def info(m):
    """Что попадает в сведения о процессе (как в deep_checks.process_info). Отличие от 21.2 одно и намеренное: строка
    шага со звёздочками впереди («** Шаг 2 …: …») теперь тоже узнаётся как шаг, как и без звёздочек."""
    g = m.group(1) if m else ""
    if not m or not deep_checks._INFO_KEY_RE.search(g) or deep_checks._STEP_WORD_RE.match(g.strip()):
        return None
    return f"{g.strip()}: {m.group(2).strip()}"


diff = [s for s in sample([" ", "-", "•", "*", "**", "_", "Результат", " границы", "Шаг 1", " шаг 2 результат", ":", ": ",
                           "значение долгое", "x", "\t"], 7, 40000)
        if info(OLD["info"].match(s)) != info(deep_checks._INFO_LINE_RE.match(s.lstrip()) if ":" in s else None)]
check(not diff, "сведения о процессе «Название: значение»: 40000 строк", str(diff[:5]))

print("4. [unit] Если MINT завис: kill -USR1 — где каждый поток, в LOG_DIR/mint_stacks.txt; MINT работает дальше")
if hasattr(signal, "SIGUSR1"):
    from mint import logs  # noqa: E402
    from mint.config import load_settings  # noqa: E402
    cfg = load_settings()[0]
    box = {}

    def streamlit_thread():          # страница Streamlit настраивает журнал не в главном потоке
        logs.setup_logging(cfg)
        os.kill(os.getpid(), signal.SIGUSR1)
        until = time.time() + 0.5
        while time.time() < until:
            pass
        box["alive"] = True
    th = threading.Thread(target=streamlit_thread)
    th.start()
    th.join(10)
    stacks = (cfg.log_path / logs.STACKS_FILE).read_text(encoding="utf-8")
    check(box.get("alive") and "streamlit_thread" in stacks and "test_regex_speed.py" in stacks,
          "снимок записан, программа работает дальше", stacks[:300])
else:
    print("  (Windows: сигнала USR1 нет — снимок недоступен, проверять нечего)")

check.finish()

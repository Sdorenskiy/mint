"""Все тесты MINT одной командой (без pytest и без сети: API-шлюз имитируется локально).

    python tests/run_all.py

Нужны пакеты из requirements.txt, кроме Streamlit и Docling (для тестов они заменены заглушками).
"""
import os
import subprocess
import sys
import time
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SUITES = [
    ("Ядро и интерфейс", ["test_app.py"]),
    ("Промпты: языки, подстановки, версия, формат ответа", ["test_prompts.py"]),
    ("Форматы: .pdf без моделей, .md, .txt", ["test_formats.py"]),
    ("Запросы к модели: рассуждения, свои параметры, таймауты аудита", ["test_llm_requests.py"]),
    ("Качество аудита: разделы, документ целиком, особое внимание, проверки без модели", ["test_audit_quality.py"]),
    ("Глубокая проверка аудита и сверка с эталоном", ["test_deep_checks.py"]),
    ("Аудит без шума: обрыв ответа, повторы, пачки, мелкое отдельно, параллельные разделы", ["test_audit_noise.py"]),
    ("Аудит: чек-листы по типам документов, правила экспертов, карточки систем", ["test_audit_expert.py"]),
    ("Разбор замечаний экспертом, сохранённые аудиты, сводка разборов", ["test_expert_review.py"]),
    ("Без зависаний: регулярные выражения на неудобном тексте, снимок потоков по сигналу", ["test_regex_speed.py"]),
    (".env, ошибки подключения, словарь", ["test_env.py"]),
    ("Оценка поиска с реранкером", ["test_eval.py"]),
    ("Оценка поиска без реранкера", ["test_eval.py", "--no-rerank"]),
    ("Самопроверка установки", ["test_check_install.py"]),
    ("Обновление на месте (update.sh)", ["test_update.py"]),
    ("Английский интерфейс и поиск, полнота перевода", ["test_i18n.py"]),
    ("Схемы в docs/ не отстают от кода", ["test_diagrams.py"]),
    ("Страница на настоящем Streamlit (смоук)", ["test_streamlit_smoke.py"]),
]


def github_error(title, text):
    """На GitHub Actions — аннотация с ошибкой: её видно в интерфейсе и через API, даже без доступа к логу."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    esc = lambda v: v.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")  # noqa: E731
    print(f"::error title={esc(title).replace(',', '%2C').replace(':', '%3A')}::{esc(text[-6000:])}", flush=True)


def main():
    failed = []
    for title, args in SUITES:
        t0 = time.time()
        print(f"\n===== {title} =====", flush=True)
        r = subprocess.run([sys.executable, str(TESTS / args[0]), *args[1:]], cwd=TESTS.parent,
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env={**os.environ, "PYTHONUTF8": "1"})   # вывод в UTF-8 и в консоли Windows
        out = "\n".join(line for line in r.stdout.splitlines()
                        if "✗" in line or line.startswith(("ИТОГ", "::notice", "::warning")))
        print(out or r.stdout[-2000:])
        if r.returncode != 0:
            failed.append(title)
            print(r.stdout[-6000:])
            print(r.stderr[-4000:])
            fails = "\n".join(line for line in r.stdout.splitlines() if "✗" in line)
            github_error(f"Тесты: {title}", f"{fails}\n--- stdout ---\n{r.stdout[-2500:]}\n--- stderr ---\n{r.stderr[-2500:]}")
        print(f"({time.time() - t0:.0f} с)")
    print("\n" + ("ВСЕ ТЕСТЫ ПРОЙДЕНЫ" if not failed else f"ПРОВАЛЕНО: {', '.join(failed)}"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

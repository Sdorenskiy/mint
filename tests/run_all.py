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
    ("Черновик Word из шаблона или образца", ["test_template_draft.py"]),
    ("Эталонная генерация раздела Word и сохранение оформления", ["test_draft_golden.py"]),
    ("MINT V2: исходный замер ограничений и диагностика", ["test_draft_v2_baseline.py"]),
    ("MINT V2: типизированный реестр и сохранение оснований", ["test_draft_registry.py"]),
    ("MINT V2: функции и обоснование ответственности", ["test_draft_function_analysis.py"]),
    ("MINT V2: детализация требований и проверка оснований", ["test_draft_derivation.py"]),
    ("MINT V2: сквозной пилот формирования раздела Word", ["test_draft_section_pilot.py"]),
    ("MINT V2: отчёт и обезличенная диагностика", ["test_draft_pilot_report.py"]),
    ("MINT V2: контрольная точка 1 — целевой реестр", ["test_draft_target_analysis.py"]),
    ("MINT V2: ссылки оснований и прогресс", ["test_draft_references_progress.py"]),
    ("MINT V2: досье функций, реестр Excel и сравнение прогонов", ["test_draft_dossiers.py"]),
    ("MINT V2: согласование перед декомпозицией", ["test_draft_target_review.py"]),
    ("MINT V2: навигация по этапам", ["test_draft_wizard.py"]),
    ("MINT V2: рабочий реестр выбранных функций", ["test_draft_review_view.py"]),
    ("Пригодный к вычитке Word: титул, 7.1, цвета, таблицы, примеры и ссылки", ["test_draft_usable_word.py"]),
    ("Чат по документу Word: предложения, подтверждение, откат, источники и целостность", ["test_document_edit.py"]),
    ("Контекст создаваемого документа: определение из шаблона и подтверждение", ["test_document_context.py"]),
    ("Применимость требований: обязанности целевой и внешних платформ", ["test_requirement_scope.py"]),
    ("Прослеживаемость: от раздела к основаниям и от основания к Word", ["test_draft_traceability.py"]),
    ("Переход из требования в чат Word и устаревшие связи после правок", ["test_trace_to_chat.py"]),
    ("Доказательная сверка для аудита и генератора", ["test_evidence.py"]),
    ("Эталонные метрики доказательности и полноты (40 + 8 сценариев)", ["eval_document_quality.py"]),
    ("Локальный экспертный разбор сформированного Word", ["test_draft_review.py"]),
    ("Контрольные точки разбора оснований", ["test_draft_checkpoint.py"]),
    ("Ускоренный разбор оснований: порядок, кэш и параллельные запросы", ["test_draft_parallel.py"]),
    ("Совместимость эмбеддингов и безопасная переиндексация", ["test_embedding_compatibility.py"]),
    ("Источники и ручная оценка содержания ответов", ["test_answer_evaluation.py"]),
    ("Опечатки: настройка, фильтр, повторы", ["test_audit_typos.py"]),
    ("Полнота аудита: сбои, повтор, сохранение", ["test_audit_completion.py"]),
    ("Завершение ответа модели: поток, обрывы, пустой ответ", ["test_stream_completion.py"]),
    ("Ядро и интерфейс", ["test_app.py"]),
    ("Консультант: разбор запроса, поиск по аспектам, разделы целиком, 📄/💡, схемы", ["test_consult.py"]),
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

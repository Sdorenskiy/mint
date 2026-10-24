"""
Оценка качества поиска MINT по набору вопросов с разметкой.

Что делает:
  • прогоняет каждый вопрос через настоящий поиск MINT в нескольких конфигурациях: только векторный
    поиск, только BM25, гибрид без реранкера, гибрид + реранкер с разными весами;
  • считает, на каком месте оказался правильный фрагмент: hit@1, hit@3, hit@K (попал ли он в контекст
    модели), MRR;
  • сравнивает конфигурации на одних и тех же вопросах (критерий знаков): случайна ли разница между ними;
  • по вопросам, ответа на которые в базе нет, показывает, сработал ли сигнал «уверенность низкая», и
    подбирает его порог;
  • с --answers задаёт каждый вопрос и чату (тем же сценарием, что вкладка «Чат») и проверяет ответ без
    модели-судьи: ссылка на нужный документ, ссылки мимо найденного, ложное и честное «информации нет»;
    каждая ошибка относится к поиску или к модели. Так проверяется правка промпта: прогон до, правка,
    прогон после с --compare — ответы сравниваются по вопросам, в итогах видна версия промптов;
  • пишет отчёт (report.md), подробности по каждому вопросу (details.csv, открывается в Excel), ответы чата
    (answers.csv) и итоги (summary.json) — их можно сравнить со следующим прогоном (--compare).

Запуск (из папки MINT, где лежат app.py, .env и config.yaml):
  python eval_search.py eval/questions.csv
  python eval_search.py eval/questions.csv --compare eval_results/2026-10-10_09-00/summary.json
  python eval_search.py --generate 40 --out eval/questions.draft.csv     # черновик вопросов по базе
  python eval_search.py eval/questions.csv --answers --repeat 3 --quick  # ответы чата (после правки промпта)

Формат файла вопросов — CSV (разделитель «;» или «,», UTF-8 или Windows-1251) или JSONL:
  question  — вопрос, как его задал бы пользователь (обязательно);
  file      — имя файла, где ответ (можно без расширения; несколько вариантов через «|»);
              пусто — в базе ответа нет (такие вопросы нужны для порогов «уверенность низкая»);
  section   — часть названия раздела (необязательно; варианты через «|»);
  contains  — короткая дословная фраза из нужного фрагмента (необязательно, но точнее всего);
  note      — комментарий (не используется).
Фрагмент считается правильным, если совпали файл и — если заданы — раздел и фраза. Разметка не зависит
от внутренних идентификаторов, поэтому набор вопросов переживает переиндексацию базы.
Строки, начинающиеся с «#», пропускаются.

То же самое без командной строки — в интерфейсе MINT: боковая панель → «Проверка качества». Ядро оценки —
mint/evaluation.py; этот скрипт — обёртка для запуска из консоли. Язык отчёта — как у MINT (MINT_LANG) или --lang.
"""
import argparse
import json
import logging
import sys
import time
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
try:
    from mint import evaluation as ev
    from mint.evaluation import (K_MAX, RERANK_WEIGHTS, Question, build_configs, calibrate,  # noqa: F401  (для тестов)
                                 current_config_name, hit_ks, is_relevant, load_questions, metrics, nearest_quote,
                                 paired, place_cell, rerank_cell, sign_test_p)
    from mint.i18n import set_lang, tr
except ImportError as e:
    sys.exit(f"Не найден пакет mint рядом с {Path(__file__).name} ({e}). Запускайте скрипт из папки MINT.")


def load_app():
    """Функции MINT одним пространством имён (см. mint/devtools.py)."""
    from mint.devtools import load_namespace
    logging.getLogger("MINT").setLevel(logging.WARNING)
    return load_namespace()


def resolve_cfg(app):
    base, notes = app.load_settings()
    app.set_profile(base.profile)          # набор промптов (profile в config.yaml) — как в интерфейсе
    for n in notes:
        print(f"config.yaml: {n}")
    for level, msg in app.check_settings(base):
        print(f"{tr('ОШИБКА') if level == 'error' else tr('Внимание')}: {msg}")
    server = app.detect_server_info(base)
    if not base.llm_model and server.get("llm_models"):
        base = replace(base, llm_model=server["llm_models"][0])
    limits = app.resolve_model_limits(base, server, None, {})
    cfg, _info = app.resolve_settings(base, limits, {})
    top_k = base.top_k or app.kb_default_top_k(cfg)
    return replace(cfg, top_k=top_k)


def evaluate(args):
    app = load_app()
    cfg = resolve_cfg(app)
    try:
        questions = load_questions(args.questions)
        snap = app.load_kb_snapshot(cfg)
        if snap is None or snap.index.ntotal == 0:
            raise ValueError(tr("База знаний пуста или не найдена ({kb_path}).", kb_path=cfg.kb_path))
    except ValueError as e:
        sys.exit(str(e))
    for n, miss in ev.missing_files(questions, snap).items():
        print(tr("⚠️ Вопрос {n}: файла {miss} нет в базе — вопрос не сможет быть найден.", n=n, miss=miss))
    top_k = args.k or cfg.top_k
    n_cfg = len(build_configs(cfg, args.multi_query))
    print(tr("Вопросов: {n}; конфигураций: {c}; top_k = {k}. База: {kb}", n=len(questions), c=n_cfg, k=top_k,
             kb=cfg.kb_path))
    t0 = time.time()

    def progress(done, total, name):
        print(f"\r  [{done}/{total}] {ev.config_label(name)}" + " " * 20, end="", flush=True)

    run = ev.evaluate(cfg, questions, top_k=top_k, with_multi_query=args.multi_query, progress=progress,
                      compare=not args.quick, answers=args.answers, repeat=args.repeat)
    print(f"\r  {tr('Готово за {s:.0f} с', s=time.time() - t0)}" + " " * 40)
    compare = prev_answers = None
    if args.compare:
        try:
            prev = json.loads(Path(args.compare).read_text(encoding="utf-8"))
            compare, prev_answers = prev.get("configs"), prev.get("answers")
        except Exception as e:
            print(tr("⚠️ Не удалось прочитать {path}: {e}", path=args.compare, e=e))
    out_dir = Path(args.out) if args.out else HERE / "eval_results" / time.strftime("%Y-%m-%d_%H-%M")
    lines = ev.write_reports(out_dir, run, compare, prev_answers if run.answers else None)
    print()
    head = "| " + tr("Конфигурация")
    start = next(i for i, ln in enumerate(lines) if ln.startswith(head))
    for ln in lines[start:start + len(run.configs) + 2]:
        print(ln)
    if run.answers:
        a = run.answers["summary"]
        print()
        for _key, label, k, n, _h in ev.answer_metrics(a):
            print(f"{tr(label)}: {ev.pct(k, n)}")
        if prev_answers and prev_answers.get("scores"):
            print(ev.answers_verdict(ev.compare_answers(a, prev_answers)))
    print("\n" + tr("Отчёт: {r}\nПо вопросам (Excel): {d}", r=out_dir / "report.md", d=out_dir / "details.csv"))


def generate(args):
    app = load_app()
    cfg = resolve_cfg(app)

    def progress(done, total):
        print("\r  " + tr("Генерирую вопросы: {i}/{n}", i=done, n=total), end="", flush=True)

    try:
        rows, failed = ev.generate_questions(cfg, args.generate, seed=args.seed, progress=progress)
    except ValueError as e:
        sys.exit(str(e))
    print()
    out = Path(args.out or HERE / "eval" / "questions.draft.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    text = ev.questions_csv(ev.questions_from_rows(rows)).lstrip("\ufeff")
    hint = tr("# Черновик: проверьте каждый вопрос, перефразируйте как спросил бы пользователь, удалите неудачные; "
              "добавьте свои реальные вопросы и 5–10 вопросов без ответа в базе (file пустой).")
    out.write_text(hint + "\r\n" + text, encoding="utf-8-sig", newline="")    # csv уже с \r\n
    near = sum(1 for r in rows if r["quote_found"] == "near")
    print(tr("Записано вопросов: {n} (не удалось: {failed}; цитата подобрана по смыслу: {near}) → {out}", n=len(rows),
             failed=failed, near=near, out=out))
    print(tr("Важно: вопросы, написанные моделью по тексту фрагмента, похожи на него по словам и завышают результат "
             "BM25. Перед оценкой перепишите их своими словами и добавьте реальные вопросы."))


def main():
    parser = argparse.ArgumentParser(description="Оценка качества поиска MINT по набору вопросов.",
                                     formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("questions", nargs="?", help="файл вопросов (.csv или .jsonl)")
    parser.add_argument("--k", type=int, default=0, help="сколько фрагментов попадает в контекст (по умолчанию — как в MINT)")
    parser.add_argument("--out", help="папка для отчёта (или файл черновика с --generate)")
    parser.add_argument("--compare", help="summary.json прошлого прогона — показать изменения")
    parser.add_argument("--multi-query", action="store_true", help="добавить конфигурацию с multi-query (+1 вызов LLM на вопрос)")
    parser.add_argument("--answers", action="store_true",
                        help="задать каждый вопрос и чату и проверить ответ (+1 вызов LLM на вопрос и повтор)")
    parser.add_argument("--repeat", type=int, default=1, help="с --answers: сколько раз задать чату каждый вопрос")
    parser.add_argument("--quick", action="store_true",
                        help="не сравнивать все настройки поиска: текущие, только векторный поиск и гибрид")
    parser.add_argument("--generate", type=int, default=0, metavar="N", help="сделать черновик из N вопросов по базе")
    parser.add_argument("--seed", type=int, default=7, help="случайное зерно для --generate")
    parser.add_argument("--lang", choices=["ru", "en"], help="язык отчёта (по умолчанию — как у MINT)")
    args = parser.parse_args()
    if args.lang:
        set_lang(args.lang)
    if args.generate:
        generate(args)
    elif args.questions:
        evaluate(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

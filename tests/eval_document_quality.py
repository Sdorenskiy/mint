"""Run 40 fictional evidence cases and 8 draft coverage matrices.

    python tests/eval_document_quality.py
    python tests/eval_document_quality.py --report-dir /path/only/on/your/machine
    python tests/eval_document_quality.py --predictions /path/predictions.jsonl --baseline /path/old.json

Predictions JSONL: {"id":"E01","model":{"status":"conflict", ...}}.
Required model fields are those accepted by mint.evidence.verify_comparison.
Never publish real cases, answers or full reports from private documents.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402  (setup offline test dependencies)
from mint import document_quality_benchmark as bench  # noqa: E402


HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "fixtures" / "document_evidence_golden.jsonl"
COVERAGE = HERE / "fixtures" / "draft_coverage_golden.jsonl"


def _pct(score):
    return "не определено" if score is None else f"{100 * score:.1f}%"


def brief(name, stats):
    return (f"{name}: TP={stats['tp']}, FP={stats['fp']}, FN={stats['fn']}, TN={stats['tn']}, "
            f"Precision={_pct(stats['precision'])}, Recall={_pct(stats['recall'])}")


def report_md(result):
    ev, cv = result["evidence"], result["coverage"]
    lines = [
        "# MINT — эталонная оценка доказательности",
        "",
        "**Ограничение:** искусственные размеченные ситуации; " +
        ("ответы модели заранее заданы в эталонах." if result["prediction_mode"] == "scripted"
         else "выводы предоставлены отдельным файлом, происхождение необходимо подтвердить вручную."),
        "Метрики **не оценивают качество поиска по рабочей базе или реальной LLM без отдельного прогона**.",
        "",
        f"- Методика: {result['version']}",
        f"- SHA256 данных и разметки: {result['dataset_sha256']}",
        f"- Сценариев доказательств: {ev['scores']['total']}; матриц покрытия: " +
        f"{len({r['id'].split(':')[0] for r in cv['cases']})}; требований: {cv['scores']['total']}",
        "",
        "## Доказанные конфликты (по заранее известной разметке)",
        "",
        brief("Все", ev["scores"]),
    ]
    lines.extend(brief(mode, stat) for mode, stat in ev["modes"].items())
    lines.extend(["", f"Проверяемые пары цитат: {ev['grounded_pairs']} / {ev['scores']['total']}.",
                  "Количество выданных статусов: " +
                  ", ".join(f"{key}: {value}" for key, value in ev["statuses"].items()),
                  "", "## Потенциально пропущенные требования черновика", "",
                  brief("Кандидаты на ручную проверку", cv["scores"]),
                  "",
                  "Здесь TP/FP — **качество списка кандидатов**, а не число доказанных пропусков.",
                  "FN включает не найденные поиском требования и ошибки учёта переноса.",
                  "", "## Ошибки против ручной разметки", "",
                  "| ID | Подсистема / тип | Золотая метка | Вывод |",
                  "|---|---|---|---|"])
    for item in ev["errors"]:
        lines.append(f"| {item['id']} | {item['group']} | {item['gold']} | {item['status']} |")
    for item in cv["errors"]:
        lines.append(f"| {item['id']} | draft_coverage | {item['gold']} | candidate={item['candidate']} |")
    if not ev["errors"] and not cv["errors"]:
        lines.append("| — | — | — | Ошибок нет |")
    if "comparison" in result:
        lines.extend(["", "## Сравнение с предыдущим прогоном", ""])
        for mode, item in result["comparison"].items():
            lines.append(f"- {mode}: ΔTP={item['tp_delta']}; ΔFP={item['fp_delta']}; "
                         f"ΔFN={item['fn_delta']}; улучшено: {', '.join(item['improved_ids']) or '—'}; "
                         f"ухудшено: {', '.join(item['worsened_ids']) or '—'}")
    lines.extend(["", "## Границы интерпретации", ""])
    lines.extend(f"- {line}" for line in result["limitations"])
    return "\n".join(lines) + "\n"


def self_test(evidence, coverage, result):
    """Deterministic invariants; *do not* require 100% accuracy or hide known FPs."""
    assert len(evidence) == 40 and len(coverage) == 8, "Golden data unexpectedly changed"
    assert len({r["id"] for r in evidence + coverage}) == 48
    assert result["evidence"]["scores"]["total"] == 40
    assert result["coverage"]["scores"]["total"] == 26
    rows = result["evidence"]["cases"]
    for row in rows:
        if row["group"] != "wrong_confident_scope":
            assert row["status"] == row["expected_status"], (row["id"], row["status"], row["expected_status"])
    assert not [x for x in rows if x["group"] in ("different_scope", "table_number_only",
                                                    "unclear", "bad_quote") and x["predicted"]]
    coverage_rows = {r["id"]: r for r in result["coverage"]["cases"]}
    assert coverage_rows["D08:R1"]["gold"] and coverage_rows["D08:R1"]["predicted"]
    assert coverage_rows["D08:R2"]["gold"] and coverage_rows["D08:R2"]["predicted"]
    assert coverage_rows["D08:R3"]["gold"] and coverage_rows["D08:R3"]["predicted"]
    assert coverage_rows["D05:R1"]["gold"] and not coverage_rows["D05:R1"]["predicted"], (
        "The current coverage metric cannot detect a fabricated used ID: keep this limitation visible"
    )
    assert bench.classification([{"gold": False, "predicted": False}])["precision"] is None
    assert bench.classification([{"gold": False, "predicted": False}])["recall"] is None
    try:
        bench.checked_predictions(evidence, [{"id": evidence[0]["id"], "model": evidence[0]["model"]}])
        raise AssertionError("Incomplete model prediction set accepted")
    except ValueError:
        pass
    try:
        bench.checked_predictions(evidence, [{"id": evidence[0]["id"], "model": {}},
                                             {"id": evidence[0]["id"], "model": {}}])
        raise AssertionError("Duplicate model prediction accepted")
    except ValueError:
        pass
    assert bench.compare_reports(result, copy.deepcopy(result))["evidence"]["fp_delta"] == 0
    corrupt = copy.deepcopy(result)
    corrupt["dataset_sha256"] = "another"
    try:
        bench.compare_reports(result, corrupt)
        raise AssertionError("Incompatible datasets were compared")
    except ValueError:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path,
                        help="Full model evidence responses in JSONL, one per E01–E40; no network calls")
    parser.add_argument("--baseline", type=Path,
                        help="Previous JSON report, same labelled set and prediction method")
    parser.add_argument("--report-dir", type=Path,
                        help="Write report JSON/Markdown here (keep real evaluation data local)")
    opts = parser.parse_args(argv)

    evidence = bench.load_cases(EVIDENCE)
    coverage = bench.load_cases(COVERAGE)
    predictions = bench.load_cases(opts.predictions) if opts.predictions else None
    result = bench.evaluate(evidence, coverage, predictions)
    if predictions is None:
        self_test(evidence, coverage, result)
    if opts.baseline:
        result["comparison"] = bench.compare_reports(result, json.loads(opts.baseline.read_text(encoding="utf-8")))
    print(brief("Эталонная доказательность", result["evidence"]["scores"]))
    print(brief("Кандидаты пропусков", result["coverage"]["scores"]))
    print("Внимание: это НЕ оценка качества реальных ответов модели или аудита на рабочих документах.")
    if opts.report_dir:
        opts.report_dir.mkdir(parents=True, exist_ok=True)
        (opts.report_dir / "document_quality.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (opts.report_dir / "document_quality.md").write_text(report_md(result), encoding="utf-8")
        print(f"Локальный отчёт: {opts.report_dir / 'document_quality.md'}")
    print("ИТОГ: размеченный набор, измерение precision/recall, полнота сценариев и проверка сравнимости")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

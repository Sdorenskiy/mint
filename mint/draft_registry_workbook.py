"""Local expert workbook and exact regression comparison.

Never use this private workbook as a diagnostic export. No writes to disk,
network calls, formulas, macros or external workbook links.
"""
from collections import defaultdict
from hashlib import sha256
from io import BytesIO
import json

from .i18n import tr
from .template_draft import _normalized
from .version import MINT_VERSION


def _digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def registry_identity(prepared, result):
    # Stable only for identical original revisions, target context and selected
    # function names. Do not compare R/P IDs across different runs.
    identity = {"hashes": prepared.get("hashes", {}), "context": prepared.get("context", {}),
                "roles": prepared.get("roles", {}),
                "profile": sorted(_normalized(p["name"]).casefold()
                                  for p in result.get("approved_profile", []))}
    if prepared.get("reference_sources"):
        identity["reference_sources"] = prepared["reference_sources"]
        identity["reference_hashes"] = prepared.get("reference_hashes", {})
    # Keep old automatic/all-selected baselines comparable, but never present
    # a deliberate change of review scope or expert guidance as a regression.
    review = result.get("review", {})
    if review.get("excluded") or review.get("notes"):
        groups = {g["id"]: g["function"] for g in result.get("groups", [])}
        identity["review"] = {
            "excluded": sorted(record_key(result["requirements"][rid]) for rid in review.get("excluded", [])),
            "notes": sorted((groups[gid], note) for gid, note in review.get("notes", {}).items())}
    return _digest(identity)


def record_key(row):
    return _digest([row["source"], row["section"], _normalized(row["quote"])])


def _accepted(p, result):
    return p.get("assessment") == "model_supported" and all(
        result["dispositions"].get(rid) == "model_covered" for rid in p["need_refs"])


def proposal_key(p, result):
    return _digest([_normalized(p["text"]).casefold(),
                    _normalized(p["actor"]).casefold(), p["kind"],
                    sorted(record_key(result["requirements"][rid]) for rid in p["need_refs"])])


def regression_snapshot(prepared, result):
    """Exact match baseline; paraphrases require expert review, not auto-match."""
    return {"format": "mint-registry-regression/1", "identity": registry_identity(prepared, result),
            "mint": MINT_VERSION,
            "records": {record_key(row): result["dispositions"].get(rid, "")
                        for rid, row in result["requirements"].items()},
            "accepted": {proposal_key(p, result): p["text"] for p in result["proposals"] if _accepted(p, result)}}


def compare_registries(previous, current):
    if not isinstance(previous, dict) or not isinstance(current, dict):
        raise ValueError("Invalid registry comparison format")
    if previous.get("format") != current.get("format") or previous.get("format") != "mint-registry-regression/1":
        raise ValueError("Invalid registry comparison format")
    if previous.get("identity") != current.get("identity"):
        raise ValueError("Different source revisions, context or approved functions")
    old_records, new_records = previous.get("records"), current.get("records")
    old, new = previous.get("accepted"), current.get("accepted")
    if not all(isinstance(d, dict) and all(isinstance(k, str) and isinstance(v, str)
                                         for k, v in d.items()) for d in (old_records, new_records, old, new)):
        raise ValueError("Invalid registry comparison")
    return {"retained_records": len(old_records.keys() & new_records.keys()),
            "missing_records": sorted(old_records.keys() - new_records.keys()),
            "new_records": len(new_records.keys() - old_records.keys()),
            "retained_accepted": len(old.keys() & new.keys()),
            "missing_accepted": [old[k] for k in sorted(old.keys() - new.keys())],
            "new_accepted": len(new.keys() - old.keys()),
            "changed_dispositions": sum(old_records[k] != new_records[k] for k in old_records.keys() & new_records.keys())}


def registry_workbook(prepared, result):
    """Full local export. All source strings are explicit text cells (including
    those starting with =, +, - or @), avoiding formula injection.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

    wb = Workbook()
    wb.remove(wb.active)

    def sheet(name, headers, rows, widths):
        ws = wb.create_sheet(name)
        def append(row):
            ws.append([ILLEGAL_CHARACTERS_RE.sub("", str(v)) if v is not None else "" for v in row])
            for cell in ws[ws.max_row]:
                cell.data_type = "s"
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        append(headers)
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="264A60")
        for row in rows:
            append(row)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for index, width in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(index)].width = width
        return ws

    records = result["requirements"]
    proposals = result["proposals"]
    groups = {g["id"]: g["function"] for g in result["groups"]}
    by_need = defaultdict(list)
    for p in proposals:
        for rid in p["need_refs"]:
            by_need[rid].append(p["id"])
    decisions = result.get("decisions", {})
    snapshot = regression_snapshot(prepared, result)
    sheet(tr("Сведения о прогоне"), [tr("Поле"), tr("Значение")],
          [("MINT", MINT_VERSION), ("identity", snapshot["identity"]),
           (tr("Целевая система"), prepared.get("context", {}).get("target", "")),
           (tr("Экспертная проверка"), tr("Обязательна")),
           ("phase", result.get("phase", "decomposed")), ("review_mode", result.get("review", {}).get("mode", "")),
           (tr("Конфиденциальность"), tr("Содержит исходные тексты. Только для локального использования."))],
          [30, 100])
    sheet(tr("Выявленные функции"), ["ID", tr("Функция"), tr("Описание"), tr("Ссылки")],
          [(p["id"], p["name"], p["description"], ", ".join(p["refs"])) for p in result.get("approved_profile", [])],
          [12, 40, 100, 36])
    if prepared.get("reference_sources"):
        sheet(tr("Справочный контекст"), ["ID", tr("Источник"), tr("Раздел"), tr("Цитата")],
              [(r["id"], r["source"], r["section"], r.get("quote", r.get("text", "")))
               for r in result.get("reference_candidates", prepared.get("reference_candidates", []))],
              [12, 40, 46, 100])
    if result.get("function_links"):
        names = {p["id"]: p["name"] for p in result.get("approved_profile", [])}
        sheet(tr("Связи требований с функциями"), ["ID", tr("Функция"), tr("Источник"), tr("Цитата")],
              [(rid, names[pid], records[rid]["source"], records[rid]["quote"])
               for rid, pids in result["function_links"].items() for pid in pids], [12, 40, 40, 100])
    def summary_rows():
        review = result.get("review", {})
        included, excluded = set(review.get("included", [])), set(review.get("excluded", []))
        for gid, rows in result.get("summaries", {}).items():
            for row in rows:
                yield (gid, groups.get(gid, ""), row["status"], row["text"], ", ".join(row["need_refs"]),
                       ", ".join(row["evidence_refs"]), ", ".join(r for r in row["need_refs"] if r in included),
                       ", ".join(r for r in row["need_refs"] if r in excluded), review.get("notes", {}).get(gid, ""))
    sheet(tr("Сводные требования"), ["ID", tr("Функция"), tr("Статус"), tr("Сводная формулировка"),
          tr("Исходные записи"), tr("Ссылки"), tr("Включено"), tr("Исключено"), tr("Уточнение эксперта (не источник)")],
          summary_rows(), [12, 40, 20, 100, 36, 36, 36, 36, 80])
    sheet(tr("Предложения"), ["ID", tr("Функция"), tr("Исполнитель"), tr("Тип"),
          tr("Требование"), tr("Статус"), tr("Обоснование"), tr("Причина проверки"), tr("Компоненты")],
          [(p["id"], groups.get(p["group"], ""), p["actor"], p["kind"], p["text"],
            "model_covered" if _accepted(p, result) else ("coverage_unresolved" if p["assessment"] == "model_supported" else p["assessment"]), p.get("reason", ""),
            p.get("assessment_reason", ""), ", ".join(dict.fromkeys(
                decisions.get(rid, {}).get("component", "") for rid in p["need_refs"] if decisions.get(rid, {}).get("component"))))
           for p in proposals], [12, 36, 30, 20, 100, 26, 60, 60, 36])
    headers = ["ID", tr("Источник"), tr("Раздел"), tr("Цитата"), tr("Тип"), tr("Статус"),
               tr("Исполнитель"), tr("Изменение"), tr("Обоснование"), tr("Причина проверки"), tr("Предложения"), tr("Ключ сравнения")]
    def source_row(rid, row):
        d = decisions.get(rid, {})
        return (rid, row["source"], row["section"], row["quote"], row.get("kind", ""),
                result["dispositions"].get(rid, ""), d.get("actor", ""), d.get("change", ""),
                d.get("reason", ""), d.get("review_reason", ""), ", ".join(by_need[rid]), record_key(row))
    widths = [12, 36, 46, 100, 20, 28, 30, 20, 60, 60, 24, 70]
    sheet(tr("Исходные записи"), headers, (source_row(rid, r) for rid, r in records.items()), widths)
    sheet(tr("Неотражённые записи"), headers, (source_row(rid, r) for rid, r in records.items()
          if result["dispositions"].get(rid) not in {"model_covered", "already_supported", "external"}), widths)
    all_evidence = {**records, **result.get("state_evidence", {})}
    def links():
        for p in proposals:
            for field in ("need_refs", "state_refs", "constraint_refs"):
                for rid in p[field]:
                    r = all_evidence[rid]
                    yield (p["id"], field, rid, r["source"], r["section"], r["quote"])
    sheet(tr("Прослеживаемость"), [tr("Предложение"), tr("Роль ссылки"), "ID", tr("Источник"),
          tr("Раздел"), tr("Цитата")], links(), [16, 24, 12, 36, 46, 100])
    def provenance():
        for rid, row in records.items():
            for location in row.get("source_spans", []):
                yield (rid, location["source"], location["section"], location["fragment"],
                       location["revision"], location["quote"])
    sheet(tr("Происхождение цитат"), ["ID", tr("Источник"), tr("Раздел"), tr("Фрагмент"),
          tr("Ревизия"), tr("Цитата")], provenance(), [12, 36, 46, 16, 70, 100])
    sheet(tr("Показатели назначения"), ["ID", tr("Объект"), tr("Значение"), tr("Единица"),
          tr("Условия"), tr("Уровень"), tr("Текущее значение"), tr("Целевое значение")],
          [(rid, *(m.get(k, "") for k in ("subject", "value", "unit", "conditions", "level", "current_value", "target_value")))
           for rid, m in result.get("metrics_registry", {}).items()], [12, 45, 24, 24, 70, 20, 24, 24])
    def dossiers():
        for pid, dossier in result.get("dossiers", {}).items():
            for facet, row in dossier["facets"].items():
                if not row["facts"]:
                    yield (pid, dossier["function"], facet, row["status"], "", "", "", "")
                for fact in row["facts"]:
                    rid = fact.get("record_id", "")
                    yield (pid, dossier["function"], facet, row["status"], rid, fact["span_id"],
                           fact["quote"], row.get("coverage", {}).get(rid, ""))
    sheet(tr("Характеристики функций"), ["ID", tr("Функция"), tr("Характеристика"),
          tr("Статус поиска"), tr("Исходная запись"), tr("Фрагмент"), tr("Цитата"), tr("Статус отражения")],
          dossiers(), [12, 42, 28, 24, 16, 16, 100, 24])
    def reference_rows():
        for rid, info in result.get("linked_by_need", {}).items():
            for item in info["items"]:
                yield (rid, item["id"], item["reference"], " → ".join(item["path"]),
                       item["source"], item["section"], item["quote"], "")
            for code, n in info["gaps"].items():
                yield (rid, "", "", "", "", "", "", f"{code}: {n}")
    sheet(tr("Связанные пункты оснований"), ["ID", tr("Фрагмент"), tr("Ссылка"), tr("Цепочка"),
          tr("Источник"), tr("Раздел"), tr("Цитата"), tr("Статус")],
          reference_rows(), [12, 12, 30, 36, 36, 46, 100, 24])
    sheet(tr("Открытые вопросы"), ["ID", tr("Вопрос")],
          [(q["need_id"], q["question"]) for q in result.get("questions", [])], [12, 100])
    out = BytesIO()
    wb.save(out)
    return out.getvalue()

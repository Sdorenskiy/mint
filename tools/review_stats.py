"""Сводка разборов замечаний экспертами: какие проверки MINT ошибаются и в чём, что эксперты добавляют сами.

Читает файлы, которые MINT выгружает на вкладке аудита: «📤 Скачать разбор (.json)» (один аудит) и «📥 Скачать
разборы (.jsonl)» в «📂 Мои аудиты» (все аудиты с разбором). Один аудит в нескольких файлах — берётся последняя
выгрузка. Только читает файлы и печатает Markdown — ничего не меняет и никуда не отправляет.

    python tools/review_stats.py mint-reviews_20261024.jsonl                 # сводка в окно
    python tools/review_stats.py папка_с_разборами > сводка.md               # все .json и .jsonl в папке
    python tools/review_stats.py разборы/ --examples 0                       # без примеров текстов

Примеры (--examples N, по умолчанию 3) — тексты неверных замечаний по причинам и свои замечания экспертов; есть
только в разборах с текстами. В них цитаты документов: пересылайте сводку туда же, куда можно сами документы.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mint.review_labels import BLOCKS, EXPORT_FORMAT, KINDS, REASONS  # noqa: E402 — без пакетов из requirements.txt

VERDICT_KEYS = ("ok", "minor", "wrong")


def read_reviews(paths):
    """Разборы из файлов и папок → список (последняя выгрузка каждого аудита), ошибки чтения."""
    files, errors = [], []
    for p in map(Path, paths):
        if p.is_dir():
            files += sorted(x for x in p.rglob("*") if x.suffix in (".json", ".jsonl"))
        else:
            files.append(p)
    by_audit = {}
    for f in files:
        try:
            text = f.read_text(encoding="utf-8-sig")
        except OSError as e:
            errors.append(f"{f}: {e}")
            continue
        items = []
        if f.suffix == ".jsonl":
            for i, line in enumerate(text.splitlines(), 1):
                if line.strip():
                    try:
                        items.append(json.loads(line))
                    except ValueError:
                        errors.append(f"{f}:{i}: не JSON")
        else:
            try:
                items.append(json.loads(text))
            except ValueError:
                errors.append(f"{f}: не JSON")
        for d in items:
            if not isinstance(d, dict) or d.get("format") != EXPORT_FORMAT:
                errors.append(f"{f}: не разбор MINT ({EXPORT_FORMAT})")
                continue
            aid = (d.get("audit") or {}).get("id") or f"{f}#{len(by_audit)}"
            if aid not in by_audit or d.get("exported", "") >= by_audit[aid].get("exported", ""):
                by_audit[aid] = d
    return list(by_audit.values()), errors


def _pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "—"


def _tally(items):
    c = Counter(x["verdict"] for x in items if x.get("verdict") in VERDICT_KEYS)
    marked = sum(c.values())
    return c, marked


def _row(label, items):
    c, marked = _tally(items)
    return (f"| {label} | {len(items)} | {marked} | {c['ok']} | {c['minor']} | {c['wrong']} | "
            f"{_pct(c['ok'] + c['minor'], marked)} | {_pct(c['ok'], marked)} |")


_HEAD = ("| | замечаний | размечено | ✅ беру | ➖ мелочь | ❌ неверно | верных (✅+➖) | беру (✅) |\n"
         "|---|---:|---:|---:|---:|---:|---:|---:|")


def _short(text, n=220):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n - 1] + "…"


def summary_markdown(reviews, examples=3):
    findings = [dict(f, _model=(r.get("audit") or {}).get("model") or "—",
                     _profile=(r.get("audit") or {}).get("profile") or "architecture")
                for r in reviews for f in r.get("findings") or []]
    added = [a for r in reviews for a in r.get("added") or []]
    with_texts = sum(1 for r in reviews if r.get("texts"))
    c, marked = _tally(findings)
    lines = ["# Сводка разборов замечаний MINT", ""]
    models = Counter((r.get("audit") or {}).get("model") or "—" for r in reviews)
    versions = Counter(r.get("mint") or "—" for r in reviews)
    lines += [f"Аудитов: {len(reviews)} (с текстами — {with_texts}). Модели: "
              + ", ".join(f"{m} — {n}" for m, n in models.most_common()) + ". Версии MINT: "
              + ", ".join(f"{v} — {n}" for v, n in versions.most_common()) + ".", ""]
    lines += [f"Замечаний MINT: {len(findings)}, размечено {marked} ({_pct(marked, len(findings))}). "
              f"Верных (✅+➖): {_pct(c['ok'] + c['minor'], marked)}; беру (✅): {_pct(c['ok'], marked)}; "
              f"неверных (❌): {_pct(c['wrong'], marked)}.",
              f"Своих замечаний экспертов (MINT их пропустил): {len(added)}; доля найденного MINT среди того, что "
              f"эксперты берут: {_pct(c['ok'], c['ok'] + len(added))}.", ""]
    if not findings and not added:
        return "\n".join(lines + ["Размеченных замечаний нет."]) + "\n"

    lines += ["## По видам проверок", "", _HEAD]
    by_kind = defaultdict(list)
    for f in findings:
        by_kind[f.get("kind") or "section"].append(f)
    for k in sorted(by_kind, key=lambda k: -len(by_kind[k])):
        lines.append(_row(KINDS.get(k, k), by_kind[k]))
    lines += ["", "## По блокам заключения", "", _HEAD]
    by_block = defaultdict(list)
    for f in findings:
        by_block[f.get("block") or "main"].append(f)
    for b in BLOCKS:
        if by_block.get(b):
            lines.append(_row(BLOCKS[b], by_block[b]))
    lines += ["", "## Признаки замечания", "", _HEAD]
    for label, pick in (("⭐ в «Главном»", lambda f: f.get("star")),
                        ("не в «Главном»", lambda f: not f.get("star")),
                        ("нашли 2+ проверок", lambda f: (f.get("found_by") or 1) > 1),
                        ("нашла 1 проверка", lambda f: (f.get("found_by") or 1) <= 1),
                        ("ссылается на документ-основание", lambda f: f.get("basis")),
                        ("не подтверждено источником", lambda f: f.get("unverified"))):
        sel = [f for f in findings if pick(f)]
        if sel:
            lines.append(_row(label, sel))
    lines += ["", "## По критичности", "", _HEAD]
    for sev in ("КРИТИЧНЫЙ", "СРЕДНИЙ", "НИЗКИЙ"):
        sel = [f for f in findings if f.get("severity") == sev]
        if sel:
            lines.append(_row(sev, sel))
    if len(models) > 1:
        lines += ["", "## По моделям", "", _HEAD]
        by_model = defaultdict(list)
        for f in findings:
            by_model[f["_model"]].append(f)
        for m in sorted(by_model):
            lines.append(_row(m, by_model[m]))
    by_profile = defaultdict(list)       # профиль (до профилей промпты были архитектурными — architecture)
    for f in findings:
        by_profile[f["_profile"]].append(f)
    if len(by_profile) > 1:
        lines += ["", "## По профилям проверки", "", _HEAD]
        for pr in sorted(by_profile):
            lines.append(_row(pr, by_profile[pr]))

    wrong = [f for f in findings if f.get("verdict") == "wrong"]
    reasons = Counter(f.get("reason") or "" for f in wrong)
    lines += ["", "## Почему неверно (❌)", "", "| причина | ❌ | доля | чаще всего у проверки |", "|---|---:|---:|---|"]
    for reason, n in reasons.most_common():
        kinds = Counter(f.get("kind") for f in wrong if (f.get("reason") or "") == reason).most_common(1)
        top = f"{KINDS.get(kinds[0][0], kinds[0][0])} ({kinds[0][1]})" if kinds else ""
        lines.append(f"| {REASONS.get(reason, reason) if reason else 'без причины'} | {n} | "
                     f"{_pct(n, len(wrong))} | {top} |")
    if added:
        sev = Counter(a.get("severity") or "СРЕДНИЙ" for a in added)
        lines += ["", "## Свои замечания экспертов", "",
                  "По критичности: " + ", ".join(f"{s} — {sev[s]}" for s in ("КРИТИЧНЫЙ", "СРЕДНИЙ", "НИЗКИЙ")
                                                 if sev[s]) + "."]

    if examples > 0:
        shown = [f for f in wrong if f.get("text")]
        if shown:
            lines += ["", f"## Примеры неверных замечаний (до {examples} на причину)", ""]
            for reason, _n in reasons.most_common():
                sel = [f for f in shown if (f.get("reason") or "") == reason][:examples]
                if not sel:
                    continue
                lines.append(f"**{REASONS.get(reason, reason) if reason else 'без причины'}**")
                for f in sel:
                    note = f" — эксперт: {_short(f['comment'], 160)}" if f.get("comment") else ""
                    lines.append(f"- [{KINDS.get(f.get('kind'), f.get('kind'))}] {_short(f['text'])}{note}")
                lines.append("")
        own = [a for a in added if a.get("text")]
        if own:
            lines += ["", f"## Примеры своих замечаний экспертов (до {examples * 3})", ""]
            lines += [f"- [{a.get('severity') or 'СРЕДНИЙ'}] {_short(a['text'])}" for a in own[:examples * 3]]
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Сводка разборов замечаний MINT (файлы .json и .jsonl).")
    ap.add_argument("paths", nargs="+", help="файлы разборов или папки с ними")
    ap.add_argument("--examples", type=int, default=3, help="примеров текстов на причину (0 — без примеров)")
    args = ap.parse_args(argv)
    reviews, errors = read_reviews(args.paths)
    for e in errors:
        print(f"⚠️ {e}", file=sys.stderr)
    if not reviews:
        print("Разборов не найдено.", file=sys.stderr)
        return 1
    sys.stdout.write(summary_markdown(reviews, args.examples))
    return 0


if __name__ == "__main__":
    sys.exit(main())

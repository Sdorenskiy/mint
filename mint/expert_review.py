"""Разбор замечаний аудита экспертом: по каждому замечанию — «беру / мелочь / неверно» с причиной, свои замечания,
которых MINT не нашёл, и итоговый список «Мои замечания» для автора документа (Markdown и Word).

Разбор — это и результат работы эксперта, и данные для улучшения MINT: export_review() собирает его в файл для
разработчиков — с текстами замечаний или без них (только виды проверок, отметки и причины).

    rows = review_rows(result)                  # строки таблицы разбора по заключению аудита
    review = {"marks": {rows[0]["key"]: {"verdict": "wrong", "reason": "present"}},
              "added": [{"section": "2.1", "severity": "СРЕДНИЙ", "text": "…"}]}
    md = my_remarks_markdown("Документ.docx", rows, review)
    data = export_review(meta, rows, review, texts=False)
"""

import hashlib
import io
import re
import time
from collections import Counter

from .audit import _SEV_PREFIX, is_typo, normalize_severity, severity_label, summary_candidates
from .i18n import tr
from .review_labels import BLOCKS, EXPORT_FORMAT, KINDS, REASONS, VERDICTS  # noqa: F401 — и для импорта отсюда
from .version import MINT_VERSION

_TEXT_META = ("file", "special", "criteria", "special_focus", "basis", "subject")
_CITE_RE = re.compile(r"\[(?:Источник|Source)\s*:\s*([^,\]]+)")


def finding_kind(f):
    """Какая проверка нашла замечание: код из KINDS."""
    if f.get("source") == "check":
        return "nomodel"
    if f.get("focus_item") is not None:
        return {"checklist": "checklist", "system": "system"}.get(f.get("point_kind") or "focus", "focus")
    if is_typo(f):
        return "typo"
    origins = f.get("origins") or []
    if f.get("source") == "deep" or (origins and all(o.startswith("deep") for o in origins)):
        kind = "deep:" + (f.get("check") or "other")
        return "typo" if kind == "deep:language" else kind if kind in KINDS else "deep:other"
    return "section"


def review_rows(result):
    """Строки разбора в порядке заключения: основные по разделам, ответы на пункты, не подтверждённые, мелкие,
    опечатки. У строки — номер в заключении (ref), вид проверки, блок, раздел, текст, «в Главном», ссылается ли на
    документ-основание и сколько проверок нашли замечание."""
    summary_ids = {id(it.get("finding")) for it in result.get("summary") or [] if it.get("finding") is not None}
    basis = {d["source"] for d in ((result.get("basis") or {}).get("docs") or [])}
    by_kind = {"focus": [], "checklist": [], "system": []}
    for f in result.get("findings") or []:
        if f.get("focus_item") is not None:
            by_kind.get(f.get("point_kind") or "focus", by_kind["focus"]).append(f)
    cands = summary_candidates(result.get("by_section") or [], result.get("focus_answers") or [], by_kind["focus"],
                               result.get("checklist_answers") or [], by_kind["checklist"],
                               result.get("system_answers") or [], by_kind["system"])
    # порядок заключения: ответы на пункты, затем замечания по разделам
    items = [(c["finding"], c["ref"], "point") for c in cands if not c["section"]]
    items += [(c["finding"], c["ref"], "main", c["section"]) for c in cands if c["section"]]
    items += [(f, "", "unverified") for f in result.get("unverified") or []]
    items += [(f, "", "minor") for f in result.get("minor") or []]
    items += [(f, "", "typo") for f in result.get("typos") or []]
    rows, keys = [], Counter()
    for n, (f, ref, block, *home) in enumerate(items, 1):
        cited = {m.group(1).strip() for m in _CITE_RE.finditer(f.get("text") or "")}
        section = "; ".join(s for s in f.get("sections") or [] if s) or (tr(home[0]) if home else "")
        key = finding_key(f)
        keys[key] += 1
        rows.append({
            "n": n, "key": key if keys[key] == 1 else f"{key}-{keys[key]}", "ref": ref, "block": block,
            "kind": finding_kind(f), "severity": normalize_severity(f["severity"]), "section": section,
            "text": f.get("text") or "", "quote": f.get("quote") or "", "star": id(f) in summary_ids,
            "basis": any(c.startswith(b) or b.startswith(c) for c in cited for b in basis),
            "found_by": max(1, len(f.get("origins") or [])), "unverified": list(f.get("unverified") or []),
        })
    return rows


def finding_key(f):
    """Постоянный ключ замечания (текст и разделы): отметки эксперта не теряются, когда перепроверка непроверенных
    разделов добавляет замечания и номера сдвигаются."""
    base = (f.get("text") or "") + "|" + "; ".join(s for s in f.get("sections") or [] if s)
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


def mark(review, row):
    return ((review or {}).get("marks") or {}).get(row["key"]) or {}


def review_progress(rows, review):
    """Сколько размечено: {"total", "marked", "ok", "minor", "wrong", "no_reason", "added"}; no_reason —
    «неверно» без причины."""
    marks = [mark(review, r) for r in rows]
    c = Counter(m.get("verdict") or "" for m in marks)
    return {"total": len(rows), "marked": len(rows) - c[""], "ok": c["ok"], "minor": c["minor"], "wrong": c["wrong"],
            "no_reason": sum(1 for m in marks if m.get("verdict") == "wrong" and not m.get("reason")),
            "added": len(added_remarks(review))}


def added_remarks(review):
    """Свои замечания эксперта (непустые)."""
    return [a for a in (review or {}).get("added") or [] if (a.get("text") or "").strip()]


def my_remarks(rows, review, include_minor=False):
    """Итоговые замечания эксперта: отмеченные «беру» (и «мелочь», если include_minor) и добавленные свои, в
    порядке заключения. → [{"section", "severity", "text", "comment", "own"}]."""
    keep = ("ok", "minor") if include_minor else ("ok",)
    out = []
    for r in rows:
        m = mark(review, r)
        if m.get("verdict") in keep:
            out.append({"section": r["section"], "severity": r["severity"], "text": r["text"], "quote": r["quote"],
                        "comment": (m.get("comment") or "").strip(), "own": False})
    for a in added_remarks(review):
        out.append({"section": (a.get("section") or "").strip(), "severity": normalize_severity(a.get("severity")),
                    "text": a["text"].strip(), "quote": "", "comment": "", "own": True})
    return out


def my_remarks_markdown(filename, rows, review, include_minor=False):
    items = my_remarks(rows, review, include_minor)
    lines = [tr("# Замечания к документу «{f}»", f=filename), "", tr("Дата: {d}", d=time.strftime("%d.%m.%Y")), ""]
    if not items:
        lines.append(tr("Замечаний нет."))
    for i, it in enumerate(items, 1):
        where = f" — *{it['section']}*" if it["section"] else ""
        note = f" ({it['comment']})" if it["comment"] else ""
        lines.append(f"{i}. {tr(_SEV_PREFIX.get(it['severity'], _SEV_PREFIX['СРЕДНИЙ']))} {it['text']}{where}{note}")
    return "\n".join(lines) + "\n"


def my_remarks_docx(filename, rows, review, include_minor=False):
    """«Мои замечания» таблицей Word: №, раздел, замечание, критичность. → bytes."""
    import docx
    items = my_remarks(rows, review, include_minor)
    doc = docx.Document()
    doc.add_heading(tr("Замечания к документу «{f}»", f=filename), level=1)
    doc.add_paragraph(tr("Дата: {d}", d=time.strftime("%d.%m.%Y")))
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, title in zip(table.rows[0].cells, (tr("№"), tr("Раздел"), tr("Замечание"), tr("Критичность"))):
        cell.text = title
    for i, it in enumerate(items, 1):
        cells = table.add_row().cells
        cells[0].text = str(i)
        cells[1].text = it["section"]
        cells[2].text = it["text"] + (f" ({it['comment']})" if it["comment"] else "")
        cells[3].text = tr(severity_label(it["severity"]))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def accepted_findings(rows, review, include_minor=False):
    """Замечания для примечаний Word в документе: «беру» (и «мелочь») и свои — как замечания аудита."""
    return [{"severity": it["severity"], "text": it["text"] + (f" ({it['comment']})" if it["comment"] else ""),
             "quote": it["quote"], "sections": [it["section"]] if it["section"] else []}
            for it in my_remarks(rows, review, include_minor)]


def export_review(meta, rows, review, texts=True):
    """Разбор для улучшения MINT — один JSON-объект. texts=False — без текстов замечаний, разделов, комментариев и
    имени файла: только виды проверок, критичность, отметки и причины (цитаты документа наружу не уходят)."""
    counts, reasons = {}, {}
    findings = []
    for r in rows:
        m = mark(review, r)
        verdict, reason = m.get("verdict") or "", m.get("reason") or ""
        c = counts.setdefault(r["kind"], {"ok": 0, "minor": 0, "wrong": 0, "none": 0})
        c[verdict or "none"] += 1
        if reason:
            reasons.setdefault(r["kind"], Counter())[reason] += 1
        item = {"kind": r["kind"], "block": r["block"], "severity": r["severity"], "star": r["star"],
                "basis": r["basis"], "found_by": r["found_by"], "unverified": bool(r["unverified"]),
                "verdict": verdict, "reason": reason}
        if texts:
            item.update(ref=r["ref"], section=r["section"], text=r["text"], quote=r["quote"],
                        comment=m.get("comment") or "")
        findings.append(item)
    added = added_remarks(review)
    audit = {k: v for k, v in (meta or {}).items() if k not in ("progress", "reviewed")}
    if not texts:                                # имена документов и формулировки пользователя — тоже тексты
        audit = {k: v for k, v in audit.items() if k not in _TEXT_META}
        audit["basis"] = len((meta or {}).get("basis") or [])
    return {
        "format": EXPORT_FORMAT, "mint": MINT_VERSION, "exported": time.strftime("%Y-%m-%d %H:%M"), "texts": texts,
        "audit": audit,
        "counts": counts, "reasons": {k: dict(v) for k, v in reasons.items()},
        "findings": findings,
        "added": ([{"severity": normalize_severity(a.get("severity")), "section": (a.get("section") or "").strip(),
                    "text": a["text"].strip()} for a in added] if texts else
                  [{"severity": normalize_severity(a.get("severity"))} for a in added]),
    }

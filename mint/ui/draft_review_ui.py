"""Review a generated draft locally, using the existing Mint requirement list."""
import json
import math

import streamlit as st

from ..draft_review import export_summary, list_runs, load_run, save_marks, save_run, summary
from ..i18n import tr
from ..prompts import render

_OPTIONS = {"": "—", "covered": "✅", "missing": "❌", "distorted": "⚠️", "not_applicable": "—"}
_PAGE_SIZE = 15


def render_draft_reviews(cfg, input_key=None, filename="", sources=(), result=None):
    with st.expander(tr("Проверка качества сформированного документа (локально)")):
        st.caption(tr("Сначала проверьте черновик Word. Оценка сохраняется только на этом компьютере."))
        if result is not None and st.button(tr("Сохранить черновик для экспертного разбора"), key="draft_review_new"):
            prompt_sig = ""
            try:
                from hashlib import sha256
                prompt_sig = sha256("\n".join(render("draft_" + name) for name in
                                         ("system", "extract", "layout", "fill", "rows", "check")).encode(
                                             "utf-8")).hexdigest()[:12]
            except (OSError, ValueError):
                pass
            st.session_state["draft_review_id"] = save_run(cfg, input_key, filename, sources, result, prompt_sig)
        runs = list_runs(cfg)
        if not runs:
            st.caption(tr("Сохранённых разборов черновика пока нет."))
            return
        ids = [r["id"] for r in runs]
        selected_id = st.session_state.get("draft_review_id")
        if selected_id not in ids:
            selected_id = ids[0]
        run_id = st.selectbox(tr("Сохранённый разбор"), ids, index=ids.index(selected_id),
                              format_func=lambda rid: next(f'{r["time"]} · {r["file"]}' for r in runs if r["id"] == rid),
                              key="draft_review_select")
        run = load_run(cfg, run_id)
        if not run:
            st.warning(tr("Не удалось открыть сохранённый разбор."))
            return
        review = run["review"]
        rows = run["requirements"]
        marks = dict(review.get("marks") or {})
        pages = max(1, math.ceil(len(rows) / _PAGE_SIZE))
        page = st.selectbox(tr("Страница требований"), list(range(1, pages + 1)),
                            key=f"draft_review_page_{run_id}")
        for row in rows[(page - 1) * _PAGE_SIZE:page * _PAGE_SIZE]:
            rid = row["id"]
            st.text(f'{rid} · {row["source"]} › {row["section"]}\n{row["quote"]}')
            value = marks.get(rid, "")
            labels = {
                "": tr("Не оценено"), "covered": tr("Перенесено правильно"),
                "missing": tr("Пропущено"), "distorted": tr("Искажено"),
                "not_applicable": tr("Не относится к документу"),
            }
            marks[rid] = st.selectbox(tr("Вердикт по требованию") + " · " + rid,
                                      list(_OPTIONS), index=list(_OPTIONS).index(value) if value in _OPTIONS else 0,
                                      format_func=lambda v: labels[v], key=f"draft_review_{run_id}_{rid}")
        missed = st.text_area(tr("Требования, которые Mint не извлёк (по одному в строке)"),
                              value="\n".join(review.get("missed_extraction") or []),
                              key=f"draft_review_missed_{run_id}")
        unsupported = st.text_area(tr("Утверждения черновика без основания (по одному в строке)"),
                                   value="\n".join(review.get("unsupported_claims") or []),
                                   key=f"draft_review_unsupported_{run_id}")
        if st.button(tr("Сохранить экспертные оценки"), key=f"draft_review_save_{run_id}"):
            save_marks(cfg, run_id, marks, missed.splitlines(), unsupported.splitlines())
            run = load_run(cfg, run_id)
            st.success(tr("Экспертная оценка сохранена локально."))
        metrics = summary(run)
        st.caption(tr("Оценено: {marked} из {total}; перенесено: {covered}; пропущено: {missing}; "
                      "искажено: {distorted}; не относится: {unrelated}.",
                      marked=metrics["reviewed"], total=metrics["total_extracted"],
                      covered=metrics["covered"], missing=metrics["missing"], distorted=metrics["distorted"],
                      unrelated=metrics["not_applicable"]))
        st.caption(tr("Доля корректно перенесённых среди оценённых применимых: {rate}. "
                      "Это не полнота всех требований исходных документов.",
                      rate="—" if metrics["coverage_of_reviewed_applicable"] is None else
                      f'{100 * metrics["coverage_of_reviewed_applicable"]:.1f}%'))
        st.download_button(tr("Скачать обезличенную сводку оценки"),
                           json.dumps(export_summary(run), ensure_ascii=False, indent=2),
                           file_name="mint_draft_review_summary.json", mime="application/json",
                           key=f"draft_review_export_{run_id}")

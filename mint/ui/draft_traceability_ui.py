"""Read-only bidirectional requirement/source view for the Word drafting tab."""
import math

import streamlit as st

from ..draft_traceability import by_basis_document, by_word_section, build_traceability, trace_counts
from ..i18n import tr

_COVERAGE = {
    "output_anchor": "В сформированном тексте найден фрагмент требования; смысловая полнота не доказана",
    "cited_without_anchor": "Основание указано, но текстовый перенос не подтверждён",
    "candidate_only": "Требование рассматривалось для раздела, но перенос не подтверждён",
    "not_selected": "Не связано с заполненными разделами",
    "external": "Обязанность внешнего участника или иной системы",
    "scope_uncertain": "Применимость к целевой системе не выяснена",
}
_FILTERS = {
    "all": "Все извлечённые",
    "output_anchor": "Есть текстовое отражение",
    "needs_review": "Требуют проверки",
    "external": "Другие участники",
}


def _visible(row, filter_name):
    if filter_name == "all":
        return True
    if filter_name == "needs_review":
        return row["coverage"] in {"cited_without_anchor", "candidate_only",
                                   "not_selected", "scope_uncertain"}
    return row["coverage"] == filter_name


def render_draft_traceability(result, source_names=()):
    rows = build_traceability(result)
    if not rows:
        return rows
    counts = trace_counts(rows)
    with st.expander(tr("Требования и их отражение в Word")):
        st.caption(tr("Показаны только извлечённые требования. Их текстовое присутствие в Word "
                      "не доказывает правильность и полноту переноса или полноту извлечения."))
        st.caption(tr("Извлечено: {extracted}; найдено текстовых отражений: {anchored}; "
                      "требуют разбора: {pending}; внешние/иные: {external}.", **counts))
        view = st.radio(tr("Направление просмотра"), ("word", "source"), horizontal=True,
                        format_func=lambda v: tr("По разделам Word") if v == "word" else
                                              tr("По документам-основаниям"),
                        key="draft_trace_view")
        groups = (by_word_section(rows, result) if view == "word" else
                  by_basis_document(rows, source_names))
        if not groups:
            st.caption(tr("Нет связей с разделами. Проверьте требования по документам-основаниям."))
            return rows
        name = st.selectbox(tr("Раздел Word") if view == "word" else tr("Документ-основание"),
                            list(groups), key=f"draft_trace_group_{view}")
        filter_name = st.selectbox(tr("Показать"), list(_FILTERS),
                                   format_func=lambda key: tr(_FILTERS[key]), key="draft_trace_filter")
        selected = [row for row in groups[name] if _visible(row, filter_name)]
        if not selected:
            st.caption(tr("Для выбранного фильтра записей нет."))
            return rows
        per_page = 40
        pages = math.ceil(len(selected) / per_page)
        page = (st.selectbox(tr("Страница"), list(range(1, pages + 1)),
                             key=f"draft_trace_page_{view}_{name}_{filter_name}") if pages > 1 else 1)
        st.caption(tr("Отображено {n} из {total}.", n=min(per_page, len(selected)), total=len(selected)))
        for row in selected[(page - 1) * per_page:page * per_page]:
            title = f'{row["source"]} › {row["source_section"]} · {row["quote"][:80]}'
            with st.expander(title):
                st.caption(tr(_COVERAGE[row["coverage"]]))
                st.text(row["quote"])
                if row["actor"]:
                    st.caption(tr("Исполнитель: {actor}", actor=row["actor"]))
                if row["scope_reason"]:
                    st.caption(tr("Применимость: {reason}", reason=row["scope_reason"]))
                confirmed = row["anchored"]
                if confirmed:
                    st.markdown("**" + tr("Где найден текст в Word") + "**")
                    for ref in confirmed:
                        st.caption(ref["section"] + " · " + ref["field"])
                        st.text(ref["text"][:1000])
                if row["cited_without_anchor"]:
                    st.caption(tr("Ссылка модели без подтверждённого текстового фрагмента: {sections}",
                                  sections=", ".join(dict.fromkeys(
                                      x["section"] for x in row["cited_without_anchor"]))))
                if row["candidate_sections"]:
                    st.caption(tr("Разделы, для которых требование рассматривалось: {sections}",
                                  sections=", ".join(row["candidate_sections"])))
    return rows

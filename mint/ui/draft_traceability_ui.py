"""Read-only bidirectional requirement/source view for the Word drafting tab."""
import hashlib
import math

import streamlit as st

from ..document_edit import list_targets
from ..draft_traceability import (by_basis_document, by_word_section, build_traceability,
                                 chat_request_for_requirement, mark_stale_after_edits, trace_counts)
from ..i18n import N_, tr

_COVERAGE = {
    "output_anchor": N_("В сформированном тексте найден фрагмент требования; смысловая полнота не доказана"),
    "cited_without_anchor": N_("Основание указано, но текстовый перенос не подтверждён"),
    "candidate_only": N_("Требование рассматривалось для раздела, но перенос не подтверждён"),
    "not_selected": N_("Не связано с заполненными разделами"),
    "external": N_("Обязанность внешнего участника или иной системы"),
    "scope_uncertain": N_("Применимость к целевой системе не выяснена"),
    "stale_after_edit": N_("После принятой правки требуется повторно проверить отражение в Word"),
}
_FILTERS = {
    "all": N_("Все извлечённые"),
    "output_anchor": N_("Есть текстовое отражение"),
    "needs_review": N_("Требуют проверки"),
    "external": N_("Другие участники"),
    "stale_after_edit": N_("После исправления Word"),
}


def _visible(row, filter_name):
    if filter_name == "all":
        return True
    if filter_name == "needs_review":
        return row["coverage"] in {"cited_without_anchor", "candidate_only",
                                   "not_selected", "scope_uncertain", "stale_after_edit"}
    return row["coverage"] == filter_name


def render_draft_traceability(result, source_names=(), input_key=None, *, allow_edit=True):
    rows = build_traceability(result)
    if not rows:
        return rows
    state = st.session_state.get("draft_edit_state")
    identity = (input_key, hashlib.sha256(result["docx"]).hexdigest())
    if state is not None and state.get("identity") == identity:
        docx = state["docx"]
        changed = {section for section, _target in state["changes"]}
        rows = mark_stale_after_edits(rows, changed)
    else:
        docx = result["docx"]
    counts = trace_counts(rows)
    with st.expander(tr("Требования и их отражение в Word")):
        if state is not None and state.get("identity") == identity and state["changes"]:
            st.warning(tr("Word уже изменён через чат. Отчёт построен по первоначальной генерации; "
                          "неподтверждённые связи требуют повторной проверки."))
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
        targets = list_targets(docx)
        destination = None
        if targets and allow_edit:
            options = [x["id"] for x in targets]
            labels = {x["id"]: x["label"] for x in targets}
            default = next((i for i, x in enumerate(targets)
                            if view == "word" and x["section"] == name
                            and x["kind"] == "section"), 0)
            destination = st.selectbox(tr("Куда направлять исправления из списка"),
                                       options, index=default, format_func=labels.__getitem__,
                                       key="draft_trace_destination")
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
        visible = selected[(page - 1) * per_page:page * per_page]
        lookup = {row["id"]: row for row in visible}
        rid = st.selectbox(tr("Требование"), list(lookup),
                           format_func=lambda key: (
                               f'{lookup[key]["source"]} › {lookup[key]["source_section"]} · '
                               f'{lookup[key]["quote"][:85]}'),
                           key=f"draft_trace_requirement_{view}_{name}_{filter_name}_{page}")
        row = lookup[rid]
        st.caption(tr(_COVERAGE[row["coverage"]]))
        if row.get("stale_sections"):
            st.warning(tr("Документ изменён в разделах {sections}. Прежнюю связь нужно проверить заново.",
                          sections=", ".join(row["stale_sections"])))
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
        if destination and st.button(tr("Доработать через чат"), key="trace_edit_" + row["id"]):
            request = chat_request_for_requirement(row)
            st.session_state["word_edit_target"] = destination
            st.session_state["word_edit_request"] = request[:3000]
            st.session_state["word_edit_focus_requirement"] = {
                "identity": identity, "target_id": destination, "requirement_id": row["id"]}
            st.session_state["word_edit_focus"] = True
            if state is not None and state.get("identity") == identity:
                state["pending"] = None
            st.rerun()
    return rows

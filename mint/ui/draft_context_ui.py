"""Small explicit confirmation gate for automatically inferred drafting context."""
import streamlit as st

from ..document_context import confirm_context, infer_context
from ..i18n import tr
from ..template_draft import DraftError

_FIELDS = ("draft_ctx_target", "draft_ctx_objective", "draft_ctx_scope", "draft_ctx_participants")


def render_draft_context(cfg, template, sources, input_signature, *, namespace='draft_context', inline=False):
    """Return a *confirmed* context or None; never silently trust model inference."""
    state_key = "draft_context_state" if namespace == "draft_context" else namespace
    fields = _FIELDS if namespace == "draft_context" else tuple(namespace + "_" + k for k in _FIELDS)
    state = st.session_state.get(state_key)
    if state is None or state.get("key") != input_signature:
        state = {"key": input_signature, "suggestion": None, "confirmed": None}
        st.session_state[state_key] = state
        for key in fields:
            st.session_state.pop(key, None)

    with (st.container() if inline else st.expander(tr("Целевая система и границы документа"), expanded=state["confirmed"] is None)):
        if state["confirmed"] is not None:
            confirmed = state["confirmed"]
            st.success(tr("Контекст подтверждён пользователем."))
            st.write(tr("Целевая система: {name}", name=confirmed["target"]))
            if confirmed["objective"]:
                st.caption(tr("Задача: {value}", value=confirmed["objective"]))
            if confirmed["scope"]:
                st.caption(tr("Границы: {value}", value=confirmed["scope"]))
            if confirmed["participants"]:
                st.caption(tr("Внешние участники: {value}", value=confirmed["participants"]))
            if st.button(tr("Исправить контекст"), key="draft_ctx_revise" if namespace == "draft_context" else namespace + "_revise"):
                state["suggestion"] = {**confirmed, "confidence": "confirmed"}
                state["confirmed"] = None
                for key in fields:
                    st.session_state.pop(key, None)
                st.rerun()
            return confirmed

        st.caption(tr("Mint предложит контекст по шаблону; подтвердите или поправьте перед сборкой Word. "
                      "Основания могут описывать другие платформы."))
        if not state["suggestion"] and st.button(tr("Определить контекст автоматически"),
                                                disabled=not (template and sources),
                                                key="draft_ctx_infer" if namespace == "draft_context" else namespace + "_infer"):
            try:
                with st.spinner(tr("Определяем целевую систему документа")):
                    state["suggestion"] = infer_context(cfg, template, sources)
            except DraftError as exc:
                st.warning(tr("Контекст не определён автоматически: {reason}. Заполните вручную.",
                              reason=str(exc)))
                state["suggestion"] = {}
            st.rerun()
        if state["suggestion"] is None:
            if inline and st.button(tr("Указать контекст вручную"), key=namespace + "_manual"):
                state["suggestion"] = {}
                st.rerun()
            return None

        proposal = state["suggestion"]
        if proposal.get("reason"):
            st.caption(tr("Почему выбран этот контекст: {reason}", reason=proposal["reason"]))
        if proposal.get("confidence") == "low":
            st.warning(tr("Mint не уверен в целевой системе. Проверьте предложение внимательно."))
        with st.form(namespace + "_confirm"):
            target = st.text_input(tr("Целевая система / объект документа"),
                                   value=proposal.get("target", ""), max_chars=180, key=fields[0])
            objective = st.text_area(tr("Назначение документа"), value=proposal.get("objective", ""),
                                     height=70, max_chars=1200, key=fields[1])
            scope = st.text_area(tr("Что меняется / границы работ"), value=proposal.get("scope", ""),
                                 height=70, max_chars=1600, key=fields[2])
            participants = st.text_input(tr("Другие участники взаимодействия"),
                                         value=proposal.get("participants", ""),
                                         max_chars=800, key=fields[3])
            accepted = st.form_submit_button(tr("Подтвердить контекст"))
        if accepted:
            try:
                state["confirmed"] = confirm_context({
                    "target": target, "objective": objective, "scope": scope,
                    "participants": participants})
            except DraftError as exc:
                st.warning(str(exc))
            else:
                st.rerun()
    return None

"""Streamlit continuation chat for reviewing and accepting small Word edits."""
import hashlib

import streamlit as st

from ..document_edit import apply_edit, get_target, list_targets, proposal_diff, propose_edit
from ..i18n import tr
from ..template_draft import DraftError

_HISTORY_LIMIT = 10


def _chat_state(input_key, result):
    """Only session-local versions. Never write user document to GitHub or logs."""
    identity = (input_key, hashlib.sha256(result["docx"]).hexdigest())
    state = st.session_state.get("draft_edit_state")
    if state is None or state.get("identity") != identity:
        state = {"identity": identity, "docx": result["docx"], "versions": [],
                 "changes": [], "threads": {}, "pending": None}
        st.session_state["draft_edit_state"] = state
    return state


def render_draft_edit_chat(cfg, input_key, result):
    """Return current accepted DOCX; keep initial result immutable for quality review."""
    state = _chat_state(input_key, result)
    with st.expander(tr("Чат по сформированному документу"), expanded=False):
        st.caption(tr("Выберите фрагмент, опишите изменение, проверьте предложение и только затем примените. "
                      "Исходный результат генерации остаётся доступен до новой сборки."))
        st.caption(tr("Принято правок: {count}. История хранится только в текущем сеансе.",
                      count=len(state["changes"])))
        if state["versions"] and st.button(tr("Отменить последнюю правку"), key="word_edit_undo"):
            state["docx"] = state["versions"].pop()
            state["changes"].pop()
            state["threads"].clear()
            state["pending"] = None
            st.rerun()

        try:
            targets = list_targets(state["docx"])
        except DraftError as exc:
            st.error(str(exc))
            return state["docx"]
        if not targets:
            st.warning(tr("В документе нет безопасных для автоматического редактирования фрагментов."))
            return state["docx"]
        lookup = {row["id"]: row for row in targets}
        selected_id = st.selectbox(tr("Что редактировать"), list(lookup),
                                   format_func=lambda key: lookup[key]["label"],
                                   key="word_edit_target")
        selected = lookup[selected_id]
        st.text_area(tr("Текущая редакция"), value=selected["text"], disabled=True,
                     height=140, key=f"word_edit_current_{selected_id}_{hashlib.sha256(state['docx']).hexdigest()[:12]}")
        thread = state["threads"].setdefault(selected_id, [])
        for item in thread[-8:]:
            with st.chat_message(item["role"]):
                st.text(item["content"][:3000])

        with st.form("word_edit_form", clear_on_submit=True):
            request = st.text_area(tr("Что изменить в этом фрагменте?"),
                                   placeholder=tr("Например: уточни порядок повторной доставки по основаниям"),
                                   max_chars=3000, height=100)
            sent = st.form_submit_button(tr("Предложить изменение"))
        if sent and request.strip():
            try:
                proposed = propose_edit(cfg, state["docx"], selected_id, request,
                                        result["requirements"], thread)
            except DraftError as exc:
                st.warning(str(exc))
            else:
                thread.append({"role": "user", "content": request})
                thread.append({"role": "assistant", "content": proposed["text"]})
                state["pending"] = proposed
                st.rerun()

        pending = state.get("pending")
        if pending and pending["target_id"] == selected_id:
            if get_target(state["docx"], selected_id) is None:
                state["pending"] = None
                st.warning(tr("Выбранный фрагмент изменился. Запросите новую редакцию."))
            else:
                st.text(tr("Предлагаемое изменение (было → станет)"))
                st.code(proposal_diff(pending), language="diff")
                if pending["reason"]:
                    st.caption(pending["reason"])
                for warning in pending["warnings"]:
                    st.warning(warning)
                if pending["sources"]:
                    with st.expander(tr("Документы-основания предложения")):
                        for source in pending["sources"]:
                            st.text(f'{source["source"]} › {source["section"]}\n{source["quote"][:800]}')
                left, right = st.columns(2)
                with left:
                    if st.button(tr("Принять правку"), type="primary", key="word_edit_accept"):
                        try:
                            new_bytes = apply_edit(state["docx"], pending)
                        except DraftError as exc:
                            st.error(str(exc))
                        else:
                            state["versions"].append(state["docx"])
                            state["changes"].append((selected["section"], selected_id))
                            if len(state["versions"]) > _HISTORY_LIMIT:
                                state["versions"].pop(0)
                                state["changes"].pop(0)
                            state["docx"] = new_bytes
                            state["pending"] = None
                            # Body-relative indices can change after adding paragraphs.
                            # Reset conversations rather than attaching them to another block.
                            state["threads"].clear()
                            st.rerun()
                with right:
                    if st.button(tr("Отклонить правку"), key="word_edit_reject"):
                        state["pending"] = None
                        st.rerun()
        elif pending:
            st.caption(tr("Есть непринятое предложение для другого фрагмента. Вернитесь к нему или отклоните."))
        st.caption(tr("Проверяйте предложенные факты и ссылки перед принятием. "
                      "Редактирование защищённых элементов Word намеренно ограничено."))
    return state["docx"]

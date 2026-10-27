"""Интерфейс: вкладка «Чат»."""

import streamlit as st

from ..chat import answer_question, chat_history
from ..citations import citation_warning
from ..feedback import new_feedback_id
from ..i18n import tr
from ..kb import list_kb_documents
from .common import _clear_chat, render_sources
from .feedback import render_feedback
from .theme import empty_chat_html


def _chat_feedback(cfg, msg, question):
    """Оценка ответа: в отзыв попадают вопрос, ответ и источники (см. mint/feedback.py)."""
    if not msg.get("id"):
        return
    render_feedback(cfg, "chat", msg["id"], subject=question, context=lambda: {
        "question": question, "search_query": msg.get("search_query") or "",
        "answer": msg["content"], "sources": msg.get("sources") or [],
        "citations_invalid": msg.get("citations_invalid") or [], "prompts": msg.get("prompts") or "",
    })


def _render_answer(msg):
    """Ответ модели: ссылки мимо контекста помечены ⚠️, под ответом — предупреждение о них.
    В истории диалога (content) ответ хранится без пометок."""
    st.markdown(msg.get("shown") or msg["content"])
    warning = citation_warning(msg.get("citations_invalid"))
    if warning:
        st.warning(warning)


def render_chat_tab(cfg, gl):
    """Вкладка «Чат»: вопросы по базе знаний с учётом истории диалога."""
    st.subheader(tr("Консультация по накопленным знаниям"))
    if "messages" not in st.session_state:
        st.session_state.messages = []
    # история и новый ответ — над полем ввода, поле ввода — в конце страницы
    chat_area = st.container()
    if st.session_state.messages:
        st.button(tr("🗑️ Новый диалог"), key="chat_clear_btn", on_click=_clear_chat,
                  help=tr("Очищает историю: следующий вопрос будет понят без учёта предыдущих реплик."))
    user_input = st.chat_input(tr("Задайте вопрос по базе знаний..."), key="chat_field")
    with chat_area:
        if not st.session_state.messages and not user_input:
            st.markdown(empty_chat_html(list_kb_documents(cfg)[0]), unsafe_allow_html=True)
        last_question = ""
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                last_question = msg["content"]
            with st.chat_message(msg["role"]):
                if msg.get("search_query"):
                    st.caption(tr("🔎 Искал по вашему вопросу и по уточнённому с учётом диалога: «{q}»",
                                  q=msg['search_query']))
                _render_answer(msg)
                if msg.get("sources"):
                    render_sources(msg["sources"])
                if msg["role"] == "assistant":
                    _chat_feedback(cfg, msg, last_question)
        if user_input:
            history = chat_history(st.session_state.messages, cfg.chat_history_turns)
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)
            with st.chat_message("assistant"):
                with st.spinner(tr("Ищу в базе знаний...")):
                    res = answer_question(user_input, cfg, glossary=gl, history=history)
                if res["search_query"]:
                    st.caption(tr("🔎 Искал по вашему вопросу и по уточнённому с учётом диалога: «{q}»",
                                  q=res["search_query"]))
                msg = {"role": "assistant", "content": res["answer"], "sources": res["sources"],
                       "search_query": res["search_query"], "id": new_feedback_id(), "shown": res["shown"],
                       "citations_invalid": res["citations_invalid"], "prompts": res["prompts"]}
                _render_answer(msg)
                if msg["sources"]:
                    render_sources(msg["sources"])
                _chat_feedback(cfg, msg, user_input)
            st.session_state.messages.append(msg)

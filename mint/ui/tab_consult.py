"""Интерфейс: вкладка «Консультант» — разбор проблем и варианты решения, схемы (код Mermaid), объяснения устройства
систем с опорой на базу знаний. Сценарий — mint/consult.py; разговор хранится отдельно от чата (у них разный
смысл истории: чату прошлые реплики нужны, чтобы понять вопрос, консультанту — как часть работы)."""

import streamlit as st

from ..chat import chat_history
from ..citations import citation_warning
from ..consult import HISTORY_ANSWER_CHARS, answer_consult
from ..feedback import new_feedback_id
from ..i18n import tr
from ..kb import list_kb_documents
from .common import CONSULT_SETTINGS, _expert_widget, btn_w, columns_center, dl_w
from .feedback import render_feedback
from .theme import consult_empty_html, consult_found_html

MESSAGES = "consult_messages"


def _clear():
    st.session_state[MESSAGES] = []


def _render_settings(cfg):
    """Настройки консультанта — на время сеанса (как «Экспертные настройки»), постоянные — в config.yaml."""
    base_cfg, info = st.session_state.get("_mint_audit_settings") or (cfg, {})
    manual = st.session_state.setdefault("mint_manual", {})
    with st.expander(tr("⚙️ Настройки консультанта")):
        for title, specs in CONSULT_SETTINGS:
            st.caption(f"**{tr(title)}**")
            for spec in specs:
                _expert_widget(spec, base_cfg, info, manual)
        st.caption(tr("Модель — та же, что в боковой панели. Тексты — страница «📝 Промпты», группа «Консультант». "
                      "Постоянные значения — в config.yaml, раздел consult."))


def _status_label(stage, info):
    if stage == "plan":
        return tr("Разбираю запрос: что просят и где искать…")
    if stage == "search":
        return tr("Ищу в базе: {i} из {n} — «{q}»", i=info.get("i"), n=info.get("n"), q=(info.get("query") or "")[:80])
    return tr("Пишу ответ по {b} фрагментам ({c} симв.)…", b=info.get("blocks"),
              c=f"{int(info.get('chars') or 0):,}".replace(",", " "))


def _render_answer(cfg, msg, request):
    st.markdown(msg.get("shown") or msg["content"])
    if msg.get("error"):
        return
    warning = citation_warning(msg.get("citations_invalid"))
    if warning:
        st.warning(warning)
    if msg.get("unsupported"):
        st.caption(tr("❔ — утверждение о ваших системах без ссылки на документ ({n}): модель могла выдать догадку за "
                      "содержание документов — проверьте.", n=msg["unsupported"]))
    for i, code in enumerate(msg.get("diagrams") or []):
        st.download_button(tr("⬇ Схема {n} (.mmd)", n=i + 1), code, file_name=f"mint_diagram_{i + 1}.mmd",
                           mime="text/plain", key=f"consult_mmd_{msg['id']}_{i}", **dl_w)
    if msg.get("diagrams"):
        st.caption(tr("Схема — код Mermaid. Открыть и доработать: draw.io → Arrange → Insert → Advanced → Mermaid; "
                      "Excalidraw → «Mermaid to Excalidraw». Код можно и скопировать из ответа."))
    with st.expander(tr("🔎 Что нашёл в вики")):
        st.markdown(consult_found_html(msg), unsafe_allow_html=True)
        st.caption(tr("Фрагментов: {c} симв. из {b} доступных · тип запроса: {k} · {s} с · {v}",
                      c=f"{int(msg.get('context_chars') or 0):,}".replace(",", " "),
                      b=f"{int(msg.get('budget') or 0):,}".replace(",", " "), k=msg.get("kind") or "—",
                      s=msg.get("seconds") or 0, v=msg.get("prompts") or ""))
    render_feedback(cfg, "consult", msg["id"], subject=request, context=lambda: {
        "question": request, "answer": msg["content"], "request_kind": msg.get("kind"),
        "queries": msg.get("queries") or [],
        "sources": [f"{b.get('source')} › {b.get('path') or ''}" for b in msg.get("blocks") or []],
        "citations_invalid": msg.get("citations_invalid") or [], "unsupported": msg.get("unsupported") or 0,
        "prompts": msg.get("prompts") or "",
    })


def _previous_context(messages, turns):
    """Фрагменты, которые модель видела в последних turns ответах: ссылки на них в новом ответе — не ошибка."""
    ctx = [m.get("context") or "" for m in messages if m.get("role") == "assistant"]
    return "\n\n".join(c for c in ctx[-max(1, turns):] if c)


def render_consult_tab(cfg, gl):
    head, new_chat = st.columns([0.74, 0.26], **columns_center())
    head.subheader(tr("Консультант: проблемы, схемы, объяснения"))
    new_chat.button(tr("➕ Новый разговор"), key="consult_clear_btn", on_click=_clear, **btn_w,
                    help=tr("Начать с чистого листа: прошлые реплики больше не учитываются."))
    messages = st.session_state.setdefault(MESSAGES, [])
    _render_settings(cfg)
    area = st.container()
    request = st.chat_input(tr("Опишите проблему или задачу — например, «нарисуй схему…»"), key="consult_field")
    with area:
        if not messages and not request:
            st.markdown(consult_empty_html(len(list_kb_documents(cfg)[0])), unsafe_allow_html=True)
        last = ""
        for msg in messages:
            if msg["role"] == "user":
                last = msg["content"]
            with st.chat_message(msg["role"]):
                if msg["role"] == "user":
                    st.markdown(msg["content"])
                else:
                    _render_answer(cfg, msg, last)
        if request:
            history = chat_history(messages, cfg.consult_history_turns, answer_chars=HISTORY_ANSWER_CHARS)
            prev = _previous_context(messages, cfg.consult_history_turns)
            messages.append({"role": "user", "content": request})
            with st.chat_message("user"):
                st.markdown(request)
            with st.chat_message("assistant"):
                with st.status(tr("Разбираю запрос: что просят и где искать…"), expanded=False) as status:
                    res = answer_consult(request, cfg, glossary=gl, history=history, prev_context=prev,
                                         progress=lambda stage, **kw: status.update(label=_status_label(stage, kw)))
                    status.update(label=tr("Готово за {s} с", s=res["seconds"]),
                                  state="error" if res["error"] else "complete")
                msg = {"role": "assistant", "content": res["answer"], "id": new_feedback_id(),
                       **{k: res[k] for k in ("shown", "kind", "queries", "aspects", "blocks", "context", "context_chars",
                                              "budget", "citations_invalid", "unsupported", "diagrams", "error",
                                              "prompts", "seconds")}}
                _render_answer(cfg, msg, request)
            messages.append(msg)

"""Интерфейс: страница целиком."""

import streamlit as st

from ..cache import _file_sig
from ..config import _load_env_files, config_file_path, env_file_candidates
from ..i18n import LANGS, default_lang, normalize_lang, set_lang, tr
from ..logs import setup_logging
from ..prompts import PROFILES, normalize_profile, set_profile, set_session_prompts
from ..services import apply_tls_policy
from ..version import MINT_VERSION
from .cards_page import OPEN as CARDS_OPEN, render_cards
from .common import _base_settings, _conn_sig, _server_info_cached
from .feedback import render_feedback_panel
from .prompts_page import OPEN as PROMPTS_OPEN, SESSION as PROMPT_SESSION, render_prompts, render_prompts_entry
from .quality import OPEN, render_quality, render_quality_entry
from .sidebar import render_glossary, render_knowledge_base, render_settings
from .tab_audit import on_profile_change, render_audit_tab
from .tab_chat import render_chat_tab
from .tab_review import render_review_tab
from .theme import inject_theme, render_header


def main():
    st.set_page_config(page_title="MINT", page_icon="🌿", layout="wide")
    inject_theme()
    _load_env_files()        # MINT_LANG из .env нужен до выбора языка
    lang = set_lang(normalize_lang(st.session_state.get("ui_lang")) or default_lang())
    set_session_prompts(st.session_state.get(PROMPT_SESSION))   # правки промптов «на время сеанса»
    base_cfg, config_notes = _base_settings(_file_sig(config_file_path(), *env_file_candidates()), lang)
    setup_logging(base_cfg)
    apply_tls_policy(base_cfg)
    if st.session_state.get("mint_profile") not in PROFILES:            # профиль сеанса: по умолчанию — config.yaml
        st.session_state["mint_profile"] = normalize_profile(base_cfg.profile)
    set_profile(st.session_state["mint_profile"])

    manual = st.session_state.setdefault("mint_manual", {})
    manual_limits = st.session_state.setdefault("mint_manual_limits", {})
    server = _server_info_cached(base_cfg.llm_base, base_cfg.embed_url, base_cfg.rerank_url,
                                 base_cfg.embed_model, base_cfg.rerank_model, _conn_sig(base_cfg), lang, base_cfg)

    with st.sidebar:
        codes = list(LANGS)
        st.selectbox("🌐 Язык / Language", options=codes, index=codes.index(lang), format_func=LANGS.get,
                     key="ui_lang", help="Интерфейс и ответы моделей / interface and model answers. "
                                         "По умолчанию / default: MINT_LANG в .env или язык системы / or the OS language.")
        # подписи — словарём на языке этого прогона: format_func могут вызвать вне потока страницы (AppTest), где язык
        # сеанса не задан
        profile_labels = {p: tr(label) for p, label in PROFILES.items()}
        st.selectbox(tr("🧭 Профиль:"), list(PROFILES), key="mint_profile", format_func=profile_labels.get,
                     on_change=lambda: on_profile_change(st.session_state["mint_profile"]),
                     help=tr("Набор промптов для чата, аудита и контроля исправлений. «Универсальный» — для любых "
                             "документов: договоров, положений, отчётов, инструкций. «Архитектура и ИТ-решения» — для "
                             "проектной документации: роли архитектурного комитета и архитектурные критерии аудита. По "
                             "умолчанию — profile в config.yaml; тексты профиля — на странице «📝 Промпты»."))
        cfg = render_settings(base_cfg, config_notes, server, manual, manual_limits)
        gl = render_glossary(cfg)
        render_quality_entry()
        render_prompts_entry()
        render_knowledge_base(cfg)
        render_feedback_panel(cfg)
        st.caption(tr("Версия MINT: {v}", v=MINT_VERSION))

    # ==========================================
    # ОСНОВНАЯ ОБЛАСТЬ
    # ==========================================
    render_header()
    if st.session_state.get(OPEN):
        render_quality(cfg)       # проверка качества занимает основную область вместо вкладок
        return
    if st.session_state.get(PROMPTS_OPEN):
        render_prompts(cfg)       # и страница промптов — тоже
        return
    if st.session_state.get(CARDS_OPEN):
        render_cards(cfg)         # и черновик карточки системы
        return

    tab1, tab2, tab3 = st.tabs([
        tr("💬 Интерактивный чат (RAG)"),
        tr("📋 Аудит документа"),
        tr("🔄 Контроль исправления замечаний"),
    ])

    with tab1:
        render_chat_tab(cfg, gl)
    with tab2:
        render_audit_tab(cfg, gl)
    with tab3:
        render_review_tab(cfg, gl)

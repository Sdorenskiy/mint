"""Интерфейс: черновик карточки системы по базе знаний (основная область вместо вкладок)."""

import re

import streamlit as st

from ..cards import CARD_SECTIONS, draft_system_card
from ..i18n import tr
from .common import btn_w

OPEN = "cards_open"             # открыта ли страница карточек вместо вкладок
RESULT = "cards_result"         # последний собранный черновик


def open_cards():
    st.session_state[OPEN] = True
    st.session_state["qa_open"] = False          # проверка качества и промпты — тоже на месте вкладок
    st.session_state["prompts_open"] = False


def close_cards():
    st.session_state[OPEN] = False


def render_cards_entry():
    """Вход на страницу — в блоке «📌 Для аудита: правила экспертов и карточки систем» боковой панели."""
    st.button(tr("🗂️ Собрать черновик карточки системы по базе"), key="cards_open_btn", on_click=open_cards, **btn_w,
              help=tr("MINT задаёт базе знаний узкие вопросы по разделам карточки и собирает черновик: у каждого "
                      "факта — источник, пробелы помечены. Черновик проверяет и дописывает эксперт."))


def _file_name(system):
    return tr("Карточка_{name}.md", name=re.sub(r'[\\/:*?"<>|\s]+', "_", system).strip("_") or "system")


def render_cards(cfg):
    """Основная область: название системы → черновик карточки по базе → скачать."""
    head, close = st.columns([0.8, 0.2])
    head.subheader(tr("🗂️ Черновик карточки системы"))
    close.button(tr("✕ Закрыть"), key="cards_close_btn", on_click=close_cards, **btn_w)
    st.caption(tr("Карточка — справка о системе для аудита: что умеет сейчас, что в планах и к какому сроку, "
                  "ограничения, как подключаются смежные системы. MINT задаёт базе знаний по вопросу на каждый "
                  "раздел ({n} вопросов) и пишет в черновик только найденное — у каждого факта ссылка на источник. "
                  "Чего в базе нет, помечено «нет в базе»: это дописывает эксперт. Сначала загрузите в базу "
                  "документацию системы и страницы вики о ней.", n=len(CARD_SECTIONS)))
    system = st.text_input(tr("Система"), key="cards_system", placeholder=tr("Например: Система А"))
    aliases = st.text_input(tr("Другие названия (через запятую, необязательно)"), key="cards_aliases",
                            help=tr("Сокращения и другие написания — попадут в строку «Названия:», по которой аудит "
                                    "узнаёт систему в документах. Найденные в базе варианты MINT добавит сам."))
    if st.button(tr("🗂️ Собрать черновик"), key="cards_run_btn", disabled=not (system or "").strip(), **btn_w):
        bar = st.progress(0.0, text=tr("Вопросы к базе по разделам карточки..."))

        def progress(done, total, entry):
            state = (tr("не получено") if entry["failed"] else
                     tr("фактов: {n}", n=len(entry["items"])) if entry["items"] else tr("нет в базе"))
            bar.progress(done / total, text=tr("«{t}» — {s}", t=entry["title"], s=state))

        try:
            st.session_state[RESULT] = draft_system_card(
                system, cfg, aliases=[a for a in (aliases or "").split(",") if a.strip()], on_progress=progress)
        except Exception as e:                   # сбой поиска или модели не роняет страницу
            st.error(tr("Черновик не собран: {e}", e=str(e)[:300]))
    res = st.session_state.get(RESULT)
    if not res:
        return
    st.markdown(tr("**Черновик карточки «{s}»:** разделов со сведениями — {f} из {n}; фактов без подтверждённого "
                   "источника — {u}; {t} с.", s=res["system"], f=res["found"], n=len(CARD_SECTIONS) - 1,
                   u=res["unconfirmed"], t=round(res["seconds"])))
    if res["gaps"]:
        st.caption(tr("Нет в базе — допишет эксперт: {v}.", v="; ".join(res["gaps"])))
    if res["failed"]:
        st.warning(tr("Модель не ответила по разделам: {v} — соберите черновик ещё раз или допишите их.",
                      v="; ".join(res["failed"])))
    st.download_button(tr("📥 Скачать черновик карточки (.md)"), data=res["markdown"], key="cards_download",
                       file_name=_file_name(res["system"]), mime="text/markdown", **btn_w)
    st.caption(tr("Дальше: проверьте каждый факт по источнику, допишите пробелы (особенно ограничения и планы со "
                  "сроками) и удалите пометку «черновик» → загрузите карточку в базу (или положите в вики и загрузите "
                  "оттуда) → отметьте её в «📌 Для аудита» → «🗂️ Карточки систем»."))
    with st.expander(tr("Черновик карточки"), expanded=True):
        st.markdown(res["markdown"])

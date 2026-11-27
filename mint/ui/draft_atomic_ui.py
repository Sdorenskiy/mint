"""Separate opt-in sample, local evidence only; no V2 session mutations."""
import json

import streamlit as st

from ..draft_atomic import (MAX_SAMPLE, atomic_diagnostics, extract_atomic_sample, prepare_atomic_sources,
                            fact_rows, fact_in_group)
from ..draft_checkpoint import _identity
from ..i18n import tr
from ..kb import list_kb_documents, source_path
from ..template_draft import DraftError
from .draft_progress_ui import render_progress
from .draft_target_ui import _wrapped, _label, _page
from .draft_review_view import update_review_selection


def _signature(cfg, sources):
    rows = []
    for name in sources:
        try:
            stat = source_path(cfg, name).stat()
            rows.append((name, stat.st_size, stat.st_mtime_ns))
        except OSError:
            rows.append((name, None, None))
    return str(cfg.kb_path), tuple(rows)


def _field_labels():
    return {
        "actor": tr("Исполнитель"), "action": tr("Действие"), "object": tr("Объект"),
        "source_party": tr("Источник данных"), "destination_party": tr("Получатель данных"),
        "data_type": tr("Категории данных"), "data_content": tr("Состав данных"),
        "interface": tr("Интерфейс"), "format": tr("Формат данных"),
        "timing": tr("Периодичность и сроки"), "condition": tr("Условия"),
        "modality": tr("Модальность исходного текста"), "constraint": tr("Ограничение"),
        "access_class": tr("Категория доступа"), "protection": tr("Безопасность"),
        "metric_subject": tr("Объект показателя"), "metric_value": tr("Значение"),
        "metric_unit": tr("Единица"),
    }


# Widget keys may disappear when a filter or page changes. Keep the selection
# in a non-widget session key, and use callbacks before the next render.
_SELECTION = "atomic_selected_ids"
_PICK_PREFIX = "atomic_pick_"


def _search_text(row):
    table = row.get("table_context") or {}
    return " ".join(" ".join(str(row.get(k, "")) for k in ("section", "text"))
                    .split()) + " " + " ".join(str(table.get(k, "")) for k in ("caption", "header"))


def _matches(row, query):
    tokens = query.casefold().split()
    text = _search_text(row).casefold()
    return all(token in text for token in tokens)


def _preview(text, query, limit=400):
    # Show context around a match instead of the identical beginnings of chunks.
    # Slicing uses the original string, not casefolded offsets (which may expand).
    import re
    hit = next((m for token in query.split()
                if (m := re.search(re.escape(token), text, re.IGNORECASE))), None)
    start = max(0, hit.start() - 100) if hit else 0
    end = min(len(text), start + limit)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def _toggle_fragment(sid, allowed):
    session = st.session_state
    previous = session.get(_SELECTION, [])
    checked = session.get(_PICK_PREFIX + sid, False)
    # Keep off-page/filtered choices; even an unexpected callback cannot exceed cap.
    updated = update_review_selection(allowed, previous, [sid], [sid] if checked else [])
    if len(updated) <= MAX_SAMPLE:
        session[_SELECTION] = updated


def _reset_sample_widgets():
    session = st.session_state
    for key in list(session):
        if key.startswith(_PICK_PREFIX) or key in (
                _SELECTION, "atomic_selection", "atomic_preview", "atomic_result_fragment",
                "atomic_query", "atomic_section_filter", "atomic_selected_only", "atomic_sample_page",
                "atomic_category", "atomic_fact_query", "atomic_fact_page", "atomic_problem_page"):
            session.pop(key, None)


def _render_sample_picker(spans):
    session = st.session_state
    allowed = list(spans)
    selected = [sid for sid in allowed if sid in session.get(_SELECTION, [])][:MAX_SAMPLE]
    session[_SELECTION] = selected
    st.subheader(tr("Фрагменты выборки"))
    st.caption(tr("Поиск выполняется по полному тексту, заголовкам разделов и шапкам таблиц."))
    query = st.text_input(tr("Поиск по тексту фрагментов"), key="atomic_query")
    sections = sorted({(row["source"], row["section"]) for row in spans.values()})
    def section_title(value):
        if value is None:
            return tr("Все разделы")
        source, section = value
        return source + " › " + (section or tr("Без заголовка"))
    section = st.selectbox(tr("Раздел"), [None, *sections], format_func=section_title,
                           key="atomic_section_filter")
    selected_only = st.checkbox(tr("Только выбранные фрагменты"), key="atomic_selected_only")
    if st.button(tr("Снять выбор всех фрагментов"), key="atomic_clear_selection",
                 disabled=not selected):
        session[_SELECTION] = []
        selected = []
    filtered = [sid for sid, row in spans.items()
                if (section is None or section == (row["source"], row["section"]))
                and (not selected_only or sid in selected)
                and _matches(row, query)]
    st.caption(tr("Найдено: {n} из {total}", n=len(filtered), total=len(spans)))
    st.caption(tr("Выбрано фрагментов: {n} из {limit}.", n=len(selected), limit=MAX_SAMPLE))
    if selected:
        st.caption(tr("Выбранные фрагменты: {ids}", ids=", ".join(selected)))
    for sid in _page(filtered, "atomic_sample_page", size=5):
        row = spans[sid]
        with st.container(border=True):
            pick_key = _PICK_PREFIX + sid
            # Restore canonical state, including when a checkbox was previously hidden.
            session[pick_key] = sid in selected
            st.checkbox(tr("Включить в выборку") + " · " + sid, key=pick_key,
                        disabled=len(selected) >= MAX_SAMPLE and sid not in selected,
                        on_change=_toggle_fragment, args=(sid, allowed))
            _wrapped(row["source"] + " › " + row["section"])
            table = row.get("table_context") or {}
            if table.get("caption"):
                _wrapped(table["caption"])
            if table.get("header"):
                _wrapped(table["header"])
            _wrapped(_preview(row["text"], query))
            with st.expander(tr("Просмотр исходного фрагмента") + " · " + sid):
                _wrapped(row["text"])
    return selected


def _result_key(cfg, signature, selected):
    return (signature, None if selected is None else tuple(sorted(selected)),
            _identity(cfg, "", "", stage="atomic_extract"), str(getattr(cfg, "llm_model", "")))


def _render_result(result):
    counts = result["counts"]
    st.subheader(tr("Реестр исходных сведений"))
    st.caption(tr("Кандидаты прошли только программную проверку. Смысловая точность и полнота требуют экспертной оценки."))
    st.text(tr("Принято кандидатов: {n}; обработано фрагментов: {done} из {total}.",
               n=counts.get("accepted", 0), done=counts.get("fragments_processed", 0),
               total=counts.get("fragments_selected", 0)))
    st.caption(tr("Без зарегистрированных ошибок: {complete}; частичные: {partial}; не обработаны: {failed}; пустые ответы: {empty}.",
                  complete=counts.get("fragments_complete", 0), partial=counts.get("partial_fragments", 0),
                  failed=counts.get("fragments_failed", 0), empty=counts.get("empty_response", 0)))
    if counts.get("metric_table_fragments") or counts.get("metric_table_fallbacks"):
        st.caption(tr("Программно извлечено строк показателей: {rows}; фрагментов таблиц: {tables}; передано модели из-за неоднозначности: {fallback}.",
                      rows=counts.get("metric_table_rows", 0), tables=counts.get("metric_table_fragments", 0),
                      fallback=counts.get("metric_table_fallbacks", 0)))
    if counts.get("source_read_errors") or counts.get("partial_fragments") or counts.get("fragments_failed"):
        st.warning(tr("Есть ограничения или ошибки разбора. Полный проход не означает полноту извлечённых сведений."))
    if result.get("scope") != "all":
        st.caption(tr("Техническая выборка, не весь документ."))
    rows = fact_rows(result)
    categories = {
        "all": tr("Все сведения"), "interactions": tr("Информационные взаимодействия"),
        "participants": tr("Участники и системы"), "data": tr("Состав и виды данных"),
        "security": tr("Категории доступа и защита"), "metrics": tr("Показатели назначения"),
        "timing": tr("Периодичность и сроки"), "actions": tr("Действия и модальность"),
        "constraints": tr("Ограничения и условия"),
    }
    totals = {g: sum(fact_in_group(fact, g) for _, fact in rows) for g in categories}
    group = st.selectbox(tr("Категория сведений"), list(categories),
                         format_func=lambda g: f"{categories[g]} ({totals[g]})", key="atomic_category")
    st.caption(tr("Одно сведение может относиться к нескольким категориям; его идентификатор сохраняется."))
    query = st.text_input(tr("Поиск по извлечённым сведениям"), key="atomic_fact_query")
    tokens = query.casefold().split()
    filtered = [(span, fact) for span, fact in rows if fact_in_group(fact, group) and
                all(t in (fact["quote"] + " " + " ".join(fact["fields"].values())).casefold() for t in tokens)]
    st.caption(tr("Найдено: {n} из {total}", n=len(filtered), total=totals[group]))
    labels = _field_labels()
    for span, fact in _page(filtered, "atomic_fact_page", size=10):
        with st.container(border=True):
            st.caption(fact["id"])
            for field, value in fact["fields"].items():
                _wrapped(labels[field] + ": " + value)
            with st.expander(tr("Просмотр исходного фрагмента") + " · " + fact["id"]):
                _wrapped(span["source"] + " › " + span["section"])
                table = span.get("table_context") or {}
                if table.get("header"):
                    _wrapped(table["header"])
                _wrapped(fact["quote"])
                st.caption(f'{span["id"]} · {fact["start"]}:{fact["end"]}')
                if span["text"] != fact["quote"]:
                    st.divider()
                    st.caption(tr("Полный контекст исходного фрагмента"))
                    _wrapped(span["text"])
    problems = [row for row in result["fragments"] if row["status"] != "processed" or not row["facts"]]
    with st.expander(tr("Диагностика фрагментов ({n})", n=len(problems))):
        st.caption(tr("Пустой ответ не доказывает отсутствие существенных сведений."))
        status_labels = {"processed": tr("Пустой ответ"), "partial": tr("Неполный результат"),
                         "invalid_payload": tr("Некорректный ответ модели")}
        for row in _page(problems, "atomic_problem_page", size=5):
            st.caption(row["id"] + " · " + (status_labels.get(row["status"]) or _label(row["status"])))
            _wrapped(row["source"] + " › " + row["section"])
            _wrapped(row["text"])
    st.caption(tr("Локальная выгрузка содержит исходные тексты. Не передавайте её за пределы контура."))
    st.download_button(tr("Скачать локальную выборку фактов"),
                       json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False),
                       file_name="mint_atomic_sample_private.json", mime="application/json", key="atomic_private")
    st.download_button(tr("Скачать обезличенные данные для анализа"),
                       json.dumps(atomic_diagnostics(result), ensure_ascii=False, indent=2, allow_nan=False),
                       file_name="mint_atomic_analysis.json", mime="application/json", key="atomic_safe")
    st.caption(tr("В диагностике нет текстов, имён файлов, названий моделей и идентификаторов источников. Проверьте файл перед передачей."))


def render_atomic_sample(cfg):
    st.subheader(tr("V3 — эксперимент извлечения фактов"))
    st.caption(tr("Выберите только исходные основания A. Вики B, поиск функций, распределение требований и Word не используются."))
    names, _ = list_kb_documents(cfg)
    sources = st.multiselect(tr("Документы-основания из вики"), names, key="atomic_sources")
    signature = _signature(cfg, sources)
    manual = st.checkbox(tr("Техническая диагностика: ручная выборка"), key="atomic_manual")
    if not manual:
        st.caption(tr("Mint автоматически обработает все фрагменты выбранных оригиналов."))
    button_label = tr("Подготовить выборку фрагментов") if manual else tr("Извлечь сведения из документов")
    if st.button(button_label, key="atomic_prepare", disabled=not sources):
        st.session_state.pop("atomic_prepared", None)
        st.session_state.pop("atomic_result", None)
        _reset_sample_widgets()
        with st.status(tr("Чтение оригиналов оснований"), expanded=False) as status:
            progress = render_progress(status)
            try:
                prepared = prepare_atomic_sources(cfg, sources, progress)
                st.session_state["atomic_prepared"] = signature, prepared
                if not manual:
                    result = extract_atomic_sample(cfg, prepared, None, progress)
                    st.session_state["atomic_result"] = _result_key(cfg, signature, None), result
            except (DraftError, OSError, ValueError, RuntimeError):
                status.update(label=tr("Не удалось обработать выборку."), state="error")
            else:
                status.update(label=tr("Выборка подготовлена") if manual else tr("Эксперимент завершён"),
                              state="complete")
    saved = st.session_state.get("atomic_prepared")
    if not saved or saved[0] != signature:
        return
    prepared = saved[1]
    for issue in prepared["issues"]:
        st.warning(issue)
    spans = prepared["spans"]
    if not spans:
        st.warning(tr("Нет доступных фрагментов для эксперимента."))
        return
    selected = None
    if manual:
        st.caption(tr("Выберите до {n} фрагментов для одинакового контрольного прогона на каждой модели.", n=MAX_SAMPLE))
        selected = _render_sample_picker(spans)
        if st.button(tr("Извлечь факты из выборки"), key="atomic_run", disabled=not selected):
            st.session_state.pop("atomic_result", None)
            with st.status(tr("Извлечение атомарных сведений"), expanded=False) as status:
                try:
                    result = extract_atomic_sample(cfg, prepared, selected, render_progress(status))
                except (DraftError, OSError, ValueError, RuntimeError):
                    status.update(label=tr("Не удалось обработать выборку."), state="error")
                else:
                    st.session_state["atomic_result"] = _result_key(cfg, signature, selected), result
                    status.update(label=tr("Эксперимент завершён"), state="complete")
    saved = st.session_state.get("atomic_result")
    if saved and saved[0] == _result_key(cfg, signature, selected):
        _render_result(saved[1])

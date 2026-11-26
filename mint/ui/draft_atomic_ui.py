"""Separate opt-in sample, local evidence only; no V2 session mutations."""
import json

import streamlit as st

from ..draft_atomic import MAX_SAMPLE, atomic_diagnostics, extract_atomic_sample, prepare_atomic_sources
from ..draft_checkpoint import _identity
from ..i18n import tr
from ..kb import list_kb_documents, source_path
from ..template_draft import DraftError
from .draft_progress_ui import render_progress
from .draft_target_ui import _wrapped, _label


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


def render_atomic_sample(cfg):
    st.subheader(tr("V3 — эксперимент извлечения фактов"))
    st.caption(tr("Выберите только исходные основания A. Вики B, поиск функций, распределение требований и Word не используются."))
    names, _ = list_kb_documents(cfg)
    sources = st.multiselect(tr("Документы-основания из вики"), names, key="atomic_sources")
    signature = _signature(cfg, sources)
    if st.button(tr("Подготовить выборку фрагментов"), key="atomic_prepare", disabled=not sources):
        st.session_state.pop("atomic_prepared", None)
        st.session_state.pop("atomic_result", None)
        for key in ("atomic_selection", "atomic_preview", "atomic_result_fragment"):
            st.session_state.pop(key, None)
        with st.status(tr("Чтение оригиналов оснований"), expanded=False) as status:
            try:
                prepared = prepare_atomic_sources(cfg, sources, render_progress(status))
            except (DraftError, OSError, ValueError, RuntimeError):
                status.update(label=tr("Не удалось подготовить выборку."), state="error")
            else:
                st.session_state["atomic_prepared"] = signature, prepared
                status.update(label=tr("Выборка подготовлена"), state="complete")
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
    st.caption(tr("Выберите до {n} фрагментов для одинакового контрольного прогона на каждой модели.", n=MAX_SAMPLE))
    def title(sid):
        row = spans[sid]
        return f"{sid} · {row['source']} › {row['section']} · {row['text'][:100]}"
    selected = st.multiselect(tr("Фрагменты выборки"), list(spans), format_func=title,
                              key="atomic_selection", max_selections=MAX_SAMPLE)
    if selected:
        sid = st.selectbox(tr("Просмотр исходного фрагмента"), selected, format_func=title,
                           key="atomic_preview")
        _wrapped(spans[sid]["text"])
        if spans[sid].get("table_context"):
            _wrapped(spans[sid]["table_context"]["header"])
    key = (signature, tuple(sorted(selected)), _identity(cfg, "", "", stage="atomic_extract"),
           str(getattr(cfg, "llm_model", "")))
    if st.button(tr("Извлечь факты из выборки"), key="atomic_run", disabled=not selected):
        st.session_state.pop("atomic_result", None)
        with st.status(tr("Извлечение атомарных сведений"), expanded=False) as status:
            try:
                result = extract_atomic_sample(cfg, prepared, selected, render_progress(status))
            except (DraftError, OSError, ValueError, RuntimeError):
                status.update(label=tr("Не удалось обработать выборку."), state="error")
            else:
                st.session_state["atomic_result"] = key, result
                status.update(label=tr("Эксперимент завершён"), state="complete")
    saved = st.session_state.get("atomic_result")
    if not saved or saved[0] != key:
        return
    result = saved[1]
    counts = result["counts"]
    st.caption(tr("Кандидаты прошли только программную проверку. Смысловая точность и полнота требуют экспертной оценки."))
    st.text(tr("Принято кандидатов: {n}; обработано фрагментов: {done} из {total}.",
               n=counts.get("accepted", 0), done=counts.get("fragments_processed", 0),
               total=counts.get("fragments_selected", 0)))
    rows = {r["id"]: r for r in result["fragments"]}
    sid = st.selectbox(tr("Результат по фрагменту"), list(rows), format_func=title, key="atomic_result_fragment")
    row = rows[sid]
    status_labels = {"processed": tr("Обработано"), "partial": tr("Неполный результат"),
                     "invalid_payload": tr("Некорректный ответ модели")}
    st.caption(status_labels.get(row["status"]) or _label(row["status"]))
    with st.expander(tr("Просмотр исходного фрагмента")):
        _wrapped(row["text"])
    if row.get("table_context"):
        _wrapped(row["table_context"]["header"])
    labels = _field_labels()
    for fact in row["facts"]:
        with st.container(border=True):
            st.caption(f'{fact["id"]} · {fact["start"]}:{fact["end"]}')
            _wrapped(fact["quote"])
            for field, value in fact["fields"].items():
                _wrapped(labels[field] + ": " + value)
    st.caption(tr("Локальная выгрузка содержит исходные тексты. Не передавайте её за пределы контура."))
    st.download_button(tr("Скачать локальную выборку фактов"),
                       json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False),
                       file_name="mint_atomic_sample_private.json", mime="application/json", key="atomic_private")
    st.download_button(tr("Скачать обезличенные данные для анализа"),
                       json.dumps(atomic_diagnostics(result), ensure_ascii=False, indent=2, allow_nan=False),
                       file_name="mint_atomic_analysis.json", mime="application/json", key="atomic_safe")
    st.caption(tr("В диагностике нет текстов, имён файлов, названий моделей и идентификаторов источников. Проверьте файл перед передачей."))

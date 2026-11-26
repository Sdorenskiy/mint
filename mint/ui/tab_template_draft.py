"""Document drafting tab."""
import hashlib
import json

import streamlit as st

from ..i18n import tr
from ..draft_registry import SOURCE_ROLES
from ..draft_pilot_report import diagnostic_package
from ..draft_section_pilot import create_section_pilot, pilot_section_options
from ..kb import list_kb_documents, source_path
from ..template_draft import DraftError, create_draft
from .draft_review_ui import render_draft_reviews
from .draft_pilot_report_ui import render_pilot_report
from .document_edit_chat import render_draft_edit_chat
from .draft_context_ui import render_draft_context
from .draft_traceability_ui import render_draft_traceability
from .draft_wizard_ui import render_draft_wizard
from .draft_atomic_ui import render_atomic_sample
from .draft_progress_ui import render_progress


def render_template_draft_tab(cfg, glossary):
    with st.expander(tr("Расширенные настройки")):
        engines = {"v2": tr("V2 — экспериментальный"), "legacy": tr("Прежний генератор (временно)"),
                   "v3_sample": tr("V3 — эксперимент извлечения фактов")}
        engine = st.radio(tr("Режим формирования"), list(engines), horizontal=True,
                          key="draft_engine", format_func=engines.__getitem__)
        pilot = engine == "v2"
        registry_only = pilot and st.checkbox(tr("Сначала проверить реестр требований (без Word)"),
                                              value=True, key="draft_registry_only")
        reset_extract_cache = st.checkbox(tr("Повторно разобрать основания (не использовать сохранённые результаты)"),
                                         value=False, key="draft_reset_extract")
        if "target_expert_review" not in st.session_state:
            st.session_state["target_expert_review"] = True
        expert = st.checkbox(tr("Согласование требований перед декомпозицией"),
                             key="target_expert_review", disabled=not registry_only)
    if engine == "v3_sample":
        render_atomic_sample(cfg)
        return
    if registry_only:
        render_draft_wizard(cfg, expert=expert, reset_cache=reset_extract_cache)
        return
    st.caption(tr("Выберите утверждённые основания из базы знаний и загрузите файл Word."))
    mode_labels = {False: tr("Шаблон с подсказками"), True: tr("Документ-образец")}
    example = False if pilot else st.radio(
        tr("Что загружаете"), [False, True], horizontal=True, key="draft_mode",
        format_func=mode_labels.__getitem__)
    template = st.file_uploader(tr("Файл Word"), type=["docx"], key="draft_template")
    names, _ = list_kb_documents(cfg)
    sources = st.multiselect(tr("Документы-основания из вики"), names, key="draft_sources")
    missing = [name for name in sources if not source_path(cfg, name).is_file()]
    if missing:
        st.warning(tr("Для этих оснований нет оригиналов: {names}", names=", ".join(missing)))
    raw = template.getvalue() if template else b""

    roles = {}
    section_index = None
    if pilot:
        if not registry_only:
            st.caption(tr("V2 формирует один выбранный раздел. Результат требует экспертной проверки."))
        role_labels = {"need": tr("Исходные требования"), "architecture": tr("Описание решения"),
                       "normative": tr("Нормативные документы"), "mixed": tr("Смешанное содержание"),
                       "unspecified": tr("Роль не определена")}
        with st.expander(tr("Роли документов-оснований"), expanded=False):
            for name in sources:
                roles[name] = st.selectbox(
                    name, sorted(SOURCE_ROLES, key=lambda role: (role != "unspecified", role)),
                    format_func=role_labels.__getitem__,
                    key="draft_pilot_role_" + hashlib.sha256(name.encode("utf-8")).hexdigest())
        if not registry_only:
            options = []
            if raw:
                try:
                    options = pilot_section_options(raw)
                except DraftError as exc:
                    st.warning(str(exc))
            sections = [row for row in options if row["status"] in {"empty", "instruction"}]
            status_labels = {
                "empty": tr("Пустой раздел"),
                "instruction": tr("Раздел с подсказками"),
                "fixed_content": tr("Содержит обычный текст или неоднозначную подсказку"),
                "protected": tr("Защищённый заголовок или сложные элементы Word"),
            }
            if sections:
                labels = {row["index"]: f'{row["title"]} — {status_labels[row["status"]]}' for row in sections}
                section_index = st.selectbox(
                    tr("Раздел для формирования"), list(labels), index=None,
                    format_func=labels.__getitem__,
                    key="draft_pilot_section_" + hashlib.sha256(raw).hexdigest())
                if section_index is not None:
                    selected = next(row for row in sections if row["index"] == section_index)
                    if selected["status"] == "instruction":
                        st.caption(tr("Подсказки и явные примеры заменяются только после успешной проверки результата."))
            elif raw:
                st.warning(tr("Нет разделов, безопасных для формирования V2."))
            if options:
                with st.expander(tr("Распознанные разделы и причины ограничений"), expanded=False):
                    for row in options:
                        st.text(f'{row["title"]} — {status_labels[row["status"]]}')
            elif raw:
                st.caption(tr("Заголовки разделов не распознаны. Проверьте структуру Word."))

    def input_key():
        versions = []
        for name in sources:
            try:
                stamp = source_path(cfg, name).stat()
                versions.append((name, stamp.st_size, stamp.st_mtime_ns))
            except OSError:
                versions.append((name, None, None))
        return (str(cfg.kb_path), example, hashlib.sha256(raw).hexdigest(), tuple(versions))

    base_key = input_key()
    context = render_draft_context(cfg, raw, sources if not missing else [], base_key)
    key = (base_key, tuple(sorted(context.items())) if context else None,
           engine, section_index, tuple(sorted(roles.items())))
    if st.button(tr("Собрать черновик Word"), disabled=not (raw and sources and context) or bool(missing) or (pilot and section_index is None), key="draft_start"):
        st.session_state.pop("draft_result", None)
        with st.status(tr("Готовим черновик"), expanded=False) as status:
            progress = render_progress(status)
            try:
                if pilot:
                    result = create_section_pilot(
                        raw, cfg, sources, roles, context, section_index, progress,
                        reset_extract_cache=reset_extract_cache)
                else:
                    result = create_draft(raw, cfg, sources, glossary, progress, example=example,
                                          reset_extract_cache=reset_extract_cache, context=context)
                if input_key() != base_key:
                    raise DraftError(tr("Одно из оснований изменилось. Запустите сборку заново."))
            except DraftError as exc:
                status.update(label=str(exc), state="error")
            except (OSError, ValueError, KeyError, RuntimeError):
                status.update(label=tr("Не удалось обработать файл Word или собрать черновик."), state="error")
            else:
                st.session_state["draft_result"] = key, result
                status.update(label=tr("Черновик собран"), state="complete")

    saved = st.session_state.get("draft_result")
    if not saved or saved[0] != key:
        render_draft_reviews(cfg)
        return
    result = saved[1]
    st.subheader(tr("Результаты формирования"))
    if pilot:
        if result["pilot_status"] == "empty_draft":
            st.error(tr("Ни одно предложение не прошло проверку для выбранного раздела."))
        else:
            st.caption(tr("Черновик V2 не согласован. Полнота извлечения не доказана."))
        edited_docx = result["docx"]
    else:
        edited_docx = render_draft_edit_chat(cfg, key, result)
    metrics = result.get("metrics", {})
    st.caption(tr("Сформировано полей: {fields}; связано исходных записей: {used} из {total}; замечаний: {issues}.",
                  fields=len(result["results"]), used=len(result["used"]),
                  total=len(result["requirements"]), issues=len(result["issues"])))
    if metrics:
        st.caption(tr("Время формирования: {seconds} с", seconds=round(metrics.get("total_seconds", 0))))
    word_col, diagnostic_col = st.columns(2)
    word_col.download_button(tr("Скачать черновик Word"), edited_docx, file_name="MINT_draft.docx",
                             mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                             key="draft_download")
    # Reserve the download position above expert details; fill it after review
    # controls have run so saving marks takes effect in the same script rerun.
    download = diagnostic_col.empty()
    if result["issues"]:
        with st.expander(tr("Замечания формирования ({n})", n=len(result["issues"]))):
            for issue in result["issues"]:
                st.text(issue)
    if metrics:
        with st.expander(tr("Замеры этапов подготовки")):
            for stage, item in metrics.get("stages", {}).items():
                stage_labels = {"layout": tr("Разбор шаблона"), "extract": tr("Разбор оснований"),
                                "rows": tr("Подготовка таблиц"), "fill": tr("Заполнение и сверка с вики"),
                                "check": tr("Сверка требований шаблона"),
                                "registry_type": tr("Типизация исходных сведений"),
                                "function_group": tr("Группировка функций"),
                                "function_allocation": tr("Распределение ответственности"),
                                "requirement_derivation": tr("Детализация требований"),
                                "requirement_assessment": tr("Проверка обоснованности"),
                                "pilot_coverage": tr("Проверка полноты раздела")}
                st.text(f"{stage_labels.get(stage, stage)}: "
                        + tr("{n} запросов к LLM, {s} с", n=item["llm_calls"], s=item["llm_seconds"]))
    if pilot:
        render_pilot_report(result)
    render_draft_traceability(result, sources, key, allow_edit=not pilot)
    review = render_draft_reviews(cfg, key, template.name if template else "", sources, result)
    package = diagnostic_package(result, pilot=pilot, input_key=key, review=review)
    download.download_button(tr("Скачать обезличенные данные для анализа"),
                             json.dumps(package, ensure_ascii=False, indent=2, allow_nan=False),
                             file_name="mint_draft_analysis.json", mime="application/json",
                             key="draft_analysis_export")
    st.caption(tr("В диагностике нет текстов, имён файлов, названий моделей и идентификаторов источников. Проверьте файл перед передачей."))
    if package["expert_review"] is None:
        st.caption(tr("Экспертная оценка текущего прогона не сохранена; выгружаются только автоматические показатели."))
    if pilot:
        return
    section_plan = result.get("section_plan", {})
    if section_plan:
        with st.expander(tr("План требований по разделам")):
            for section, summary in section_plan.items():
                st.text(f"{section}: " + tr("{selected} требований для {fields} полей из {total}",
                                            selected=len(summary["selected_ids"]), fields=summary["fields"],
                                            total=summary["total_requirements"]))
    unresolved = {section: ids for section, ids in result.get("unresolved_candidates", {}).items() if ids}
    if unresolved:
        with st.expander(tr("Кандидаты требований, не отражённые в черновике — проверить применимость")):
            requirements = {item["id"]: item for item in result["requirements"]}
            for section, ids in unresolved.items():
                st.markdown(f"**{section}**")
                for rid in ids:
                    item = requirements.get(rid)
                    if item:
                        st.text(f"{rid}: {item['source']} › {item['section']} — {item['quote']}")
    scope_counts = result.get("scope_counts", {})
    if scope_counts:
        st.caption(tr("Применимость: целевая система — {target}, общие — {shared}, "
                      "взаимодействия — {interaction}, другие системы — {other}, неясные — {uncertain}.",
                      **scope_counts))
    if result.get("removed_examples"):
        st.caption(tr("Удалено блоков с примерами: {n}.", n=result["removed_examples"]))
    statuses = {"checked": tr("Проверено по найденной норме"), "conflict": tr("Противоречие с вики"),
                "basis_conflict": tr("Противоречие в основаниях"), "uncertain": tr("Проверить применимость нормы"),
                "unchecked": tr("Проверка по вики не завершена"), "missing": tr("Требуется уточнение"),
                "manual": tr("Требуется ручная вставка")}
    refs = {item["id"]: item for item in result["requirements"]}
    for item in result["results"]:
        label = tr("Предложение V2 — проверить экспертом") if pilot else statuses[item["status"]]
        with st.expander(f"{label} · {item['field']}"):
            if item["text"]:
                st.text(item["text"])
            if item["detail"]:
                st.text(item["detail"])
            if item.get("unconfirmed_coverage"):
                st.caption(tr("Вставка не подтверждает перенос пунктов: {ids}. Проверьте текст.",
                              ids=", ".join(item["unconfirmed_coverage"])))
            for key in item["refs"]:
                source = refs[key]
                st.text(f"{key} · {source['source']} › {source['section']}\n{source['quote']}")
    with st.expander(tr("Требования и источники")):
        for item in result["requirements"]:
            if pilot and item["id"] in result["used"]:
                state = tr("Связано с текстом")
            else:
                state = tr("Перенесено") if item["id"] in result["used"] else tr("Требует разбора")
            st.text(f"{item['id']} · {state} · {item['source']} › {item['section']}\n{item['quote']}")


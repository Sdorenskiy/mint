"""Document drafting tab."""
import hashlib
import time

import streamlit as st

from ..i18n import tr
from ..kb import list_kb_documents, source_path
from ..template_draft import DraftError, create_draft


def render_template_draft_tab(cfg, glossary):
    st.caption(tr("Выберите утверждённые основания из базы знаний и загрузите файл Word."))
    mode_labels = {False: tr("Шаблон с подсказками"), True: tr("Документ-образец")}
    example = st.radio(tr("Что загружаете"), [False, True], horizontal=True, key="draft_mode",
                       format_func=mode_labels.__getitem__)
    template = st.file_uploader(tr("Файл Word"), type=["docx"], key="draft_template")
    names, _ = list_kb_documents(cfg)
    sources = st.multiselect(tr("Документы-основания из вики"), names, key="draft_sources")
    missing = [name for name in sources if not source_path(cfg, name).is_file()]
    if missing:
        st.warning(tr("Для этих оснований нет оригиналов: {names}", names=", ".join(missing)))
    reset_extract_cache = st.checkbox(tr("Повторно разобрать основания (не использовать сохранённые результаты)"),
                                     value=False, key="draft_reset_extract")
    raw = template.getvalue() if template else b""

    def input_key():
        versions = []
        for name in sources:
            try:
                stamp = source_path(cfg, name).stat()
                versions.append((name, stamp.st_size, stamp.st_mtime_ns))
            except OSError:
                versions.append((name, None, None))
        return (str(cfg.kb_path), example, hashlib.sha256(raw).hexdigest(), tuple(versions))

    key = input_key()
    if st.button(tr("Собрать черновик Word"), disabled=not (raw and sources) or bool(missing), key="draft_start"):
        st.session_state.pop("draft_result", None)
        with st.status(tr("Готовим черновик"), expanded=True) as status:
            extraction = {"total": 0, "cached": 0, "durations": [], "started": None, "hit": False}
            stages = {"layout": tr("Разбор шаблона"), "extract": tr("Разбор оснований"),
                      "table": tr("Подготовка таблиц"), "fill": tr("Заполнение и сверка с вики"),
                      "fixed": tr("Сверка требований шаблона")}

            def progress(stage, index):
                if stage == "extract_total":
                    extraction["total"] = index
                    return
                if stage == "extract":
                    extraction["started"] = time.monotonic()
                    extraction["hit"] = False
                elif stage == "extract_cached":
                    extraction["cached"] = index
                    extraction["hit"] = True
                    return
                elif stage == "extract_done":
                    if extraction["started"] is not None and not extraction["hit"]:
                        extraction["durations"].append(time.monotonic() - extraction["started"])
                    extraction["started"] = None
                else:
                    status.update(label=f"{stages[stage]} · {index}")
                    return

                total = extraction["total"]
                label = f"{stages['extract']} · {index} / {total}" if total else f"{stages['extract']} · {index}"
                if extraction["cached"]:
                    label += " · " + tr("Из кэша") + f": {extraction['cached']}"
                durations = extraction["durations"]
                if total > index and len(durations) >= 3:
                    remaining_minutes = round((total - index) * (sum(durations) / len(durations)) / 60)
                    label += " · " + tr("Осталось примерно {minutes} мин", minutes=remaining_minutes)
                status.update(label=label)

            try:
                result = create_draft(raw, cfg, sources, glossary, progress, example=example,
                                      reset_extract_cache=reset_extract_cache)
                if input_key() != key:
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
        return
    result = saved[1]
    st.download_button(tr("Скачать черновик Word"), result["docx"], file_name="MINT_draft.docx",
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                       key="draft_download")
    for issue in result["issues"]:
        st.warning(issue)
    st.caption(tr("Перенесено извлечённых пунктов: {used} из {total}. Прочитано фрагментов оснований: {chunks}.",
                  used=len(result["used"]), total=len(result["requirements"]), chunks=result["chunks"]))
    metrics = result.get("metrics", {})
    if metrics:
        st.caption(tr("Время формирования: {seconds} с", seconds=metrics.get("total_seconds", 0)))
        with st.expander(tr("Замеры этапов подготовки")):
            stage_labels = {"layout": tr("Разбор шаблона"), "extract": tr("Разбор оснований"),
                            "rows": tr("Подготовка таблиц"), "fill": tr("Заполнение и сверка с вики"),
                            "check": tr("Сверка требований шаблона")}
            for stage, item in metrics.get("stages", {}).items():
                st.text(f"{stage_labels.get(stage, stage)}: "
                        + tr("{n} запросов к LLM, {s} с", n=item["llm_calls"], s=item["llm_seconds"]))
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
    if result["removed_examples"]:
        st.caption(tr("Удалено блоков с примерами: {n}.", n=result["removed_examples"]))
    statuses = {"checked": tr("Проверено по найденной норме"), "conflict": tr("Противоречие с вики"),
                "basis_conflict": tr("Противоречие в основаниях"), "uncertain": tr("Проверить применимость нормы"),
                "unchecked": tr("Проверка по вики не завершена"), "missing": tr("Требуется уточнение"),
                "manual": tr("Требуется ручная вставка")}
    refs = {item["id"]: item for item in result["requirements"]}
    for item in result["results"]:
        with st.expander(f"{statuses[item['status']]} · {item['field']}"):
            if item["text"]:
                st.text(item["text"])
            if item["detail"]:
                st.text(item["detail"])
            for key in item["refs"]:
                source = refs[key]
                st.text(f"{key} · {source['source']} › {source['section']}\n{source['quote']}")
    with st.expander(tr("Требования и источники")):
        for item in result["requirements"]:
            state = tr("Перенесено") if item["id"] in result["used"] else tr("Требует разбора")
            st.text(f"{item['id']} · {state} · {item['source']} › {item['section']}\n{item['quote']}")

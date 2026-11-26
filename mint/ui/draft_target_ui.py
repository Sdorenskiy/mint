"""Local STOP-1 review and explicit private registry export."""
import json
from collections import Counter

import streamlit as st

from ..draft_target_analysis import (prepare_target_analysis, collect_target_requirements,
                                     decompose_target_requirements, extend_function_preview)
from ..draft_target_review import MAX_NOTE
from ..draft_pilot_report import target_registry_export
from ..draft_registry_workbook import registry_workbook, regression_snapshot, compare_registries
from ..i18n import tr
from .draft_progress_ui import render_progress
from .draft_wizard_state import sync_target
from ..template_draft import DraftError

def _label(code):
    labels = {
        "model_supported": tr("Поддержано моделью"),
        "applicability_supported": tr("Ответственность подтверждена моделью"),
        "implementation_unknown": tr("Необходимость доработки не установлена"),
        "model_covered": tr("Перенос подтверждён моделью"),
        "awaiting_decomposition": tr("Ожидает детализации"),
        "expert_excluded": tr("Исключено экспертом"),
        "already_supported": tr("Уже реализовано"),
        "external": tr("Другой участник"),
        "context_only": tr("Справочное сведение"),
        "coverage_gap": tr("Не отражено в требованиях"),
        "open_question": tr("Открытый вопрос"),
        "needs_review": tr("Требует экспертной проверки"),
        "reference_unresolved": tr("Не разрешена ссылка"),
        "missing_evidence": tr("Не хватает оснований"),
        "missing_metric_evidence": tr("Не хватает данных о показателе"),
        "wrong_actor": tr("Неверный исполнитель"),
        "batch_error": tr("Ошибка обработки"),
        "invalid_response": tr("Некорректный ответ модели"),
        "missing_response": tr("Нет ответа модели"),
        "duplicate_response": tr("Повтор ответа модели"),
        "review_error": tr("Ошибка проверки"),
        "allocation_context_limit": tr("Ограничение контекста распределения"),
        "group_context_limit": tr("Ограничение контекста детализации"),
        "review_context_limit": tr("Ограничение контекста проверки"),
        "untyped": tr("Тип не определён"),
        "unknown": tr("Не определено"),
        "explicit": tr("Прямое требование"),
        "new": tr("Новая функция"),
        "change": tr("Изменение"),
        "need": tr("Исходные требования"),
        "interface": tr("Интерфейс"),
        "metric": tr("Показатель назначения"),
        "architecture": tr("Описание решения"),
        "constraint": tr("Ограничение"),
        "business": tr("Бизнес-контекст"),
        "reference": tr("Справочное сведение"),
        "functional": tr("Функциональное требование"),
        "found": tr("Найдено"),
        "found_partial": tr("Найдено частично"),
        "not_found": tr("Не найдено"),
        "not_searched": tr("Не проверено"),
        "context_limit": tr("Ограничение контекста"),
        "error": tr("Ошибка обработки"),
        "purpose": tr("Назначение"),
        "participants": tr("Участники"),
        "direction": tr("Направление обмена"),
        "data_categories": tr("Категории данных"),
        "data_content": tr("Состав данных"),
        "data_format": tr("Формат данных"),
        "trigger": tr("Условия запуска"),
        "timing": tr("Периодичность и сроки"),
        "performance": tr("Производительность"),
        "capacity": tr("Ёмкость и нагрузка"),
        "security": tr("Безопасность"),
        "data_constraints": tr("Ограничения данных"),
        "reliability": tr("Надёжность"),
        "operations": tr("Эксплуатация"),
    }
    return labels.get(code, tr("Требует разбора"))


def _show_refs(refs, prepared, result):
    for rid in refs:
        row = result["requirements"].get(rid) or result["state_evidence"].get(rid)
        if row:
            st.caption(f"{rid} · {row['source']} › {row['section']}")
            if row.get("source_role") == "reference_context":
                st.caption(tr("Справочный контекст — не основание требования"))
            if row.get("table_context"):
                st.caption(row["table_context"].get("caption", ""))
                st.text(row["table_context"]["header"])
            st.text(row["quote"])
        elif rid in prepared["spans"]:
            row = prepared["spans"][rid]
            st.caption(f"{rid} · {row['source']} › {row['section']}")
            if row.get("table_context"):
                st.caption(row["table_context"].get("caption", ""))
                st.text(row["table_context"]["header"])
            st.text(row["text"])


def _review_collection(collected, prepared, expert):
    """Review individual original obligations, grouped by primary allocation."""
    run = collected["metrics"]["run_id"]
    decisions, records = collected["decisions"], collected["requirements"]
    selected, notes = [], {}
    session = st.session_state
    draft = session.get("target_registry_review_draft")
    if not draft or draft["run"] != run:
        draft = {"run": run, "selected": {}, "notes": {}}
        session["target_registry_review_draft"] = draft
    st.subheader(tr("Собранные требования по функциям"))
    st.caption(tr("Проверьте исходные требования и выберите те, которые нужно детализировать. Функция объединяет требования, но не заменяет их."))
    candidates = len({rid for group in collected["groups"] for rid in group["requirement_ids"]
                      if decisions[rid]["change"] != "already_supported"})
    profile_names = {p["id"]: p["name"] for p in collected.get("approved_profile", [])}
    st.caption(tr("Функций: {n}; исходных потребностей для детализации: {count}.", n=len(collected["groups"]), count=candidates))
    primary_names = {g["function"] for g in collected["groups"]}
    for group in collected["groups"]:
        gid = group["id"]
        ids = [rid for rid in group["requirement_ids"] if decisions[rid]["change"] != "already_supported"]
        with st.expander(f"{group['function']} · {len(ids)}", expanded=len(collected["groups"]) == 1):
            if st.checkbox(tr("Показать исходные требования"), key=f"target_review_quotes_{run}_{gid}"):
                for rid in _page(group["requirement_ids"], f"target_review_quotes_page_{run}_{gid}"):
                    d = decisions[rid]
                    st.caption(_label(d["change"]))
                    if d.get("status") == "applicability_supported":
                        st.caption(tr("Ответственность подтверждена моделью; необходимость доработки не установлена."))
                    _show_refs([rid], prepared, collected)
                    names = [profile_names[pid] for pid in collected.get("function_links", {}).get(rid, [])
                             if pid in profile_names and profile_names[pid] != group["function"]]
                    if names:
                        st.caption(tr("Возможная связь с другими функциями: {names}", names=", ".join(names)))
            if expert:
                scope_key = f"target_review_scope_{run}_{gid}"
                note_key = f"target_review_note_{run}_{gid}"
                if scope_key not in session:
                    chosen_functions = collected.get("selected_functions")
                    defaults = ids
                    if chosen_functions is not None:
                        # Non-functional, constraint and unlinked obligations remain
                        # visible; do not silently select a newly suggested function.
                        defaults = [rid for rid in ids if records[rid].get("kind") in {"nonfunctional", "constraint"}
                                    or (set(collected.get("function_links", {}).get(rid, [])) & set(chosen_functions))
                                    or (not collected.get("function_links", {}).get(rid)
                                        and decisions[rid].get("function") != "new")]
                    session[scope_key] = draft["selected"].get(gid, defaults)
                if note_key not in session:
                    session[note_key] = draft["notes"].get(gid, "")
                chosen = st.multiselect(tr("Включить требования в детализацию"),
                                        ids, format_func=lambda rid: records[rid]["quote"][:180],
                                        key=scope_key)
                selected.extend(chosen)
                note = st.text_area(tr("Уточнение эксперта (не источник)"), max_chars=MAX_NOTE,
                                    key=note_key, disabled=not chosen)
                draft["selected"][gid] = list(chosen)
                draft["notes"][gid] = note
                if chosen and note.strip():
                    notes[gid] = note.strip()
            show = st.checkbox(tr("Показать связанные пункты и сведения о реализации"), key=f"target_review_refs_{run}_{gid}")
            if show:
                for rid in _page(group["requirement_ids"], f"target_review_refs_page_{run}_{gid}"):
                    d = decisions[rid]
                    st.caption(f"{rid} · {_label(d['change'])} · {_label(d['status'])}")
                    refs = list(dict.fromkeys(d.get("state_refs", []) + d.get("reference_refs", []) + d.get("dossier_refs", [])))
                    _show_refs([r for r in refs if r != rid], prepared, collected)
                    related = collected.get("linked_by_need", {}).get(rid, {})
                    for item in related.get("items", []):
                        st.caption(f"{item['source']} › {item['section']} · {item['reference']}")
                        st.text(item["quote"])
                    if related.get("gaps"):
                        st.warning(tr("Некоторые перекрёстные ссылки не удалось раскрыть."))
            for rid in group["requirement_ids"]:
                metric = collected["metrics_registry"].get(rid)
                if metric:
                    st.text(f"{rid} · {metric['subject']} · {metric['value']} {metric['unit']} · {metric['level']}")
                    st.text(metric["conditions"])
    # Show candidate-only associations even when no allocation could be verified.
    # A shared record remains one selectable obligation in its primary group.
    candidate_only = [p for p in collected.get("approved_profile", []) if p["name"] not in primary_names]
    for p in candidate_only:
        related = [rid for rid, ids in collected.get("function_links", {}).items() if p["id"] in ids]
        with st.expander(p["name"] + " · " + tr("Требует экспертной проверки")):
            st.caption(tr("Связанных записей: {n}", n=len(related)))
            if st.checkbox(tr("Показать исходные требования"), key=f"target_candidate_show_{run}_{p['id']}"):
                for rid in _page(related, f"target_candidate_{run}_{p['id']}"):
                    _show_refs([rid], prepared, collected)
    technical = {"invalid_response", "missing_response", "duplicate_response", "batch_error",
                 "review_error", "allocation_context_limit", "review_context_limit"}
    technical_count = sum(d["status"] in technical for d in decisions.values())
    pending_owner = sum(d["status"] == "applicability_supported" for d in decisions.values())
    unresolved = [rid for rid, d in decisions.items() if d["status"] != "model_supported"]
    if unresolved:
        st.warning(tr("Исходных требований, требующих дополнительного разбора: {n}. Они сохранены в реестре.", n=len(unresolved)))
        st.caption(tr("Технические сбои: {technical}; ответственность подтверждена, доработка не доказана: {pending}.",
                      technical=technical_count, pending=pending_owner))
        for code, count in Counter(decisions[rid]["status"] for rid in unresolved).most_common():
            st.caption(f"{_label(code)}: {count}")
        if st.checkbox(tr("Показать исходные требования"), key=f"target_unresolved_show_{run}"):
            codes = sorted({decisions[rid]["status"] for rid in unresolved})
            code = st.selectbox(tr("Причина"), codes, format_func=_label, key=f"target_unresolved_filter_{run}")
            for rid in _page([rid for rid in unresolved if decisions[rid]["status"] == code],
                             f"target_review_unresolved_{run}"):
                _show_refs([rid], prepared, collected)
    if expert:
        st.caption(tr("Выбрано {n} из {total} требований. Исключённые записи остаются в реестре.",
                      n=len(selected), total=candidates))
    return selected, notes


def _prepare(cfg, session, sources, roles, context, reference_sources=()):
    with st.status(tr("Подготовка оснований"), expanded=False) as status:
        try:
            prepared = prepare_target_analysis(cfg, sources, roles, context, render_progress(status),
                                               reference_sources=reference_sources, discover_profile=False)
        except (DraftError, OSError, ValueError, KeyError, RuntimeError):
            status.update(label=tr("Не удалось подготовить исходные материалы."), state="error")
            return None
        session["target_registry_prepared"] = prepared
        status.update(label=tr("Основания подготовлены"), state="complete")
        return prepared


def _decompose(cfg, session, prepared, identity, collected, selection=None, notes=None):
    session.pop("target_registry_result", None)
    session.pop("target_full_workbook", None)
    with st.status(tr("Детализация требований"), expanded=False) as status:
        try:
            result = decompose_target_requirements(cfg, prepared, collected, render_progress(status),
                                                   selection=selection, notes=notes)
        except (DraftError, OSError, ValueError, KeyError, RuntimeError):
            status.update(label=tr("Не удалось сформировать реестр требований."), state="error")
            return False
        session["target_registry_result"] = identity, result
        status.update(label=tr("Реестр подготовлен"), state="complete")
        return True


def _select_functions(preview):
    """Compact user checkpoint; hypotheses do not decide which quotes survive."""
    st.subheader(tr("Выберите функции для дальнейшего анализа"))
    st.caption(tr("Выбор ограничивает углублённый поиск. Все исходные требования сохраняются; применимость пока предварительная."))
    profile = {p["id"]: p for p in preview["approved_profile"]}
    records = preview["requirements"]
    applicability = preview["applicability"]
    links = preview["function_links"]
    run = preview["metrics"]["run_id"]
    draft = st.session_state.get("target_registry_profile_draft")
    if not draft or draft["run"] != run:
        draft = {"run": run, "selected": []}
        st.session_state["target_registry_profile_draft"] = draft
    labels = {"target": tr("Целевая система"), "shared": tr("Совместная ответственность"),
              "interaction": tr("Внешнее взаимодействие"), "other": tr("Другой участник"),
              "uncertain": tr("Не определено")}
    counts = Counter(a["category"] for a in applicability.values())
    st.caption(" · ".join(f"{labels.get(code, code)}: {counts[code]}" for code in labels))
    selected = []
    for pid, p in profile.items():
        ids = [rid for rid in applicability if pid in links.get(rid, [])]
        key = f"target_function_pick_{run}_{pid}"
        if key not in st.session_state:
            st.session_state[key] = pid in draft["selected"]
        if st.checkbox(f"{p['name']} · {len(ids)}", key=key):
            selected.append(pid)
    draft["selected"] = selected
    cross = [rid for rid in applicability if records[rid].get("kind") in {"nonfunctional", "constraint"}]
    unlinked = [rid for rid in applicability if not links.get(rid)]
    st.caption(tr("Сквозные требования и ограничения: {n}; не распределено по функциям: {m}. Они остаются на контроле.",
                  n=len(cross), m=len(unlinked)))
    profile_status = preview.get("profile_status", {})
    if any(profile_status.get(code) for code in ("model_error", "invalid_response", "partial")):
        st.warning(tr("Часть функций не удалось определить: ошибка модели или формата ответа."))
    if profile_status.get("context_limit"):
        st.warning(tr("Выявление функций ограничено контекстом; проверьте также нераспределённые требования."))
    if st.checkbox(tr("Показать исходные требования"), key=f"target_preview_show_{run}"):
        options = ["all", "cross", "unlinked", *profile]
        names = {"all": tr("Все требования"), "cross": tr("Сквозные требования"),
                 "unlinked": tr("Не распределено по функциям")}
        which = st.selectbox(tr("Функция"), options,
                             format_func=lambda pid: names.get(pid, profile.get(pid, {}).get("name", pid)),
                             key=f"target_preview_filter_{run}")
        ids = (list(applicability) if which == "all" else cross if which == "cross" else unlinked
               if which == "unlinked" else [rid for rid in applicability if which in links.get(rid, [])])
        for rid in _page(ids, f"target_preview_page_{run}"):
            a = applicability[rid]
            st.caption(f"{labels.get(a['category'], a['category'])} · {a['actor']} · {a['reason']}")
            _show_refs([rid], {}, {"requirements": records, "state_evidence": {}})
    return selected


def render_target_registry(cfg, key, sources, roles, context, enabled, reset_cache, *, step, expert, advance, reference_sources=()):
    """Render the active stage only. Navigation never starts an LLM operation."""
    session = st.session_state
    sync_target(session, key)
    prepared = session.get("target_registry_prepared")
    if step == 2:
        st.subheader(tr("Сбор исходных требований"))
        st.caption(tr("Сначала MINT разбирает все основания и определяет функции и предварительную применимость. Затем вы выбираете область углублённого поиска."))
        preview = session.get("target_registry_preview")
        if preview is None:
            if not st.button(tr("Собрать исходные требования"), key="target_analyze", type="primary", disabled=not enabled):
                return
            if prepared is None:
                prepared = _prepare(cfg, session, sources, roles, context, reference_sources)
            if prepared is None:
                return
            with st.status(tr("Сбор исходных требований"), expanded=False) as status:
                try:
                    preview = collect_target_requirements(cfg, prepared, None, render_progress(status),
                                                          reset_cache=reset_cache, summaries=False, preview_only=True)
                except DraftError as exc:
                    status.update(label=tr("Не удалось собрать исходные требования."), state="error")
                    st.error(str(exc))
                    return
                except (OSError, ValueError, KeyError, RuntimeError):
                    status.update(label=tr("Не удалось собрать исходные требования."), state="error")
                    return
                session["target_registry_preview"] = preview
                status.update(label=tr("Исходные требования собраны"), state="complete")
            st.rerun()
            return
        with st.expander(tr("Расширенные действия")):
            if st.button(tr("Повторно собрать требования"), key="target_collect_again"):
                for name in ("target_registry_preview", "target_registry_prepared", "target_registry_collected",
                             "target_registry_result", "target_full_workbook", "target_registry_review_draft",
                             "target_registry_profile_draft"):
                    session.pop(name, None)
                st.rerun()
                return
        failed = [location for location, code in preview.get("fragment_status", {}).items()
                  if code in {"failed", "invalid_quote"}]
        if failed:
            st.warning(tr("Разбор неполный: {n} фрагментов требуют повторной обработки.", n=len(failed)))
            with st.expander(tr("Необработанные фрагменты")):
                for source, number in _page(failed, "target_failed_fragments"):
                    st.text(f"{source} · {number}")
            if st.button(tr("Повторить неполный разбор"), key="target_retry_partial"):
                with st.status(tr("Сбор исходных требований"), expanded=False) as status:
                    try:
                        refreshed = collect_target_requirements(cfg, prepared, None, render_progress(status),
                            reset_cache=False, summaries=False, preview_only=True)
                    except (DraftError, OSError, ValueError, KeyError, RuntimeError):
                        status.update(label=tr("Не удалось собрать исходные требования."), state="error")
                        return
                    for name in ("target_registry_collected", "target_registry_result", "target_full_workbook",
                                 "target_registry_review_draft", "target_registry_profile_draft"):
                        session.pop(name, None)
                    session["target_registry_preview"] = refreshed
                    status.update(label=tr("Исходные требования собраны"), state="complete")
                st.rerun()
                return
        if not preview["requirements"]:
            st.info(tr("В обработанных основаниях не найдено существенных записей."))
            return
        selected = _select_functions(preview)
        previous = session.get("target_registry_collected")
        same = bool(previous and previous[1].get("selected_functions") == sorted(selected))
        label = tr("Продолжить к собранным требованиям") if same else tr("Уточнить требования по выбранным функциям")
        if not st.button(label, key="target_analyze", type="primary", disabled=not enabled):
            return
        if not same:
            for name in ("target_registry_collected", "target_registry_result", "target_full_workbook",
                         "target_registry_review_draft"):
                session.pop(name, None)
            with st.status(tr("Сбор исходных требований"), expanded=False) as status:
                try:
                    collected = collect_target_requirements(cfg, prepared, None, render_progress(status),
                        reset_cache=reset_cache, summaries=False, preview=preview, selected_functions=selected)
                except (DraftError, OSError, ValueError, KeyError, RuntimeError):
                    status.update(label=tr("Не удалось собрать исходные требования."), state="error")
                    return
                identity = collected["input_identity"]
                session["target_registry_collected"] = identity, collected
                status.update(label=tr("Исходные требования собраны"), state="complete")
        advance(3)
        return

    item = session.get("target_registry_collected")
    if not prepared or not item:
        advance(2)
        return
    identity, collected = item
    saved = session.get("target_registry_result")
    if step == 3:
        preview = session.get("target_registry_preview")
        known = {p["id"] for p in preview["approved_profile"]} if preview else set()
        new_functions = [p for p in collected.get("approved_profile", []) if p["id"] not in known] if preview else []
        if new_functions:
            st.info(tr("Дополнительный поиск выявил новые функции: {names}. Они не выбраны автоматически.",
                       names=", ".join(p["name"] for p in new_functions)))
            if st.button(tr("Вернуться к выбору функций"), key="target_expand_scope"):
                try:
                    session["target_registry_preview"] = extend_function_preview(cfg, prepared, preview, collected)
                except (DraftError, ValueError, KeyError):
                    st.warning(tr("Настройки анализа изменились. Соберите требования заново."))
                    return
                advance(2)
                return
        # A function-scope decision is followed by explicit individual review.
        expert = expert or collected.get("selected_functions") is not None
        chosen, notes = _review_collection(collected, prepared, expert) if expert else ([], {})
        review = saved[1].get("review", {}) if saved and saved[0] == identity else {}
        same = review.get("mode") == ("expert" if expert else "automatic") and (
            not expert or (review.get("included") == sorted(chosen) and review.get("notes") == notes))
        if saved and not same:
            st.warning(tr("Изменённая область согласования требует повторной декомпозиции, но не сбора требований."))
        label = tr("Открыть готовый реестр") if same else tr("Согласовать и детализировать")
        if any(collected["decisions"].get(rid, {}).get("change") == "unknown" for rid in chosen):
            st.caption(tr("Выбранные требования с неизвестной необходимостью доработки сохранятся без неподтверждённой детализации."))
        if st.button(label, key="target_decompose", type="primary"):
            if same or _decompose(cfg, session, prepared, identity, collected,
                                  selection=chosen if expert else None, notes=notes if expert else None):
                advance(4)
                return
        with st.expander(tr("Подробности сбора и выгрузки")):
            _render_registry_details(prepared, collected, key, identity, finished=False)
        return
    if not saved or saved[0] != identity:
        advance(3)
        return
    _render_registry_details(prepared, saved[1], key, identity, finished=True)
    st.info(tr("Формирование Word из согласованного реестра V2 пока в разработке. Реестр можно выгрузить в Excel."))


def _render_registry_details(prepared, result, key, identity, *, finished):
    session = st.session_state
    proposals = result["proposals"]
    accepted = [p for p in proposals if p["assessment"] == "model_supported" and
                all(result["dispositions"].get(rid) == "model_covered" for rid in p["need_refs"])]
    if finished:
        st.subheader(tr("Реестр требований к целевой системе"))
        st.caption(tr("Предложений: {n}; прошли проверки модели: {ok}; групп: {groups}. Экспертное согласование обязательно.",
                      n=len(proposals), ok=len(accepted), groups=len(result["groups"])))
        if not accepted:
            st.error(tr("Нет требований, прошедших все автоматические проверки."))
        cols = st.columns(3)
        cols[0].metric(tr("Предложения"), len(proposals))
        cols[1].metric(tr("Поддержано моделью"), len(accepted))
        cols[2].metric(tr("Открытые вопросы"), len(result["questions"]))
    else:
        st.caption(tr("Декомпозиция ещё не выполнена для выбранного набора. Исходные данные сохранены в текущем сеансе."))

    views = {"functions": tr("Характеристики функций"), "metrics": tr("Показатели назначения"),
             "sources": tr("Исходные записи и причины непереноса"), "questions": tr("Открытые вопросы"),
             "diagnostics": tr("Диагностика и выгрузки")}
    if finished:
        views = {"proposals": tr("Предложения по функциям"), **views}
    view = st.radio(tr("Раздел реестра"), list(views), format_func=views.__getitem__,
                    horizontal=True, key=f"target_view_{finished}")
    if view == "proposals":
        groups = {g["id"]: g["function"] for g in result["groups"]}
        choices = {None: tr("Все функции"), **groups}
        gid = st.selectbox(tr("Функция"), list(choices), format_func=choices.__getitem__,
                           key="target_proposal_group")
        statuses = {None: tr("Все статусы"), True: tr("Поддержано моделью"), False: tr("Требует экспертной проверки")}
        approved = st.selectbox(tr("Статусы обработки"), list(statuses), format_func=statuses.__getitem__,
                                key="target_proposal_status")
        accepted_ids = {p["id"] for p in accepted}
        rows = [p for p in proposals if (gid is None or p["group"] == gid)
                and (approved is None or (p["id"] in accepted_ids) == approved)]
        for p in _page(rows, "target_proposal_page"):
            st.caption(f"{p['id']} · {groups.get(p['group'], '')} · {_label(p['kind'])} · "
                       + (tr("Поддержано моделью") if p["id"] in accepted_ids else tr("Требует экспертной проверки")))
            st.write(p["text"])
            with st.expander(tr("Показать исходные цитаты и основания") + " · " + p["id"]):
                _show_refs(p["need_refs"] + p["state_refs"] + p["constraint_refs"], prepared, result)
    elif view == "functions":
        dossiers = result.get("dossiers", {})
        if dossiers:
            pid = st.selectbox(tr("Функция"), list(dossiers), format_func=lambda k: dossiers[k]["function"],
                               key="target_dossier_function")
            for facet, row in dossiers[pid]["facets"].items():
                st.caption(f"{_label(facet)} · {_label(row['status'])} · {len(row['facts'])}")
                for fact in row["facts"]:
                    rid = fact.get("record_id", "")
                    status = row.get("coverage", {}).get(rid)
                    st.text(f"{rid} · {(_label(status) + ' · ') if status else ''}{fact['quote']}")
        else:
            st.caption(tr("Для выбранного фильтра записей нет."))
    elif view == "metrics":
        for rid, row in _page(list(result["metrics_registry"].items()), "target_metric_page"):
            st.text(f"{rid} · {row['subject']} · {row['value']} {row['unit']} · {row['level']}")
            st.text(row["conditions"])
            st.text(f"{row['current_value']} → {row['target_value']}")
            _show_refs([rid], prepared, result)
    elif view == "sources":
        dispositions = result["dispositions"]
        choices = {None: tr("Все статусы"), **{code: _label(code) for code in sorted(set(dispositions.values()))}}
        code = st.selectbox(tr("Статусы обработки"), list(choices), format_func=choices.__getitem__, key="target_disposition")
        documents = {None: tr("Все документы"), **{r["source"]: r["source"] for r in result["requirements"].values()}}
        source = st.selectbox(tr("Документ-основание"), list(documents), format_func=documents.__getitem__, key="target_source_filter")
        ids = [rid for rid, value in dispositions.items() if (code is None or value == code)
               and (source is None or result["requirements"][rid]["source"] == source)]
        for rid in _page(ids, "target_source_page"):
            row = result["requirements"][rid]
            st.caption(f"{rid} · {_label(dispositions[rid])} · {row['source']} › {row['section']}")
            st.text(row["quote"])
            with st.expander(tr("Подтверждающие сведения") + " · " + rid):
                d = result["decisions"].get(rid, {})
                st.text(" · ".join(_label(d[k]) for k in ("change", "status") if d.get(k)))
                st.text(d.get("reason", ""))
                st.text(d.get("review_reason", ""))
                _show_refs(d.get("state_refs", []), prepared, result)
                related = result.get("linked_by_need", {}).get(rid, {})
                if related:
                    st.caption(tr("Связанные пункты оснований"))
                    for item in related["items"]:
                        st.caption(f"{item['source']} › {item['section']} · {item['reference']} · {' → '.join(item['path'])}")
                        st.text(item["quote"])
                    if related["gaps"]:
                        st.json(related["gaps"])
                for p in proposals:
                    if rid in p["need_refs"] + p["state_refs"] + p["constraint_refs"]:
                        st.text(f"{p['id']} · {p['text']}")
    elif view == "questions":
        for row in _page(result["questions"], "target_question_page"):
            st.text(f"{row['need_id']} · {row['question']}")
        if result["issues"]:
            with st.expander(tr("Замечания формирования ({n})", n=len(result["issues"]))):
                for issue in result["issues"]:
                    st.text(issue)
    else:
        _render_diagnostics(prepared, result, key, identity, finished)


def _page(rows, key, size=10):
    if not rows:
        st.caption(tr("Для выбранного фильтра записей нет."))
        return []
    pages = (len(rows) + size - 1) // size
    if st.session_state.get(key, 1) > pages:
        st.session_state[key] = 1
    page = st.selectbox(tr("Страница"), list(range(1, pages + 1)), key=key) if pages > 1 else 1
    first = (page - 1) * size
    st.caption(tr("Отображено {n} из {total}.", n=min(first + size, len(rows)), total=len(rows)))
    return rows[first:first + size]


def _render_diagnostics(prepared, result, key, identity, finished):
    session = st.session_state
    st.caption(tr("Полный реестр содержит исходные тексты. Храните его только внутри разрешённого контура."))
    workbook_key = (key, identity, result.get("metrics", {}).get("run_id"))
    workbook = session.get("target_full_workbook")
    if not workbook or workbook[:3] != workbook_key:
        try:
            workbook = (*workbook_key, registry_workbook(prepared, result))
        except (ImportError, ValueError, OSError, KeyError, RuntimeError):
            workbook = (*workbook_key, None)
        session["target_full_workbook"] = workbook
    if workbook[3] is not None:
        st.download_button(tr("Скачать полный реестр Excel"), workbook[3], file_name="mint_registry.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="target_full_export")
    else:
        st.warning(tr("Не удалось подготовить полный реестр Excel."))
    export = target_registry_export(prepared, result)
    st.download_button(tr("Скачать обезличенные данные для анализа"),
                       json.dumps(export, ensure_ascii=False, indent=2, allow_nan=False),
                       file_name="mint_draft_analysis.json", mime="application/json", key="target_diagnostic_export")
    st.caption(tr("В диагностике нет текстов, имён файлов, названий моделей и идентификаторов источников. Проверьте файл перед передачей."))
    if finished:
        with st.expander(tr("Сравнение прогонов (локально)")):
            snapshot = regression_snapshot(prepared, result)
            st.download_button(tr("Скачать контрольный снимок реестра"), json.dumps(snapshot, ensure_ascii=False, indent=2),
                               file_name="mint_registry_baseline.json", mime="application/json", key="target_baseline_export")
            baseline = st.file_uploader(tr("Контрольный снимок прошлого прогона"), type=["json"], key="target_baseline_import")
            if baseline is not None:
                try:
                    delta = compare_registries(json.loads(baseline.getvalue()), snapshot)
                except (ValueError, TypeError, AttributeError, UnicodeError):
                    st.warning(tr("Несовместимые прогоны: проверьте исходные ревизии, контекст и выбранные функции."))
                else:
                    st.json(delta)
                    st.caption(tr("Сравнение дословное: переформулированные требования проверяет эксперт."))
    with st.expander(tr("Замеры этапов подготовки")):
        st.json(export)
        st.caption(tr("Классификация разделов оснований (не извлечённые требования)"))
        for row in prepared.get("sections", {}).values():
            st.text(f"{_label(row['role'])} · {row['source']} › {row['section']}")

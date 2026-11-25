"""Local STOP-1 review and explicit private registry export."""
import hashlib
import json

import streamlit as st

from ..draft_target_analysis import (prepare_target_analysis, collect_target_requirements,
                                     decompose_target_requirements)
from ..draft_target_review import MAX_NOTE
from ..draft_pilot_report import target_registry_export
from ..draft_registry_workbook import registry_workbook, regression_snapshot, compare_registries
from ..i18n import tr
from .draft_progress_ui import render_progress
from .draft_wizard_state import sync_target, clear_target
from ..template_draft import DraftError

def _label(code):
    labels = {
        "model_supported": tr("Поддержано моделью"),
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
            st.text(row["quote"])
        elif rid in prepared["spans"]:
            row = prepared["spans"][rid]
            st.caption(f"{rid} · {row['source']} › {row['section']}")
            st.text(row["text"])


def _review_collection(collected, prepared, expert):
    """One review control per function, no compulsory checkbox per quote."""
    run = collected["metrics"]["run_id"]
    decisions, records = collected["decisions"], collected["requirements"]
    selected, notes = [], {}
    session = st.session_state
    draft = session.get("target_registry_review_draft")
    if not draft or draft["run"] != run:
        draft = {"run": run, "selected": {}, "notes": {}}
        session["target_registry_review_draft"] = draft
    st.subheader(tr("Собранные требования перед декомпозицией"))
    st.caption(tr("Сводные формулировки — черновик модели по всей функции. Выбор меняет область декомпозиции, но не исходную сводку. Декомпозиция опирается на цитаты и проверенное распределение."))
    candidates = sum(decisions[rid]["change"] != "already_supported"
                     for group in collected["groups"] for rid in group["requirement_ids"])
    st.caption(tr("Функций: {n}; исходных потребностей для детализации: {count}.", n=len(collected["groups"]), count=candidates))
    for group in collected["groups"]:
        gid = group["id"]
        ids = [rid for rid in group["requirement_ids"] if decisions[rid]["change"] != "already_supported"]
        rows = collected["summaries"].get(gid, [])
        if not rows and ids:
            # Automatic collection has no summary calls; allow later expert
            # review of the original needs without rescanning the sources.
            rows = [{"status": "not_requested", "need_refs": ids}]
        if not ids:
            continue
        with st.expander(f"{group['function']} · {len(ids)}", expanded=len(collected["groups"]) == 1):
            for row in rows:
                if row["status"] == "draft":
                    st.text(row["text"])
                    st.caption(", ".join(row["need_refs"] + row["evidence_refs"]))
                else:
                    st.caption(tr("Сводка не получена; используйте исходные формулировки."))
                    _show_refs(row["need_refs"], prepared, collected)
            if expert:
                scope_key = f"target_review_scope_{run}_{gid}"
                note_key = f"target_review_note_{run}_{gid}"
                if scope_key not in session:
                    session[scope_key] = draft["selected"].get(gid, ids)
                if note_key not in session:
                    session[note_key] = draft["notes"].get(gid, "")
                chosen = st.multiselect(tr("Включить исходные потребности в декомпозицию"),
                                        ids, format_func=lambda rid: f"{rid} · {records[rid]['quote'][:140]}",
                                        key=scope_key)
                selected.extend(chosen)
                note = st.text_area(tr("Уточнение эксперта (не источник)"), max_chars=MAX_NOTE,
                                    key=note_key, disabled=not chosen)
                draft["selected"][gid] = list(chosen)
                draft["notes"][gid] = note
                if chosen and note.strip():
                    notes[gid] = note.strip()
            show = st.checkbox(tr("Показать исходные цитаты и основания"), key=f"target_review_refs_{run}_{gid}")
            if show:
                for rid in group["requirement_ids"]:
                    d = decisions[rid]
                    st.caption(f"{rid} · {_label(d['change'])} · {_label(d['status'])}")
                    _show_refs([rid] + d.get("state_refs", []) + d.get("reference_refs", [])
                               + d.get("dossier_refs", []), prepared, collected)
            for rid in group["requirement_ids"]:
                metric = collected["metrics_registry"].get(rid)
                if metric:
                    st.text(f"{rid} · {metric['subject']} · {metric['value']} {metric['unit']} · {metric['level']}")
                    st.text(metric["conditions"])
    if expert:
        st.caption(tr("Выбрано {n} из {total} потребностей. Исключённые записи остаются в реестре.",
                      n=len(selected), total=candidates))
    return selected, notes


def _prepare(cfg, session, sources, roles, context):
    with st.status(tr("Профиль целевой системы"), expanded=False) as status:
        try:
            prepared = prepare_target_analysis(cfg, sources, roles, context, render_progress(status))
        except (DraftError, OSError, ValueError, KeyError, RuntimeError):
            status.update(label=tr("Не удалось подготовить профиль системы."), state="error")
            return None
        session["target_registry_prepared"] = prepared
        status.update(label=tr("Профиль подготовлен"), state="complete")
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


def render_target_registry(cfg, key, sources, roles, context, enabled, reset_cache, *, step, expert, advance):
    """Render the active stage only. Navigation never starts an LLM operation."""
    session = st.session_state
    sync_target(session, key)
    prepared = session.get("target_registry_prepared")
    if step == 2:
        if prepared is None:
            if st.button(tr("Подготовить профиль системы"), disabled=not enabled, key="target_prepare", type="primary"):
                if _prepare(cfg, session, sources, roles, context):
                    st.rerun()
            return
        sig = hashlib.sha256(json.dumps(prepared["profile"], ensure_ascii=False).encode()).hexdigest()[:16]
        draft = session.get("target_registry_profile_draft")
        if not draft or draft["sig"] != sig:
            draft = {"sig": sig, "selected": []}
            session["target_registry_profile_draft"] = draft
        st.subheader(tr("Профиль целевой системы"))
        st.caption(tr("Подтвердите только верные функции. При необходимости исправьте общий контекст и подготовьте профиль заново."))
        selected = []
        for row in prepared["profile"]:
            pid = row["id"]
            widget = f"target_profile_{sig}_{pid}"
            if widget not in session:
                session[widget] = pid in draft["selected"]
            if st.checkbox(row["name"], key=widget):
                selected.append(row)
            st.caption(row["description"])
            with st.expander(tr("Подтверждающие сведения") + " · " + pid):
                for sid in row["refs"]:
                    span = prepared["spans"][sid]
                    st.caption(f"{span['source']} › {span['section']}")
                    st.text(span["text"])
        if not prepared["profile"]:
            st.caption(tr("Функции не подтверждены источниками; анализ может выявить прямые обязанности и пробелы."))
        draft["selected"] = [p["id"] for p in selected]
        identity = (sig, tuple(draft["selected"]))
        previous = session.get("target_registry_collected")
        same = bool(previous and previous[0] == identity)
        if previous and not same:
            st.warning(tr("После подтверждения изменений последующие результаты потребуется собрать заново."))
        with st.expander(tr("Карта разделов оснований")):
            for row in prepared["sections"].values():
                st.text(f"{_label(row['role'])} · {row['source']} › {row['section']}")
        # The primary action confirms the selected function set, including an
        # intentionally empty profile. Explicit re-collection is separate.
        if same:
            label = tr("Продолжить к собранным требованиям")
        else:
            label = tr("Подтвердить функции и собрать требования")
        again = False
        with st.expander(tr("Расширенные действия")):
            again = st.button(tr("Повторно собрать требования"), disabled=not same, key="target_collect_again")
            if st.button(tr("Повторно определить профиль"), key="target_prepare_again"):
                clear_target(session)
                sync_target(session, key)
                if _prepare(cfg, session, sources, roles, context):
                    st.rerun()
                return
        proceed = st.button(label, key="target_analyze", type="primary")
        if not (proceed or again):
            return
        if not same or again:
            for name in ("target_registry_collected", "target_registry_result", "target_full_workbook",
                         "target_registry_review_draft"):
                session.pop(name, None)
            with st.status(tr("Распределение ответственности"), expanded=False) as status:
                try:
                    collected = collect_target_requirements(cfg, prepared, selected, render_progress(status),
                                                           reset_cache=reset_cache, summaries=expert)
                except (DraftError, OSError, ValueError, KeyError, RuntimeError):
                    status.update(label=tr("Не удалось собрать исходные требования."), state="error")
                    return
                session["target_registry_collected"] = identity, collected
                status.update(label=tr("Исходные требования собраны"), state="complete")
        else:
            collected = previous[1]
        if not expert:
            saved = session.get("target_registry_result")
            if saved and saved[0] == identity and saved[1].get("review", {}).get("mode") == "automatic":
                advance(4)
                return
            if _decompose(cfg, session, prepared, identity, collected):
                advance(4)
                return
        advance(3)
        return

    item = session.get("target_registry_collected")
    if not prepared or not item:
        advance(2)
        return
    identity, collected = item
    saved = session.get("target_registry_result")
    if step == 3:
        chosen, notes = _review_collection(collected, prepared, expert)
        review = saved[1].get("review", {}) if saved and saved[0] == identity else {}
        same = review.get("mode") == ("expert" if expert else "automatic") and (
            not expert or (review.get("included") == sorted(chosen) and review.get("notes") == notes))
        if saved and not same:
            st.warning(tr("Изменённая область согласования требует повторной декомпозиции, но не сбора требований."))
        label = tr("Открыть готовый реестр") if same else tr("Подтвердить и декомпозировать")
        if st.button(label, key="target_decompose", type="primary"):
            if same or _decompose(cfg, session, prepared, identity, collected,
                                  selection=chosen if expert else None, notes=notes if expert else None):
                advance(4)
                return
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
    export = target_registry_export(prepared, result)
    st.download_button(tr("Скачать обезличенные данные для анализа"),
                       json.dumps(export, ensure_ascii=False, indent=2, allow_nan=False),
                       file_name="mint_draft_analysis.json", mime="application/json",
                       key="target_diagnostic_export")
    st.caption(tr("В диагностике нет текстов, имён файлов, названий моделей и идентификаторов источников. Проверьте файл перед передачей."))
    with st.expander(tr("Предложения по функциям")):
        groups = {g["id"]: g["function"] for g in result["groups"]}
        if proposals:
            lookup = {p["id"]: p for p in proposals}
            pid = st.selectbox(tr("Требование"), list(lookup),
                               format_func=lambda k: f"{k} · {lookup[k]['text'][:100]}",
                               key="target_proposal")
            p = lookup[pid]
            st.caption(f"{groups.get(p['group'], '')} · {p['kind']} · {p['assessment']}")
            st.text(p["text"])
            _show_refs(p["need_refs"] + p["state_refs"] + p["constraint_refs"], prepared, result)
    with st.expander(tr("Характеристики функций")):
        dossiers = result.get("dossiers", {})
        if dossiers:
            pid = st.selectbox(tr("Функция"), list(dossiers), format_func=lambda k: dossiers[k]["function"], key="target_dossier_function")
            for facet, row in dossiers[pid]["facets"].items():
                st.caption(f"{facet} · {row['status']} · {len(row['facts'])}")
                for fact in row["facts"]:
                    rid = fact.get("record_id", "")
                    st.text(f"{rid} · {row.get('coverage', {}).get(rid, '')} · {fact['quote']}")
    with st.expander(tr("Показатели назначения")):
        for rid, row in result["metrics_registry"].items():
            st.text(f"{rid} · {row['subject']} · {row['value']} {row['unit']} · {row['level']}")
            st.text(row["conditions"])
            st.text(f"{row['current_value']} → {row['target_value']}")
            _show_refs([rid], prepared, result)
    with st.expander(tr("Исходные записи и причины непереноса")):
        dispositions = result["dispositions"]
        codes = sorted(set(dispositions.values()))
        if codes:
            code = st.selectbox(tr("Статусы обработки"), codes, key="target_disposition")
            ids = [rid for rid, value in dispositions.items() if value == code]
            rid = st.selectbox(tr("Требование"), ids,
                               format_func=lambda k: f"{k} · {result['requirements'][k]['quote'][:100]}",
                               key="target_source_record")
            _show_refs([rid], prepared, result)
            d = result["decisions"].get(rid, {})
            st.text(f"{d.get('category', '')} · {d.get('change', '')} · {d.get('status', '')}")
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
                if rid in p["need_refs"]:
                    st.text(f"{p['id']} · {p['text']}")
    with st.expander(tr("Открытые вопросы")):
        for row in result["questions"]:
            st.text(f"{row['need_id']} · {row['question']}")
    with st.expander(tr("Замечания формирования ({n})", n=len(result["issues"]))):
        for issue in result["issues"]:
            st.text(issue)
    with st.expander(tr("Замеры этапов подготовки")):
        st.json(export)

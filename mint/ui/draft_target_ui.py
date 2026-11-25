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
from ..template_draft import DraftError

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
    st.subheader(tr("Собранные требования перед декомпозицией"))
    st.caption(tr("Сводные формулировки — черновик модели по всей функции. Выбор меняет область декомпозиции, но не исходную сводку. Декомпозиция опирается на цитаты и проверенное распределение."))
    candidates = sum(len(row["need_refs"]) for rows in collected["summaries"].values() for row in rows)
    st.caption(tr("Функций: {n}; исходных потребностей для детализации: {count}.", n=len(collected["groups"]), count=candidates))
    for group in collected["groups"]:
        gid = group["id"]
        ids = [rid for rid in group["requirement_ids"] if decisions[rid]["change"] != "already_supported"]
        rows = collected["summaries"].get(gid, [])
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
                chosen = st.multiselect(tr("Включить исходные потребности в декомпозицию"),
                                        ids, default=ids, format_func=lambda rid: f"{rid} · {records[rid]['quote'][:140]}",
                                        key=f"target_review_scope_{run}_{gid}")
                selected.extend(chosen)
                note = st.text_area(tr("Уточнение эксперта (не источник)"), max_chars=MAX_NOTE,
                                    key=f"target_review_note_{run}_{gid}", disabled=not chosen)
                if chosen and note.strip():
                    notes[gid] = note.strip()
            show = st.checkbox(tr("Показать исходные цитаты и основания"), key=f"target_review_refs_{run}_{gid}")
            if show:
                for rid in group["requirement_ids"]:
                    d = decisions[rid]
                    st.caption(f"{rid} · {d['change']} · {d['status']}")
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


def render_target_registry(cfg, key, sources, roles, context, enabled, reset_cache):
    session = st.session_state
    if session.get("target_registry_key") != key:
        session["target_registry_key"] = key
        session.pop("target_registry_prepared", None)
        session.pop("target_registry_result", None)
        session.pop("target_registry_collected", None)
        session.pop("target_full_workbook", None)
    st.caption(tr("Контрольная точка 1: сначала анализ требований, без формирования Word."))
    if st.button(tr("Подготовить профиль системы"), disabled=not enabled, key="target_prepare"):
        session.pop("target_registry_prepared", None)
        session.pop("target_registry_result", None)
        session.pop("target_registry_collected", None)
        session.pop("target_full_workbook", None)
        with st.status(tr("Профиль целевой системы"), expanded=False) as status:
            try:
                prepared = prepare_target_analysis(cfg, sources, roles, context, render_progress(status))
            except (DraftError, OSError, ValueError, KeyError, RuntimeError):
                status.update(label=tr("Не удалось подготовить профиль системы."), state="error")
            else:
                session["target_registry_prepared"] = prepared
                status.update(label=tr("Профиль подготовлен"), state="complete")
    prepared = session.get("target_registry_prepared")
    if not prepared or not enabled:
        return
    profile = {p["id"]: p for p in prepared["profile"]}
    sig = hashlib.sha256(json.dumps(prepared["profile"], ensure_ascii=False).encode()).hexdigest()[:16]
    with st.expander(tr("Карта разделов оснований")):
        for row in prepared["sections"].values():
            st.text(f"{row['role']} · {row['source']} › {row['section']}")
    st.subheader(tr("Профиль целевой системы"))
    st.caption(tr("Подтвердите только верные функции. При необходимости исправьте общий контекст и подготовьте профиль заново."))
    selected = []
    for pid, row in profile.items():
        if st.checkbox(row["name"], value=False, key=f"target_profile_{sig}_{pid}"):
            selected.append(row)
        st.caption(row["description"])
        with st.expander(tr("Подтверждающие сведения") + " · " + pid):
            for sid in row["refs"]:
                span = prepared["spans"][sid]
                st.caption(f"{span['source']} › {span['section']}")
                st.text(span["text"])
    if not profile:
        st.caption(tr("Функции не подтверждены источниками; анализ может выявить прямые обязанности и пробелы."))
    approved = st.checkbox(tr("Подтверждаю выбранный профиль и неизвестные границы"),
                           value=False, key="target_profile_confirm_" + sig)
    identity = (sig, tuple(p["id"] for p in selected))
    expert = st.checkbox(tr("Согласование требований перед декомпозицией"), value=True,
                         key="target_expert_review")
    if st.button(tr("Собрать исходные требования"), disabled=not approved, key="target_analyze"):
        session.pop("target_registry_result", None)
        session.pop("target_registry_collected", None)
        session.pop("target_full_workbook", None)
        with st.status(tr("Распределение ответственности"), expanded=False) as status:
            try:
                collected = collect_target_requirements(cfg, prepared, selected, render_progress(status),
                                                       reset_cache=reset_cache)
            except (DraftError, OSError, ValueError, KeyError, RuntimeError):
                status.update(label=tr("Не удалось собрать исходные требования."), state="error")
            else:
                session["target_registry_collected"] = identity, collected
                status.update(label=tr("Исходные требования собраны"), state="complete")
                if not expert:
                    with st.status(tr("Детализация требований"), expanded=False) as detail:
                        try:
                            result = decompose_target_requirements(cfg, prepared, collected, render_progress(detail))
                        except (DraftError, OSError, ValueError, KeyError, RuntimeError):
                            detail.update(label=tr("Не удалось сформировать реестр требований."), state="error")
                        else:
                            session["target_registry_result"] = identity, result
                            detail.update(label=tr("Реестр подготовлен"), state="complete")
    collected_item = session.get("target_registry_collected")
    if not approved or not collected_item or collected_item[0] != identity:
        return
    collected = collected_item[1]
    chosen, notes = _review_collection(collected, prepared, expert)
    saved = session.get("target_registry_result")
    desired_mode = "expert" if expert else "automatic"
    def matches(item):
        if not item or item[0] != identity:
            return False
        review = item[1].get("review", {})
        return review.get("mode") == desired_mode and (not expert or
            review.get("included") == sorted(chosen) and review.get("notes") == notes)
    confirmed = True
    if expert:
        scope = hashlib.sha256(json.dumps([collected["metrics"]["run_id"], sorted(chosen), notes],
                                          ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
        confirmed = st.checkbox(tr("Подтверждаю выбранные потребности для декомпозиции"),
                                value=False, key="target_need_confirm_" + scope)
    if st.button(tr("Декомпозировать требования"), disabled=not confirmed, key="target_decompose"):
        session.pop("target_registry_result", None)
        session.pop("target_full_workbook", None)
        saved = None
        with st.status(tr("Детализация требований"), expanded=False) as detail:
            try:
                result = decompose_target_requirements(cfg, prepared, collected, render_progress(detail),
                                                       selection=chosen if expert else None,
                                                       notes=notes if expert else None)
            except (DraftError, OSError, ValueError, KeyError, RuntimeError):
                detail.update(label=tr("Не удалось сформировать реестр требований."), state="error")
            else:
                saved = identity, result
                session["target_registry_result"] = saved
                detail.update(label=tr("Реестр подготовлен"), state="complete")
    finished = confirmed and matches(saved)
    result = saved[1] if finished else collected
    if not finished:
        st.caption(tr("Декомпозиция ещё не выполнена для выбранного набора. Исходные данные сохранены в текущем сеансе."))
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

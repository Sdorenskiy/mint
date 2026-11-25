"""Local STOP-1 review. No Word output or private data downloads."""
import hashlib
import json

import streamlit as st

from ..draft_target_analysis import prepare_target_analysis, analyze_target_registry
from ..draft_pilot_report import target_registry_export
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


def render_target_registry(cfg, key, sources, roles, context, enabled, reset_cache):
    session = st.session_state
    if session.get("target_registry_key") != key:
        session["target_registry_key"] = key
        session.pop("target_registry_prepared", None)
        session.pop("target_registry_result", None)
    st.caption(tr("Контрольная точка 1: сначала анализ требований, без формирования Word."))
    if st.button(tr("Подготовить профиль системы"), disabled=not enabled, key="target_prepare"):
        session.pop("target_registry_prepared", None)
        session.pop("target_registry_result", None)
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
    if st.button(tr("Сформировать реестр требований"), disabled=not approved, key="target_analyze"):
        session.pop("target_registry_result", None)
        with st.status(tr("Распределение ответственности"), expanded=False) as status:
            try:
                result = analyze_target_registry(cfg, prepared, selected, render_progress(status),
                                                 reset_cache=reset_cache)
            except (DraftError, OSError, ValueError, KeyError, RuntimeError):
                status.update(label=tr("Не удалось сформировать реестр требований."), state="error")
            else:
                session["target_registry_result"] = identity, result
                status.update(label=tr("Реестр подготовлен"), state="complete")
    saved = session.get("target_registry_result")
    if not approved or not saved or saved[0] != identity:
        return
    result = saved[1]
    proposals = result["proposals"]
    accepted = [p for p in proposals if p["assessment"] == "model_supported" and
                all(result["dispositions"].get(rid) == "model_covered" for rid in p["need_refs"])]
    st.subheader(tr("Реестр требований к целевой системе"))
    st.caption(tr("Предложений: {n}; прошли проверки модели: {ok}; групп: {groups}. Экспертное согласование обязательно.",
                  n=len(proposals), ok=len(accepted), groups=len(result["groups"])))
    if not accepted:
        st.error(tr("Нет требований, прошедших все автоматические проверки."))
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

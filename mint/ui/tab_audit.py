"""Интерфейс: вкладка «Аудит документа»."""

import json
import logging
import os
import time
from dataclasses import replace
from pathlib import Path

import streamlit as st

try:
    import docx  # noqa: F401  — нужен для «Документа с замечаниями» (.docx)
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

from ..audit import (
    REASONING_TIMEOUT, WHOLE_MAX_TOKENS, WHOLE_TIMEOUT, annotate_docx_with_findings, audit_basis_documents, audit_cfg,
    audit_passes, compare_with_reference, raw_answers_markdown, recheck_failed_sections, reference_markdown,
    retry_timeout, run_audit,
)
from ..audit_store import (audits_root, delete_audit, list_audits, load_audit, load_document, load_meta, load_raw,
                           save_audit)
from ..basis import reference_label
from ..expert import (CHECKLIST_MAX, checklists_path, detect_document_type, load_checklists, load_expert_materials,
                      save_checklists)
from ..kb import list_kb_documents
from ..feedback import new_feedback_id
from ..expert_review import export_review, review_rows
from ..i18n import N_, get_lang, tr
from ..parsing import SUPPORTED_FORMATS, DocumentUnreadable, document_format, document_to_markdown
from ..prompts import (DEFAULT_AUDIT_FOCUS, DEFAULT_AUDIT_FOCUS_EN, all_profile_focus_texts, default_audit_focus,
                       get_profile, profile_audit_focus)
from .audit_review import render_expert_review
from .common import AUDIT_SETTINGS, _expert_widget, btn_w, dl_w, render_audit_log_entry, render_deep_log
from .feedback import render_feedback
from .theme import audit_verdict_html

logger = logging.getLogger("MINT")

_MODE_NOTES = {"full": N_("Каждый раздел проверяется вместе с документом целиком."),
               "outline": N_("Документ целиком не помещается в окно модели: к разделам прилагается оглавление."),
               "single": N_("Документ проверяется одной частью.")}


def _docx_review(doc_bytes, res):
    """Документ с замечаниями MINT примечаниями Word: (байты, статистика) или (None, {"error"})."""
    try:
        unverified = [{**f, "text": tr("[Не подтверждено источником: {v}] {finding}", v=", ".join(f["unverified"]),
                                       finding=f["text"])} for f in res.get("unverified", [])]
        return annotate_docx_with_findings(doc_bytes, list(res.get("findings") or []) + unverified)
    except Exception as docx_err:
        logger.exception("Экспорт документа с замечаниями в Word не удался")
        return None, {"error": str(docx_err)}


def on_profile_change(profile):
    """Выбран другой профиль (боковая панель) — в поле критериев аудита его критерии: выбор профиля — явный, свой
    текст поля заменяется."""
    st.session_state["tab2_user_focus"] = profile_audit_focus(profile)


def _run_settings(cfg, use_wiki_rag):
    """Настройки прогона — в meta.json сохранённого аудита и в файл разбора."""
    return {"profile": get_profile(),
            "use_kb": use_wiki_rag, "deep": st.session_state.get("tab2_deep", cfg.audit_deep),
            "whole": st.session_state.get("tab2_whole", False), "passes": audit_passes(cfg),
            "self_critique": cfg.use_self_critique, "reasoning": cfg.audit_reasoning,
            "merge": cfg.audit_merge_duplicates, "basis_on": cfg.audit_basis_docs, "lang": get_lang()}


def _show(name, res, rows, review, log, aid, ctx, docx_review, reopened, meta=None):
    """Аудит на экран: заключение, замечания, лог, разбор эксперта."""
    ss = st.session_state
    ss.pop("_tab2_raw", None)
    ss["tab2_meta"] = meta
    ss["tab2_audit_result"] = res
    ss["tab2_final_report_data"] = res["report"]
    ss["tab2_findings"] = res["findings"]
    ss["tab2_audit_active_file"] = name
    ss["tab2_audit_log"] = log
    ss["tab2_audit_id"] = aid or new_feedback_id()
    ss["tab2_saved_id"] = aid
    ss["tab2_feedback_ctx"] = ctx
    ss["tab2_audit_log_md"] = res.get("log_md") or ""
    ss["tab2_rows"], ss["tab2_review"] = rows, review
    ss["tab2_reopened"] = reopened
    if docx_review is None:
        ss.pop("tab2_docx_review", None)
    else:
        ss["tab2_docx_review"] = docx_review


def _store_result(cfg, res, audit_file, use_wiki_rag, status, recheck=False):
    """Итог аудита (или перепроверки — в ту же папку, разбор эксперта остаётся) — на диск (LOG_DIR/audits) и в
    сеанс: заключение, лог, документ с примечаниями, контекст отзыва, разбор эксперта."""
    failed_sections = res["failed_sections"]
    is_docx = document_format(audit_file.name) == "docx"
    doc_bytes = bytes(audit_file.getbuffer()) if is_docx else None
    raw_md = raw_answers_markdown(res, audit_file.name) if (res.get("state") or {}).get("raw") else ""
    res["raw_md"] = raw_md
    prev = st.session_state.get("tab2_saved_id") if recheck else None
    aid = None
    try:
        aid = save_audit(cfg, res, audit_file.name, doc_bytes=doc_bytes, settings=_run_settings(cfg, use_wiki_rag),
                         raw_md=raw_md, aid=prev)
    except Exception as e:
        logger.exception("Аудит не сохранён на диск")
        st.warning(tr("Аудит не сохранён в «📂 Мои аудиты»: {e}", e=e))
    rows = review_rows(res)
    review = (st.session_state.get("tab2_review") if recheck else None) or {"marks": {}, "added": []}
    ctx = {
        "file": audit_file.name, "special_focus": res["special"], "criteria": res["focus"],
        "use_kb": use_wiki_rag, "sections": res["sections"], "failed_sections": len(failed_sections),
        "findings": len(res["findings"]), "unverified": len(res.get("unverified", [])), "prompts": res["prompts"],
        "document_mode": res.get("document_mode"), "audit_id": aid,
    }
    _show(audit_file.name, res, rows, review, res["log"], aid, ctx,
          _docx_review(doc_bytes, res) if HAS_DOCX and is_docx else None, reopened=False,
          meta=load_meta(cfg, aid) if aid else None)
    if failed_sections:
        status.update(label=tr("🏁 Экспертиза завершена, но {n_failed_sections} из {n_sections} разделов не проверены", n_failed_sections=len(failed_sections), n_sections=res["sections"]), state="error", expanded=True)
    else:
        status.update(label=tr("🏁 Аналитическая экспертиза завершена!"), state="complete", expanded=False)


def _open_saved(cfg, aid):
    """Сохранённый аудит — на экран (без перепроверки: состояния прогона на диске нет)."""
    saved = load_audit(cfg, aid)
    if not saved:
        st.warning(tr("Аудит не найден: {v}", v=aid))
        return
    meta, res = saved["meta"], dict(saved["result"])
    res.update(report=saved["report"], log_md=saved["log_md"])
    res.setdefault("findings", [])
    res["failed_sections"] = [tuple(x) for x in res.get("failed_sections") or []]
    name = meta.get("file") or aid
    doc = load_document(cfg, aid)
    ctx = {"file": name, "special_focus": meta.get("special", ""), "criteria": meta.get("criteria", ""),
           "use_kb": meta.get("use_kb"), "sections": meta.get("sections", 0), "failed_sections": meta.get("failed", 0),
           "findings": len(res["findings"]), "unverified": len(res.get("unverified") or []),
           "prompts": meta.get("prompts", ""), "document_mode": meta.get("document_mode"), "audit_id": aid,
           "reopened": True}
    _show(name, res, saved["rows"], saved["review"], [], aid, ctx,
          _docx_review(doc, res) if HAS_DOCX and doc else None, reopened=True, meta=meta)
    # таблица своих замечаний — заново из сохранённого разбора (новый ключ: правки прежней таблицы не повторяются)
    st.session_state[f"rv_ver::{aid}"] = st.session_state.get(f"rv_ver::{aid}", 0) + 1


def _audit_label(meta):
    prog = meta.get("progress") or {}
    done = (tr(" · разобрано {m} из {n}", m=prog.get("marked", 0), n=prog.get("total", 0))
            if prog.get("marked") or prog.get("added") else "")
    return tr("{t} · {f} · {m} · замечаний {n}", t=meta.get("time", ""), f=meta.get("file", ""),
              m=meta.get("model") or "—", n=meta.get("findings", 0)) + done


def _render_my_audits(cfg):
    """«📂 Мои аудиты»: сохранённые аудиты — открыть, удалить, выгрузить все разборы."""
    audits = list_audits(cfg)
    # подпись постоянная: блок с другой подписью Streamlit считает новым и сворачивает его
    with st.expander(tr("📂 Мои аудиты")):
        st.caption(tr("Каждый аудит сохраняется на этом компьютере ({p}): заключение, лог, документ с замечаниями и "
                      "разбор эксперта. Откройте аудит, чтобы продолжить разбор замечаний.", p=audits_root(cfg)))
        if not audits:
            st.caption(tr("Сохранённых аудитов пока нет."))
            return
        by_id = {m["id"]: m for m in audits}
        aid = st.selectbox(tr("Аудит"), list(by_id), key="tab2_saved_pick", format_func=lambda a: _audit_label(by_id[a]))
        c1, c2, c3 = st.columns([1, 1, 1.4])
        with c1:
            if st.button(tr("📂 Открыть"), key="tab2_saved_open", **btn_w):
                _open_saved(cfg, aid)
        with c2:
            sure = st.checkbox(tr("Да, удалить"), key="tab2_saved_sure")
        with c3:
            if st.button(tr("🗑️ Удалить аудит"), key="tab2_saved_delete", disabled=not sure, **btn_w):
                delete_audit(cfg, aid)
                if st.session_state.get("tab2_saved_id") == aid:
                    st.session_state["tab2_saved_id"] = None
                for k in ("tab2_saved_sure", "tab2_saved_pick"):
                    st.session_state.pop(k, None)
                st.rerun()
        reviewed = [m for m in audits if (m.get("progress") or {}).get("marked") or (m.get("progress") or {}).get("added")]
        st.markdown(tr("**📤 Все разборы для улучшения MINT** — аудитов с разбором: {n}", n=len(reviewed)))
        no_texts = st.checkbox(tr("Без текстов замечаний"), value=False, key="tab2_export_notext",
                               help=tr("Только виды проверок, критичность, отметки и причины — без текстов "
                                       "замечаний, цитат, разделов, комментариев и имени файла."))
        if st.button(tr("📤 Собрать разборы"), key="tab2_export_all", disabled=not reviewed):
            lines = []
            for m in reviewed:
                saved = load_audit(cfg, m["id"])
                if saved:
                    lines.append(json.dumps(export_review(saved["meta"], saved["rows"], saved["review"],
                                                          texts=not no_texts), ensure_ascii=False))
            st.session_state["_tab2_export_all"] = (no_texts, "\n".join(lines) + "\n", len(lines))
        ready = st.session_state.get("_tab2_export_all")
        if ready and ready[0] == no_texts:
            st.download_button(tr("📥 Скачать разборы ({n}, .jsonl)", n=ready[2]), data=ready[1],
                               file_name=time.strftime("mint-reviews_%Y%m%d.jsonl"), mime="application/json",
                               key="tab2_export_all_dl")
        st.caption(tr("Сводка по файлам разборов — tools/review_stats.py. С текстами в файле есть цитаты документов: "
                      "передавайте его только туда, куда можно передавать сами документы."))


def _point_entries(result):
    """Ответы на пункты: особое внимание, чек-лист, требования к системам."""
    return [e for k in ("focus_answers", "checklist_answers", "system_answers") for e in result.get(k) or []]


def _lines(text):
    return [x.strip(" \t-•*–—") for x in (text or "").split("\n") if x.strip(" \t-•*–—")]


def _render_checklist(md_text, filename):
    """Чек-лист по типу документа: тип (авто или вручную), пункты на этот прогон, сохранение в свой файл.
    → (пункты, название типа)."""
    data = load_checklists()
    types = {t["name"]: t for t in data["types"]}
    detected, word = detect_document_type(md_text, filename, data)
    auto, none = "__auto__", "__none__"
    if "_tab2_doc_type_next" in st.session_state:     # тип добавлен или удалён — выбор меняется до виджета
        st.session_state["tab2_doc_type"] = st.session_state.pop("_tab2_doc_type_next")
    choice = st.session_state.get("tab2_doc_type", auto)
    if choice not in (auto, none) and choice not in types:      # тип удалён из чек-листов — снова «Авто»
        choice = st.session_state["tab2_doc_type"] = auto
    doc_type = detected if choice == auto else types.get(choice)
    type_name = doc_type["name"] if doc_type else ""
    use = st.session_state.get("tab2_checklist_on", True)
    k_common, k_type = "tab2_cl_common", f"tab2_cl_items::{type_name}"
    st.session_state.setdefault(k_common, "\n".join(data["common"]))
    if doc_type:
        st.session_state.setdefault(k_type, "\n".join(doc_type["items"]))
    items = list(dict.fromkeys(_lines(st.session_state[k_common]) + (_lines(st.session_state[k_type]) if doc_type else [])))
    label = (tr("📋 Чек-лист: {t} — пунктов {n}", t=type_name or tr("общие пункты"), n=min(len(items), CHECKLIST_MAX))
             if use else tr("📋 Чек-лист: выключен"))
    with st.expander(label):
        use = st.checkbox(tr("Проверить документ по чек-листу (+1 вызов LLM на пункт)"), value=True,
                          key="tab2_checklist_on")
        options = [auto] + list(types) + [none]
        st.selectbox(
            tr("Тип документа"), options, key="tab2_doc_type",
            format_func=lambda o: (tr("Авто: {t}", t=detected["name"]) if detected else tr("Авто: тип не определён"))
            if o == auto else tr("Без типа — только общие пункты") if o == none else o,
            help=tr("Авто — по словам из названия документа (имя файла и начало документа), их список — у каждого "
                    "типа в чек-листах. Каждый пункт — отдельный вопрос модели по всему документу; ответ «да / "
                    "частично / нет / не относится» и замечания — в блоке «Чек-лист» заключения."))
        if choice == auto:
            st.caption(tr("Тип определён по словам «{w}».", w=word) if detected else
                       tr("Тип не определён: в начале документа нет слов ни одного типа — будут только общие пункты."))
        st.text_area(tr("Общие пункты (для любого документа), по одному на строку:"), key=k_common, height=120)
        if doc_type:
            st.text_area(tr("Пункты для типа «{t}», по одному на строку:", t=type_name), key=k_type, height=160)
        if len(items) > CHECKLIST_MAX:
            st.warning(tr("Пунктов {n} — проверяются первые {m}.", n=len(items), m=CHECKLIST_MAX))
        source = {"file": tr("свой файл {p}", p=Path(data["path"]).name),
                  "example": tr("образец {p} (свой файл ещё не создан)", p=Path(data["path"]).name),
                  "none": tr("чек-листов нет")}[data["source"]]
        st.caption(tr("Чек-листы: {v}. Правки выше действуют на этот прогон; «Сохранить» записывает их в {own} — "
                      "этот файл не попадает в репозиторий и не затирается при обновлении.", v=source,
                      own=checklists_path().name))
        if st.button(tr("💾 Сохранить пункты в чек-листы"), key="tab2_cl_save"):
            new = {"common": _lines(st.session_state[k_common]), "types": [dict(t) for t in data["types"]]}
            for t in new["types"]:
                if doc_type and t["name"] == type_name:
                    t["items"] = _lines(st.session_state[k_type])
            st.toast(tr("Сохранено: {p}", p=save_checklists(new)))
        if st.checkbox(tr("⚙️ Типы документов: добавить, изменить слова, удалить"), key="tab2_cl_types"):
            _render_type_editor(data, doc_type)
    if not use:
        return [], type_name
    return items[:CHECKLIST_MAX], type_name


def _render_basis(cfg, md_text, filename, use_wiki):
    """Документы-основания: документы базы, на которые проверяемый документ ссылается как на своё основание
    (найдены по шифру или названию) — можно снять или добавить свои. → список документов базы для аудита."""
    if not use_wiki:
        return []
    if not cfg.audit_basis_docs:
        return []
    key = (filename, len(md_text or ""), hash((md_text or "")[:6000]))
    saved = st.session_state.get("_tab2_basis_auto")
    if not saved or saved[0] != key:
        try:
            expert = load_expert_materials(cfg)
        except Exception:
            expert = None
        info = audit_basis_documents(md_text, filename, cfg, expert=expert)
        saved = (key, info)
        st.session_state["_tab2_basis_auto"] = saved
        st.session_state["tab2_basis_docs"] = [d["source"] for d in info["docs"]]
    info = saved[1]
    names = list_kb_documents(cfg)[0]
    chosen = [d for d in st.session_state.get("tab2_basis_docs") or [] if d in names]
    label = (tr("📎 Документы-основания из базы: {n}", n=len(chosen)) if chosen else
             tr("📎 Документы-основания: в базе не найдены") if info["refs"] else
             tr("📎 Документы-основания: документ на них не ссылается"))
    with st.expander(label):
        st.caption(tr("Документы, по которым разработан проверяемый документ: MINT берёт ссылки с титула («в "
                      "соответствии с …», «на основании …») и из раздела «Ссылочные документы» и ищет их в базе по "
                      "шифру и названию. Их фрагменты, ближайшие к разделу, модель получает в каждой проверке — "
                      "«документ должен им соответствовать»."))
        st.multiselect(tr("Документы базы — основания этого документа"), names, key="tab2_basis_docs",
                       help=tr("Снимите лишний или добавьте документ, которого MINT не узнал (например, техническое "
                               "задание, по которому разработан документ). Лимит текста на один запрос — «⚙️ Настройки "
                               "аудита» → «Документы-основания на запрос»."))
        by = {"code": tr("по шифру"), "title": tr("по названию")}
        for d in info["docs"]:
            st.caption(tr("📎 {src} — найден {by}: {ref}", src=d["source"], by=by.get(d["by"], d["by"]),
                          ref=reference_label(d["ref"])))
        if info["missing"]:
            st.caption(tr("Нет в базе: {v}. Загрузите их в базу, если они нужны для проверки.",
                          v="; ".join(reference_label(r) for r in info["missing"][:8])))
    return [d for d in st.session_state.get("tab2_basis_docs") or [] if d in names]


def _render_type_editor(data, current):
    """Новый тип документа, слова распознавания и удаление типа — запись в свой файл чек-листов."""
    if current:
        words = st.text_input(tr("Слова, по которым узнаётся «{t}» (через «;»):", t=current["name"]),
                              value="; ".join(current["match"]), key=f"tab2_cl_match::{current['name']}")
        c1, c2 = st.columns(2)
        with c1:
            if st.button(tr("💾 Сохранить слова"), key="tab2_cl_match_save"):
                new = {"common": data["common"], "types": [dict(t) for t in data["types"]]}
                for t in new["types"]:
                    if t["name"] == current["name"]:
                        t["match"] = [w.strip() for w in words.split(";") if w.strip()]
                save_checklists(new)
                st.rerun()
        with c2:
            if st.button(tr("🗑️ Удалить тип «{t}»", t=current["name"]), key="tab2_cl_delete"):
                save_checklists({"common": data["common"],
                                 "types": [t for t in data["types"] if t["name"] != current["name"]]})
                st.session_state["_tab2_doc_type_next"] = "__auto__"
                st.rerun()
    name = st.text_input(tr("Новый тип документа:"), key="tab2_cl_new_name",
                         placeholder=tr("Например: Задание на доработку"))
    words = st.text_input(tr("Слова для распознавания (через «;»):"), key="tab2_cl_new_match",
                          placeholder=tr("например: задание на доработку; заданию на доработку"))
    if st.button(tr("➕ Добавить тип"), key="tab2_cl_add", disabled=not name.strip()):
        if name.strip() in {t["name"] for t in data["types"]}:
            st.warning(tr("Тип «{t}» уже есть.", t=name.strip()))
        else:
            save_checklists({"common": data["common"], "types": data["types"] + [
                {"name": name.strip(), "match": [w.strip() for w in words.split(";") if w.strip()], "items": []}]})
            st.session_state["_tab2_doc_type_next"] = name.strip()
            st.rerun()


def _render_reference(cfg, name):
    """Сверка заключения с эталоном: какие из ожидаемых замечаний нашла выбранная модель."""
    result = st.session_state.get("tab2_audit_result")
    if not result:
        return
    with st.expander(tr("📏 Сверка с эталоном — что нашла модель из ожидаемых замечаний")):
        reference = st.text_area(
            tr("Ожидаемые замечания (по одному на строку):"), key="tab2_reference", height=150,
            help=tr("Замечания эксперта или прошлого согласования этого документа. Модель сверяет их с заключением: "
                    "то же место и та же суть, формулировка может отличаться (+1 вызов LLM). Прогоните аудит с другой "
                    "моделью или настройками и сверьте снова — так видно, какая модель что находит."))
        if st.button(tr("📏 Сверить с эталоном"), key="tab2_reference_btn", **btn_w):
            with st.spinner(tr("Сверка с эталоном...")):
                cmp = compare_with_reference(result, reference, cfg)
            st.session_state["tab2_reference_result"] = (name, cfg.llm_model, cmp)
        saved = st.session_state.get("tab2_reference_result")
        if saved and saved[0] == name:
            md = reference_markdown(saved[2], name, replace(cfg, llm_model=saved[1]))
            st.markdown(md.split("\n", 2)[2])
            st.download_button(tr("📥 Скачать сверку (.md)"), data=md, key="tab2_reference_dl",
                               file_name=tr("Сверка_с_эталоном_{v}.md", v=os.path.splitext(name)[0]),
                               mime="text/markdown")


def _yes(v):
    return tr("да") if v else tr("нет")


def _render_audit_settings(cfg):
    """Все настройки аудита в одном месте: что проверять, качество и время, объём контекста. Значения — на время
    сеанса (как «Экспертные настройки» в боковой панели), постоянные — в config.yaml. → (база, глубокая, целиком)."""
    base_cfg, info = st.session_state.get("_mint_audit_settings") or (cfg, {})
    manual = st.session_state.setdefault("mint_manual", {})
    # подпись блока постоянная: блок с другой подписью Streamlit считает новым и сворачивает его после каждой правки
    with st.expander(tr("⚙️ Настройки аудита")):
        use_wiki_rag = st.checkbox(
            tr("🧠 Подключать нормативную базу при анализе"), value=True, key="tab2_wiki_rag",
            help=tr("Для каждого раздела документа из базы подбираются нормативные фрагменты, и модель проверяет "
                    "раздел с их учётом. Без базы аудит идёт только по тексту документа (быстрее, но без опоры на "
                    "регламенты)."),
        )
        use_deep = st.checkbox(
            tr("🔬 Глубокая проверка (процесс по шагам, противоречия, цифры, опечатки)"), value=cfg.audit_deep,
            key="tab2_deep",
            help=tr("Кроме проверки разделов модель отвечает на много узких вопросов: каждая пара соседних шагов процесса "
                    "(таблица операций, список шагов или разделы «Шаг N»), каждое требование к процессу, границы "
                    "процесса; утверждения разных разделов на одну тему; "
                    "согласованность цифр (расчёт делает программа); опечатки. Узкий вопрос надёжно решает и модель "
                    "среднего размера. Это десятки коротких вызовов LLM (не больше {n}, по {p} одновременно).",
                    n=cfg.audit_deep_max_calls or "∞", p=cfg.audit_parallel),
        )
        use_whole = st.checkbox(
            tr("📄 Весь документ одним запросом (для сравнения)"), value=False, key="tab2_whole",
            help=tr("Вместо проверки по разделам модель получает весь документ и пишет все замечания одним ответом (до "
                    "{t} токенов, таймаут не меньше {s} с). Быстрее и без повторов, но модели среднего размера в таком "
                    "режиме обычно находят меньше конкретных замечаний. Сравните оба режима «Сверкой с эталоном». Не "
                    "помещается в окно модели — проверка по разделам.", t=WHOLE_MAX_TOKENS, s=WHOLE_TIMEOUT),
        )
        for title, specs in AUDIT_SETTINGS:
            st.caption(f"**{tr(title)}**")
            for spec in specs:
                _expert_widget(spec, base_cfg, info, manual)
        acfg = audit_cfg(cfg)
        st.caption(tr("Запрос аудита к модели: таймаут {t} с, ответ до {n} токенов, рассуждения — {r}. Модель, таймаут "
                      "и длина ответа — в боковой панели («Модели и лимиты», «Экспертные настройки» → «Языковая "
                      "модель»).", t=acfg.llm_timeout, n=acfg.max_tokens,
                      r=(tr("включены для аудита (таймаут не меньше {s} с)", s=REASONING_TIMEOUT) if cfg.audit_reasoning
                         else tr("выключены") if cfg.llm_no_reasoning else tr("как настроено на сервере"))))
        st.caption(tr("Значения действуют на время сеанса (✋ вручную); постоянные — в config.yaml, раздел audit. "
                      "«↩️ Сбросить изменения сеанса» в «Экспертных настройках» возвращает и их."))
    reasoning = (tr("включены для аудита") if cfg.audit_reasoning else tr("выключены") if cfg.llm_no_reasoning
                 else tr("как настроено на сервере"))
    st.caption(tr("Сейчас: база — {kb} · глубокая проверка — {deep} · проходов — {p} · рассуждения — {r} · "
                  "самокритика — {c} · сведение повторов — {m} · «Главное» — {s}", kb=_yes(use_wiki_rag),
                  deep=_yes(use_deep), p=audit_passes(cfg), r=reasoning, c=_yes(cfg.use_self_critique),
                  m=_yes(cfg.audit_merge_duplicates), s=cfg.audit_summary_max or tr("нет")))
    return use_wiki_rag, use_deep, use_whole


def render_audit_tab(cfg, gl):
    """Вкладка «Аудит документа»: проверка документа по критериям и нормам из базы."""
    st.subheader(tr("🛡️ Экспертный аудит документа"))
    st.info(tr("Загрузите документ на проверку — любой: договор, положение, отчёт, техническое задание, курсовую. "
               "MINT проверит каждый раздел по вашим критериям и по документам из базы знаний."))
    _render_my_audits(cfg)
    use_wiki_rag, use_deep, use_whole = _render_audit_settings(cfg)
    audit_file = st.file_uploader(
        tr("Загрузить документ на согласование (.docx, .pdf, .md, .txt)"), type=list(SUPPORTED_FORMATS),
        key="tab2_audit_uploader",
        help=tr("Документ преобразуется в Markdown и режется на разделы. Замечания примечаниями Word ставятся "
                "только в .docx; для других форматов — заключение и лог проверки."),
    )
    special_focus = st.text_area(
        tr("🎯 Особое внимание (необязательно):"), value="", key="tab2_special_focus", height=90,
        placeholder=tr("Например: интеграция с системой X; хранение и передача персональных данных; резервное "
                       "копирование и время восстановления"),
        help=tr("То, что важно именно в этом документе. На каждый пункт модель отвечает отдельно, по всему "
                "документу (блок «Ответы на пункты особого внимания» в заключении); при проверке разделов эти места "
                "проверяются в первую очередь, а самокритика не удаляет замечания по ним без опровержения в тексте. "
                "Каждый пункт — с новой строки, через «;» или вопросом."),
    )
    # Критерии профиля — на языке интерфейса; при смене языка не тронутые пользователем критерии меняются
    # (значение задаётся через session_state, а не value=: иначе Streamlit предупреждает о двух источниках значения)
    if st.session_state.get("tab2_user_focus") in ({None, DEFAULT_AUDIT_FOCUS, DEFAULT_AUDIT_FOCUS_EN}
                                                    | all_profile_focus_texts()):
        st.session_state["tab2_user_focus"] = default_audit_focus()
    user_focus = st.text_area(
        tr("📝 Общие критерии проверки:"), key="tab2_user_focus", height=140,
        help=tr("Список проверок для каждого раздела — критерии профиля (боковая панель → «🧭 Профиль»). Можно "
                "сократить или переписать под конкретный документ; пустое поле заменяется общим аудитом."),
    )

    just_ran = False
    if audit_file is not None:
        st.success(tr("Файл '{name}' готов к проверке.", name=audit_file.name))
        if (st.session_state.get("compiled_markdown_filename") != audit_file.name
                or "compiled_markdown_data" not in st.session_state):
            with st.spinner(tr("🔍 Разбор документа...")):
                try:
                    st.session_state["compiled_markdown_data"] = document_to_markdown(
                        audit_file.name, bytes(audit_file.getbuffer()))
                except DocumentUnreadable as e:
                    st.error(str(e))
                    return
                st.session_state["compiled_markdown_filename"] = audit_file.name

        col_md, _ = st.columns([0.4, 0.6])
        with col_md:
            st.download_button(
                label=tr("🔍 Как прочитан документ (.md)"), data=st.session_state["compiled_markdown_data"],
                file_name=f"{os.path.splitext(audit_file.name)[0]}_compiled.md", mime="text/markdown",
                key="tab2_instant_md_download", **dl_w,
            )

        checklist, doc_type = _render_checklist(st.session_state["compiled_markdown_data"], audit_file.name)
        basis = _render_basis(cfg, st.session_state["compiled_markdown_data"], audit_file.name, use_wiki_rag)

        if st.button(tr("🚀 Запустить аудит документа"), key="tab2_run_btn", **btn_w):
            just_ran = True
            with st.status(tr("Запущен конвейер смыслового аудита..."), expanded=True) as status:
                ui = {}

                def on_progress(event, **d):
                    if event == "whole_too_big":
                        st.warning(tr("Документ ({c} симв.) не помещается в окно модели одним запросом (места — {r} "
                                      "симв.): проверка по разделам. Задайте настоящее окно в «Модели и лимиты».",
                                      c=d["chars"], r=d["room"]))
                    elif event == "sections":
                        if d.get("mode") == "whole":         # лимит части не действует: документ — один запрос
                            st.write(tr("📜 Весь документ ({chars} симв.) проверяется одним запросом.",
                                        chars=d.get("chars", 0)))
                        else:
                            st.write(tr("📜 Документ разбит на части по разделам: {n_sections} (до {audit_map_size} "
                                        "симв.).", n_sections=d["n"], audit_map_size=cfg.audit_map_size)
                                     + " " + tr(_MODE_NOTES[d.get("mode", "outline")]))
                    elif event == "basis":
                        if d["docs"]:
                            st.write(tr("📎 Документы-основания: {v}", v="; ".join(x["source"] for x in d["docs"])))
                    elif event == "checks":
                        if d["findings"]:
                            st.write(tr("🔤 Проверка сокращений: ") + " ".join(f["text"] for f in d["findings"]))
                    elif event == "points":
                        parts = []
                        if d["focus"]:
                            parts.append(tr("особое внимание — {n}", n=d["focus"]))
                        if d["checklist"]:
                            parts.append(tr("чек-лист — {n}", n=d["checklist"]))
                        if d["systems"]:
                            parts.append(tr("требования к системам — {v}", v=", ".join(d["systems"])))
                        st.write(tr("📋 Вопросы по всему документу: {v} (по {p} одновременно).", v="; ".join(parts),
                                    p=d["parallel"]))
                        ui["points_log"] = st.container()
                    elif event in ("focus_answer", "checklist_answer", "system_answer"):
                        if "points_log" not in ui:
                            ui["points_log"] = st.container()
                        with ui["points_log"]:
                            render_audit_log_entry(d["entry"])
                    elif event == "merge":
                        if d["error"]:
                            st.write(tr("🧩 Сведение повторов не выполнено: {err}", err=d["error"]))
                        elif d["groups"]:
                            st.write(tr("🧩 Повторы сведены: групп {g}, замечаний было {a}, стало {b}.",
                                        g=d["groups"], a=d["before"], b=d["after"]))
                    elif event == "focus_norms":
                        st.write(tr("🎯 Нормы по «особому вниманию»: ")
                                 + ("; ".join(it["short"] for it in d["items"]) if d["items"]
                                    else tr("в базе не найдены — пункты проверяются по тексту документа")))
                    elif event == "retry":
                        st.write(tr("🔁 Не проверено разделов: {n} — проверяю их ещё раз с таймаутом {t} с.",
                                    n=d["n"], t=d["timeout"]))
                        ui.clear()
                    elif event == "section":
                        if not ui:
                            ui["bar"], ui["log"] = st.progress(0), st.container()
                        with ui["log"]:
                            render_audit_log_entry(d["entry"])
                        ui["bar"].progress((d["index"] + 1) / d["total"])
                    elif event == "pass":
                        st.write(tr("🔂 Проход {n} из {t}: разделов — {s}, вопросов глубокой проверки — {d} "
                                    "(температура {temp}).", n=d["n"], t=d["total"], s=d["sections"], d=d["deep"],
                                    temp=d["temperature"]))
                        ui.clear()
                        ui["bar"], ui["log"] = st.progress(0), st.container()
                        if d["deep"]:
                            ui["deep_bar"], ui["deep_done"] = st.progress(0), 0
                    elif event == "summary":
                        if d["error"]:
                            st.write(tr("⭐ «Главное» выбрано без модели ({err}): {n}.", err=d["error"][:120], n=d["n"]))
                        elif d["n"]:
                            st.write(tr("⭐ «Главное» — в начале заключения (замечаний: {n}).", n=d["n"]))
                    elif event == "deep":
                        st.write(tr("🔬 Глубокая проверка: вопросов модели — {n}, по {p} одновременно.", n=d["n"],
                                    p=d["parallel"])
                                 + (" " + tr("Пропущено по лимиту: {s}.", s=d["skipped"]) if d["skipped"] else ""))
                        ui["deep_bar"], ui["deep_done"] = st.progress(0), 0
                    elif event == "deep_task":
                        if "deep_bar" in ui:
                            ui["deep_done"] += 1
                            ui["deep_bar"].progress(min(1.0, ui["deep_done"] / max(1, d["total"])),
                                                    text=d["entry"]["title"][:90])

                res = run_audit(st.session_state["compiled_markdown_data"], audit_file.name, cfg, focus=user_focus,
                                special=special_focus, use_wiki=use_wiki_rag, glossary=gl, on_progress=on_progress,
                                deep=use_deep, whole=use_whole, checklist=checklist, doc_type=doc_type,
                                basis=basis if use_wiki_rag and cfg.audit_basis_docs else None)
                _store_result(cfg, res, audit_file, use_wiki_rag, status)

        result = st.session_state.get("tab2_audit_result")
        n_failed = (len(result["failed_sections"]) + sum(1 for e in _point_entries(result) if e["failed"])
                    + sum(1 for e in result.get("deep") or [] if e["failed"]) if result else 0)
        # перепроверка — только у аудита этого сеанса: у открытого из «Моих аудитов» нет состояния прогона
        if (st.session_state.get("tab2_audit_active_file") == audit_file.name and n_failed and not just_ran
                and (result or {}).get("state")):
            if st.button(tr("🔁 Перепроверить непроверенные разделы ({n})", n=n_failed), key="tab2_recheck_btn",
                         help=tr("Ещё раз проверить только те разделы, на которых модель не ответила, с таймаутом {t} с. "
                                 "Новые замечания добавятся к заключению; уже проверенные разделы не повторяются.",
                                 t=retry_timeout(cfg)), **btn_w):
                just_ran = True
                with st.status(tr("Перепроверка непроверенных разделов..."), expanded=True) as status:
                    box = st.container()

                    def on_recheck(event, **d):
                        if event == "retry":
                            box.write(tr("🔁 Разделов: {n}, таймаут {t} с.", n=d["n"], t=d["timeout"]))
                        elif event in ("section", "focus_answer", "checklist_answer", "system_answer"):
                            with box:
                                render_audit_log_entry(d["entry"])
                        elif event == "deep_task":
                            box.write(("❌ " if d["entry"]["failed"] else "✓ ") + d["entry"]["title"])

                    res = recheck_failed_sections(result, audit_file.name, cfg, on_progress=on_recheck)
                    _store_result(cfg, res, audit_file, st.session_state.get("tab2_wiki_rag", True), status,
                                  recheck=True)


    name = st.session_state.get("tab2_audit_active_file")
    if "tab2_final_report_data" in st.session_state and name and (audit_file is None or audit_file.name == name):
        _render_results(cfg, name, just_ran)


def _raw_answers(cfg, name):
    """Сырые ответы модели: с диска (сохранённый аудит) или из состояния прогона."""
    aid = st.session_state.get("tab2_saved_id")
    if aid:
        cached = st.session_state.get("_tab2_raw")
        if not cached or cached[0] != aid:              # с диска — один раз, а не на каждой перерисовке
            cached = st.session_state["_tab2_raw"] = (aid, load_raw(cfg, aid))
        if cached[1]:
            return cached[1]
    result_ = st.session_state.get("tab2_audit_result") or {}
    if result_.get("raw_md"):
        return result_["raw_md"]
    return raw_answers_markdown(result_, name) if (result_.get("state") or {}).get("raw") else ""


def _render_results(cfg, name, just_ran):
    """Заключение, лог, файлы, сверка с эталоном, разбор экспертом и оценка — у аудита этого сеанса и у открытого
    из «📂 Мои аудиты»."""
    ss = st.session_state
    stem = os.path.splitext(name)[0]
    st.markdown(tr("## 📄 Итоговое экспертное заключение"))
    ctx = ss.get("tab2_feedback_ctx") or {}
    if ss.get("tab2_reopened"):
        st.caption(tr("Открыт сохранённый аудит: {f}.", f=name))
    st.markdown(audit_verdict_html(ss.get("tab2_findings"), ctx.get("failed_sections", 0), ctx.get("sections", 0)),
                unsafe_allow_html=True)
    st.markdown(ss["tab2_final_report_data"])
    saved_log = (ss.get("tab2_audit_log") or []) + _point_entries(ss.get("tab2_audit_result") or {})
    if saved_log and not just_ran:   # после перерисовки (например, после скачивания) лог не пропадает
        st.caption(tr("⚙️ Лог проверки по разделам ({n_saved_log}):", n_saved_log=len(saved_log)))
        for entry in saved_log:
            render_audit_log_entry(entry)
    deep_log = (ss.get("tab2_audit_result") or {}).get("deep") or []
    if deep_log:
        render_deep_log(deep_log)
    _render_reference(cfg, name)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            label=tr("📥 Скачать заключение (.md)"), data=ss["tab2_final_report_data"],
            file_name=tr("Заключение_{name}.md", name=name), mime="text/markdown",
            key="tab2_final_md_download",
        )
    with c2:
        docx_bytes, docx_stats = ss.get("tab2_docx_review") or (None, {})
        if docx_bytes:
            st.download_button(
                label=tr("📥 Скачать документ с замечаниями (.docx)"), data=docx_bytes,
                file_name=tr("Аудит_MINT_{name}", name=name),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="tab2_final_docx_review_download",
                help=tr("Замечания добавлены примечаниями Word (текст документа не меняется) — каждое к одному месту: "
                        "по цитате из самокритики или к абзацу с наибольшим совпадением слов. Замечания, которые не "
                        "удалось однозначно привязать, — списком в начале документа."),
            )
            how = tr("примечаниями") if docx_stats.get("mode") == "comments" else tr("вставками в текст")
            st.caption(tr("Привязано {how}: {v} (по цитате — {v2}); списком в начале: {v3}.", how=how, v=docx_stats.get('bound', 0), v2=docx_stats.get('by_quote', 0), v3=docx_stats.get('unbound', 0)))
        elif docx_stats.get("error"):
            st.warning(tr("📥 Экспорт рецензии в Word недоступен: {error}", error=docx_stats['error']))
        elif document_format(name) != "docx":
            st.caption(tr("Примечания в документ ставятся только для .docx — для этого формата есть "
                          "заключение и лог проверки."))
    with c3:
        if ss.get("tab2_audit_log_md"):
            st.download_button(
                label=tr("📥 Скачать лог проверки (.md)"), data=ss["tab2_audit_log_md"],
                file_name=tr("Лог_проверки_{v}.md", v=stem), mime="text/markdown",
                key="tab2_log_md_download",
                help=tr("Настройки прогона и по каждому разделу: результат, нормативные источники, отклонённое "
                        "самокритикой. Нужен для разбора пропусков при тестировании."),
            )
        raw = _raw_answers(cfg, name)
        if raw:
            st.download_button(
                label=tr("📥 Скачать сырые ответы модели (.md)"), data=raw,
                file_name=tr("Сырые_ответы_{v}.md", v=stem), mime="text/markdown",
                key="tab2_raw_answers_download",
                help=tr("Каждый запрос к модели во время аудита и сверки с эталоном и её ответ слово в слово — до "
                        "разбора на замечания. Файл большой; нужен, чтобы разобрать спорный случай."),
            )
    aid = ss.get("tab2_saved_id")
    document = (lambda: load_document(cfg, aid)) if aid and document_format(name) == "docx" else None
    meta = ss.get("tab2_meta") or {k: v for k, v in ctx.items() if k not in ("report",)}
    render_expert_review(cfg, aid, name, ss.get("tab2_rows") or [], document=document, meta=meta)
    st.markdown(tr("**Оцените проверку:** найдены ли важные замечания, нет ли лишних и ошибочных?"))
    render_feedback(cfg, "audit", ss.get("tab2_audit_id") or "audit", subject=name,
                    context=lambda: {**ss.get("tab2_feedback_ctx", {}), "report": ss["tab2_final_report_data"]})

"""Интерфейс: разбор замечаний аудита экспертом (блок «✍️ Разбор замечаний экспертом» под заключением) и выгрузка
разбора для улучшения MINT. Ядро — mint/expert_review.py, хранение — mint/audit_store.py.

По каждому замечанию эксперт ставит отметку «✅ беру / ➖ мелочь / ❌ неверно» (у «неверно» — причина из списка),
добавляет свои замечания, которых MINT не нашёл, и скачивает «Мои замечания» (Word, Markdown) или документ с ними
примечаниями Word. Отметки сохраняются сразу: разбор можно продолжить позже из «📂 Мои аудиты».
"""

import json
import logging
import math
import os

import streamlit as st

from ..audit import _SEV_PREFIX, _SEVERITIES, annotate_docx_with_findings, normalize_severity
from ..audit_store import save_review
from ..expert_review import (BLOCKS, KINDS, REASONS, VERDICTS, accepted_findings, added_remarks, export_review, mark,
                             my_remarks, my_remarks_docx, my_remarks_markdown, review_progress)
from ..i18n import N_, tr
from .common import _width_kwargs
from .quality import records

logger = logging.getLogger("MINT")

PAGE_SIZE = 15
FILTERS = {"all": N_("все"), "main": N_("основные и ответы на пункты"), "unverified": N_("не подтверждено"),
           "minor": N_("мелкие"), "typo": N_("опечатки")}
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _filtered(rows, flt):
    if flt == "main":
        return [r for r in rows if r["block"] in ("main", "point")]
    if flt in ("unverified", "minor", "typo"):
        return [r for r in rows if r["block"] == flt]
    return list(rows)


def _keys(aid, row):
    base = f"rv::{aid}::{row['key']}"
    return base + "::v", base + "::r", base + "::c"


def _card(aid, row, review):
    """Одно замечание: где и кем найдено, текст и цитата, отметка, причина (для «неверно»), комментарий."""
    kv, kr, kc = _keys(aid, row)
    m = mark(review, row)
    ss = st.session_state
    ss.setdefault(kv, m.get("verdict") or "")
    ss.setdefault(kc, m.get("comment") or "")
    head = [f"**{row['ref'] or tr(BLOCKS[row['block']])}**"]
    if row["section"]:
        head.append(row["section"])
    head.append(tr(KINDS.get(row["kind"], KINDS["section"])))
    if row["star"]:
        head.append(tr("⭐ в «Главном»"))
    if row["basis"]:
        head.append(tr("📎 по документу-основанию"))
    if row["found_by"] > 1:
        head.append(tr("нашли проверок: {n}", n=row["found_by"]))
    with st.container(border=True):
        st.caption(" · ".join(head))
        st.markdown(f"{tr(_SEV_PREFIX.get(row['severity'], _SEV_PREFIX['СРЕДНИЙ']))} {row['text']}")
        if row["quote"]:
            st.caption(tr("Цитата: «{q}»", q=row["quote"][:400]))
        if row["unverified"]:
            st.caption(tr("Не найдено ни в документе, ни в нормах: {v}", v=", ".join(row["unverified"])))
        c1, c2, c3 = st.columns([3.6, 2.0, 2.2])     # четыре варианта отметки — в одну строку
        with c1:
            verdicts = {c: tr(v) for c, v in VERDICTS.items()}     # подписи на языке прогона (см. mint/ui/app.py)
            st.radio(tr("Отметка"), list(VERDICTS), key=kv, format_func=verdicts.get, horizontal=True,
                     label_visibility="collapsed")
        with c2:
            if ss.get(kv) == "wrong":
                ss.setdefault(kr, m.get("reason") or "")
                reasons = {c: tr(v) if c else tr("Причина: —") for c, v in REASONS.items()}
                st.selectbox(tr("Причина"), list(REASONS), key=kr, label_visibility="collapsed",
                             format_func=reasons.get)
        with c3:
            st.text_input(tr("Комментарий"), key=kc, label_visibility="collapsed",
                          placeholder=tr("комментарий (необязательно)"))
    return _widget_mark(aid, row, m)


def _widget_mark(aid, row, prev):
    """Отметка замечания по виджетам его карточки (prev — если карточки ещё не было на странице)."""
    kv, kr, kc = _keys(aid, row)
    ss = st.session_state
    if kv not in ss:
        return prev
    verdict = ss.get(kv) or ""
    new = {"verdict": verdict, "reason": (ss.get(kr, prev.get("reason")) or "") if verdict == "wrong" else "",
           "comment": (ss.get(kc, prev.get("comment")) or "").strip()}
    return {k: v for k, v in new.items() if v}


def _editor_rows(base, state):
    """Строки таблицы своих замечаний с правками, которые Streamlit хранит в состоянии виджета (edited_rows,
    added_rows, deleted_rows), — чтобы счётчики над таблицей были верными в той же перерисовке."""
    if not isinstance(state, dict):
        return None
    rows = [dict(r) for r in base]
    for i, changes in (state.get("edited_rows") or {}).items():
        if 0 <= int(i) < len(rows):
            rows[int(i)].update(changes or {})
    deleted = {int(i) for i in state.get("deleted_rows") or []}
    rows = [r for i, r in enumerate(rows) if i not in deleted]
    return rows + [dict(r) for r in state.get("added_rows") or []]


def _normalized_added(rows):
    out = []
    for r in rows:
        text = str(r.get("text") or "").strip()
        if text:
            out.append({"section": str(r.get("section") or "").strip(), "severity": _sev_code(r.get("severity")),
                        "text": text})
    return out


def _sev_options():
    return [tr(c) for c in _SEVERITIES]


def _sev_code(label):
    by_label = {tr(c): c for c in _SEVERITIES}
    return by_label.get(label) or normalize_severity(label)


def _added_editor(aid, review):
    """Свои замечания: то, чего MINT не нашёл. → список [{section, severity, text}] (непустые)."""
    ss = st.session_state
    ver = ss.get(f"rv_ver::{aid}", 0)                # растёт, когда аудит открывается заново из «Моих аудитов»
    base_key, editor_key = f"rv_added_base::{aid}::{ver}", f"rv_added::{aid}" + (f"::{ver}" if ver else "")
    # таблица строится заново из сохранённого разбора, если её не было на прошлой перерисовке (Streamlit тогда
    # забыл её правки): иначе устаревшие строки записались бы поверх сохранённых
    if base_key not in ss or editor_key not in ss:
        ss[base_key] = [{"section": a.get("section", ""), "severity": tr(normalize_severity(a.get("severity"))),
                         "text": a.get("text", "")} for a in added_remarks(review)] or [
            {"section": "", "severity": tr("СРЕДНИЙ"), "text": ""}]
    cc = st.column_config
    config = {
        "section": cc.TextColumn(tr("Раздел"), width="small"),
        "severity": cc.SelectboxColumn(tr("Критичность"), options=_sev_options(), default=tr("СРЕДНИЙ"),
                                       width="small"),
        "text": cc.TextColumn(tr("Замечание"), width="large"),
    }
    edited = st.data_editor(ss[base_key], key=editor_key, num_rows="dynamic", hide_index=True,
                            column_order=list(config), column_config=config, **_width_kwargs(st.data_editor))
    return _normalized_added(records(edited))


def _pending_added(aid, review):
    """Свои замечания с учётом правок таблицы, ещё не сохранённых (таблица ниже на странице)."""
    ss = st.session_state
    ver = ss.get(f"rv_ver::{aid}", 0)
    base_key, editor_key = f"rv_added_base::{aid}::{ver}", f"rv_added::{aid}" + (f"::{ver}" if ver else "")
    rows = _editor_rows(ss.get(base_key) or [], ss.get(editor_key)) if base_key in ss else None
    return added_remarks(review) if rows is None else _normalized_added(rows)


def _save(cfg, aid, rows, review, marks, added):
    """Разбор изменился — на диск и в сеанс. → актуальный разбор."""
    if marks == (review.get("marks") or {}) and added == added_remarks(review):
        return review
    review = {"marks": marks, "added": added}
    if aid:
        try:
            review = save_review(cfg, aid, review, rows=rows)
        except OSError as e:
            st.warning(tr("Разбор не сохранён на диск: {e}", e=e))
    st.session_state["tab2_review"] = review
    return review


def render_expert_review(cfg, aid, name, rows, document=None, meta=None):
    """Блок «✍️ Разбор замечаний экспертом». aid — id сохранённого аудита (None — аудит не сохранён: отметки живут
    до конца сеанса), rows — строки разбора (review_rows), document — функция → байты проверенного документа .docx
    (для документа с замечаниями эксперта), meta — сведения об аудите для файла разбора."""
    ss = st.session_state
    review = ss.get("tab2_review") or {"marks": {}, "added": []}
    space = aid or "session"
    # подпись блока постоянная: блок с другой подписью Streamlit считает новым и сворачивает
    with st.expander(tr("✍️ Разбор замечаний экспертом и «Мои замечания»")):
        st.caption(tr("По каждому замечанию: ✅ беру — замечание верное и войдёт в «Мои замечания»; ➖ мелочь — верное, "
                      "но несущественное; ❌ неверно — выберите причину. Внизу — свои замечания, которых MINT не "
                      "нашёл. Отметки сохраняются сразу: разбор можно продолжить позже в «📂 Мои аудиты».")
                   if aid else tr("Аудит не сохранён на диск — отметки действуют до конца сеанса."))
        if not rows:
            st.caption(tr("Замечаний нет — можно добавить свои ниже."))
        # отметки, поставленные на прошлой перерисовке, — до счётчиков: иначе они отставали бы на один щелчок
        marks = dict(review.get("marks") or {})
        for row in rows:
            m = _widget_mark(space, row, mark(review, row))
            if m:
                marks[row["key"]] = m
            else:
                marks.pop(row["key"], None)
        review = _save(cfg, aid, rows, review, marks, _pending_added(space, review))
        prog = review_progress(rows, review)
        if rows:
            st.progress(prog["marked"] / max(1, prog["total"]),
                        text=tr("Размечено {m} из {n}: ✅ {ok} · ➖ {mi} · ❌ {w} · своих замечаний — {a}",
                                m=prog["marked"], n=prog["total"], ok=prog["ok"], mi=prog["minor"], w=prog["wrong"],
                                a=prog["added"]))
            if prog["no_reason"]:
                st.caption(tr("❌ без причины: {n} — причина нужна, чтобы понять, что исправлять в MINT.",
                              n=prog["no_reason"]))
            c1, c2, c3 = st.columns([2, 1, 1.3])
            with c1:
                filters = {k: tr(v) for k, v in FILTERS.items()}
                flt = st.selectbox(tr("Показать"), list(FILTERS), key=f"rv_filter::{space}", format_func=filters.get)
            shown = _filtered(rows, flt)
            pages = max(1, math.ceil(len(shown) / PAGE_SIZE))
            page_key = f"rv_page::{space}"
            if ss.get(page_key, 1) > pages:
                ss[page_key] = pages
            with c3:
                st.write("")
                if st.button(tr("➡️ К неразмеченным"), key=f"rv_next::{space}", **_width_kwargs(st.button)):
                    todo = next((i for i, r in enumerate(shown) if not mark(review, r).get("verdict")), None)
                    if todo is not None:
                        ss[page_key] = todo // PAGE_SIZE + 1
            with c2:
                page = st.number_input(tr("Страница (из {n})", n=pages), min_value=1, max_value=pages, step=1,
                                       key=page_key)
            marks = dict(review.get("marks") or {})
            for row in shown[(int(page) - 1) * PAGE_SIZE:int(page) * PAGE_SIZE]:
                new = _card(space, row, review)
                if new:
                    marks[row["key"]] = new
                else:
                    marks.pop(row["key"], None)
        else:
            marks = dict(review.get("marks") or {})
        st.markdown(tr("**➕ Свои замечания** — то, что MINT пропустил (строки добавляются внизу таблицы):"))
        added = _added_editor(space, review)
        review = _save(cfg, aid, rows, review, marks, added)
        _render_outputs(space, name, rows, review, document, meta)


def _render_outputs(space, name, rows, review, document, meta):
    """«Мои замечания» (Word, Markdown), документ с ними и файл разбора для улучшения MINT."""
    ss = st.session_state
    stem = os.path.splitext(name)[0]
    st.markdown(tr("**📄 Мои замечания** — отмеченные ✅ и свои:"))
    with_minor = st.checkbox(tr("Включить и отмеченные ➖ мелочь"), value=False, key=f"rv_minor::{space}")
    items = my_remarks(rows, review, with_minor)
    st.caption(tr("Замечаний в списке: {n}.", n=len(items)))
    c1, c2, c3 = st.columns(3)
    with c1:
        try:
            data = my_remarks_docx(name, rows, review, with_minor)
        except Exception as e:                       # нет python-docx — только Markdown
            data = None
            st.caption(tr("Word недоступен: {e}", e=e))
        if data:
            st.download_button(tr("📥 Мои замечания (.docx)"), data=data, mime=_DOCX_MIME,
                               file_name=tr("Замечания_{v}.docx", v=stem), key=f"rv_dl_docx::{space}",
                               disabled=not items)
    with c2:
        st.download_button(tr("📥 Мои замечания (.md)"), data=my_remarks_markdown(name, rows, review, with_minor),
                           file_name=tr("Замечания_{v}.md", v=stem), mime="text/markdown", key=f"rv_dl_md::{space}",
                           disabled=not items)
    with c3:
        if document:
            doc_key = f"rv_doc::{space}"
            sig = json.dumps([with_minor, items], ensure_ascii=False, sort_keys=True, default=str)
            if st.button(tr("📝 Документ с моими замечаниями"), key=f"rv_doc_btn::{space}", disabled=not items,
                         help=tr("Проверенный документ, в котором ваши замечания стоят примечаниями Word.")):
                try:
                    original = document()
                    if not original:
                        raise OSError(tr("копия документа не найдена в папке аудита"))
                    ss[doc_key] = (sig, annotate_docx_with_findings(original,
                                                                    accepted_findings(rows, review, with_minor))[0])
                except Exception as e:
                    logger.exception("Документ с замечаниями эксперта не собран")
                    st.warning(tr("Документ не собран: {e}", e=e))
            saved = ss.get(doc_key)
            if saved and saved[0] == sig:
                st.download_button(tr("📥 Скачать документ (.docx)"), data=saved[1], mime=_DOCX_MIME,
                                   file_name=tr("Замечания_эксперта_{v}.docx", v=stem), key=f"rv_doc_dl::{space}")
            elif saved:
                st.caption(tr("Отметки изменились — соберите документ заново."))
    st.markdown(tr("**📤 Разбор для улучшения MINT** — какие проверки MINT ошибаются и что он пропускает:"))
    no_texts = st.checkbox(
        tr("Без текстов замечаний"), value=False, key=f"rv_notext::{space}",
        help=tr("Только виды проверок, критичность, отметки и причины — без текстов замечаний, цитат, разделов, "
                "комментариев и имени файла. С текстами разбор полезнее: видно, в чём именно ошибка."))
    data = export_review(meta or {}, rows, review, texts=not no_texts)
    st.download_button(tr("📤 Скачать разбор (.json)"), data=json.dumps(data, ensure_ascii=False, indent=1),
                       file_name=f"mint-review_{space}.json", mime="application/json", key=f"rv_export::{space}",
                       disabled=not review_progress(rows, review)["marked"] and not added_remarks(review))
    st.caption(tr("С текстами в файле есть цитаты документа — передавайте его только туда, куда можно передавать сам "
                  "документ. Все разборы сразу — в «📂 Мои аудиты»."))

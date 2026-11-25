"""Default V2 workflow: only the active stage is rendered."""
import hashlib

import streamlit as st

from ..draft_registry import SOURCE_ROLES
from ..i18n import tr
from ..kb import list_kb_documents, source_path
from .draft_context_ui import render_draft_context
from .draft_target_ui import render_target_registry
from .draft_wizard_state import apply_materials, clamp_step, clear_target, reachable_step, sync_target


def _signature(cfg, raw, sources, roles):
    versions = []
    for name in sources:
        try:
            stat = source_path(cfg, name).stat()
            versions.append((name, stat.st_size, stat.st_mtime_ns))
        except OSError:
            versions.append((name, None, None))
    return (str(cfg.kb_path), hashlib.sha256(raw).hexdigest(),
            tuple(versions), tuple(sorted(roles.items())))


def _go(step):
    st.session_state["draft_wizard_step"] = step
    st.rerun()


def _materials(cfg):
    session = st.session_state
    saved = session.get("draft_wizard_materials") or {}
    st.subheader(tr("Исходные материалы"))
    if saved:
        st.caption(tr("Сохранённый шаблон: {name}", name=saved["name"]))
    upload = st.file_uploader(tr("Файл Word"), type=["docx"], key="wizard_template")
    raw = upload.getvalue() if upload else saved.get("raw", b"")
    name = upload.name if upload else saved.get("name", "")
    names, _ = list_kb_documents(cfg)
    if "wizard_sources" not in session:
        session["wizard_sources"] = [n for n in saved.get("sources", []) if n in names]
    sources = st.multiselect(tr("Документы-основания из вики"), names, key="wizard_sources")
    missing = [n for n in sources if not source_path(cfg, n).is_file()]
    if missing:
        st.warning(tr("Для этих оснований нет оригиналов: {names}", names=", ".join(missing)))
    labels = {"need": tr("Исходные требования"), "architecture": tr("Описание решения"),
              "normative": tr("Нормативные документы"), "mixed": tr("Смешанное содержание"),
              "unspecified": tr("Роль не определена")}
    options = sorted(SOURCE_ROLES, key=lambda role: (role != "unspecified", role))
    roles = {}
    for source in sources:
        key = "wizard_role_" + hashlib.sha256(source.encode("utf-8")).hexdigest()
        if key not in session:
            session[key] = saved.get("roles", {}).get(source, "unspecified")
        roles[source] = st.selectbox(source, options, format_func=labels.__getitem__, key=key)
    signature = _signature(cfg, raw, sources, roles)
    if saved and signature != saved["signature"]:
        st.warning(tr("После подтверждения изменений последующие результаты потребуется собрать заново."))
    if st.button(tr("Продолжить к контексту"), key="wizard_materials_next",
                 disabled=not (raw and sources) or bool(missing), type="primary"):
        apply_materials(session, {"raw": raw, "name": name, "sources": list(sources),
                                  "roles": roles, "signature": signature})
        _go(2)


def render_draft_wizard(cfg, *, expert, reset_cache):
    session = st.session_state
    saved = session.get("draft_wizard_materials")
    # Invalidate stale original revisions even if the material stage is hidden.
    if saved and _signature(cfg, saved["raw"], saved["sources"], saved["roles"]) != saved["signature"]:
        clear_target(session)
        session.pop("draft_wizard_context", None)
        session["draft_wizard_step"] = 1
        st.warning(tr("Исходные материалы изменились. Подтвердите их заново."))
    context_state = session.get("draft_wizard_context") or {}
    context = context_state.get("confirmed")
    step = clamp_step(session, context_ready=bool(context))
    last = reachable_step(session, context_ready=bool(context))
    labels = [tr("Материалы"), tr("Контекст"), tr("Сбор требований"),
              tr("Детализация"), tr("Word — в разработке")]
    cols = st.columns(5)
    for i, (col, label) in enumerate(zip(cols, labels), 1):
        prefix = "✓ " if i < last and i != step else f"{i}. "
        if col.button(prefix + label, key=f"wizard_stage_{i}", disabled=i >= step or i > last,
                      type="primary" if i == step else "secondary", use_container_width=True):
            _go(i)
    st.caption(tr("Этап {step} из 5", step=step))
    if step == 1:
        _materials(cfg)
        return
    if not saved:
        _go(1)
        return
    if step == 2:
        st.subheader(tr("Контекст и функции системы"))
        context = render_draft_context(cfg, saved["raw"], saved["sources"], saved["signature"],
                                       namespace="draft_wizard_context", inline=True)
        if not context:
            clear_target(session)
            return
    if not context:
        return
    key = (saved["signature"], tuple(sorted(context.items())))
    sync_target(session, key)
    # No downstream data are rendered while upstream inputs are being edited.
    if step > reachable_step(session, context_ready=True):
        _go(reachable_step(session, context_ready=True))
        return
    render_target_registry(cfg, key, saved["sources"], saved["roles"], context,
                           True, reset_cache, step=step, expert=expert, advance=_go)

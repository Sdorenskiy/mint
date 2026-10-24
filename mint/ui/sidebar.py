"""Интерфейс: боковая панель — настройки, глоссарий, база знаний."""

import json
from dataclasses import replace

import streamlit as st

from ..cache import _process_cache
from ..config import FALLBACK_LIMITS, check_settings, env_file_candidates
from ..expert import load_expert_materials, load_roles, save_roles
from ..i18n import get_lang, tr
from ..kb import (
    delete_document_from_kb, kb_default_top_k, kb_document_status, kb_language, kb_parent_lengths, load_glossary,
    process_and_add_to_kb, reindex_documents,
)
from ..limits import (
    DERIVED_LABELS, LIMIT_LABELS, detect_server_info, limits_warnings, measure_chars_per_token,
    resolve_model_limits, resolve_settings,
)
from ..parsing import SUPPORTED_FORMATS
from ..services import model_reasons
from .cards_page import render_cards_entry
from .common import (
    EXPERT_GROUPS, LIMIT_HELP, _conn_sig, _expert_widget, _probe_reranker_cached,
    _reset_session_settings, _server_info_cached, _slider, _width_kwargs, btn_w, dl_w,
)


def render_settings(base_cfg, config_notes, server, manual, manual_limits):
    """Боковая панель: подключения, основные настройки, модели и лимиты, экспертные настройки."""
    # ---------------- Состояние подключений ----------------
    problems = check_settings(base_cfg)
    for level, msg in problems:
        (st.error if level == "error" else st.warning)(f"⚠️ {msg}")
    if base_cfg.env_files:
        st.caption(tr("📄 .env прочитан: {env_files}", env_files=base_cfg.env_files)
                   + (f" — {base_cfg.env_parser}" if base_cfg.env_parser != "python-dotenv" else ""))
    elif problems:
        st.warning(tr("Файл .env не найден. MINT ищет его здесь: ")
                   + tr(" и ").join(str(p) for p in dict.fromkeys(env_file_candidates()))
                   + tr(". Имя — ровно «.env» (без .txt и без .example)."))
    else:
        st.caption(tr("📄 .env не найден — используются переменные окружения системы"))
    for note in config_notes:
        st.warning(f"config.yaml: {note}")
    st.caption(tr("🔑 Ключ API задан") if base_cfg.llm_api_key
               else tr("🔑 Ключ API не задан — подходит для локальных серверов без авторизации"))
    r_code, r_desc = _probe_reranker_cached(base_cfg.rerank_url, base_cfg.rerank_model, _conn_sig(base_cfg),
                                            get_lang(), base_cfg)
    if r_code is None:
        st.caption(tr("🎯 Реранкер: {r_desc}", r_desc=r_desc))
    elif r_code == 200:
        st.success(tr("🟢 Реранкер: доступен"))
    elif r_code:
        st.warning(tr("⚠️ Реранкер: {r_desc}", r_desc=r_desc))
    else:
        st.error(tr("❌ Реранкер: {r_desc}", r_desc=r_desc))

    # ---------------- Уровень 1: основные настройки ----------------
    st.header(tr("⚙️ Настройки"))
    models = list(server.get("llm_models") or [])
    if base_cfg.llm_model and base_cfg.llm_model not in models:
        models.insert(0, base_cfg.llm_model)
    if models:
        default_idx = models.index(base_cfg.llm_model) if base_cfg.llm_model in models else 0
        llm_model = st.selectbox(
            tr("Модель ИИ (LLM):"), options=models, index=default_idx, key="cfg_llm_model",
            help=tr("Модель для ответов в чате и замечаний в аудите. Список запрашивается у сервера; модель по "
                    "умолчанию задаётся в .env (LLM_MODEL).\n\n**По умолчанию:** {v}.", v=models[default_idx]),
        )
    else:
        reason = server.get("llm_error") or tr("сервер не вернул ни одной модели")
        st.error(tr("Список моделей не получен у сервера: {reason}. Если сервер не отдаёт список моделей, задайте "
                    "модель в .env (LLM_MODEL).", reason=reason))
        llm_model = ""

    temperature = _slider(
        tr("Температура (креативность):"), "cfg_temperature", 0.0, 1.0, 0.1, base_cfg.temperature,
        tr("Чем ниже, тем ближе ответ к тексту регламентов; чем выше, тем больше вариативности и риск "
           "домыслов. Для регламентов обычно 0.0–0.2.\n\n**По умолчанию:** {temperature}.", temperature=base_cfg.temperature),
    )
    auto_k = base_cfg.top_k or kb_default_top_k(base_cfg)
    top_k = _slider(
        tr("Глубина поиска (Top-K):"), "cfg_top_k", 2, 8, 1, auto_k,
        tr("Сколько фрагментов попадёт в контекст модели. Больше — полнее ответ, но больше шума; при "
           "маленьком окне модели каждый фрагмент станет короче.\n\n**По умолчанию:** {auto_k} (4 при базе "
           "до 300 фрагментов, иначе 5).", auto_k=auto_k),
    )
    level1 = {"llm_model": llm_model, "temperature": temperature, "top_k": top_k}

    # ---------------- Расчёт: лимиты моделей → зависимые параметры ----------------
    cfg_for_limits = replace(base_cfg, llm_model=llm_model)
    measured = _process_cache()["cpt"].get(llm_model)
    limit_keys = {name: ((llm_model if name == "llm_context_tokens" else "*"), name) for name in FALLBACK_LIMITS}
    session_limits = {name: manual_limits[mk] for name, mk in limit_keys.items() if mk in manual_limits}
    limits = resolve_model_limits(cfg_for_limits, server, measured[0] if measured else None, session_limits)
    cfg, info = resolve_settings(base_cfg, limits, {**manual, **level1})
    # настройки аудита — во вкладке «Аудит документа» (render_audit_settings): те же ручные значения сеанса
    st.session_state["_mint_audit_settings"] = (base_cfg, info)

    # ---------------- Уровень 2: модели и лимиты ----------------
    with st.expander(tr("🧩 Модели и лимиты"), expanded=False):
        st.caption(
            tr("От этих чисел MINT рассчитывает размеры фрагментов и объём контекста. Источник значения указан "
               "в подписи: config.yaml, сервер, типовое значение или вручную (на время сеанса).")
        )
        msg = st.session_state.pop("_limits_msg", None)
        if msg:
            st.info(msg)
        for name in FALLBACK_LIMITS:
            if name == "rerank_max_tokens" and not base_cfg.rerank_enabled:
                continue
            value, source = limits[name]
            mk = limit_keys[name]
            is_float = name == "chars_per_token"
            wkey = f"lim_{name}_{mk[0]}_{'m' if mk in manual_limits else value}"

            def _on_limit_change(wkey=wkey, mk=mk, is_float=is_float):
                v = st.session_state[wkey]
                manual_limits[mk] = float(v) if is_float else int(v)

            shown = float(value) if is_float else int(value)
            kwargs = {} if wkey in st.session_state else {"value": shown}
            st.number_input(
                f"{tr(LIMIT_LABELS[name])} · {tr(source)}", key=wkey, on_change=_on_limit_change,
                min_value=min(1.0, shown) if is_float else min(128, shown),
                max_value=max(8.0, shown) if is_float else max(4_000_000, shown),
                step=0.1 if is_float else 1024, help=tr(LIMIT_HELP[name]), **kwargs,
            )
        max_tokens_val = _slider(
            tr("Макс. длина ответа модели (токенов):"), "x_max_tokens", 256, 8000, 128,
            manual.get("max_tokens", base_cfg.max_tokens),
            tr("Если ответы обрываются на полуслове — увеличьте. Моделям с рассуждениями (R1 и др.) нужен "
               "запас. Больше ответ — меньше места под найденные фрагменты.\n\n**По умолчанию:** {max_tokens}.", max_tokens=base_cfg.max_tokens),
            on_change=lambda: manual.__setitem__("max_tokens", int(st.session_state["x_max_tokens"])),
        )
        if model_reasons(cfg_for_limits, llm_model) and not manual.get("llm_no_reasoning", base_cfg.llm_no_reasoning):
            st.caption(tr("💭 Модель рассуждает перед ответом — это медленнее. Выключить: «Экспертные настройки» → "
                          "«Языковая модель» → «Выключить рассуждения модели»."))
        if st.button(tr("📏 Определить у сервера"), key="detect_limits_btn", **btn_w,
                     help=tr("Спрашивает у сервера окна моделей и измеряет «символов на токен» короткими запросами "
                             "на языке базы знаний. Значения, введённые вручную в этом блоке, сбрасываются.")):
            _server_info_cached.clear()
            fresh = detect_server_info(cfg_for_limits)
            kb_lang, ru_share = kb_language(cfg_for_limits)
            with st.spinner(tr("Измеряю «символов на токен»...")):
                cpt, cpt_src = measure_chars_per_token(cfg_for_limits, llm_model, kb_lang)
            if cpt:
                _process_cache()["cpt"][llm_model] = (cpt, cpt_src)
            for mk in list(manual_limits):
                del manual_limits[mk]
            found = [
                tr("окно LLM — {v}", v=fresh['llm_context'].get(llm_model) or tr("не сообщается")),
                tr("вход эмбеддингов — {v}", v=fresh.get('embed_max_tokens') or tr("не сообщается")),
            ]
            if base_cfg.rerank_enabled:
                found.append(tr("вход реранкера — {v}", v=fresh.get('rerank_max_tokens') or tr("не сообщается")))
            lang_note = {
                "ru": tr("база на русском — измерено на русском тексте"),
                "en": tr("база на английском — измерено на английском тексте"),
                "mixed": tr("в базе русский и английский ({pct}% русского) — взято меньшее из двух",
                            pct=round(ru_share * 100)),
            }.get(kb_lang, tr("база пуста — взято меньшее из русского и английского"))
            found.append(tr("символов на токен — {cpt} ({cpt_src}; {lang_note})", cpt=cpt, cpt_src=cpt_src,
                            lang_note=lang_note) if cpt else tr("символов на токен — не измерено"))
            st.session_state["_limits_msg"] = (
                tr("Сервер: ") + "; ".join(found) + tr(". Чего сервер не сообщает — введите вручную или запишите в config.yaml (раздел models). "
                                                   "Значения из config.yaml важнее найденных у сервера.")
            )
            st.rerun()

        st.markdown(tr("**MINT рассчитал:**"))
        icon = {"авто": "⚙️", "config.yaml": "📄", "вручную": "✋"}
        st.markdown("\n".join(
            f"- {icon.get(i['source'], '')} {tr(DERIVED_LABELS[f])}: **{i['value']}**"
            + (tr(" (авто было бы {auto})", auto=i["auto"]) if i["source"] != "авто" and i["auto"] != i["value"] else "")
            for f, i in info.items()
        ))
        prefix_note = (f"«{cfg.embed_query_prefix[:60]}{'…' if len(cfg.embed_query_prefix) > 60 else ''}»"
                       if cfg.embed_query_prefix else tr("нет префикса"))
        st.caption(tr("Префикс запроса для модели эмбеддингов ({embed_prefix_source}): {prefix_note}", embed_prefix_source=cfg.embed_prefix_source, prefix_note=prefix_note)
                   + (tr("; префикс документов: «{embed_doc_prefix}»", embed_doc_prefix=cfg.embed_doc_prefix) if cfg.embed_doc_prefix else ""))
        st.caption(tr("Контекст чата: до ≈ {v:,} симв. (Top-K {top_k} × фрагмент {smart_truncate_chars}) · ⚙️ авто · "
                      "📄 config.yaml · ✋ вручную", v=cfg.top_k * cfg.smart_truncate_chars, top_k=cfg.top_k, smart_truncate_chars=cfg.smart_truncate_chars)
                   .replace(",", " "))
        for w in limits_warnings(info):
            st.warning(w)
        lens = kb_parent_lengths(cfg)
        if lens:
            over = sum(1 for n in lens if n > cfg.smart_truncate_chars)
            st.caption(tr("📊 В базе {n_lens} parent-фрагментов, самый длинный — {v} симв.; длиннее лимита (будут "
                          "обрезаны): {over}.", n_lens=len(lens), v=max(lens), over=over))

    # ---------------- Уровень 3: экспертные настройки ----------------
    with st.expander(tr("🛠️ Экспертные настройки"), expanded=False):
        st.caption(tr("Любое значение можно изменить на время сеанса (✋ вручную). Постоянные значения — в "
                      "config.yaml. Рассчитанные MINT параметры помечены «авто»: при ручном изменении расчёт для них "
                      "отключается."))
        st.button(tr("↩️ Сбросить изменения сеанса"), key="reset_settings_btn", on_click=_reset_session_settings,
                  **btn_w, help=tr("Возвращает все параметры к config.yaml и расчёту MINT."))
        st.caption(tr("📜 Настройки аудита — во вкладке «Аудит документа», блок «⚙️ Настройки аудита»: все в одном "
                      "месте."))
        for group_title, specs in EXPERT_GROUPS:
            st.write("---")
            st.caption(f"**{tr(group_title)}**")
            for spec in specs:
                if spec[0].startswith("rerank_") and not base_cfg.rerank_enabled and spec[0] != "rerank_top_k":
                    continue
                _expert_widget(spec, base_cfg, info, manual)

    return cfg


def render_glossary(cfg):
    """Боковая панель: глоссарий сокращений."""
    # ---------------- Глоссарий ----------------
    gl = load_glossary(cfg)
    with st.expander(tr("📘 Сокращения: {n_gl}", n_gl=len(gl)), expanded=False):
        st.caption(
            tr("Глоссарий связывает сокращение с расшифровкой («СЗИ» ↔ «средства защиты информации»): поиск "
               "находит документ и по сокращению, и по полной форме, а модель может расшифровать сокращение в "
               "ответе. Сокращения собираются из загруженных документов автоматически (перечни сокращений, "
               "«полная форма (СОКР)»). Свои расшифровки — в файле {name}; они важнее найденных.", name=cfg.glossary_file.name)
        )
        st.caption(tr("Из документов: {auto_count} · свои: {manual_count}", auto_count=gl.auto_count, manual_count=gl.manual_count)
                   + (tr(" · убрано своим файлом: {removed_count}", removed_count=gl.removed_count) if gl.removed_count else "")
                   + tr(" · свой файл: {glossary_file}", glossary_file=cfg.glossary_file) + ("" if cfg.glossary_file.is_file() else tr(" (нет)")))
        st.caption(tr("Найденное в документах хранится в базе (auto_glossary.json) и не пропадает при перезапуске. "
                      "Свой файл нужен, только чтобы исправить, добавить или убрать записи."))
        if len(gl):
            st.dataframe(gl.rows(), hide_index=True, **_width_kwargs(st.dataframe))
            export = {tr("_как_пользоваться"): (
                tr("Оставьте в файле только исправленные и новые записи — остальное MINT найдёт в документах сам и "
                   "будет обновлять при загрузке новых. Чтобы убрать ошибочную расшифровку, оставьте пустую "
                   'строку: "АБВ": "". Сохраните файл рядом с программой под именем glossary.json (или укажите '
                   "путь в GLOSSARY_PATH). Ключи, начинающиеся с «_», игнорируются."))}
            export.update(dict(sorted(gl.entries.items())))
            st.download_button(
                tr("⬇️ Скачать для правки (glossary.json)"),
                data=json.dumps(export, ensure_ascii=False, indent=2),
                file_name="glossary.json", mime="application/json", key="dl_glossary", **dl_w,
                help=tr("Весь текущий список с инструкцией в начале. Оставьте только то, что исправили или добавили, — "
                        "иначе записи из документов перестанут обновляться."),
            )

    return gl


def _render_audit_roles(cfg, names, roles):
    """Роли документов базы для аудита: правила экспертов («учитывать всегда») и карточки систем."""
    always = [d for d in roles["always"] if d in names]
    cards = [d for d in roles["cards"] if d in names]
    with st.expander(tr("📌 Для аудита: правила экспертов и карточки систем ({n})", n=len(always) + len(cards))):
        st.caption(tr("Обычные документы аудит находит поиском по каждому разделу. Отмеченные здесь модель получает "
                      "в каждой проверке, сверх нормативного контекста (лимит — «Экспертные настройки» → «Правила "
                      "экспертов и карточки систем на запрос»)."))

        def save():
            save_roles(cfg, st.session_state.get("kb_roles_always") or [], st.session_state.get("kb_roles_cards") or [])

        st.multiselect(
            tr("📌 Учитывать в аудите всегда (правила экспертов)"), names, default=always, key="kb_roles_always",
            on_change=save,
            help=tr("Документ с правилами, которые проверяются в каждом документе: модель получает его целиком, а если "
                    "не помещается — самые близкие к проверяемому разделу фрагменты. Пишите правила так, чтобы каждое "
                    "было понятно само по себе: когда применяется, правило, типичная ошибка, основание."))
        st.multiselect(
            tr("🗂️ Карточки систем"), names, default=cards, key="kb_roles_cards", on_change=save,
            help=tr("Карточка — что система умеет сейчас, что в планах и к какому сроку, ограничения, как к ней "
                    "подключаются. Подключается к проверке, когда система упоминается в разделе; по каждой системе, "
                    "упомянутой в документе не меньше двух раз, модель выписывает, что документ от неё требует. "
                    "Названия системы MINT берёт из строки «Названия: …» в начале карточки и из её заголовка."))
        if cards:
            try:
                mat = load_expert_materials(cfg)
            except Exception:
                mat = None
            for c in (mat.cards if mat else []):
                st.caption(tr("🗂️ {file}: MINT узнаёт систему по названиям — {names}", file=c["source"],
                              names=", ".join(f"«{n}»" for n in c["names"])))
        render_cards_entry()


def render_knowledge_base(cfg):
    """Боковая панель: добавление документов, список документов, переиндексация."""
    # ---------------- База знаний ----------------
    st.write("---")
    st.subheader(tr("📥 Добавить регламенты в базу"))
    kb_batch_done = st.session_state.get("_kb_batch_done", False)
    if kb_batch_done:
        for _name, _ok, _msg in st.session_state.get("_kb_batch_results", []):
            if not _ok:
                st.error(f"❌ **{_name}** — {_msg}")
            elif "⚠️" in _msg:       # часть фрагментов пропущена (см. process_and_add_to_kb)
                st.warning(f"⚠️ **{_name}** — {_msg}")
            else:
                st.success(f"✅ **{_name}** — {_msg}")
        if st.button(tr("➕ Загрузить новые документы в базу"), key="kb_reset_btn", **btn_w):
            st.session_state.pop("_kb_batch_done", None)
            st.session_state.pop("_kb_batch_results", None)
            st.rerun()
        st.write("---")

    kb_files = st.file_uploader(
        tr("Загрузить документы в общую Wiki (.docx, .pdf, .md, .txt)"), type=list(SUPPORTED_FORMATS),
        accept_multiple_files=True, key="kb_uploader",
        help=tr("Документ разбирается (.docx — Docling; .pdf — по текстовому слою, без моделей: заголовки из "
                "закладок, оглавления или по шрифту), нарезается на фрагменты по рассчитанным параметрам и "
                "добавляется в базу. Сканы без текстового слоя не читаются. Повторная загрузка файла с тем же "
                "именем заменяет прежнюю версию. Оригинал сохраняется для переиндексации."),
    )
    if kb_files and not kb_batch_done:
        st.caption(tr("📎 Выбрано файлов: **{n_kb_files}**", n_kb_files=len(kb_files)))
        if st.button(tr("🚀 Проиндексировать все файлы в базу знаний"), key="kb_index_all_btn", type="primary", **btn_w):
            kb_progress = st.progress(0)
            results = []
            for idx, kb_file in enumerate(kb_files):
                status_box = st.empty()
                status_box.info(tr("⏳ Обрабатываю {v}/{n_kb_files}: **{name}**...", v=idx + 1, n_kb_files=len(kb_files), name=kb_file.name))
                try:
                    ok, msg = process_and_add_to_kb(kb_file.name, bytes(kb_file.getbuffer()), cfg)
                    results.append((kb_file.name, ok, msg))
                except Exception as e:
                    results.append((kb_file.name, False, str(e)))
                kb_progress.progress((idx + 1) / len(kb_files))
            st.session_state["_kb_batch_done"] = True
            st.session_state["_kb_batch_results"] = results
            st.rerun()

    st.write("---")
    st.subheader(tr("📁 Документы в базе"))
    for _name, _ok, _msg in st.session_state.pop("_reindex_results", []):
        (st.success if _ok else st.error)(f"{'✅' if _ok else '❌'} **{_name}** — {_msg}")
    rows, n_vectors = kb_document_status(cfg)
    if rows:
        roles = load_roles(cfg)
        for r in rows:
            errors = [t for lvl, t in r["issues"] if lvl == "error"]
            notes = [t for lvl, t in r["issues"] if lvl != "error"]
            marker = "⛔ " if errors else ("ℹ️ " if notes else "")
            icon = "🗂️" if r["name"] in roles["cards"] else "📌" if r["name"] in roles["always"] else "📄"
            col_text, col_btn = st.columns([0.85, 0.15])
            with col_text:
                st.caption(f"{icon} {marker}{r['name']}", help="\n\n".join(errors + notes) or None)
            with col_btn:
                if st.button("🗑️", key=f"del_{r['name']}", help=tr("Удалить {name} из базы", name=r['name'])):
                    if delete_document_from_kb(r["name"], cfg):
                        st.toast(tr("Файл {name} удалён из базы", name=r['name']))
                        st.rerun()
        st.metric(label=tr("Всего векторов в FAISS"), value=n_vectors)
        _render_audit_roles(cfg, [r["name"] for r in rows], roles)

        n_bad = sum(1 for r in rows if any(lvl == "error" for lvl, _ in r["issues"]))
        n_changed = sum(1 for r in rows if any(lvl == "info" for lvl, _ in r["issues"]))
        n_src = sum(1 for r in rows if r["has_source"])
        if n_bad:
            st.error(tr("⛔ {n_bad} док. проиндексированы другой моделью эмбеддингов — векторный поиск по ним не "
                        "работает. Переиндексируйте базу.", n_bad=n_bad))
        elif n_changed:
            st.caption(tr("ℹ️ {n_changed} док. нарезаны с другими параметрами или загружены до v18 (наведите на ℹ️). Это "
                          "не ошибка; для единообразия — переиндексация.", n_changed=n_changed))
        with st.expander(tr("🔄 Переиндексация"), expanded=bool(n_bad)):
            st.caption(
                tr("Нужна после смены модели эмбеддингов или параметров нарезки. Переиндексируются документы, "
                   "оригиналы которых сохранены (загруженные в v18 и новее). Документы, загруженные раньше, "
                   "загрузите заново. Если сменилась размерность векторов, база строится заново, и документы без "
                   "оригинала удаляются.")
            )
            if n_src == 0:
                st.caption(tr("Переиндексировать нечего: ни у одного из {n_rows} док. нет сохранённого оригинала. Загрузите "
                              "их заново через «Добавить документы в базу» — с теми же именами файлов, старые версии "
                              "заменятся.", n_rows=len(rows)))
            elif n_src < len(rows):
                st.caption(tr("Без оригинала: {v} док.", v=len(rows) - n_src))
            if st.button(tr("🔄 Переиндексировать ({n_src} док.)", n_src=n_src), key="reindex_btn", disabled=n_src == 0, **btn_w):
                bar = st.progress(0.0)
                res = reindex_documents(cfg, progress=lambda frac, name: bar.progress(frac, text=name))
                st.session_state["_reindex_results"] = res
                st.rerun()
    else:
        st.info(tr("В базе знаний пока нет документов."))

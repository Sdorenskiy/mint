"""Интерфейс: страница «📝 Промпты» — правка текстов для модели. Ядро — mint/prompts.

Открывается кнопкой на боковой панели и занимает основную область вместо вкладок (как «Проверка качества»).
Правится текст на языке интерфейса:
  • «Попробовать в сеансе» — правка действует только в этом окне браузера, пока его не закрыть;
  • «Сохранить» — правка записывается в prompts.yaml рядом с программой (или PROMPTS_PATH) и действует везде;
  • «Вернуть умолчание» — правка убирается из сеанса и из prompts.yaml;
  • «Проверить правку» — правка применяется в сеансе и открывается «Проверка качества» с ответами чата на вопросах
    прошлой проверки: результат сравнится с прошлой проверкой ответов по версии промптов.
Обязательные части формата ответа (их разбирает код) и подстановки {{…}} удалить нельзя: такая правка не
применяется, страница говорит, чего не хватает.
"""

import difflib

import streamlit as st

from .. import prompts as P
from ..i18n import LANGS, get_lang, tr
from .common import btn_w
from . import quality

OPEN = "prompts_open"             # открыта ли страница промптов вместо вкладок
SESSION = "prompt_session"        # правки сеанса: {язык: {ключ: текст}}
VER = "prompts_ver"               # счётчик: поле текста строится заново после сохранения и сброса


def open_prompts():
    st.session_state[OPEN] = True
    st.session_state[quality.OPEN] = False
    st.session_state["cards_open"] = False


def close_prompts():
    st.session_state[OPEN] = False


def session_prompts():
    return st.session_state.setdefault(SESSION, {})


def _status_label(status):
    return {"file": tr("✎ сохранено"), "session": tr("✎ в сеансе")}.get(status, "")


def render_prompts_entry():
    """Боковая панель: вход на страницу промптов и число своих правок."""
    st.write("---")
    st.subheader(tr("📝 Промпты"))
    custom = P.custom_status()
    note = tr("Свои правки: {n}.", n=len(custom)) if custom else tr("Действуют тексты по умолчанию.")
    st.caption(tr("Тексты для модели: правка, проверка на вопросах, возврат к умолчанию.") + " " + note)
    st.button(tr("Открыть промпты"), key="pr_open_btn", on_click=open_prompts, **btn_w)


def diff_text(old, new):
    """Разница двух текстов построчно (для показа в st.code с подсветкой diff)."""
    lines = difflib.unified_diff(old.splitlines(), new.splitlines(), tr("по умолчанию"), tr("сейчас"), lineterm="", n=1)
    return "\n".join(lines)


def _set_session(lang, key, text):
    """Правка сеанса: текст как у сохранённого или умолчания — правка сеанса убирается."""
    sess = session_prompts().setdefault(lang, {})
    sess.pop(key, None)
    if text != P.prompt_text(key, lang):          # действующий без правки сеанса (её только что убрали)
        sess[key] = text
    P.set_session_prompts(session_prompts())


def _bump():
    st.session_state[VER] = st.session_state.get(VER, 0) + 1


def render_prompts(cfg):
    """Основная область: правка промптов вместо вкладок."""
    lang = get_lang()
    head, close = st.columns([0.8, 0.2])
    head.subheader(tr("📝 Промпты"))
    close.button(tr("✕ Закрыть"), key="pr_close_btn", on_click=close_prompts, **btn_w)
    custom = P.custom_status(lang)
    path = P.custom_file()
    st.caption(tr("Язык: {language} — тексты на другом языке правятся при другом языке интерфейса. Профиль: "
                  "{profile} — умолчания этого профиля (сменить — боковая панель → «🧭 Профиль»). Версия набора: {v}. "
                  "Свои правки сохраняются в {path}{exists}; они действуют во всех профилях.", language=LANGS[lang],
                  profile=tr(P.PROFILES[P.get_profile()]), v=P.prompts_version(lang),
                  path=path, exists="" if path.is_file() else tr(" (пока нет)")))
    for problem in P.custom_file_prompts()[1]:
        st.warning(problem)

    keys = list(P.EDITABLE)
    key = st.selectbox(tr("Промпт"), options=keys, key="pr_key",
                       format_func=lambda k: f"{tr(P.EDITABLE[k][0])} · {tr(P.EDITABLE[k][1])}"
                                             + (f"  {_status_label(custom[k])}" if k in custom else ""))
    _group, _name, about = P.EDITABLE[key]
    st.caption(tr(about))
    default = P.default_text(key, lang)
    current = P.prompt_text(key, lang)
    if P.default_changed(key, lang):
        st.warning(tr("Текст по умолчанию изменился после того, как вы сохранили свою правку (обновление MINT). "
                      "Сравните их ниже и перенесите нужное в свою правку — или верните умолчание."))

    parts, need = P.format_parts(key, lang)
    if parts or need:
        lines = [tr("**Обязательно в тексте** — без этого правка не применится:")]
        if need:
            lines.append(tr("- подстановки (их заполняет MINT): {v}", v=", ".join(f"`{{{{{p}}}}}`" for p in need)))
        if parts:
            lines.append(tr("- формат ответа (его разбирает MINT): {v}", v="; ".join(f"`{p}`" for p in parts)))
        st.markdown("\n".join(lines))

    ver = st.session_state.get(VER, 0)
    text = st.text_area(tr("Текст"), value=current, height=340, key=f"pr_text_{lang}_{key}_{ver}")
    problems = P.check_text(key, lang, text)
    for p in problems:
        st.error(p)
    changed = text != current

    c = st.columns(4)
    try_ = c[0].button(tr("Попробовать в сеансе"), key="pr_try_btn", disabled=bool(problems) or not changed,
                       help=tr("Правка действует только в этом окне браузера: чат, аудит и проверка качества идут с "
                               "ней. Другие пользователи и после перезапуска — по-прежнему."), **btn_w)
    save = c[1].button(tr("Сохранить"), key="pr_save_btn", type="primary", disabled=bool(problems)
                       or (not changed and custom.get(key) != "session"),
                       help=tr("Записать в {name}: правка действует для всех и после перезапуска.", name=path.name),
                       **btn_w)
    reset = c[2].button(tr("Вернуть умолчание"), key="pr_reset_btn",
                        disabled=key not in custom and not changed and not P.file_has(key, lang),
                        help=tr("Убрать свою правку из сеанса и из {name}.", name=path.name), **btn_w)
    measured = key in P.MEASURED_BY_ANSWERS
    check = c[3].button(tr("Проверить правку"), key="pr_check_btn", disabled=bool(problems) or not measured,
                        help=tr("Применить правку в сеансе и открыть «Проверку качества» с ответами чата на вопросах "
                                "прошлой проверки: результат сравнится с прошлой проверкой ответов.") if measured else
                        (tr("Ответы консультанта проверкой качества не измеряются — попробуйте правку в сеансе на "
                            "своих запросах; версия текстов консультанта пишется в отзывы 👍/👎, по ней видно, при "
                            "какой правке получен ответ.") if key.startswith(P.CONSULT_PREFIX) else
                         tr("Аудит, контроль исправлений и черновик вопросов проверкой ответов чата не измеряются — "
                            "проверьте правку на документе с известными замечаниями.")), **btn_w)
    if key == "paraphrase_system" and not cfg.use_multi_query:
        st.caption(tr("Перефразировка работает, только если включён multi-query (Экспертные настройки → Поиск и контекст)."))

    version = P.consult_prompts_version if key.startswith(P.CONSULT_PREFIX) else P.prompts_version
    if try_:
        _set_session(lang, key, text)
        st.toast(tr("Правка действует в этом сеансе. Версия промптов: {v}", v=version(lang)))
        st.rerun()
    elif save:
        try:
            saved = P.save_custom(key, lang, text)
        except (OSError, ValueError) as e:
            st.error(tr("Не сохранено: {e}", e=e))
        else:
            session_prompts().get(lang, {}).pop(key, None)
            P.set_session_prompts(session_prompts())
            _bump()
            st.toast(tr("Сохранено в {path}. Версия промптов: {v}", path=saved, v=version(lang)))
            st.rerun()
    elif reset:
        session_prompts().get(lang, {}).pop(key, None)
        P.set_session_prompts(session_prompts())
        try:
            if P.file_has(key, lang):
                P.remove_custom(key, lang)
        except (OSError, ValueError) as e:
            st.error(tr("Не удалось изменить {path}: {e}", path=path, e=e))
        else:
            _bump()
            st.toast(tr("Действует текст по умолчанию."))
            st.rerun()
    elif check:
        if changed:
            _set_session(lang, key, text)
        has_questions = quality.prepare_answer_check(cfg)
        st.session_state[OPEN] = False
        st.session_state[quality.OPEN] = True
        if not has_questions:
            st.session_state["qa_hint"] = tr("Прошлой проверки нет: составьте вопросы — ответы чата будут проверены, "
                                             "а следующая проверка после правки сравнится с этой.")
        st.rerun()

    if text != default:
        with st.expander(tr("Разница с текстом по умолчанию")):
            st.code(diff_text(default, text) or tr("(разница только в пробелах)"), language="diff")
    with st.expander(tr("Разметка — не правится ({n})", n=len(P.default_prompts(lang)) - len(keys))):
        st.caption(tr("Заголовки контекста, вопроса и источников, которые MINT собирает сам: их разбирает код "
                      "(например, проверка ссылок ищет «=== ИСТОЧНИК: … ===»)."))
        for k, v in P.default_prompts(lang).items():
            if k not in P.EDITABLE:
                st.markdown(f"`{k}`")
                st.code(v, language=None)

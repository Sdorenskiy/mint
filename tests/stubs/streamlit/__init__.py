"""Заглушка Streamlit для прогона интерфейса MINT (mint.ui.app.main) без браузера.

Сигнатуры основных виджетов повторяют настоящие, поэтому неверный аргумент даст TypeError.
Слайдеры и числовые поля проверяют диапазон и согласованность типов, как настоящий Streamlit.
"""
import functools

LOG = []
SCRIPT = {"chat_input": None, "buttons": set(), "file_uploader": {}, "data_editor": {}}


class StreamlitAPIException(Exception):
    pass


class RerunException(Exception):
    pass


class _SessionState(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self[k] = v


session_state = _SessionState()


class _Elem:
    def __init__(self, name="elem"):
        self._name = name

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return globals()[name] if name in _PUBLIC else _make(name)

    def update(self, **kw):
        LOG.append(("status.update", kw.get("label")))

    def progress(self, value, text=None):
        _check_progress(value)
        return self


def _make(name):
    def f(*args, **kwargs):
        LOG.append((name, args[0] if args else None))
        return _Elem(name)
    return f


def _check_progress(value):
    if not (0 <= float(value) <= 1):
        raise StreamlitAPIException(f"progress value out of range: {value}")


def _cache(func=None, **_kw):
    def deco(f):
        memo = {}

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            key = repr(args) + repr(sorted(kwargs.items()))
            if key not in memo:
                memo[key] = f(*args, **kwargs)
            return memo[key]

        wrapper.clear = memo.clear
        return wrapper
    return deco(func) if callable(func) else deco


cache_resource = _cache
cache_data = _cache


def set_page_config(page_title=None, page_icon=None, layout="centered", initial_sidebar_state="auto", menu_items=None):
    LOG.append(("set_page_config", page_title))


def _text(name):
    def f(body, *args, help=None, **kwargs):
        LOG.append((name, str(body)))
        return _Elem(name)
    return f


title = _text("title")
header = _text("header")
subheader = _text("subheader")
markdown = _text("markdown")
info = _text("info")
success = _text("success")
warning = _text("warning")
error = _text("error")
toast = _text("toast")


def caption(body, unsafe_allow_html=False, *, help=None):
    LOG.append(("caption", str(body)))


def write(*args, **kwargs):
    LOG.append(("write", args[0] if args else None))


def metric(label, value, delta=None, delta_color="normal", help=None, label_visibility="visible"):
    LOG.append(("metric", f"{label}={value}"))


def dataframe(data=None, width=None, height=None, *, use_container_width=None, hide_index=None,
              column_order=None, column_config=None, key=None):
    LOG.append(("dataframe", len(data) if data is not None else 0))


def data_editor(data, *, width=None, height=None, use_container_width=None, hide_index=None, column_order=None,
                column_config=None, num_rows="fixed", disabled=False, key=None, on_change=None, args=None,
                kwargs=None, row_height=None):
    """Возвращает правки из SCRIPT["data_editor"][key] (функция: данные → новые данные) или данные без изменений."""
    if num_rows not in ("fixed", "dynamic"):
        raise StreamlitAPIException(f"num_rows: {num_rows}")
    for col in (column_order or []):
        if column_config and col not in column_config:
            raise StreamlitAPIException(f"column {col} has no config")
    LOG.append(("data_editor", key))
    edit = SCRIPT["data_editor"].get(key)
    return edit(data) if edit else data


class _ColumnConfig:
    """st.column_config: конструкторы колонок проверяют имена аргументов, как настоящие."""

    @staticmethod
    def CheckboxColumn(label=None, *, width=None, help=None, disabled=None, required=None, pinned=None, default=None):
        return {"type": "checkbox", "label": label}

    @staticmethod
    def TextColumn(label=None, *, width=None, help=None, disabled=None, required=None, pinned=None, default=None,
                   max_chars=None, validate=None):
        return {"type": "text", "label": label}

    @staticmethod
    def SelectboxColumn(label=None, *, width=None, help=None, disabled=None, required=None, pinned=None,
                        default=None, options=None):
        if options is not None and len(set(options)) != len(list(options)):
            raise StreamlitAPIException(f"{label}: duplicate options")
        return {"type": "selectbox", "label": label, "options": list(options or [])}

    @staticmethod
    def NumberColumn(label=None, *, width=None, help=None, disabled=None, required=None, pinned=None, default=None,
                     format=None, min_value=None, max_value=None, step=None):
        return {"type": "number", "label": label}


column_config = _ColumnConfig()


def radio(label, options, index=0, format_func=str, key=None, help=None, on_change=None, args=None, kwargs=None, *,
          disabled=False, horizontal=False, captions=None, label_visibility="visible"):
    options = list(options)
    LOG.append(("radio", label))
    return _register(key, options[index] if options else None)


def code(body, language="python", *, line_numbers=False, wrap_lines=False, height=None):
    LOG.append(("code", body))


def _register(key, value):
    if key is not None:
        if key in session_state:
            return session_state[key]
        session_state[key] = value
    return value


def _check_numeric(label, min_value, max_value, value, step):
    vals = [v for v in (min_value, max_value, value, step) if v is not None]
    kinds = {type(v) for v in vals}
    if int in kinds and float in kinds:
        raise StreamlitAPIException(f"{label}: mixed numeric types {[(type(v).__name__, v) for v in vals]}")
    if min_value is not None and value is not None and value < min_value:
        raise StreamlitAPIException(f"{label}: value {value} < min {min_value}")
    if max_value is not None and value is not None and value > max_value:
        raise StreamlitAPIException(f"{label}: value {value} > max {max_value}")


def slider(label, min_value=None, max_value=None, value=None, step=None, format=None, key=None, help=None,
           on_change=None, args=None, kwargs=None, *, disabled=False, label_visibility="visible"):
    if value is None and key in session_state:
        value = session_state[key]
    _check_numeric(label, min_value, max_value, value, step)
    LOG.append(("slider", label))
    return _register(key, value)


def select_slider(label, options=(), value=None, format_func=str, key=None, help=None, on_change=None, args=None,
                  kwargs=None, *, disabled=False, label_visibility="visible"):
    options = list(options)
    if value is not None and value not in options:
        raise StreamlitAPIException(f"{label}: value {value!r} is not among the options")
    LOG.append(("select_slider", label))
    return _register(key, options[0] if value is None and options else value)


def number_input(label, min_value=None, max_value=None, value="min", step=None, format=None, key=None, help=None,
                 on_change=None, args=None, kwargs=None, *, placeholder=None, disabled=False,
                 label_visibility="visible"):
    if value == "min":
        value = session_state.get(key, min_value)
    _check_numeric(label, min_value, max_value, value, step)
    LOG.append(("number_input", label))
    return _register(key, value)


def checkbox(label, value=False, key=None, help=None, on_change=None, args=None, kwargs=None, *, disabled=False,
             label_visibility="visible"):
    LOG.append(("checkbox", label))
    return _register(key, value)


def selectbox(label, options, index=0, format_func=str, key=None, help=None, on_change=None, args=None,
              kwargs=None, *, placeholder=None, disabled=False, label_visibility="visible"):
    options = list(options)
    if not options:
        return None
    if not (0 <= index < len(options)):
        raise StreamlitAPIException(f"{label}: index {index} out of range")
    LOG.append(("selectbox", label))
    LOG.append(("selectbox_options", " | ".join(str(format_func(o)) for o in options)))
    return _register(key, options[index])


def multiselect(label, options, default=None, format_func=str, key=None, help=None, on_change=None, args=None,
                kwargs=None, *, max_selections=None, placeholder=None, disabled=False, label_visibility="visible",
                accept_new_options=False):
    options = list(options)
    default = list(default or [])
    if any(d not in options for d in default):
        raise StreamlitAPIException(f"{label}: default value is not among the options")
    LOG.append(("multiselect", label))
    return _register(key, default)


def toast(body, *, icon=None, duration="short"):
    LOG.append(("toast", body))


def text_area(label, value="", height=None, max_chars=None, key=None, help=None, on_change=None, args=None,
              kwargs=None, *, placeholder=None, disabled=False, label_visibility="visible"):
    LOG.append(("text_area", label))
    return _register(key, value)


def text_input(label, value="", max_chars=None, key=None, type="default", help=None, autocomplete=None,
               on_change=None, args=None, kwargs=None, *, placeholder=None, disabled=False,
               label_visibility="visible", icon=None, width="stretch"):
    LOG.append(("text_input", label))
    return _register(key, value)


def button(label, key=None, help=None, on_click=None, args=None, kwargs=None, *, type="secondary", icon=None,
           disabled=False, use_container_width=False):
    LOG.append(("button", label))
    if disabled:
        LOG.append(("button_disabled", label))
    pressed = key in SCRIPT["buttons"] and not disabled     # как в Streamlit: неактивная кнопка не нажимается
    if pressed:
        SCRIPT["buttons"].discard(key)
        if on_click:
            on_click(*(args or ()), **(kwargs or {}))
    return pressed


def download_button(label, data, file_name=None, mime=None, key=None, help=None, on_click="rerun", args=None,
                    kwargs=None, *, type="secondary", icon=None, disabled=False, use_container_width=False):
    if data is None:
        raise StreamlitAPIException(f"{label}: data is None")
    LOG.append(("download_button", label))
    return False


def file_uploader(label, type=None, accept_multiple_files=False, key=None, help=None, on_change=None,
                  args=None, kwargs=None, *, disabled=False, label_visibility="visible"):
    LOG.append(("file_uploader", label))
    return SCRIPT["file_uploader"].get(key)


def chat_input(placeholder="Your message", *, key=None, max_chars=None, disabled=False, on_submit=None,
               args=None, kwargs=None):
    v = SCRIPT["chat_input"]
    SCRIPT["chat_input"] = None
    return v


def progress(value, text=None):
    _check_progress(value)
    return _Elem("progress")


def columns(spec, *, gap="small", vertical_alignment="top", border=False):
    n = spec if isinstance(spec, int) else len(spec)
    return [_Elem("column") for _ in range(n)]


def tabs(labels):
    return [_Elem("tab") for _ in labels]


def expander(label, expanded=False, *, icon=None):
    LOG.append(("expander", label))
    return _Elem("expander")


def status(label="Running...", *, expanded=False, state="running"):
    return _Elem("status")


def spinner(text="In progress...", *, show_time=False):
    return _Elem("spinner")


def container(height=None, border=None, key=None):
    return _Elem("container")


def chat_message(name, *, avatar=None):
    return _Elem("chat_message")


def empty():
    return _Elem("empty")


def rerun():
    raise RerunException()


sidebar = _Elem("sidebar")
_PUBLIC = {n for n in dir() if not n.startswith("_")}

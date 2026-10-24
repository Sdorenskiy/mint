"""Interface languages: Russian (source) and English.

Strings are written in Russian in the code and wrapped in tr():

    tr("Документ загружен")                       → "Document uploaded" when the language is English
    tr("Загружено {n} документов", n=3)            → placeholders are filled with str.format

The Russian text is the key; English translations live in mint/i18n/en.py. A missing translation falls back
to Russian (tests/test_i18n.py fails on missing ones). Prompts for the models are not translated through tr():
they have separate English versions in mint/prompts.py.

The current language is per session (Streamlit runs every session in its own thread): mint.ui.app sets it at
the start of each page run. Scripts use default_lang(): MINT_LANG, otherwise the system locale.
"""
import contextvars
import locale
import os
from contextlib import contextmanager

from .en import EN

LANGS = {"ru": "Русский", "en": "English"}

_current = contextvars.ContextVar("mint_lang", default=None)


def normalize_lang(value):
    """'en', 'EN', 'en_US.UTF-8', 'english' → 'en'; anything unknown → None."""
    v = str(value or "").strip().lower().replace("-", "_")
    for code in LANGS:
        if v == code or v.startswith(code + "_") or v.startswith(code + ".") or v == LANGS[code].lower():
            return code
    return None


def system_lang():
    """Language of the operating system: Russian locale → 'ru', any other → 'en'."""
    candidates = [os.environ.get(k) for k in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE")]
    try:
        candidates.append(locale.getlocale()[0])
    except Exception:
        pass
    for c in candidates:
        if c and c not in ("C", "POSIX", "C.UTF-8"):
            return "ru" if str(c).lower().startswith(("ru", "russian")) else "en"
    return "en"


def default_lang():
    """MINT_LANG from the environment or .env (ru / en); otherwise the system language."""
    return normalize_lang(os.environ.get("MINT_LANG")) or system_lang()


def get_lang():
    return _current.get() or default_lang()


def set_lang(lang):
    """Language for the current session (thread). Unknown values fall back to default_lang()."""
    code = normalize_lang(lang) or default_lang()
    _current.set(code)
    return code


@contextmanager
def use_lang(lang):
    token = _current.set(normalize_lang(lang) or default_lang())
    try:
        yield
    finally:
        _current.reset(token)


def tr(text, lang=None, **kwargs):
    """Translated text for the current (or given) language; kwargs fill {placeholders}."""
    code = normalize_lang(lang) or get_lang()
    out = EN.get(text, text) if code == "en" else text
    if kwargs:
        try:
            return out.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text.format(**kwargs)
    return out


def is_english():
    return get_lang() == "en"


def N_(text):
    """Marks a module-level string for translation without translating it at import time (gettext-style no-op).
    Translate it where it is shown: tr(CONSTANT)."""
    return text

"""Язык надписей на схемах: русский (исходный текст в скриптах) или английский (переводы в en.py).

Скрипты пишут надписи по-русски. В английской сборке T() подменяет каждую надпись переводом прямо в функциях
переноса и размещения (wrap, text_size, text_el), поэтому размеры блоков считаются уже по английскому тексту.

    python build_engineering.py ../../docs/MINT_engineering --lang en

Ключ перевода — русская надпись с пробелами и переносами, сжатыми до одного пробела. Ненайденные переводы
сборка перечисляет и завершается с ошибкой. DIAGRAM_COLLECT=файл.json — выписать все русские надписи (для en.py).
"""
import atexit
import json
import os
import re
import sys

LANG = "ru"
if "--lang" in sys.argv:
    i = sys.argv.index("--lang")
    LANG = sys.argv[i + 1]
    del sys.argv[i:i + 2]

_CYR = re.compile("[А-Яа-яЁё]")
_TAG = re.compile(r"^(◆ |◇ )?\[([РАТПУ])\] ")
TAGS_EN = {"Р": "M", "А": "A", "Т": "T", "П": "C", "У": "D"}   # вручную, авто, тест, проверка, умолчание
MISSING, _seen = [], {}
_collect = os.environ.get("DIAGRAM_COLLECT")


def key(text):
    return re.sub(r"\s+", " ", text).strip()


def T(text):
    if not text or not _CYR.search(text):
        return text
    if _collect:
        _seen.setdefault(key(text), text)
    if LANG == "ru":
        return text
    from en import EN
    m = _TAG.match(text)
    if m:                                          # «[Р] LLM_API_URL» → «[M] LLM_API_URL»
        rest = text[m.end():]
        tagged = f"{m.group(1) or ''}[{TAGS_EN[m.group(2)]}] "
        if not _CYR.search(rest):
            return tagged + rest
    out = EN.get(key(text))
    if out is None:
        if key(text) not in MISSING:
            MISSING.append(key(text))
        return text
    return out


@atexit.register
def _report():
    if _collect:
        with open(_collect, "w", encoding="utf-8") as f:
            json.dump(_seen, f, ensure_ascii=False, indent=1)
    if LANG != "ru" and MISSING:
        print(f"Нет перевода для {len(MISSING)} надписей (en.py):", file=sys.stderr)
        for k in MISSING[:40]:
            print("  " + k[:150], file=sys.stderr)
        os._exit(1)

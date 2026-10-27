"""Промпты моделей: тексты по умолчанию — в ru.yaml и en.yaml рядом, свои правки — в prompts.yaml, здесь — их
чтение, проверка и сборка.

Все тексты, которые получает модель (системные промпты, разметка контекста и вопроса, пометки), лежат в
mint/prompts/<язык>.yaml: один ключ — один текст, {{имя}} — подстановка, которую заполняет код. Язык текстов —
язык интерфейса (mint/i18n). Ключи и подстановки в двух файлах одинаковые — это проверяет tests/test_prompts.py.

Профиль (PROFILES) — набор умолчаний: «general» — <язык>.yaml, другие профили заменяют часть текстов своими из
profiles/<профиль>.<язык>.yaml. Профиль сеанса задаёт set_profile() (как язык — set_lang()).

Действующий текст = умолчание профиля ← своя правка из prompts.yaml (рядом с программой или PROMPTS_PATH) ← правка
«на время сеанса» (страница «📝 Промпты»). Править можно только ключи из EDITABLE; разметку контекста и
вопроса — нет. Правка не принимается, если в ней нет обязательных частей формата ответа (FORMAT_PARTS: их
разбирает код) или подстановок {{…}} умолчания — check_text() говорит, чего не хватает.

    prompt_text("chat_system")                    # действующий текст на языке интерфейса
    render("audit_user", section=text)            # с подстановками
    prompts_version()                             # «ru-1a2b3c4d»: язык и хэш всех действующих текстов

Версия набора пишется в отзывы, лог аудита и проверку качества: по ней видно, при каких текстах получен
результат. Константы CHAT_SYSTEM_PROMPT и др. — тексты по умолчанию (для тестов и совместимости).
"""

import contextvars
import hashlib
import json
import logging
import os
import re
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

import yaml

from ..config import prompts_file_path
from ..i18n import LANGS, N_, get_lang, tr

logger = logging.getLogger("MINT")

PROMPTS_DIR = Path(__file__).resolve().parent

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")

_CACHE = {}
_FILE_CACHE = {"sig": None, "data": {}, "problems": []}
_FILE_LOCK = threading.Lock()
_WRITE_LOCK = threading.Lock()    # сохранения из разных сеансов не затирают друг друга
_SESSION = contextvars.ContextVar("mint_prompt_session", default=None)   # {язык: {ключ: текст}} — правки сеанса
_PROFILE = contextvars.ContextVar("mint_prompt_profile", default=None)   # профиль промптов сеанса (PROFILES)
_DEFAULTS_ONLY = contextvars.ContextVar("mint_prompt_defaults_only", default=False)


# ---------------------------------------------------------------- что можно править

# Ключи, которые правятся на странице «📝 Промпты»: ключ → (группа, название, что делает). Остальное — разметка
# контекста и вопроса (её разбирает код), она не правится.
EDITABLE = {
    "chat_system": (N_("Чат"), N_("Системный промпт чата"),
                    N_("Роль и правила ответа в чате. Ссылки — в формате [Источник: файл, раздел]: по нему MINT "
                       "проверяет, что ссылка ведёт на найденный фрагмент.")),
    "chat_no_info": (N_("Чат"), N_("Фраза «информации нет»"),
                     N_("Что модель отвечает, если в документах ответа нет. Подставляется в системный промпт; по ней "
                        "проверка качества узнаёт честное «информации нет».")),
    "search_low_confidence": (N_("Чат"), N_("Пометка «уверенность низкая»"),
                              N_("Добавляется в начало контекста, когда поиск не уверен в найденном. Системный промпт "
                                 "чата ссылается на неё — меняйте их вместе.")),
    "condense_system": (N_("Чат"), N_("Уточнение вопроса по истории"),
                        N_("Переписывает уточняющий вопрос («а для второго контура?») в самостоятельный — для поиска.")),
    "paraphrase_system": (N_("Чат"), N_("Перефразировка вопроса (multi-query)"),
                          N_("Вторая формулировка вопроса для поиска, если включён multi-query.")),
    "audit_system": (N_("Аудит документа"), N_("Проверка раздела"),
                     N_("Роль и правила проверки одного раздела. Теги критичности и фраза «раздел чистый» обязательны: "
                        "по ним MINT разбирает замечания.")),
    "audit_focus_default": (N_("Аудит документа"), N_("Критерии по умолчанию"),
                            N_("Текст поля «Общие критерии проверки» во вкладке «Аудит документа». У каждого профиля "
                               "(боковая панель → «🧭 Профиль») — свои критерии.")),
    "audit_focus_generic": (N_("Аудит документа"), N_("Критерии, если поле пустое"),
                            N_("Используются, когда поле критериев очищено.")),
    "audit_special_rule": (N_("Аудит документа"), N_("Правило «особого внимания»"),
                           N_("Добавляется к правилам проверки, если заполнено поле «Особое внимание».")),
    "audit_norms": (N_("Аудит документа"), N_("Нормы из базы"),
                    N_("Заголовок блока с нормативными фрагментами, найденными для раздела.")),
    "audit_no_norms": (N_("Аудит документа"), N_("Нормы не найдены"),
                       N_("Пометка, если для раздела в базе ничего не нашлось.")),
    "audit_autonomous": (N_("Аудит документа"), N_("Аудит без базы знаний"),
                         N_("Пометка, если аудит идёт без нормативной базы.")),
    "audit_focus_answer_system": (N_("Аудит документа"), N_("Ответ на пункт «особого внимания»"),
                                  N_("Отдельный шаг на весь документ: ответ на каждый пункт поля «Особое внимание» и "
                                     "замечания по нему. Строка «Ответ:» и теги критичности обязательны.")),
    "audit_checklist_system": (N_("Аудит документа"), N_("Пункт чек-листа"),
                               N_("Ответ на каждый пункт чек-листа по типу документа — по всему документу. Строка "
                                  "«Ответ:» со словом «да / частично / нет / не относится» и теги критичности "
                                  "обязательны.")),
    "audit_pinned": (N_("Аудит документа"), N_("Правила экспертов и карточки систем"),
                     N_("Заголовок блока с документами базы «учитывать в аудите всегда» и карточками упомянутых "
                        "систем: они передаются модели в каждой проверке, отдельно от найденных норм.")),
    "audit_basis": (N_("Аудит документа"), N_("Документы-основания"),
                    N_("Заголовок блока с фрагментами документов-оснований из базы — документов, по которым "
                       "разработан проверяемый документ (ссылки на титуле и в «Ссылочных документах»): они "
                       "передаются модели в каждой проверке, отдельно от найденных норм.")),
    "audit_card_system": (N_("Аудит документа"), N_("Что документ требует от системы"),
                          N_("По карточке каждой системы, упомянутой в документе: требования документа к системе со "
                             "статусами «есть / в планах / доработка / противоречие / неясно» и замечания. Статусы и "
                             "теги критичности обязательны.")),
    "audit_absence_system": (N_("Аудит документа"), N_("Сверка «не описано» с документом"),
                             N_("Когда документ целиком не помещается в окно модели: есть ли в других разделах то, "
                                "чего по замечанию нет. JSON-поля обязательны.")),
    "audit_merge_system": (N_("Аудит документа"), N_("Сведение повторов"),
                           N_("Последний шаг аудита: группы замечаний об одном и том же недостатке. Формат ответа — "
                              "JSON-массив групп номеров.")),
    "audit_summary_system": (N_("Аудит документа"), N_("«Главное» в начале заключения"),
                             N_("Из всех замечаний — самые важные (не больше audit_summary_max), каждое одной строкой: "
                                "в начале заключения они идут указателями на замечания по номерам. Формат ответа — "
                                "JSON-массив с полями n и gist.")),
    "deep_step_system": (N_("Глубокая проверка"), N_("Процесс: переход между шагами"),
                         N_("Для каждой пары соседних шагов процесса (таблица операций, список шагов или разделы «Шаг N»): "
                            "откуда вход, кто передаёт, может ли получатель обработать данные, совпадает ли с "
                            "требованиями.")),
    "deep_requirement_system": (N_("Глубокая проверка"), N_("Процесс: требование и шаги"),
                                N_("Для каждого требования к процессу: есть ли шаг, который его выполняет, и нет ли "
                                   "шага, который ему противоречит.")),
    "deep_boundary_system": (N_("Глубокая проверка"), N_("Процесс: границы и результаты"),
                             N_("Первый и последний шаг процесса — по границам процесса; шаг для каждого результата "
                                "и потребителя; участники и системы.")),
    "deep_claims_system": (N_("Глубокая проверка"), N_("Утверждения раздела"),
                           N_("Из каждой части — утверждения для сверки с другими разделами, с темой из списка. "
                              "JSON-поля обязательны.")),
    "deep_conflict_system": (N_("Глубокая проверка"), N_("Противоречия между разделами"),
                             N_("Утверждения разных разделов на одну тему: есть ли противоречия.")),
    "deep_numbers_system": (N_("Глубокая проверка"), N_("Согласованность цифр"),
                            N_("Показатели документа и расчёты программы: сходятся ли объёмы, среднее и максимум, "
                               "одинаковые показатели в разных разделах.")),
    "deep_language_system": (N_("Глубокая проверка"), N_("Опечатки"),
                             N_("Явные опечатки и грамматические ошибки в каждой части.")),
    "audit_reference_system": (N_("Аудит документа"), N_("Сверка с эталоном"),
                               N_("Какие замечания эталона нашёл аудит. JSON-поля и коды вердиктов обязательны.")),
    "critique_system": (N_("Аудит документа"), N_("Самокритика"),
                        N_("Второй проход: оставить или удалить каждое замечание, критичность и дословная цитата. "
                           "JSON-поля и коды вердиктов и критичности обязательны.")),
    "card_section_system": (N_("Карточки систем"), N_("Черновик карточки: раздел"),
                            N_("Черновик карточки системы по базе: на каждый раздел карточки — ответ только по "
                               "найденным фрагментам, у каждого факта ссылка [Источник: …]. Фраза «НЕТ В БАЗЕ» "
                               "обязательна: по ней MINT отмечает пробел для эксперта.")),
    "review_system": (N_("Контроль исправлений"), N_("Проверка замечания"),
                      N_("Исправлено ли замечание в новой редакции. JSON-ответ со статусом и цитатой обязателен.")),
    "question_gen_system": (N_("Проверка качества"), N_("Черновик вопросов по базе"),
                            N_("По фрагменту базы — вопрос и дословная цитата с ответом. JSON-ответ обязателен.")),
}

# Ключи, правку которых измеряет проверка качества с ответами чата (вопросы без истории диалога)
MEASURED_BY_ANSWERS = ("chat_system", "chat_no_info", "search_low_confidence", "paraphrase_system")

# Обязательные части формата ответа: их разбирает код (audit.py, review.py, citations.py, evaluation.py)
FORMAT_PARTS = {
    "chat_system": {"ru": ["[Источник:"], "en": ["[Source:"]},
    "audit_system": {"ru": ["[КРИТИЧНЫЙ]", "[СРЕДНИЙ]", "[НИЗКИЙ]", "Часть чистая"],
                     "en": ["[CRITICAL]", "[MEDIUM]", "[LOW]", "Section is clean"]},
    "critique_system": {
        "ru": ['"n": 1', '"verdict": "ОСТАВИТЬ|УДАЛИТЬ"', '"severity": "КРИТИЧНЫЙ|СРЕДНИЙ|НИЗКИЙ"', '"quote":',
               '"text":', '"reason":'],
        "en": ['"n": 1', '"verdict": "KEEP|DROP"', '"severity": "CRITICAL|MEDIUM|LOW"', '"quote":', '"text":',
               '"reason":']},
    "audit_focus_answer_system": {"ru": ["Ответ:", "[КРИТИЧНЫЙ]", "[СРЕДНИЙ]", "[НИЗКИЙ]"],
                                  "en": ["Answer:", "[CRITICAL]", "[MEDIUM]", "[LOW]"]},
    "audit_checklist_system": {"ru": ["Ответ:", "«да»", "«частично»", "«нет»", "«не относится»", "[КРИТИЧНЫЙ]",
                                      "[СРЕДНИЙ]", "[НИЗКИЙ]"],
                               "en": ["Answer:", '"yes"', '"partially"', '"no"', '"not applicable"', "[CRITICAL]",
                                      "[MEDIUM]", "[LOW]"]},
    "audit_card_system": {"ru": ["[ЕСТЬ]", "[В ПЛАНАХ]", "[ДОРАБОТКА]", "[ПРОТИВОРЕЧИЕ]", "[НЕЯСНО]", "[КРИТИЧНЫЙ]",
                                 "[СРЕДНИЙ]", "[НИЗКИЙ]", "Требований к системе нет"],
                          "en": ["[HAVE]", "[PLANNED]", "[CHANGE]", "[CONFLICT]", "[UNCLEAR]", "[CRITICAL]", "[MEDIUM]",
                                 "[LOW]", "No requirements for the system"]},
    "audit_absence_system": {"ru": ['"found":', '"quote":', '"reason":'], "en": ['"found":', '"quote":', '"reason":']},
    "audit_merge_system": {"ru": ["[[1, 4], [2, 7, 9]]"], "en": ["[[1, 4], [2, 7, 9]]"]},
    "audit_summary_system": {"ru": ['"n":', '"gist":'], "en": ['"n":', '"gist":']},
    **{k: {"ru": ["[КРИТИЧНЫЙ]", "[СРЕДНИЙ]", "[НИЗКИЙ]", "Часть чистая"],
           "en": ["[CRITICAL]", "[MEDIUM]", "[LOW]", "Section is clean"]}
       for k in ("deep_step_system", "deep_requirement_system", "deep_boundary_system", "deep_conflict_system",
                 "deep_numbers_system")},
    "deep_language_system": {"ru": ["[НИЗКИЙ]", "Часть чистая"], "en": ["[LOW]", "Section is clean"]},
    "deep_claims_system": {"ru": ['"topic":', '"claim":'], "en": ['"topic":', '"claim":']},
    "audit_reference_system": {"ru": ['"verdict": "НАЙДЕНО|ЧАСТИЧНО|НЕТ"', '"found":'],
                               "en": ['"verdict": "FOUND|PARTIAL|NO"', '"found":']},
    "card_section_system": {"ru": ["[Источник:", "НЕТ В БАЗЕ"], "en": ["[Source:", "NOT IN THE BASE"]},
    "review_system": {"ru": ['{"status": "ИСПРАВЛЕНО|ЧАСТИЧНО|НЕ_ИСПРАВЛЕНО", "quote": "...", "comment": "..."}'],
                      "en": ['{"status": "FIXED|PARTIAL|NOT_FIXED", "quote": "...", "comment": "..."}']},
    "question_gen_system": {"ru": ['{"question": "...", "quote": "..."}'], "en": ['{"question": "...", "quote": "..."}']},
}


# ---------------------------------------------------------------- тексты

def _lang(lang):
    return lang if lang in LANGS else get_lang()


def _short_hash(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:8]


# ---------------------------------------------------------------- профили

# Профиль — набор промптов по умолчанию: «general» — <язык>.yaml (роли и критерии для любых документов),
# остальные — <язык>.yaml с заменой части текстов из profiles/<профиль>.<язык>.yaml. «architecture» — промпты MINT до
# появления профилей слово в слово (роли «Архитектурного комитета», архитектурные критерии): версия набора та же, что
# раньше, — результаты сравнимы. Профиль сеанса — боковая панель «🧭 Профиль», по умолчанию — profile в config.yaml
# (не задан — DEFAULT_PROFILE).
PROFILES = {
    "architecture": N_("Архитектура и ИТ-решения"),
    "general": N_("Универсальный — любые документы"),
}
DEFAULT_PROFILE = "architecture"


def normalize_profile(name):
    """Известный профиль или профиль по умолчанию."""
    return name if name in PROFILES else DEFAULT_PROFILE


def get_profile():
    return _PROFILE.get() or DEFAULT_PROFILE


def set_profile(name):
    """Профиль промптов для текущего сеанса (потока), как i18n.set_lang(). Возвращает действующий профиль."""
    name = normalize_profile(name)
    _PROFILE.set(name)
    return name


@contextmanager
def use_profile(name):
    token = _PROFILE.set(normalize_profile(name))
    try:
        yield
    finally:
        _PROFILE.reset(token)


def _read_texts(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
        raise ValueError(f"{path}: ожидаются пары «ключ: текст»")
    return data


def profile_overrides(profile, lang=None):
    """Тексты профиля, которые заменяют <язык>.yaml: {ключ: текст} (у «general» — пусто)."""
    lang, profile = _lang(lang), normalize_profile(profile)
    if profile == "general":
        return {}
    key = ("profile", profile, lang)
    if key not in _CACHE:
        _CACHE[key] = _read_texts(PROMPTS_DIR / "profiles" / f"{profile}.{lang}.yaml")
    return _CACHE[key]


def default_prompts(lang=None):
    """Все тексты по умолчанию действующего профиля: <язык>.yaml ← profiles/<профиль>.<язык>.yaml. Читаются один
    раз."""
    lang, profile = _lang(lang), get_profile()
    key = (lang, profile)
    if key not in _CACHE:
        if lang not in _CACHE:
            _CACHE[lang] = _read_texts(PROMPTS_DIR / f"{lang}.yaml")
        _CACHE[key] = {**_CACHE[lang], **profile_overrides(profile, lang)}
    return _CACHE[key]


def default_text(key, lang=None):
    texts = default_prompts(lang)
    if key not in texts:
        raise KeyError(f"нет промпта «{key}» ({_lang(lang)}.yaml)")
    return texts[key]


def placeholders(text):
    """Имена подстановок {{имя}} в тексте — в порядке появления, без повторов."""
    return list(dict.fromkeys(_PLACEHOLDER_RE.findall(text or "")))


def format_parts(key, lang=None):
    """Обязательные части формата ответа и подстановки умолчания: ([части], [подстановки])."""
    lang = _lang(lang)
    return list(FORMAT_PARTS.get(key, {}).get(lang, [])), placeholders(default_text(key, lang))


def check_text(key, lang, text):
    """Что не так со своей правкой: [описание] (пусто — правку можно применить)."""
    lang = _lang(lang)
    if key not in EDITABLE:
        if key in default_prompts(lang):
            return [tr("«{key}» — разметка, её не правят", key=key)]
        return [tr("промпта «{key}» нет", key=key)]
    if not (text or "").strip():
        return [tr("текст пустой")]
    problems = []
    parts, need = format_parts(key, lang)
    have = set(placeholders(text))
    missing = [p for p in need if p not in have]
    extra = sorted(have - set(need))
    if missing:
        problems.append(tr("нет подстановки: {v} — её заполняет MINT", v=", ".join("{{" + p + "}}" for p in missing)))
    if extra:
        problems.append(tr("неизвестная подстановка: {v} — MINT её не заполнит",
                           v=", ".join("{{" + p + "}}" for p in extra)))
    lost = [part for part in parts if part not in text]
    if lost:
        problems.append(tr("нет обязательной части формата ответа: {v} — по ней MINT разбирает ответ модели",
                           v="; ".join(lost)))
    return problems


# ---------------------------------------------------------------- свои правки: prompts.yaml и сеанс

def custom_file():
    return prompts_file_path()


def _file_sig(path):
    try:
        st_ = path.stat()
        return (str(path), st_.st_mtime_ns, st_.st_size)
    except OSError:
        return (str(path), None, None)


def custom_file_prompts():
    """Правки из prompts.yaml: ({язык: {ключ: {"text", "base"}}}, [что пропущено и почему]). Неверные правки
    (нет обязательных частей, неизвестный ключ) не применяются — MINT работает с умолчанием. Файл
    перечитывается, когда меняется."""
    path = custom_file()
    sig = _file_sig(path) + (get_lang(),)        # пояснения — на языке интерфейса
    with _FILE_LOCK:
        if _FILE_CACHE["sig"] == sig:
            return _FILE_CACHE["data"], _FILE_CACHE["problems"]
        data, problems = {}, []
        if sig[1] is not None:
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
            except Exception as e:
                raw = {}
                problems.append(tr("{name} не прочитан ({e}) — действуют промпты по умолчанию.", name=path.name,
                                   e=str(e)[:150]))
            if not isinstance(raw, dict):
                problems.append(tr("{name}: ожидаются разделы ru: и en: — файл пропущен.", name=path.name))
                raw = {}
            for lang, entries in raw.items():
                if lang not in LANGS or not isinstance(entries, dict):
                    problems.append(tr("{name}: раздел «{language}» пропущен — нужны ru: или en:.", name=path.name, language=lang))
                    continue
                for key, value in entries.items():
                    text, base = (value.get("text"), value.get("base")) if isinstance(value, dict) else (value, None)
                    if not isinstance(text, str):
                        problems.append(tr("{language}.{key}: нет текста — пропущено.", language=lang, key=key))
                        continue
                    bad = check_text(key, lang, text)
                    if bad:
                        problems.append(tr("{language}.{key} не применён: {why}.", language=lang, key=key, why="; ".join(bad)))
                        continue
                    data.setdefault(lang, {})[key] = {"text": text, "base": None if base is None else str(base)}
        for p in problems:
            logger.warning(f"Свои правки промптов: {p}")
        _FILE_CACHE.update(sig=sig, data=data, problems=problems)
        return data, problems


def set_session_prompts(overrides):
    """Правки «на время сеанса» для текущего потока (сеанса Streamlit): {язык: {ключ: текст}} или None. Вызывается
    в начале каждого прогона страницы, как i18n.set_lang()."""
    _SESSION.set(overrides or None)


@contextmanager
def defaults_only():
    """Внутри блока действуют только тексты по умолчанию (без prompts.yaml и правок сеанса)."""
    token = _DEFAULTS_ONLY.set(True)
    try:
        yield
    finally:
        _DEFAULTS_ONLY.reset(token)


def effective_prompts(lang=None):
    """Действующие тексты языка: умолчание ← prompts.yaml ← правки сеанса."""
    lang = _lang(lang)
    texts = dict(default_prompts(lang))
    if _DEFAULTS_ONLY.get():
        return texts
    file_data, _ = custom_file_prompts()
    for key, v in (file_data.get(lang) or {}).items():
        texts[key] = v["text"]
    for key, text in ((_SESSION.get() or {}).get(lang) or {}).items():
        if key in EDITABLE and isinstance(text, str) and not check_text(key, lang, text):
            texts[key] = text
    return texts


def custom_status(lang=None):
    """Какие тексты отличаются от умолчания: {ключ: "session" | "file"}."""
    lang = _lang(lang)
    defaults = default_prompts(lang)
    file_data, _ = custom_file_prompts()
    out = {k: "file" for k, v in (file_data.get(lang) or {}).items() if v["text"] != defaults.get(k)}
    for key, text in ((_SESSION.get() or {}).get(lang) or {}).items():
        if key in EDITABLE and text != defaults.get(key) and not check_text(key, lang, text):
            out[key] = "session"
    return out


def custom_label(custom):
    """Свои правки для итогов: «Системный промпт чата (в сеансе); …» ({ключ: "file" | "session"} → текст)."""
    where = {"session": N_("в сеансе"), "file": N_("сохранено")}
    return "; ".join(f"{tr(EDITABLE[k][1]) if k in EDITABLE else k} ({tr(where.get(v, v))})"
                     for k, v in (custom or {}).items())


def default_changed(key, lang=None):
    """Умолчание изменилось после того, как правка сохранена в prompts.yaml (обновление MINT)."""
    lang = _lang(lang)
    entry = (custom_file_prompts()[0].get(lang) or {}).get(key)
    return bool(entry and entry.get("base") and entry["base"] != _short_hash(default_text(key, lang)))


_FILE_HEADER = """\
# Свои правки промптов MINT / your own prompt edits. Пишет страница «📝 Промпты» / written by the "📝 Prompts" page.
# Здесь — только изменённые тексты; остальные берутся по умолчанию из mint/prompts/<язык>.yaml.
# base — хэш умолчания, от которого сделана правка: если MINT обновится и умолчание изменится, страница
# «📝 Промпты» об этом скажет. Обязательные части формата ответа (теги, JSON, [Источник: …]) удалять нельзя:
# такая правка не применится.
"""


class _Literal(str):
    pass


def _literal(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|" if "\n" in data or len(data) > 80 else None)


yaml.SafeDumper.add_representer(_Literal, _literal)


def _read_raw(path):
    """prompts.yaml как есть — со всеми записями, и неверными тоже: при сохранении одной правки остальное в файле
    не теряется. Нечитаемый файл — ValueError: перезаписывать его нельзя."""
    if not path.is_file():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    except Exception as e:
        raw = e
    if not isinstance(raw, dict):
        raise ValueError(tr("{name} не прочитан — исправьте или удалите файл и сохраните снова ({e}).",
                            name=path.name, e=str(raw)[:150] if isinstance(raw, Exception) else type(raw).__name__))
    return raw


def _yaml_entry(value):
    if isinstance(value, str):
        return _Literal(value)
    if isinstance(value, dict) and isinstance(value.get("text"), str):
        return {**{k: v for k, v in value.items() if k != "text"}, "text": _Literal(value["text"])}
    return value


def _write_custom(raw):
    path = custom_file()
    out = {lang: ({key: _yaml_entry(v) for key, v in entries.items()} if isinstance(entries, dict) else entries)
           for lang, entries in raw.items() if entries}
    body = _FILE_HEADER + (yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=10 ** 6) if out else "")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".prompts-", suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    os.replace(tmp, path)
    _FILE_CACHE["sig"] = None
    return path


def save_custom(key, lang, text):
    """Сохраняет правку в prompts.yaml (текст как у умолчания — правка убирается). Возвращает путь к файлу.
    Неверная правка — ValueError с описанием."""
    lang = _lang(lang)
    bad = check_text(key, lang, text)
    if bad:
        raise ValueError("; ".join(bad))
    with _WRITE_LOCK:
        raw = _read_raw(custom_file())
        section = raw.get(lang) if isinstance(raw.get(lang), dict) else {}
        if text == default_text(key, lang):
            section.pop(key, None)
        else:
            section[key] = {"base": _short_hash(default_text(key, lang)), "text": text}
        raw[lang] = section
        return _write_custom(raw)


def file_has(key, lang):
    """Есть ли в prompts.yaml запись для ключа — в том числе неверная, которая не применяется."""
    try:
        section = _read_raw(custom_file()).get(_lang(lang))
    except ValueError:
        return False
    return isinstance(section, dict) and key in section


def remove_custom(key, lang):
    """Убирает правку из prompts.yaml — действует умолчание."""
    return save_custom(key, lang, default_text(key, lang))


def prompt_extra_chars(keys, lang=None):
    """На сколько символов действующие тексты длиннее умолчаний (для запаса окна модели в mint/limits.py)."""
    lang = _lang(lang)
    eff, base = effective_prompts(lang), default_prompts(lang)
    return sum(max(0, len(eff.get(k, "")) - len(base.get(k, ""))) for k in keys)


def prompt_text(key, lang=None):
    """Действующий текст промпта (с {{подстановками}})."""
    texts = effective_prompts(lang)
    if key not in texts:
        raise KeyError(f"нет промпта «{key}» ({_lang(lang)}.yaml)")
    return texts[key]


def fill(template, values, name="промпт"):
    """Подставляет значения за один проход: {{…}} внутри подставленного текста (документа, вопроса) не трогается."""
    def sub(m):
        if m.group(1) not in values:
            raise KeyError(f"{name}: не задана подстановка {{{{{m.group(1)}}}}}")
        return str(values[m.group(1)])
    return _PLACEHOLDER_RE.sub(sub, template)


def render(key, lang=None, **values):
    """Действующий текст промпта с подстановками на языке интерфейса (или заданном)."""
    return fill(prompt_text(key, lang), values, name=key)


def prompts_version(lang=None):
    """Версия набора промптов: «<язык>-<8 знаков хэша>» действующих текстов. Меняется при любой правке."""
    lang = _lang(lang)
    texts = effective_prompts(lang)
    digest = hashlib.sha256(json.dumps(texts, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return f"{lang}-{digest[:8]}"


# ---------------------------------------------------------------- чат

def chat_system_prompt(lang=None):
    return render("chat_system", lang, no_info=prompt_text("chat_no_info", lang))


def chat_user_content(context, question, abbreviations="", search_question=None):
    parts = []
    if abbreviations:
        parts.append(render("chat_user_abbreviations", abbreviations=abbreviations))
    parts.append(render("chat_user_context", context=context))
    if search_question and search_question.strip() != (question or "").strip():
        parts.append(render("chat_user_question_rewritten", question=question, search_question=search_question))
    else:
        parts.append(render("chat_user_question", question=question))
    return "\n\n".join(parts)


def condense_system(lang=None):
    return prompt_text("condense_system", lang)


def paraphrase_system(lang=None):
    return prompt_text("paraphrase_system", lang)


def low_confidence_note(lang=None):
    return prompt_text("search_low_confidence", lang) + "\n\n"


# ---------------------------------------------------------------- аудит

def no_norms_note(lang=None):
    return prompt_text("audit_no_norms", lang) + "\n\n"


def autonomous_note(lang=None):
    return prompt_text("audit_autonomous", lang) + "\n\n"


def norms_block(norms_text):
    return render("audit_norms", norms=norms_text) + "\n\n"


def default_audit_focus(lang=None):
    """Критерии действующего профиля."""
    return prompt_text("audit_focus_default", lang)


def profile_audit_focus(profile, lang=None):
    """Критерии профиля на языке интерфейса (или lang); неизвестный профиль — профиль по умолчанию."""
    with use_profile(profile):
        return prompt_text("audit_focus_default", lang)


def texts_all_profiles(key):
    """Текст ключа во всех профилях на всех языках — действующий и по умолчанию. Нужен, чтобы узнать текст, который
    пользователь не правил (критерии в поле), или ответ «информации нет» любого профиля."""
    out = set()
    for profile in PROFILES:
        with use_profile(profile):
            for lang in LANGS:
                out.add(prompt_text(key, lang))
                with defaults_only():
                    out.add(prompt_text(key, lang))
    return out


def all_profile_focus_texts():
    """Критерии всех профилей на всех языках: поле с таким текстом пользователь не правил."""
    return texts_all_profiles("audit_focus_default")


def generic_audit_focus(lang=None):
    return prompt_text("audit_focus_generic", lang)


def special_focus_block(special):
    """Блок «особого внимания» — то, что пользователь отметил как важное именно в этом документе."""
    if not (special or "").strip():
        return ""
    return render("audit_special", special=special.strip()) + "\n\n"


def audit_map_prompt(norms_prompt, focus, special="", max_findings=10):
    has_special = bool((special or "").strip())
    return render("audit_system", norms=norms_prompt, special=special_focus_block(special), focus=focus,
                  special_rule=prompt_text("audit_special_rule") + "\n" if has_special else "",
                  max_findings=max_findings)


def critique_system(lang=None):
    return prompt_text("critique_system", lang)


def document_block(document):
    """Документ целиком — для справки к проверке раздела, самокритике и ответам на «особое внимание»."""
    return render("audit_document", document=document) + "\n\n" if (document or "").strip() else ""


def outline_block(outline):
    """Оглавление — когда документ целиком в окно модели не помещается."""
    return render("audit_outline", outline=outline) + "\n\n" if (outline or "").strip() else ""


def location_line(path, continued=False):
    """Строка «Расположение главы в документе: …» перед проверяемой частью."""
    if not (path or "").strip():
        return ""
    return render("audit_location_continued" if continued else "audit_location", path=path) + "\n\n"


def focus_answer_prompt(norms_prompt):
    return render("audit_focus_answer_system", norms=norms_prompt)


def basis_block(basis_text):
    """Документы-основания — отдельным блоком перед правилами экспертов и найденными нормами."""
    return render("audit_basis", basis=basis_text) + "\n\n" if (basis_text or "").strip() else ""


def pinned_block(pinned_text):
    """Правила экспертов и карточки систем — отдельным блоком перед найденными нормами."""
    return render("audit_pinned", pinned=pinned_text) + "\n\n" if (pinned_text or "").strip() else ""


def checklist_prompt(norms_prompt, doc_type=""):
    kind = (" " + render("audit_checklist_doc_type", doc_type=doc_type.strip())) if (doc_type or "").strip() else ""
    return render("audit_checklist_system", norms=norms_prompt, doc_type=kind)


def card_prompt(system):
    return render("audit_card_system", system=system)


# ---------------------------------------------------------------- контроль исправлений

def review_prompt(wiki_part):
    return render("review_system", norms=wiki_part)


# ---------------------------------------------------------------- проверка качества

def question_gen_system(lang=None):
    """Черновик вопросов по фрагментам базы (mint/evaluation.py): вопрос — на языке фрагмента, потому что
    пользователи спрашивают на языке базы, а не интерфейса."""
    return prompt_text("question_gen_system", lang)


# ---------------------------------------------------------------- тексты по умолчанию (тесты, совместимость)

with defaults_only():
    PARAPHRASE_SYSTEM, PARAPHRASE_SYSTEM_EN = paraphrase_system("ru"), paraphrase_system("en")
    CHAT_SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT_EN = chat_system_prompt("ru"), chat_system_prompt("en")
    CONDENSE_SYSTEM, CONDENSE_SYSTEM_EN = condense_system("ru"), condense_system("en")
    LOW_CONFIDENCE_NOTE, LOW_CONFIDENCE_NOTE_EN = low_confidence_note("ru"), low_confidence_note("en")
    NO_NORMS_NOTE, NO_NORMS_NOTE_EN = no_norms_note("ru"), no_norms_note("en")
    AUTONOMOUS_NOTE, AUTONOMOUS_NOTE_EN = autonomous_note("ru"), autonomous_note("en")
    DEFAULT_AUDIT_FOCUS, DEFAULT_AUDIT_FOCUS_EN = default_audit_focus("ru"), default_audit_focus("en")
    GENERIC_AUDIT_FOCUS, GENERIC_AUDIT_FOCUS_EN = generic_audit_focus("ru"), generic_audit_focus("en")
    CRITIQUE_SYSTEM, CRITIQUE_SYSTEM_EN = critique_system("ru"), critique_system("en")
    QUESTION_GEN_SYSTEM, QUESTION_GEN_SYSTEM_EN = question_gen_system("ru"), question_gen_system("en")


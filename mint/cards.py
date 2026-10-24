"""Черновик карточки системы по базе знаний: по каждому разделу карточки — узкий вопрос, поиск по базе и ответ
модели только по найденному, со ссылкой на источник у каждого факта. Пробелы помечаются для эксперта.

    from mint.cards import draft_system_card
    card = draft_system_card("Система А", cfg)
    card["markdown"]  # карточка по шаблону — скачать, проверить, дописать и загрузить в базу с отметкой «🗂️»

Почему по разделам, а не «составь карточку целиком»: поиск на каждый вопрос находит несколько фрагментов, и общий
вопрос нашёл бы фрагменты про одну-две темы, а остальное модель пропустила бы или додумала. Узкий вопрос — один
раздел карточки — находит нужное; тот же принцип, что в глубокой проверке аудита.
"""

import logging
import re
import time
from dataclasses import replace

from .audit import is_llm_error
from .citations import check_citations
from .i18n import N_, tr
from .kb import load_glossary
from .parallel import parallel_map
from .prompts import render
from .search import search_parent_child
from .services import ask_llm

logger = logging.getLogger("MINT")

CARD_TOP_K = 8              # фрагментов базы на раздел карточки: раздел шире вопроса чата
CARD_PARALLEL = 3           # разделов одновременно (если в настройках аудита не меньше)
NAMES_MAX = 12              # названий системы в строке «Названия:»

# Разделы карточки: (ключ, заголовок, запрос к поиску, вопрос модели). {system} — название системы. Заголовок
# группы «Что умеет сейчас» объединяет несколько разделов (CARD_LAYOUT).
CARD_SECTIONS = [
    ("names", N_("Названия"),
     N_("{system} полное название сокращение"),
     N_("Как ещё называется {system} в документах: полное название, сокращения, названия частей? Каждый вариант "
        "написания — отдельной строкой.")),
    ("purpose", N_("Назначение"),
     N_("{system} назначение пользователи смежные системы"),
     N_("Для чего предназначена {system}, кто её пользователи и с какими системами она взаимодействует?")),
    ("services", N_("Сервисы и функции"),
     N_("{system} сервисы функции возможности"),
     N_("Какие сервисы и функции {system} предоставляет смежным системам?")),
    ("limits", N_("Лимиты и объёмы"),
     N_("{system} ограничения объём размер производительность время ответа режим работы"),
     N_("Какие ограничения по объёму и производительности есть у {system}: размер сообщения или файла, количество "
        "в сутки, время ответа, режим работы? Цифры — с единицами измерения.")),
    ("security", N_("Защита данных"),
     N_("{system} шифрование электронная подпись сертификат ключи"),
     N_("Как {system} защищает данные: подпись и шифрование, на чьих сертификатах, кто расшифровывает, где хранятся "
        "ключи?")),
    ("storage", N_("Хранение данных"),
     N_("{system} хранение данных срок хранения файлов"),
     N_("Сколько и где {system} хранит данные и файлы и что с ними происходит по окончании срока хранения?")),
    ("plans", N_("Что в планах и к какому сроку"),
     N_("{system} планы развития доработки сроки релиз"),
     N_("Какие доработки {system} запланированы и к каким срокам? Каждая — отдельной строкой: доработка — срок или "
        "релиз — статус.")),
    ("limitations", N_("Ограничения — чего система не умеет"),
     N_("{system} не поддерживает ограничения запреты"),
     N_("Чего {system} не умеет или не поддерживает? Какие ограничения и запреты установлены для смежных систем?")),
    ("connect", N_("Как подключаются смежные системы"),
     N_("{system} подключение смежной системы интеграция протокол формат заявка"),
     N_("Как смежная система подключается к {system}: через какие платформы, по каким протоколам и в каких форматах; "
        "какие заявки, согласования и испытания нужны?")),
    ("requirements", N_("Требования к смежным системам"),
     N_("{system} требования к смежным системам документации"),
     N_("Какие требования {system} предъявляет к смежным системам и к их документации?")),
]

# Порядок в карточке: (заголовок ##, [ключи разделов]); раздел с одним ключом — без подзаголовка ###
CARD_LAYOUT = [
    (N_("Назначение"), ["purpose"]),
    (N_("Что умеет сейчас"), ["services", "limits", "security", "storage"]),
    (N_("Что в планах и к какому сроку"), ["plans"]),
    (N_("Ограничения — чего система не умеет"), ["limitations"]),
    (N_("Как подключаются смежные системы"), ["connect"]),
    (N_("Требования к смежным системам"), ["requirements"]),
]

NO_INFO = ("НЕТ В БАЗЕ", "NOT IN THE BASE")      # ответ модели «по разделу в фрагментах ничего нет» (оба языка)
_ITEM_RE = re.compile(r"^\s*(?:[-–—•*·]|\d{1,2}[.)])\s+(.*\S)\s*$")
_CITE_RE = re.compile(r"\[(?:Источник|Source)\s*:[^\]]*\]", re.IGNORECASE)
_DETAILS_RE = re.compile(r"\s\((?:итог|total|rerank)\b.*$", re.IGNORECASE)     # баллы поиска в подписи источника


def source_name(label):
    """Подпись найденного фрагмента без баллов поиска и значка: «Файл.docx › 1.2 Раздел»."""
    return _DETAILS_RE.sub("", label or "").lstrip("📄📌🗂️\ufe0f ").strip()


def _section_items(answer):
    """Пункты ответа модели (строки списка); ответ без списка, но не «нет в базе» — один пункт."""
    items = [m.group(1) for m in (_ITEM_RE.match(ln) for ln in (answer or "").splitlines()) if m]
    if not items and (answer or "").strip() and not is_no_info(answer):
        items = [" ".join(answer.split())]
    return [it for it in items if not is_no_info(it)]


def is_no_info(text):
    low = (text or "").strip().upper()
    return any(low.startswith(m) or low == m for m in NO_INFO) or any(f"«{m}»" in low for m in NO_INFO)


def _names(items, system, aliases):
    """Строка «Названия:» — название, заданные вручную и найденные в базе варианты (без ссылок на источник)."""
    out = [system] + [a.strip() for a in aliases if a.strip()]
    for it in items:
        name = _CITE_RE.sub("", it).strip(" .;—–-")
        name = re.split(r"\s[—–-]\s|:\s", name, maxsplit=1)[0].strip(" «»\"")
        if 1 < len(name) <= 80:
            out.append(name)
    seen, names = set(), []
    for n in out:
        if n.lower() not in seen:
            seen.add(n.lower())
            names.append(n)
    return names[:NAMES_MAX]


def ask_section(section, system, cfg, glossary=None):
    """Один раздел карточки: поиск по базе → ответ модели по найденному → пункты, проверка ссылок."""
    key, title, query, question = section
    t0 = time.time()
    query_text = tr(query, system=system)
    context, sources = search_parent_child(query_text, cfg, k_neighbors=CARD_TOP_K, glossary=glossary)
    entry = {"key": key, "title": tr(title), "query": query_text, "sources": list(sources or []), "items": [],
             "unconfirmed": [], "failed": False, "error": "", "answer": ""}
    if not sources:
        entry["seconds"] = time.time() - t0
        return entry
    answer = _ask(system, tr(title), tr(question, system=system), context, cfg)
    entry["answer"] = answer
    if is_llm_error(answer):
        entry["failed"], entry["error"] = True, answer.strip()
    else:
        bad = {c["text"] for c in check_citations(answer, context) if not c["ok"]}
        for item in _section_items(answer):
            cites = _CITE_RE.findall(item)
            if not cites or any(c in bad for c in cites):
                entry["unconfirmed"].append(item)
            entry["items"].append(item)
    entry["seconds"] = time.time() - t0
    return entry


def _ask(system, title, question, context, cfg):
    return ask_llm(render("card_section_system", system=system, section=title),
                   render("card_section_user", question=question, context=context), cfg, guard=True)


def card_markdown(system, aliases, entries, model="", when=None):
    """Черновик карточки по шаблону: название и «Названия:» (по ним MINT узнаёт систему в документах), пометка
    «черновик», разделы с фактами и источниками, пробелы — для эксперта, список источников."""
    by_key = {e["key"]: e for e in entries}
    when = when or time.strftime("%d.%m.%Y")
    names = _names(by_key.get("names", {}).get("items", []), system, aliases)
    lines = [tr("# Карточка системы «{system}»", system=system), "",
             tr("Названия: {names}", names=", ".join(names)), "",
             tr("Актуально на: {d} (черновик)", d=time.strftime("%m.%Y")), "",
             "> " + tr("⚠️ ЧЕРНОВИК: собран MINT по базе знаний {d}{model}. Проверьте каждый факт по источнику, "
                       "допишите пробелы («нет в базе»), особенно ограничения и планы со сроками, и удалите эту "
                       "пометку, прежде чем загружать карточку в базу.", d=when,
                       model=(tr(", модель {m}", m=model) if model else "")), ""]

    def body(e):
        if e is None:
            return []
        if e["failed"]:
            return [tr("_Не получено: {err} — повторите сборку или допишите раздел._", err=e["error"][:200])]
        if not e["items"]:
            return [tr("_Нет в базе — заполнит эксперт._")]
        out = []
        for it in e["items"]:
            mark = " " + tr("⚠️ проверьте: источник не найден среди фрагментов") if it in e["unconfirmed"] else ""
            out.append(f"- {it}{mark}")
        return out

    for head, keys in CARD_LAYOUT:
        lines += [f"## {tr(head)}", ""]
        if len(keys) == 1:
            lines += body(by_key.get(keys[0])) + [""]
            continue
        for k in keys:
            e = by_key.get(k)
            lines += [f"### {e['title'] if e else k}", ""] + body(e) + [""]
    sources = list(dict.fromkeys(source_name(s) for e in entries for s in e.get("sources") or []))
    lines += [tr("## Источники, по которым собран черновик"), ""] + [f"- {s}" for s in sources[:40]]
    return "\n".join(lines).rstrip() + "\n"


def draft_system_card(system, cfg, aliases=(), glossary=None, on_progress=None):
    """Черновик карточки системы по базе знаний: по разделу карточки — запрос к поиску и вопрос модели (вызов LLM
    на раздел, только если в базе что-то нашлось). on_progress(готово, всего, запись раздела) — после каждого
    раздела. → {"markdown", "entries", "found", "gaps", "unconfirmed", "failed", "seconds"}."""
    system = " ".join((system or "").split())
    if not system:
        raise ValueError(tr("не указано название системы"))
    t0 = time.time()
    gl = glossary if glossary is not None else load_glossary(cfg)
    ccfg = replace(cfg, use_multi_query=False)
    done = []

    def finished(i, entry):
        done.append(i)
        if on_progress:
            on_progress(len(done), len(CARD_SECTIONS), entry)

    entries = parallel_map(lambda s: ask_section(s, system, ccfg, gl), CARD_SECTIONS,
                           parallel=min(CARD_PARALLEL, max(1, int(cfg.audit_parallel or 1))), on_done=finished)
    content = [e for e in entries if e["key"] != "names"]
    return {
        "system": system,
        "markdown": card_markdown(system, list(aliases or []), entries, model=cfg.llm_model),
        "entries": entries,
        "found": sum(1 for e in content if e["items"]),
        "gaps": [e["title"] for e in content if not e["items"] and not e["failed"]],
        "unconfirmed": sum(len(e["unconfirmed"]) for e in entries),
        "failed": [e["title"] for e in entries if e["failed"]],
        "seconds": time.time() - t0,
    }

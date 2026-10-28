"""Оформление интерфейса: стили, шапка, штамп заключения, счётчики и список источников.

Всё своё — шрифты из ./static (server.enableStaticServing в .streamlit/config.toml), ничего не грузится из
интернета, поэтому работает в закрытом контуре. Стили — mint/ui/assets/mint.css.
"""

import html
import re
from functools import lru_cache
from pathlib import Path

import streamlit as st

from ..audit import _SEVERITIES
from ..i18n import get_lang, tr

_CSS = Path(__file__).with_name("assets") / "mint.css"


@lru_cache(maxsize=1)
def _css():
    return _CSS.read_text(encoding="utf-8")


def inject_theme():
    """Стили страницы. Якорь нужен, чтобы контейнер со стилями не занимал места (см. mint.css)."""
    st.markdown(f"<style>{_css()}</style><span id=\"mint-theme-anchor\"></span>", unsafe_allow_html=True)


_LEAF = ('<svg class="mint-mark" viewBox="0 0 48 48" aria-hidden="true">'
         '<path class="mint-mark__leaf" d="M7 41 C 7 19, 21 7, 41 7 C 41 27, 29 41, 7 41 Z"/>'
         '<path class="mint-mark__vein" d="M7 41 C 17 31, 25 23, 33 15"/></svg>')


def header_html():
    return (f'<header class="mint-hero">{_LEAF}<div class="mint-hero__text">'
            '<div class="mint-wordmark" role="heading" aria-level="1"><span class="mint-wordmark__ink">MINT</span></div>'
            f'<p class="mint-hero__lede">{html.escape(tr("Интеллектуальная RAG-система: ответы по базе знаний, аудит документов и контроль исправлений — со ссылками на источники"))}</p>'
            '</div></header>')


def render_header():
    st.markdown(header_html(), unsafe_allow_html=True)


def empty_chat_html(docs, shown=6):
    """Пустой чат: что лежит в базе и чего ждать от ответа."""
    if not docs:
        text = tr("База знаний пока пуста. Добавьте документы на боковой панели («Добавить регламенты в базу») — "
                  "и задавайте вопросы: ответ придёт со ссылками на разделы.")
        return f'<div class="mint-empty"><p>{html.escape(text)}</p></div>'
    text = tr("Документов в базе: {n}. Задайте вопрос — ответ придёт со ссылками на разделы, из которых он взят.",
              n=len(docs))
    chips = "".join(f'<li style="--i:{i}">{html.escape(d)}</li>' for i, d in enumerate(docs[:shown]))
    if len(docs) > shown:
        chips += f'<li class="is-more" style="--i:{shown}">{html.escape(tr("и ещё {n}", n=len(docs) - shown))}</li>'
    return f'<div class="mint-empty"><p>{html.escape(text)}</p><ul class="mint-empty__docs">{chips}</ul></div>'


def _fold(s):
    """Название для поиска: без регистра, «ё» = «е», «_», «-», «.» и пробелы — один пробел."""
    return re.sub(r"[\s_.\-]+", " ", (s or "").lower().replace("ё", "е")).strip()


def doc_matches(name, query):
    """Подходит ли документ к строке поиска: все слова запроса есть в названии («записка ч1» ↔
    «Пояснительная_записка_ч1.docx»). Пустой запрос — подходит любой."""
    name = _fold(name)
    return all(w in name for w in _fold(query).split())


def _short_date(stamp):
    """«2026-10-20 14:33:10» → «20.10.2026» (по-английски — «2026-10-20»)."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", stamp or "")
    if not m:
        return ""
    y, mo, d = m.groups()
    return f"{y}-{mo}-{d}" if get_lang() == "en" else f"{d}.{mo}.{y}"


def _breakable(name):
    """Длинное имя файла переносится по «_» и «-», а не посреди слова."""
    return re.sub(r"([_\-])", r"\1<wbr>", html.escape(name))


def kb_docs_html(rows, roles=None):
    """Документы базы (kb.kb_document_status) компактным списком: значок роли, название, векторы и дата; ошибка
    (другая модель эмбеддингов) — коротко под названием, подробности и примечания — подсказкой при наведении.
    Список прокручивается внутри себя (mint.css)."""
    roles = roles or {}
    cards, always = set(roles.get("cards") or ()), set(roles.get("always") or ())
    items = []
    for r in rows:
        errors = [t for lvl, t in r["issues"] if lvl == "error"]
        notes = [t for lvl, t in r["issues"] if lvl != "error"]
        if r["name"] in cards:
            icon, role = "🗂️", tr("карточка системы")
        elif r["name"] in always:
            icon, role = "📌", tr("правила экспертов: учитываются в каждом аудите")
        else:
            icon, role = "📄", ""
        meta = [tr("векторов: {n}", n=f"{int(r.get('vectors') or 0):,}".replace(",", "\u00a0"))]
        date = _short_date(r.get("indexed_at"))
        if date:
            meta.append(date)
        note = (f' <span class="mint-kbdocs__note" title="{html.escape(" ".join(notes))}">ℹ️</span>' if notes else "")
        flag = (f'<span class="mint-kbdocs__flag" title="{html.escape(" ".join(errors))}">⛔ '
                f'{html.escape(tr("другая модель эмбеддингов — переиндексируйте"))}</span>' if errors else "")
        title = f' title="{html.escape(role)}"' if role else ""
        items.append(f'<li class="{"is-error" if errors else ""}"><span class="mint-kbdocs__icon"{title}>{icon}</span>'
                     f'<span class="mint-kbdocs__name">{_breakable(r["name"])}</span>'
                     f'<span class="mint-kbdocs__meta">{html.escape(" · ".join(meta))}{note}</span>{flag}</li>')
    return f'<ul class="mint-kbdocs" aria-label="{html.escape(tr("Документы в базе"))}">{"".join(items)}</ul>'


def tally_html(items):
    """[(css-класс, подпись, число)] → счётчики; число дублируется скрыто для экранных дикторов."""
    cells = []
    for cls, label, n in items:
        cls = f"{cls} is-zero" if not n else cls
        cells.append(f'<div class="{cls}"><dt>{html.escape(label)}</dt>'
                     f'<dd><span class="mint-count" style="--mint-n:{int(n)}" aria-hidden="true"></span>'
                     f'<span class="mint-sr">{int(n)}</span></dd></div>')
    return f'<dl class="mint-tally">{"".join(cells)}</dl>'


def audit_verdict(findings, n_failed=0):
    """Вердикт аудита по замечаниям: (вид, надпись на штампе, {критичность: число})."""
    counts = {sev: 0 for sev in _SEVERITIES}
    for f in findings or []:
        if f.get("severity") in counts:
            counts[f["severity"]] += 1
    critical, medium, low = (counts[s] for s in _SEVERITIES)
    if critical:
        kind, label = "rework", tr("Требует доработки")
    elif medium or low:
        kind, label = "remarks", tr("Есть замечания")
    elif n_failed:
        kind, label = "incomplete", tr("Проверено не полностью")
    else:
        kind, label = "approved", tr("Согласовано")
    return kind, label, counts


def audit_verdict_html(findings, n_failed=0, n_sections=0):
    kind, label, counts = audit_verdict(findings, n_failed)
    critical, medium, low = (counts[s] for s in _SEVERITIES)
    note = ""
    if n_failed:
        note = tr("Не удалось проверить разделов: {n_failed} из {n_sections} — результат нельзя считать согласованием.",
                  n_failed=n_failed, n_sections=n_sections)
    tally = tally_html([("is-critical", tr("критичные"), critical), ("is-medium", tr("средние"), medium),
                    ("is-low", tr("низкие"), low)])
    return (f'<section class="mint-verdict mint-verdict--{kind}" aria-label="{html.escape(label)}">'
            f'<div class="mint-stamp">{html.escape(label)}</div>{tally}'
            + (f'<p class="mint-verdict__note">{html.escape(note)}</p>' if note else "") + "</section>")


def review_tally(rows):
    """Счётчики контроля исправлений по первому символу статуса (✅ ⚠️ ❌ ❓ — одинаковы во всех языках)."""
    keys = {"✅": "fixed", "⚠": "partial", "❌": "not_fixed", "❓": "unverified"}
    counts = dict.fromkeys(keys.values(), 0)
    for row in rows or []:
        key = keys.get((row.get("status") or " ")[0])
        if key:
            counts[key] += 1
    return counts


def review_tally_html(rows):
    c = review_tally(rows)
    if c["not_fixed"]:
        kind, label = "rework", tr("Есть неисправленные")
    elif c["partial"] or c["unverified"]:
        kind, label = "remarks", tr("Исправлено не всё")
    else:
        kind, label = "approved", tr("Всё исправлено")
    tally = tally_html([("is-ok", tr("исправлено"), c["fixed"]), ("is-medium", tr("частично"), c["partial"]),
                    ("is-critical", tr("не исправлено"), c["not_fixed"]),
                    ("is-low", tr("не удалось проверить"), c["unverified"])])
    return (f'<section class="mint-verdict mint-verdict--{kind}" aria-label="{html.escape(label)}">'
            f'<div class="mint-stamp">{html.escape(label)}</div>{tally}</section>')


def split_source(label):
    """«📄 файл › раздел (итог … · dense …)» → (файл, раздел, подробности); формат — search.search_parent_child."""
    text = label[2:].strip() if label.startswith("📄") else label.strip()
    meta = ""
    m = re.search(r" \((?:" + re.escape(tr("итог")) + r" |rerank)", text)
    if m and text.endswith(")"):
        text, meta = text[:m.start()], text[m.start() + 2:-1]
    doc, _, path = text.partition(" › ")
    return doc.strip(), path.strip(), meta.strip()


def sources_html(sources):
    items = []
    for i, label in enumerate(sources):
        doc, path, meta = split_source(str(label))
        doc_html = html.escape(doc) + (f" <span>› {html.escape(path)}</span>" if path else "")
        meta_html = f'<span class="mint-src__meta">{html.escape(meta)}</span>' if meta else "<span></span>"
        items.append(f'<li style="--i:{i}"><span class="mint-src__n">{i + 1}</span>'
                     f'<span class="mint-src__doc">{doc_html}</span>{meta_html}</li>')
    return f'<ol class="mint-sources">{"".join(items)}</ol>'

"""Интерфейс: проверка качества поиска — вопросы по базе, прогон, результаты. Ядро — mint/evaluation.py.

Открывается кнопкой на боковой панели и занимает основную область вместо вкладок. Три шага:
  1. «Вопросы» — MINT составляет вопросы по фрагментам базы (или берёт вопросы прошлой проверки), пользователь
     правит их в таблице и дописывает свои — без CSV;
  2. «Прогон» — каждый вопрос проходит через поиск в нескольких настройках (и, по желанию, через чат — ответ
     проверяется без модели: ссылка на нужный документ, «информации нет», ошибка поиска или модели);
  3. «Результаты» — метрики, сравнение настроек с проверкой на случайность, рекомендации, которые можно
     применить к текущей сессии, вопросы-промахи, ответы чата и их сравнение с прошлой проверкой по версии
     промптов, отчёты для скачивания. Каждая проверка сохраняется в LOG_DIR/eval/<дата_время> и сравнивается с
     предыдущей.
"""

import html
import json
import re

import streamlit as st

from .. import evaluation as ev
from ..i18n import tr
from ..kb import load_kb_snapshot, source_path
from ..prompts import custom_label
from .common import _width_kwargs, btn_w, dl_w
from .theme import tally_html

QA = "qa"                       # состояние проверки в session_state
OPEN = "qa_open"                # открыта ли проверка вместо вкладок
GEN_MORE = 10
STEPS = ("setup", "review", "results")


def _qa():
    return st.session_state.setdefault(QA, {"stage": "setup", "rows": [], "ver": 0, "fragments": {}, "seed": 7})


def open_quality():
    st.session_state[OPEN] = True
    st.session_state["cards_open"] = False
    st.session_state["prompts_open"] = False       # страница «📝 Промпты» (ui/prompts_page.py) закрывается


def prepare_answer_check(cfg, repeat=2):
    """Проверка правки промпта: ответы чата (repeat раз) на вопросах прошлой проверки, без сравнения настроек
    поиска. Есть прошлая проверка — сразу шаг «Вопросы», иначе «Настройка» с отмеченными ответами чата.
    Возвращает, нашлись ли вопросы."""
    qa = _qa()
    qa["opts"] = {"compare": False, "answers": True, "multi": False, "repeat": repeat}
    st.session_state.update(qa_answers=True, qa_compare=False, qa_repeat=repeat)
    runs = ev.list_runs(cfg, limit=1)
    snap = load_kb_snapshot(cfg)
    if runs and snap is not None:
        try:
            questions = ev.load_questions(runs[0][0] / "questions.csv")
        except (OSError, ValueError):
            questions = []
        if questions:
            qa.update(rows=ev.question_rows(questions, snap), fragments={}, failed=0, stage="review")
            qa["ver"] += 1
            return True
    qa["stage"] = "setup"
    return False


def close_quality():
    st.session_state[OPEN] = False


def render_quality_entry():
    """Боковая панель: вход в проверку качества."""
    st.write("---")
    st.subheader(tr("🧪 Проверка качества"))
    st.caption(tr("Вопросы по документам базы, прогон поиска в нескольких настройках, рекомендации — без CSV и "
                  "командной строки."))
    st.button(tr("Открыть проверку качества"), key="qa_open_btn", on_click=open_quality, **btn_w)


# ---------------------------------------------------------------- HTML (чистые функции — проверяются тестами)

def steps_html(stage):
    """Три шага проверки; линия между ними дорастает до текущего шага."""
    labels = [tr("Настройка"), tr("Вопросы"), tr("Результаты")]
    cur = STEPS.index(stage) if stage in STEPS else 0
    items = []
    for i, label in enumerate(labels):
        cls = "is-done" if i < cur else ("is-current" if i == cur else "")
        aria = ' aria-current="step"' if i == cur else ""
        items.append(f'<li class="{cls}"{aria}><span>{html.escape(label)}</span></li>')
    return (f'<ol class="mint-steps" style="--from:{max(cur - 1, 0)};--to:{cur}" aria-label="{html.escape(tr("Шаги проверки"))}">'
            f'{"".join(items)}</ol>')


def highlight(text, quote, limit=1600):
    """Фрагмент с выделенной цитатой (<mark>); длинный фрагмент обрезается вокруг цитаты."""
    text = text or ""
    span = None
    if quote:
        words = re.findall(r"\w+", quote)
        if words:
            m = re.search(r"\W+".join(map(re.escape, words)), text, flags=re.IGNORECASE)
            span = m.span() if m else None
    if len(text) > limit:
        start = max(0, (span[0] if span else 0) - limit // 3)
        end = min(len(text), start + limit)
        prefix, suffix = ("… " if start else ""), (" …" if end < len(text) else "")
        if span:
            span = (span[0] - start + len(prefix), span[1] - start + len(prefix))
        text = prefix + text[start:end] + suffix
    if span:
        a, b = span
        body = f"{html.escape(text[:a])}\x00{html.escape(text[a:b])}\x01{html.escape(text[b:])}"
    else:
        body = html.escape(text)
    lines = []
    for ln in body.split("\n"):
        head = re.match(r"^(#{1,6})\s+(.*)$", ln)
        lines.append(f'<b class="mint-fragment__h">{head.group(2)}</b>' if head else ln)
    body = re.sub(r"(<br>){3,}", "<br><br>", "<br>".join(lines))
    body = re.sub(r"(<br>)+(<b class)", r"\2", re.sub(r"(</b>)(<br>)+", r"\1", body))   # заголовок — блок, без пустот
    # Markdown кончает HTML-блок на пустой строке, поэтому переводы строк — только <br>
    return body.replace("\x00", "<mark>").replace("\x01", "</mark>")


def fragment_html(source, section, text, quote):
    where = html.escape(source) + (f" <span>› {html.escape(section)}</span>" if section else "")
    return (f'<figure class="mint-fragment"><figcaption>{where}</figcaption>'
            f'<blockquote>{highlight(text, quote)}</blockquote></figure>')


def _pct(k, n):
    return round(100.0 * k / n) if n else 0


def _delta_html(value, unit=""):
    if value is None:
        return ""
    if abs(value) < 1e-9:
        return f'<span class="mint-delta is-flat">{html.escape(tr("без изменений"))}</span>'
    cls, sign = ("is-up", "▲") if value > 0 else ("is-down", "▼")
    text = f"{abs(value):.3f}" if unit == "mrr" else f"{abs(value):.0f} {tr('п.п.')}"
    return f'<span class="mint-delta {cls}">{sign} {html.escape(text)}</span>'


def _prev_metrics(run, prev):
    """Метрики текущих настроек в прошлой проверке — только если набор вопросов того же размера."""
    if not prev:
        return None
    m = (prev.get("configs") or {}).get(run.current) or {}
    if m.get("n_answerable") != run.n_answerable or m.get("n_no_answer") != run.n_no_answer:
        return None
    return m


def scorecard_html(run, prev=None):
    """Главные числа текущих настроек; рядом — изменение с прошлой проверки (если набор того же размера)."""
    m, k = run.summary[run.current], run.top_k
    p = _prev_metrics(run, prev)
    cells = []
    if run.n_answerable:
        n = run.n_answerable
        hits = [(f"hit@{k}", tr("в контексте модели"), m[f"hit@{k}"], "is-lead"), ("hit@1", tr("первым"), m["hit@1"], "")]
        for key, label, v, cls in hits:
            d = _pct(v, n) - _pct(p[key], n) if p and key in p else None
            cells.append(f'<div class="mint-score {cls}"><dt>{html.escape(label)} <small>{key}</small></dt>'
                         f'<dd><span class="mint-count" style="--mint-n:{_pct(v, n)}" aria-hidden="true"></span>'
                         f'<span class="mint-score__unit" aria-hidden="true">%</span><span class="mint-sr">{_pct(v, n)} %</span>'
                         f'{_delta_html(d)}</dd></div>')
        d = m["mrr"] - p["mrr"] if p and "mrr" in p else None
        cells.append(f'<div class="mint-score"><dt>MRR <small>{html.escape(tr("1 — всегда первым"))}</small></dt>'
                     f'<dd><span class="mint-score__static">{m["mrr"]:.2f}</span>{_delta_html(d, "mrr")}</dd></div>')
        fa = m["false_low_conf"]
        cells.append(f'<div class="mint-score{" is-warn" if fa else ""}"><dt>{html.escape(tr("ложные тревоги"))}</dt>'
                     f'<dd><span class="mint-count" style="--mint-n:{fa}" aria-hidden="true"></span>'
                     f'<span class="mint-score__of">/ {n}</span><span class="mint-sr">{fa} / {n}</span></dd></div>')
    if run.n_no_answer:
        det, n0 = m["detected_no_answer"], run.n_no_answer
        cells.append(f'<div class="mint-score"><dt>{html.escape(tr("нет ответа распознан"))}</dt>'
                     f'<dd><span class="mint-count" style="--mint-n:{det}" aria-hidden="true"></span>'
                     f'<span class="mint-score__of">/ {n0}</span><span class="mint-sr">{det} / {n0}</span></dd></div>')
    caption = tr("Текущие настройки: {name}. Вопросов с ответом в базе — {a}, без ответа — {b}.",
                 name=ev.config_label(run.current), a=run.n_answerable, b=run.n_no_answer)
    return (f'<section class="mint-scorecard" aria-label="{html.escape(tr("Итоги проверки"))}">'
            f'<dl>{"".join(cells)}</dl><p>{html.escape(caption)}</p></section>')


def ladder_html(run):
    """Настройки поиска по убыванию MRR: полоса — hit@K, тёмная часть — hit@1; текущие и лучшие отмечены."""
    if not run.n_answerable:
        return ""
    n, k, best = run.n_answerable, run.top_k, run.best
    order = sorted(run.configs, key=lambda c: (-run.summary[c[0]]["mrr"], c[0] != run.current))
    rows = []
    for i, (name, _c) in enumerate(order):
        m = run.summary[name]
        tags = ""
        if name == run.current:
            tags += f'<em>{html.escape(tr("сейчас"))}</em>'
        if name == best:
            tags += f'<b title="{html.escape(tr("лучшая по MRR"))}">★</b>'
        cls = " ".join(c for c in ("is-current" if name == run.current else "", "is-best" if name == best else "") if c)
        rows.append(
            f'<li class="{cls}" style="--i:{i};--v:{m[f"hit@{k}"] / n:.3f};--v1:{m["hit@1"] / n:.3f}">'
            f'<span class="mint-ladder__name">{html.escape(ev.config_label(name))}{tags}</span>'
            f'<span class="mint-ladder__bar" aria-hidden="true"><i></i><s></s></span>'
            f'<span class="mint-ladder__val">{_pct(m[f"hit@{k}"], n)} %<small>{_pct(m["hit@1"], n)} %</small></span>'
            f'<span class="mint-ladder__mrr">{m["mrr"]:.2f}</span></li>')
    head = (f'<li class="mint-ladder__head" aria-hidden="true"><span>{html.escape(tr("Настройки"))}</span><span></span>'
            f'<span>hit@{k} / hit@1</span><span>MRR</span></li>')
    legend = tr("Вся полоса — правильный фрагмент попал в контекст модели (hit@{k}), тёмная часть — он был первым "
                "(hit@1).", k=k)
    return f'<ol class="mint-ladder">{head}{"".join(rows)}</ol><p class="mint-ladder__legend">{html.escape(legend)}</p>'


ANSWER_CLS = {"ok_answerable": "is-ok", "cites_expected": "is-ok", "false_refusal": "is-medium",
              "honest_refusal": "is-ok", "dirty": "is-critical"}


def answers_html(run):
    """Счётчики ответов чата: верные, со ссылкой на нужный документ, ложное и честное «информации нет», ссылки
    мимо найденного (по всем ответам: вопрос × повтор)."""
    a = run.answers["summary"]
    items = [(ANSWER_CLS[key], f"{tr(label)} / {n}", k) for key, label, k, n, _h in ev.answer_metrics(a)]
    return f'<div class="mint-answers">{tally_html(items)}</div>'


def answers_delta_text(cur, prev):
    """«верный ответ ▲ 10 п.п.; …» — изменение долей с прошлой проверки с ответами чата."""
    c = ev.compare_answers(cur, prev)
    parts = []
    for key, label, _k, _n, higher in ev.answer_metrics(cur):
        d = c["deltas"].get(key)
        if d is None:
            continue
        if abs(d) < 0.5:
            parts.append(f"{tr(label)}: {tr('без изменений')}")
        else:
            good = (d > 0) == higher
            parts.append(f"{tr(label)}: {'▲' if d > 0 else '▼'} {abs(d):.0f} {tr('п.п.')}{' ✓' if good else ' ✗'}")
    return "; ".join(parts), c


# ---------------------------------------------------------------- данные таблиц

def records(data):
    """Результат st.data_editor → список словарей (в разных версиях Streamlit это список или DataFrame)."""
    if hasattr(data, "to_dict"):
        return data.to_dict("records")
    return [dict(r) for r in (data or [])]


def blank_row():
    return {"use": True, "question": "", "file": "", "section": "", "contains": "", "note": "", "id": None}


def generated_rows(items):
    return [{"use": True, "question": r["question"], "file": r["file"], "section": r["section"],
             "contains": r["contains"], "note": r["note"], "id": r.get("pid")} for r in items]


def answer_cell(runs):
    """Итог ответов на вопрос: «✓», «✗ причина» или «2 из 3 ✓ · причина» при повторах."""
    ok = sum(1 for r in runs if r["ok"])
    why = next((tr(ev.ANSWER_REASONS[r["reason"]]) for r in runs if r["reason"]), "")
    if len(runs) == 1:
        return "✓" if ok else f"✗ {why}"
    return tr("{ok} из {n} ✓", ok=ok, n=len(runs)) + (f" · {why}" if why else "")


def result_rows(run, show):
    """Строки таблицы «по вопросам». show: all | miss | none | bad."""
    cur, k = run.results[run.current], run.top_k
    out = []
    for q in run.questions:
        r = cur[q.n]
        miss = q.answerable and (r["rank"] or ev.K_MAX + 1) > k
        a = (run.answers or {}).get("rows", {}).get(q.n)
        if show == "miss" and not miss:
            continue
        if show == "none" and q.answerable:
            continue
        if show == "bad" and not (a and not all(x["ok"] for x in a)):
            continue
        row = {"№": q.n, tr("Вопрос"): q.question, tr("Ожидалось"): q.expected,
               tr("Место"): str(ev.place_cell(r, q)), tr("Найдено первым"): (r["top"] or [tr("ничего не найдено")])[0]}
        if a:
            row[tr("Ответ: итог")] = answer_cell(a)
            row[tr("Ответ чата")] = next((x["answer"] for x in a if not x["ok"]), a[0]["answer"])
        out.append(row)
    return out


# ---------------------------------------------------------------- шаги

def _apply(rec):
    """Рекомендации → ручные настройки текущей сессии (как если бы их выставили в «Экспертных настройках»)."""
    manual = st.session_state.setdefault("mint_manual", {})
    for name, value in rec.items():
        manual[name] = value
        for key in [k for k in st.session_state if isinstance(k, str) and k.startswith(f"x_{name}_")]:
            del st.session_state[key]
    st.session_state["qa_applied"] = dict(rec)


def _setup(cfg, snap, qa):
    hint = st.session_state.pop("qa_hint", None)
    if hint:
        st.info(hint)
    st.markdown(tr("MINT составит вопросы по документам базы, вы их проверите и дополните, затем каждый вопрос "
                   "пройдёт через поиск в нескольких настройках. В итоге видно, на каком месте оказывается нужный "
                   "фрагмент, какие настройки лучше и на каких вопросах поиск ошибается."))
    n_docs = len(ev.known_files(snap))
    c1, c2 = st.columns([0.45, 0.55])
    with c1:
        n = st.slider(tr("Сколько вопросов составить"), 5, 60, 20, 5, key="qa_n",
                      help=tr("Один вызов модели на вопрос. Фрагменты берутся поровну из каждого документа."))
    with c2:
        st.checkbox(tr("Сравнить настройки поиска"), value=True, key="qa_compare",
                    help=tr("Кроме текущих настроек — только векторный поиск, только BM25, гибрид и разные веса "
                            "реранкера. Без сравнения быстрее: текущие настройки, векторный поиск и гибрид."))
        st.checkbox(tr("Проверить и ответы чата"), value=False, key="qa_answers",
                    help=tr("Каждый вопрос задаётся чату с текущими настройками (+1 вызов модели на вопрос): есть "
                            "ли ссылка на нужный документ, нет ли ссылок мимо найденного, честное ли «информации нет», "
                            "если ответа в базе нет; ошибка — поиска или модели. Нужно после правки промптов: "
                            "результат сравнивается с прошлой проверкой по версии промптов."))
        if st.session_state.get("qa_answers"):
            st.select_slider(tr("Сколько раз задать чату каждый вопрос"), options=[1, 2, 3], value=1, key="qa_repeat",
                             help=tr("Модель отвечает не всегда одинаково. Чтобы сравнить промпты до и после правки, "
                                     "задайте каждый вопрос 2–3 раза: случайные расхождения сгладятся."))
        if not cfg.use_multi_query:
            st.checkbox(tr("Добавить вариант с multi-query"), value=False, key="qa_multi",
                        help=tr("Ещё одна настройка: поиск по нескольким формулировкам вопроса (+1 вызов модели на "
                                "вопрос)."))
    repeat = int(st.session_state.get("qa_repeat") or 1) if st.session_state.get("qa_answers") else 1
    if st.session_state.get("qa_answers"):
        cost = tr("Документов в базе: {d}. Вызовов модели: {n} — по одному на вопрос и на каждый ответ чата.", d=n_docs,
                  n=n + n * repeat)
    else:
        cost = tr("Документов в базе: {d}. Вызовов модели: {n} — по одному на вопрос.", d=n_docs, n=n)
    st.caption(cost + " " + tr("Повторные запросы к эмбеддингам и реранкеру в разных настройках не отправляются."))
    runs = ev.list_runs(cfg, limit=1)
    cols = st.columns(3 if runs else 2)
    gen = cols[0].button(tr("✨ Составить вопросы"), key="qa_gen_btn", type="primary", **btn_w)
    manual = cols[1].button(tr("✍️ Написать вопросы самому"), key="qa_manual_btn", **btn_w)
    prev = runs and cols[2].button(tr("↺ Вопросы прошлой проверки ({when})", when=runs[0][1].get("created", "")[:16]),
                                   key="qa_prev_btn", **btn_w)
    if gen or manual or prev:
        qa["opts"] = {"compare": bool(st.session_state.get("qa_compare", True)),
                      "answers": bool(st.session_state.get("qa_answers")), "multi": bool(st.session_state.get("qa_multi")),
                      "repeat": repeat}
    if gen:
        bar = st.progress(0.0, text=tr("Составляю вопросы…"))

        def progress(i, total):
            bar.progress(i / total if total else 1.0, text=tr("Составляю вопросы: {i} из {n}", i=i, n=total))

        items, failed = ev.generate_questions(cfg, n, seed=qa["seed"], progress=progress, snap=snap)
        qa["fragments"] = {r["pid"]: r for r in items}
        qa["rows"], qa["failed"], qa["asked"] = generated_rows(items), failed, n
        _goto(qa, "review")
    elif manual:
        qa["rows"], qa["fragments"], qa["failed"] = [blank_row()], {}, 0
        _goto(qa, "review")
    elif prev:
        try:
            questions = ev.load_questions(runs[0][0] / "questions.csv")
        except (OSError, ValueError) as e:
            st.error(str(e))
            return
        qa["rows"], qa["fragments"], qa["failed"] = ev.question_rows(questions, snap), {}, 0
        _goto(qa, "review")


def _goto(qa, stage):
    qa["stage"] = stage
    qa["ver"] += 1               # таблица вопросов строится заново из qa["rows"]
    st.rerun()


def _editor(rows, files, ver):
    cc = st.column_config
    no_answer = tr(ev.NO_ANSWER)
    config = {
        "use": cc.CheckboxColumn("✓", help=tr("Снимите галочку, чтобы не включать вопрос в проверку"), default=True,
                                 width="small"),
        "question": cc.TextColumn(tr("Вопрос"), help=tr("Как спросил бы сотрудник"), width="large", required=True),
        "file": cc.SelectboxColumn(tr("Документ с ответом"), options=[no_answer] + files, width="medium",
                                   help=tr("Где ответ. «{na}» — для вопросов, ответа на которые в базе нет: по ним "
                                           "проверяется сигнал «уверенность низкая».", na=no_answer)),
        "section": cc.TextColumn(tr("Раздел"), help=tr("Часть названия раздела — необязательно"), width="small"),
        "contains": cc.TextColumn(tr("Ответ в документе — дословная фраза"), width="medium",
                                  help=tr("Короткая фраза из нужного фрагмента: по ней понятно, что поиск нашёл именно "
                                          "его. Необязательно, но точнее всего.")),
        "note": cc.TextColumn(tr("Примечание"), width="small"),
    }
    edited = st.data_editor(rows, key=f"qa_editor_{ver}", num_rows="dynamic", hide_index=True,
                            column_order=list(config), column_config=config, **_width_kwargs(st.data_editor))
    return records(edited)


def _review(cfg, snap, qa):
    st.markdown(tr("**Проверьте вопросы.** Перепишите вопрос так, как спросил бы сотрудник: модель берёт слова из "
                   "фрагмента, и такие вопросы завышают результат поиска по словам. Снимите галочку с неудачных, "
                   "добавьте свои строки внизу таблицы."))
    made = len(qa["fragments"])
    if qa.get("failed"):
        st.caption(tr("Не удалось составить вопросов: {n} — модель ответила не в том формате.", n=qa["failed"]))
    elif qa.get("asked") and made < qa["asked"]:
        st.caption(tr("Составлено вопросов: {made} из {asked} — в базе больше нет фрагментов, по которым можно задать "
                      "вопрос (нужно от 300 символов текста).", made=made, asked=qa["asked"]))
    opts = qa.get("opts") or {}
    st.caption(tr("Прогон: {compare}{answers}{multi}. Изменить — «← Назад».",
                  compare=tr("сравнение настроек поиска") if opts.get("compare", True) else tr("только текущие настройки, "
                                                                                              "векторный поиск и гибрид"),
                  answers=(tr("; ответы чата") + (tr(" ×{n}", n=opts.get("repeat", 1)) if opts.get("repeat", 1) > 1 else "")
                           if opts.get("answers") else ""),
                  multi=tr("; вариант с multi-query") if opts.get("multi") else ""))
    rows = _editor(qa["rows"], ev.known_files(snap), qa["ver"])
    questions, issues = ev.rows_to_questions(rows)
    problems = ev.markup_problems(questions, snap)
    n_ans = sum(1 for q in questions if q.answerable)
    st.markdown(tally_html([("is-ok", tr("в проверке"), len(questions)), ("", tr("с ответом"), n_ans),
                        ("is-low", tr("без ответа в базе"), len(questions) - n_ans),
                        ("is-medium", tr("поправить"), len(issues) + len(problems))]), unsafe_allow_html=True)
    if issues or problems:
        by_n = {q.n: q.question for q in questions}
        with st.expander(tr("Что поправить ({n})", n=len(issues) + len(problems)), expanded=True):
            for i in sorted(issues):
                st.markdown("- " + tr("«{q}» — не выбран документ: выберите файл или «{na}»; пока строка не входит в "
                                      "проверку", q=ev.cell(rows[i - 1].get("question"))[:90], na=tr(ev.NO_ANSWER)))
            for i, why in sorted(problems.items()):
                st.markdown("- " + tr("«{q}» — {why}", q=by_n[i][:90], why=why))
    if questions and n_ans == len(questions):
        st.info(tr("Нет вопросов, ответа на которые в базе нет: порог «уверенность низкая» подобрать не получится. "
                   "Добавьте 5–10 вопросов о том, чего в документах точно нет."))
    shown = [(i, r) for i, r in enumerate(rows) if r.get("id") in qa["fragments"]]
    if shown:
        with st.expander(tr("Фрагмент, по которому составлен вопрос")):
            pick = st.selectbox(tr("Вопрос"), options=[i for i, _ in shown], key="qa_preview",
                                format_func=lambda i: f"{i + 1}. {ev.cell(rows[i].get('question'))[:80]}")
            r = rows[pick] if pick is not None else shown[0][1]
            frag = qa["fragments"][r["id"]]
            st.markdown(fragment_html(frag["file"], frag["section"], frag["fragment"], ev.cell(r.get("contains"))),
                        unsafe_allow_html=True)
            original = source_path(cfg, frag["file"])
            if original.is_file():
                st.download_button(tr("⬇ Документ целиком ({name})", name=frag["file"]), original.read_bytes(),
                                   file_name=frag["file"], key="qa_src_dl")
    c = st.columns([0.34, 0.22, 0.22, 0.22])
    run = c[0].button(tr("▶ Запустить проверку ({n})", n=len(questions)), key="qa_run_btn", type="primary",
                      disabled=not questions, **btn_w)
    more = c[1].button(tr("✨ Ещё {n} вопросов", n=GEN_MORE), key="qa_more_btn", **btn_w)
    back = c[2].button(tr("← Назад"), key="qa_back_btn", **btn_w)
    if questions:
        c[3].download_button(tr("⬇ Вопросы (.csv)"), ev.questions_csv(questions), file_name="questions.csv",
                             mime="text/csv", key="qa_q_dl", **dl_w)
    if more:
        qa["seed"] += 1
        bar = st.progress(0.0, text=tr("Составляю вопросы…"))
        items, failed = ev.generate_questions(cfg, GEN_MORE, seed=qa["seed"], snap=snap, exclude=set(qa["fragments"]),
                                              progress=lambda i, t: bar.progress(i / t if t else 1.0, text=tr(
                                                  "Составляю вопросы: {i} из {n}", i=i, n=t)))
        qa["fragments"].update({r["pid"]: r for r in items})
        qa["rows"], qa["failed"] = rows + generated_rows(items), failed
        _goto(qa, "review")
    elif back:
        qa["rows"] = rows
        _goto(qa, "setup")
    elif run:
        qa["rows"] = rows
        _run(cfg, qa, questions)


def _run(cfg, qa, questions):
    bar = st.progress(0.0, text=tr("Готовлю прогон…"))

    def progress(done, total, stage):
        label = tr(stage) if stage == ev.STAGE_ANSWERS else ev.config_label(stage)
        bar.progress(done / total if total else 1.0, text=tr("{stage}: {done} из {total}", stage=label, done=done,
                                                              total=total))

    try:
        opts = qa.get("opts") or {}
        run = ev.evaluate(cfg, questions, with_multi_query=opts.get("multi", False), compare=opts.get("compare", True),
                          answers=opts.get("answers", False), repeat=opts.get("repeat", 1), progress=progress)
    except ValueError as e:
        st.error(str(e))
        return
    runs = ev.list_runs(cfg)
    prev_summary = runs[0][1] if runs else None
    prev_answers = ev.latest_answers(runs) if run.answers else None   # последняя проверка, где были ответы чата
    qa.update(run=run, prev=prev_summary, prev_answers=prev_answers, saved=None, save_error=None, scroll=True)
    try:
        folder, lines = ev.save_run(cfg, run, (prev_summary or {}).get("configs"), prev_answers)
        qa["saved"], qa["report"] = str(folder), "\n".join(lines) + "\n"
    except OSError as e:
        qa["save_error"], qa["report"] = str(e), "\n".join(ev.report_lines(run, None, prev_answers)) + "\n"
    _goto(qa, "results")


def _scroll_to_top():
    """После прогона страница осталась бы прокручена туда, где была кнопка, — итоги и их анимация ушли бы за
    верхний край. Скрипт в невидимом iframe прокручивает основную область к шагам проверки."""
    try:
        from streamlit.components.v1 import html as component_html
    except Exception:
        return
    component_html("<script>const d = window.parent.document; const el = d.querySelector('.mint-steps');"
                   "if (el) el.scrollIntoView({block: 'start'});</script>", height=0)


def _results(cfg, qa):
    run = qa["run"]
    if qa.pop("scroll", False):
        _scroll_to_top()
    applied = st.session_state.pop("qa_applied", None)
    if applied:
        st.toast(tr("Применено к текущей сессии: {v}", v=", ".join(f"{k} = {v:g}" for k, v in applied.items())))
    st.markdown(scorecard_html(run, qa.get("prev")), unsafe_allow_html=True)
    prev = qa.get("prev")
    if prev and _prev_metrics(run, prev) is None:
        st.caption(tr("Прошлая проверка ({when}) была на другом наборе вопросов — изменения не показаны.",
                      when=prev.get("created", "")[:16]))
    elif prev:
        st.caption(tr("▲▼ — изменение с прошлой проверки ({when}).", when=prev.get("created", "")[:16]))

    if run.n_answerable:
        st.markdown(ladder_html(run), unsafe_allow_html=True)
        for a, b in ev.pairs_to_compare(run):
            wins, losses, diff = ev.paired(run.results[a], run.results[b], run.questions)
            st.markdown("- " + ev.pair_verdict(a, b, wins, losses, diff, run.n_answerable))
    _recommendations(run)
    if run.calib:
        _calibration(run)
    if run.answers:
        _answers(run, qa.get("prev_answers"))
    _per_question(run)
    _downloads(run, qa)
    c = st.columns(3)
    if c[0].button(tr("✏️ Изменить вопросы и проверить снова"), key="qa_edit_btn", **btn_w):
        _goto(qa, "review")
    if c[1].button(tr("🔄 Новая проверка"), key="qa_new_btn", **btn_w):
        st.session_state[QA] = {"stage": "setup", "rows": [], "ver": qa["ver"] + 1, "fragments": {}, "seed": qa["seed"] + 1}
        st.rerun()
    c[2].button(tr("✕ Закрыть"), key="qa_close2_btn", on_click=close_quality, **btn_w)


def _answers(run, prev):
    """Ответы чата: счётчики, причины ошибок (поиск или модель), сравнение с прошлой проверкой по версии промптов."""
    a = run.answers["summary"]
    st.markdown(f"#### {tr('Ответы чата')}")
    st.caption(tr("Промпты: {v} · язык: {language} · модель: {m}", v=a.get("prompts", "—"), language=a.get("lang", "—"),
                  m=a.get("llm_model", "—"))
               + (" · " + tr("повторов каждого вопроса: {n}", n=a["repeat"]) if a.get("repeat", 1) > 1 else "")
               + (" · " + tr("свои правки: {v}", v=custom_label(a["prompts_custom"])) if a.get("prompts_custom") else ""))
    st.markdown(answers_html(run), unsafe_allow_html=True)
    if a.get("failed"):
        st.caption(tr("Модель не ответила {n} раз — эти ответы не учтены.", n=a["failed"]))
    reasons = a.get("reasons") or {}
    if reasons:
        search_n = reasons.get("search", 0)
        model_n = sum(v for k, v in reasons.items() if k not in ("search", "error"))
        st.markdown(tr("**Где ошибки:** поиск — {s}, модель — {m}.", s=search_n, m=model_n) + " "
                    + "; ".join(f"{tr(ev.ANSWER_REASONS[k])} — {v}" for k, v in sorted(reasons.items(),
                                                                                      key=lambda kv: -kv[1])))
        st.caption(tr("«Поиск» — нужного фрагмента не было в контексте: правьте настройки поиска. «Модель» — фрагмент "
                      "был, а ответ не тот: правьте промпт чата или модель."))
    if prev:
        text, c = answers_delta_text(a, prev)
        what = ev.meta_text(c["meta"]) or tr("ничего из настроек")
        st.markdown(tr("**С прошлой проверкой ответов** (изменилось: {what}). {verdict}", what=what,
                       verdict=ev.answers_verdict(c)))
        if text:
            st.caption(text)
        if c["several"]:
            st.caption(tr("⚠️ Изменилось больше одного параметра — разницу нельзя приписать чему-то одному."))
    else:
        st.caption(tr("Это первая проверка ответов: следующая (например, после правки промпта) сравнится с ней."))


def _recommendations(run):
    rec = ev.recommendations(run)
    st.markdown(f"#### {tr('Что поменять')}")
    if not rec:
        st.markdown(tr("Текущие настройки — лучшие из проверенных; менять ничего не нужно."))
        return
    labels = {"weight_rerank": tr("Вес реранкера"), "low_conf_rerank": tr("Порог «уверенность низкая»: балл реранкера"),
              "low_conf_lexical": tr("Порог «уверенность низкая»: доля слов вопроса")}
    for name, value in rec.items():
        st.markdown(f"- {labels.get(name, name)}: `{getattr(run.cfg, name):g}` → `{value:g}`")
    if "weight_rerank" in rec:
        wins, losses, _ = ev.paired(run.results[run.best], run.results[run.current], run.questions)
        p = ev.sign_test_p(wins, losses)
        if p >= 0.05:
            st.caption(tr("Разница в поиске может быть случайной (p = {p:.2f}): прежде чем менять config.yaml, "
                          "проверьте на большем наборе вопросов.", p=p))
    c1, c2 = st.columns([0.3, 0.7])
    manual = st.session_state.get("mint_manual") or {}
    if all(manual.get(name) == value for name, value in rec.items()):
        c1.button(tr("✓ Применено в этой сессии"), key="qa_apply_btn", disabled=True, **btn_w)
    else:
        c1.button(tr("Применить в этой сессии"), key="qa_apply_btn", type="primary", on_click=_apply, args=(rec,),
                  **btn_w)
    section = {"weight_rerank": "search", "low_conf_rerank": "confidence", "low_conf_lexical": "confidence"}
    groups = {}
    for name, value in rec.items():
        groups.setdefault(section.get(name, "search"), []).append(f"  {name}: {value:g}")
    with c2:
        st.caption(tr("Чтобы закрепить — в config.yaml:"))
        st.code("\n".join(f"{g}:\n" + "\n".join(v) for g, v in groups.items()), language="yaml")


def _calibration(run):
    calib = run.calib
    key, idx = ("low_conf_rerank", 0) if calib["has_rerank"] else ("low_conf_lexical", 1)
    with st.expander(tr("Пороги сигнала «уверенность низкая»")):
        if calib["has_rerank"]:
            st.caption(tr("Лучший балл реранкера: на вопросах с ответом — {a}; без ответа — {b}.",
                          a=calib["rerank_answerable"], b=calib["rerank_no_answer"]))
        st.caption(tr("Доля слов вопроса в контексте: с ответом — {a}; без ответа — {b}.",
                      a=calib["lexical_answerable"], b=calib["lexical_no_answer"]))
        rows = []
        for row in calib["rows"]:
            mark = (tr("сейчас") if abs(row[0] - calib["current"][0]) < 1e-9 and abs(row[1] - calib["current"][1]) < 1e-9
                    else "") + (" ★" if row is calib["best"] else "")
            rows.append({key: f"{row[idx]:.2f}", tr("Нет ответа распознан"): f"{row[2] * 100:.0f} %",
                         tr("Ложная тревога"): f"{row[3] * 100:.0f} %", " ": mark.strip()})
        st.dataframe(rows, hide_index=True, **_width_kwargs(st.dataframe))


def _per_question(run):
    st.markdown(f"#### {tr('По вопросам')}")
    options = {"all": tr("все"), "miss": tr("не попали в контекст"), "none": tr("без ответа в базе")}
    if run.answers:
        options["bad"] = tr("ответы с ошибками")
    show = st.radio(tr("Показать"), options=list(options), format_func=options.get, horizontal=True, key="qa_show")
    rows = result_rows(run, show or "all")
    if rows:
        cc = st.column_config
        widths = {"№": cc.NumberColumn("№", width="small"), tr("Вопрос"): cc.TextColumn(tr("Вопрос"), width="large"),
                  tr("Место"): cc.TextColumn(tr("Место"), width="small"),
                  tr("Найдено первым"): cc.TextColumn(tr("Найдено первым"), width="medium")}
        st.dataframe(rows, hide_index=True, column_config=widths, **_width_kwargs(st.dataframe))
    else:
        st.caption(tr("Таких вопросов нет."))


def _downloads(run, qa):
    files = [(tr("⬇ Отчёт (.md)"), qa.get("report") or "", "report.md", "text/markdown"),
             (tr("⬇ По вопросам (.csv)"), ev.details_csv(run), "details.csv", "text/csv"),
             (tr("⬇ Вопросы (.csv)"), ev.questions_csv(run.questions), "questions.csv", "text/csv"),
             ("⬇ summary.json", json.dumps(ev.summary_dict(run), ensure_ascii=False, indent=2), "summary.json",
              "application/json")]
    if run.answers:
        files.append((tr("⬇ Ответы чата (.csv)"), ev.answers_csv(run), "answers.csv", "text/csv"))
    cols = st.columns(len(files))
    for col, (label, data, name, mime) in zip(cols, files):
        col.download_button(label, data, file_name=name, mime=mime, key=f"qa_dl_{name}", **dl_w)
    if qa.get("saved"):
        st.caption(tr("Отчёт сохранён: {path}", path=qa["saved"]))
    elif qa.get("save_error"):
        st.warning(tr("Отчёт не сохранён на диск ({e}) — скачайте его кнопками выше.", e=qa["save_error"]))


def render_quality(cfg):
    """Основная область: проверка качества вместо вкладок."""
    qa = _qa()
    head, close = st.columns([0.8, 0.2])
    head.subheader(tr("🧪 Проверка качества поиска"))
    close.button(tr("✕ Закрыть"), key="qa_close_btn", on_click=close_quality, **btn_w)
    st.markdown(steps_html(qa["stage"]), unsafe_allow_html=True)
    snap = load_kb_snapshot(cfg)
    if snap is None or not snap.parent_store:
        st.info(tr("База знаний пуста: проверять нечего. Добавьте документы на боковой панели («Добавить регламенты "
                   "в базу»)."))
        return
    if qa["stage"] == "results" and qa.get("run"):
        _results(cfg, qa)
    elif qa["stage"] == "review":
        _review(cfg, snap, qa)
    else:
        _setup(cfg, snap, qa)

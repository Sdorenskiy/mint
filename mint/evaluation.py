"""Оценка качества поиска по набору вопросов с разметкой: ядро для eval_search.py и для проверки в интерфейсе.

Каждый вопрос прогоняется через настоящий поиск MINT в нескольких конфигурациях (только векторный поиск,
только BM25, гибрид, гибрид + реранкер с разными весами). Считается, на каком месте оказался правильный
фрагмент (hit@1, hit@3, hit@K, MRR), на скольких вопросах конфигурации расходятся и случайна ли разница
(критерий знаков), срабатывает ли сигнал «уверенность низкая» на вопросах без ответа и какой порог для него
лучше. Разметка — имя файла, раздел и дословная фраза, поэтому набор вопросов переживает переиндексацию.

По желанию каждый вопрос задаётся и чату — тем же сценарием, что во вкладке «Чат» (chat.answer_question), — и
ответ проверяется без модели-судьи (check_answers): ссылка на нужный документ, ссылки мимо найденного, ложное и
честное «информации нет». Каждая ошибка относится к поиску (нужного фрагмента не было в контексте) или к модели.
В итоги пишется версия промптов: прогон до и после правки промпта сравнивается по вопросам (compare_answers).
"""

import csv
import io
import json
import math
import random
import re
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path

from .audit import is_llm_error
from .chat import answer_question, is_no_info_answer
from .citations import cited_files
from .i18n import N_, get_lang, tr
from .kb import kb_default_top_k, load_glossary, load_kb_snapshot
from .prompts import custom_label, custom_status, prompts_version, question_gen_system, render
from .search import is_low_confidence, search_parent_child
from .services import ask_llm, request_cache
from .bm25 import bm25_tokenize
from .text import extract_json, norm_for_match

K_MAX = 10                       # глубина, на которой ищется правильный фрагмент
RERANK_WEIGHTS = [0.35, 0.7, 1.0, 1.5, 3.0]
COLUMN_ALIASES = {
    "question": ("question", "вопрос"),
    "file": ("file", "файл", "source", "источник"),
    "section": ("section", "раздел"),
    "contains": ("contains", "содержит", "фраза", "цитата", "quote"),
    "note": ("note", "примечание", "комментарий"),
}
# внутренние имена конфигураций (ключи summary.json — по ним сравниваются прогоны); показ — config_label()
CFG_DENSE, CFG_BM25, CFG_HYBRID = N_("только dense"), N_("только BM25"), N_("гибрид")
CFG_RERANK = N_("гибрид + реранкер {w}")
CFG_MULTI = N_("{name} + multi-query")
STAGE_ANSWERS = N_("ответы чата")
NO_ANSWER = N_("— ответа в базе нет —")     # значение колонки «Документ» в таблице вопросов интерфейса


# ---------------------------------------------------------------- вопросы

@dataclass
class Question:
    n: int
    question: str
    files: list = field(default_factory=list)
    sections: list = field(default_factory=list)
    contains: list = field(default_factory=list)
    note: str = ""

    @property
    def answerable(self):
        return bool(self.files)

    @property
    def expected(self):
        if not self.files:
            return tr("— (нет в базе)")
        out = " | ".join(self.files)
        if self.sections:
            out += " › " + " | ".join(self.sections)
        if self.contains:
            out += " «" + " | ".join(c[:40] for c in self.contains) + "»"
        return out


def split_alts(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value or "").split("|") if v.strip()]


def questions_from_rows(rows):
    """[{question, file, section, contains, note}] → [Question]; строки без вопроса пропускаются."""
    out = []
    for i, r in enumerate(rows, 1):
        q = str(r.get("question") or "").strip()
        if q:
            out.append(Question(i, q, split_alts(r.get("file")), split_alts(r.get("section")),
                                split_alts(r.get("contains")), str(r.get("note") or "")))
    return out


def _read_text(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def load_questions(path):
    """CSV (разделитель «;» или «,», UTF-8 или Windows-1251) или JSONL. Строки с «#» пропускаются.
    Ошибка формата — ValueError с понятным текстом."""
    text = _read_text(path)
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    rows = []
    if str(path).lower().endswith((".jsonl", ".json")):
        for i, ln in enumerate(lines, 1):
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError as e:
                raise ValueError(tr("{path}, строка {i}: не JSON ({e}).", path=path, i=i, e=e))
    else:
        sample = "\n".join(lines[:5])
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        except csv.Error:
            class dialect(csv.excel):
                delimiter = ";" if sample.count(";") >= sample.count(",") else ","
        reader = csv.DictReader(io.StringIO("\n".join(lines)), dialect=dialect)
        header = {}
        for col in reader.fieldnames or []:
            key = (col or "").strip().lower()
            for canon, aliases in COLUMN_ALIASES.items():
                if key in aliases:
                    header[col] = canon
        if "question" not in header.values():
            raise ValueError(tr("{path}: нет колонки question (вопрос). Найдены колонки: {cols}",
                                path=path, cols=reader.fieldnames))
        for row in reader:
            rows.append({header[k]: v for k, v in row.items() if k in header})
    questions = questions_from_rows(rows)
    if not questions:
        raise ValueError(tr("{path}: вопросов не найдено.", path=path))
    return questions


def questions_csv(questions):
    """Набор вопросов в формате eval_search.py (разделитель «;», UTF-8 с BOM — открывается в Excel)."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["question", "file", "section", "contains", "note"])
    for q in questions:
        w.writerow([q.question, " | ".join(q.files), " | ".join(q.sections), " | ".join(q.contains), q.note])
    return "﻿" + buf.getvalue()


def known_files(snap):
    return sorted({(pd.get("source") or "") for pd in snap.parent_store.values()} - {""})


def missing_files(questions, snap):
    """{номер вопроса: [файлы, которых нет в базе]}."""
    known = {k.lower() for k in known_files(snap)}
    out = {}
    for q in questions:
        miss = [f for f in q.files if not any(f.lower() in k for k in known)]
        if miss:
            out[q.n] = miss
    return out


_norm = lru_cache(maxsize=16384)(norm_for_match)   # тексты фрагментов сверяются много раз за прогон


def is_relevant(q, pd):
    if not q.files:
        return False
    src = (pd.get("source") or "").lower()
    if not any(f.lower() in src for f in q.files):
        return False
    if q.sections:
        # раздел — в пути заголовков фрагмента или заголовком внутри его текста (фрагмент может начинаться
        # в предыдущем разделе: тогда путь заголовков указывает на начало, а нужный раздел — внутри)
        headings = " ".join(ln for ln in (pd.get("text") or "").splitlines() if ln.lstrip().startswith("#"))
        where = _norm(f"{pd.get('heading_path') or ''} {pd.get('section') or ''} {headings}")
        if not any(_norm(s) in where for s in q.sections):
            return False
    if q.contains:
        body = _norm(pd.get("text") or "")
        if not any(_norm(c) in body for c in q.contains):
            return False
    return True


# ---------------------------------------------------------------- конфигурации

def build_configs(cfg, with_multi_query=False, compare=True):
    """[(имя, cfg)]. compare=False — быстрый прогон: текущие настройки и для сравнения только dense и гибрид."""
    no_rr = replace(cfg, rerank_url="", use_multi_query=False)
    configs = [(CFG_DENSE, replace(no_rr, weight_dense=1.0, weight_bm25=0.0))]
    if compare:
        configs.append((CFG_BM25, replace(no_rr, weight_dense=0.0, weight_bm25=1.0)))
    configs.append((CFG_HYBRID, no_rr))
    if cfg.rerank_enabled:
        weights = sorted(set((RERANK_WEIGHTS if compare else []) + [round(cfg.weight_rerank, 2)]))
        for w in weights:
            configs.append((CFG_RERANK.format(w=f"{w:g}"), replace(cfg, weight_rerank=w, use_multi_query=False)))
        if with_multi_query:
            name = CFG_MULTI.format(name=CFG_RERANK.format(w=f"{cfg.weight_rerank:g}"))
            configs.append((name, replace(cfg, use_multi_query=True)))
    elif with_multi_query:
        configs.append((CFG_MULTI.format(name=CFG_HYBRID), replace(no_rr, use_multi_query=True)))
    return configs


def current_config_name(cfg):
    if cfg.rerank_enabled:
        return CFG_RERANK.format(w=f"{round(cfg.weight_rerank, 2):g}")
    return CFG_HYBRID


def config_label(name):
    """Имя конфигурации на языке интерфейса (внутренние имена — русские, они же ключи summary.json)."""
    m = re.fullmatch(r"(.*?)( \+ multi-query)?", name)
    base, multi = m.group(1), bool(m.group(2))
    rr = re.fullmatch(r"гибрид \+ реранкер (\S+)", base)
    label = tr(CFG_RERANK, w=rr.group(1)) if rr else tr(base)
    return tr(CFG_MULTI, name=label) if multi else label


# ---------------------------------------------------------------- прогон

def run_question(q, ccfg, snap, gl, top_k):
    diag = {}
    items, _ = search_parent_child(q.question, ccfg, k_neighbors=K_MAX, return_items=True, glossary=gl,
                                   use_multi_query=ccfg.use_multi_query)
    if isinstance(items, str):
        items = []
    # сигналы уверенности — при той глубине, что в чате (top_k)
    search_parent_child(q.question, ccfg, k_neighbors=top_k, glossary=gl, diagnostics=diag,
                        use_multi_query=ccfg.use_multi_query)
    rank = None
    for pos, it in enumerate(items, 1):
        # склеенный блок соседних фрагментов засчитывается, если нужный текст — в любом из них
        if any(is_relevant(q, snap.parent_store.get(p, {})) for p in (it.get("ids") or [it["id"]])):
            rank = pos
            break
    top = [it["short"].replace("📄 ", "") for it in items[:3]]
    return {"rank": rank, "top": top, "diag": diag}


def hit_ks(top_k):
    """Глубины для hit@N: 1, 3 и top_k (без повтора, если top_k — 1 или 3)."""
    return sorted({1, 3, top_k})


def metrics(results, questions, top_k):
    ans = [q for q in questions if q.answerable]
    none = [q for q in questions if not q.answerable]
    ranks = [results[q.n]["rank"] for q in ans]
    out = {"n_answerable": len(ans), "n_no_answer": len(none)}
    if ans:
        for k in hit_ks(top_k):
            out[f"hit@{k}"] = sum(1 for r in ranks if r and r <= k)
        out["mrr"] = sum(1.0 / r for r in ranks if r) / len(ans)
        out["false_low_conf"] = sum(1 for q in ans if results[q.n]["diag"].get("low_conf"))
    if none:
        out["detected_no_answer"] = sum(1 for q in none if results[q.n]["diag"].get("low_conf", True))
    return out


def sign_test_p(wins, losses):
    """Двусторонний критерий знаков: вероятность получить такой или больший перекос случайно, если
    конфигурации на самом деле равны. Вопросы, где места совпали, не учитываются."""
    n = wins + losses
    if not n:
        return 1.0
    k = min(wins, losses)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def paired(res_a, res_b, questions):
    """Сравнение двух конфигураций на одних и тех же вопросах с ответом: где A ставит правильный фрагмент
    выше, где ниже. Возвращает (лучше, хуже, [(вопрос, место A, место B)])."""
    better = worse = 0
    diff = []
    for q in questions:
        if not q.answerable:
            continue
        ra, rb = res_a[q.n]["rank"] or K_MAX + 1, res_b[q.n]["rank"] or K_MAX + 1
        if ra != rb:
            better += ra < rb
            worse += ra > rb
            diff.append((q, res_a[q.n]["rank"], res_b[q.n]["rank"]))
    return better, worse, diff


def calibrate(results, questions, cfg):
    """Таблица порогов сигнала «уверенность низкая» → доля распознанных «нет ответа» и ложных тревог.
    Правило то же, что в поиске (is_low_confidence): с реранкером сигнал зависит только от low_conf_rerank,
    без реранкера — от low_conf_lexical."""
    ans = [results[q.n]["diag"] for q in questions if q.answerable and results[q.n]["diag"]]
    none = [results[q.n]["diag"] for q in questions if not q.answerable and results[q.n]["diag"]]
    if not ans or not none:
        return None
    has_rerank = any(d.get("best_rerank") is not None for d in ans + none)
    cur = (cfg.low_conf_rerank, cfg.low_conf_lexical)
    if has_rerank:
        grid = [(t, cur[1]) for t in sorted({0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, round(cur[0], 2)})]
    else:
        grid = [(cur[0], t) for t in sorted({0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, round(cur[1], 2)})]
    rows = []
    for t_r, t_l in grid:
        def low(d):
            return is_low_confidence(d.get("best_rerank"), d.get("lexical_cov", 1.0), d.get("lists_agree"), t_r, t_l)
        det = sum(1 for d in none if low(d)) / len(none)
        fa = sum(1 for d in ans if low(d)) / len(ans)
        rows.append((t_r, t_l, det, fa, det - fa))
    # лучший баланс «распознано − ложные тревоги»; при равенстве — меньше ложных тревог, затем текущие пороги
    best = max(rows, key=lambda r: (round(r[4], 6), -r[3],
                                    abs(r[0] - cur[0]) < 1e-9 and abs(r[1] - cur[1]) < 1e-9))

    def dist(values):
        values = [v for v in values if v is not None]
        if not values:
            return "—"
        return tr("медиана {m:.2f} (мин {lo:.2f}, макс {hi:.2f})", m=statistics.median(values), lo=min(values),
                  hi=max(values))

    return {
        "rows": rows, "best": best, "current": cur, "has_rerank": has_rerank,
        "rerank_answerable": dist([d.get("best_rerank") for d in ans]),
        "rerank_no_answer": dist([d.get("best_rerank") for d in none]),
        "lexical_answerable": dist([d.get("lexical_cov") for d in ans]),
        "lexical_no_answer": dist([d.get("lexical_cov") for d in none]),
    }


@dataclass
class EvalRun:
    questions: list
    configs: list               # [(имя, cfg)]
    current: str
    results: dict               # имя → {номер вопроса → {rank, top, diag}}
    summary: dict               # имя → metrics()
    calib: dict
    top_k: int
    cfg: object
    stats: dict
    answers: dict = None        # check_answers(), если проверялись ответы чата
    created: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    prompts: str = field(default_factory=prompts_version)     # версия промптов (язык интерфейса на момент прогона)

    @property
    def n_answerable(self):
        return self.summary[self.configs[0][0]]["n_answerable"]

    @property
    def n_no_answer(self):
        return self.summary[self.configs[0][0]]["n_no_answer"]

    @property
    def best(self):
        """Лучшая конфигурация по MRR (при равенстве — по hit@K, затем текущая)."""
        if not self.n_answerable:
            return self.current
        return max(self.configs, key=lambda c: (round(self.summary[c[0]]["mrr"], 6),
                                                self.summary[c[0]][f"hit@{self.top_k}"], c[0] == self.current))[0]


def evaluate(cfg, questions, top_k=None, with_multi_query=False, compare=True, progress=None, answers=False,
             repeat=1):
    """Прогон набора вопросов. progress(сделано, всего, имя этапа) — для полосы прогресса. answers=True —
    ещё и ответы чата на каждый вопрос (+1 вызов LLM на вопрос и повтор, см. check_answers); repeat — сколько
    раз задать чату каждый вопрос (модель отвечает не всегда одинаково).
    Повторные запросы к сервисам в разных конфигурациях уходят один раз (request_cache)."""
    snap = load_kb_snapshot(cfg)
    if snap is None or snap.index.ntotal == 0:
        raise ValueError(tr("База знаний пуста или не найдена ({kb_path}).", kb_path=cfg.kb_path))
    top_k = top_k or cfg.top_k or kb_default_top_k(cfg)
    gl = load_glossary(cfg)
    configs = build_configs(cfg, with_multi_query, compare)
    current = current_config_name(cfg)
    results, summary, checked = {}, {}, None
    repeat = max(1, int(repeat or 1))
    total, done = len(configs) * len(questions) + (len(questions) * repeat if answers else 0), 0
    with request_cache() as stats:
        for name, ccfg in configs:
            res = {}
            for q in questions:
                res[q.n] = run_question(q, ccfg, snap, gl, top_k)
                done += 1
                if progress:
                    progress(done, total, name)
            results[name] = res
            summary[name] = metrics(res, questions, top_k)
        if answers:
            base = len(configs) * len(questions)
            checked = check_answers(replace(cfg, top_k=top_k), questions, gl, repeat=repeat, progress=(
                (lambda i, n: progress(base + i, total, STAGE_ANSWERS)) if progress else None))
        stats = dict(stats)
    calib = calibrate(results[current], questions, cfg)
    return EvalRun(questions, configs, current, results, summary, calib, top_k, cfg, stats, checked)


def recommendations(run):
    """Что поменять по итогам прогона: {параметр: значение}; пусто — менять нечего."""
    out = {}
    best = run.best
    if best != run.current and "multi-query" not in best:
        rr = re.fullmatch(r"гибрид \+ реранкер (\S+)", best)
        if rr:
            out["weight_rerank"] = float(rr.group(1))
        elif best == CFG_HYBRID and run.cfg.rerank_enabled:
            out["weight_rerank"] = 0.0
    if run.calib:
        b, cur = run.calib["best"], run.calib["current"]
        if run.calib["has_rerank"] and abs(b[0] - cur[0]) > 1e-9:
            out["low_conf_rerank"] = b[0]
        elif not run.calib["has_rerank"] and abs(b[1] - cur[1]) > 1e-9:
            out["low_conf_lexical"] = b[1]
    return out


def pairs_to_compare(run):
    """Пары (A, B) для раздела «Где конфигурации расходятся»: лучшая и простой гибрид против текущей,
    текущая против одного векторного поиска."""
    best, current = run.best, run.current
    pairs = [(best, current)] if best != current else []
    if CFG_HYBRID not in (best, current):
        pairs.append((CFG_HYBRID, current))
    if current != CFG_DENSE:
        pairs.append((current, CFG_DENSE))
    return pairs


# ---------------------------------------------------------------- отчёт

def pct(k, n):
    return f"{k}/{n} ({100.0 * k / n:.0f} %)" if n else "—"


def place_cell(res, q):
    """Ячейка «Место» в details.csv: место правильного фрагмента, а для вопроса без ответа в базе —
    сработал ли сигнал «уверенность низкая» (что и должно происходить на таких вопросах)."""
    if q.answerable:
        return res["rank"] or f"> {K_MAX}"
    return tr("✓ сигнал") if res["diag"].get("low_conf") else tr("✗ без сигнала")


def rerank_cell(diag, ccfg):
    if not ccfg.rerank_enabled:
        return tr("нет реранкера")
    if diag.get("best_rerank") is None:
        return tr("реранкер не ответил")
    return f"{diag['best_rerank']:.3f}"


def report_lines(run, compare=None, prev_answers=None):
    """report.md построчно. compare — configs из summary.json прошлого прогона; prev_answers — итоги ответов
    прошлой проверки с ответами чата (latest_answers())."""
    cfg, top_k, current, questions = run.cfg, run.top_k, run.current, run.questions
    configs, summary, all_results, calib = run.configs, run.summary, run.results, run.calib
    n_ans, n_none = run.n_answerable, run.n_no_answer
    lines = [
        tr("# Оценка поиска MINT — {when}", when=time.strftime("%d.%m.%Y %H:%M")),
        "",
        tr("Вопросов: {n} (с ответом в базе — {n_ans}, без ответа — {n_none}). Фрагментов в контексте модели (top_k): "
           "{top_k}. Модель эмбеддингов: {embed}; реранкер: {rr}.", n=len(questions), n_ans=n_ans, n_none=n_none,
           top_k=top_k, embed=cfg.embed_model, rr=cfg.rerank_model if cfg.rerank_enabled else tr("не подключён")),
        "",
        tr("## Сравнение конфигураций"),
        "",
        tr("hit@N — правильный фрагмент среди первых N; hit@{top_k} — попал в контекст модели (top_k); MRR — "
           "средняя обратная позиция (1 — всегда первый). «Нет ответа распознан» — доля вопросов без ответа, по "
           "которым сработал сигнал «уверенность низкая»; «ложная тревога» — сигнал на вопросах, где ответ есть.",
           top_k=top_k),
        "",
    ]
    ks = hit_ks(top_k)
    head = [tr("Конфигурация")] + [f"hit@{k}" for k in ks] + ["MRR"]
    if n_none:
        head += [tr("Нет ответа распознан")]
    if n_ans:
        head += [tr("Ложная тревога")]
    if compare:
        head += ["Δ MRR", f"Δ hit@{top_k}"]
    lines += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for name, _c in configs:
        m = summary[name]
        row = [config_label(name) + (tr(" ⬅ текущие настройки") if name == current else "")]
        if n_ans:
            row += [pct(m[f"hit@{k}"], n_ans) for k in ks] + [f"{m['mrr']:.3f}"]
        else:
            row += ["—"] * (len(ks) + 1)
        if n_none:
            row.append(pct(m["detected_no_answer"], n_none))
        if n_ans:
            row.append(pct(m["false_low_conf"], n_ans))
        if compare:
            prev = compare.get(name)
            prev_n = (prev or {}).get("n_answerable") or 0
            if prev and n_ans and "mrr" in prev and prev_n and f"hit@{top_k}" in prev:
                d_hit = 100.0 * (m[f"hit@{top_k}"] / n_ans - prev[f"hit@{top_k}"] / prev_n)
                row += [f"{m['mrr'] - prev['mrr']:+.3f}", tr("{d:+.0f} п.п.", d=d_hit)]
            else:
                row += ["—", "—"]
        lines.append("| " + " | ".join(row) + " |")
    if compare:
        prev_counts = {v.get("n_answerable") for v in compare.values() if isinstance(v, dict)}
        if prev_counts and prev_counts != {n_ans}:
            lines += ["", tr("⚠️ В прошлом прогоне было другое число вопросов с ответом ({prev}, сейчас {n_ans}): "
                             "сравнение показательно, только если набор вопросов тот же.",
                             prev=", ".join(map(str, sorted(prev_counts))), n_ans=n_ans)]

    if n_ans:
        best = run.best
        lines += ["", tr("**Лучшая по MRR:** {best}.", best=config_label(best))]
        rec = recommendations(run)
        if "weight_rerank" in rec and rec["weight_rerank"] > 0:
            lines += [tr("Чтобы применить: в config.yaml `weight_rerank: {w}` (раздел search).", w=f"{rec['weight_rerank']:g}")]
        elif "weight_rerank" in rec:
            lines += [tr("Чтобы применить, не отключая реранкер: в config.yaml `weight_rerank: 0` (раздел search) — "
                         "порядок станет как у гибрида, а баллы реранкера по-прежнему решают, ставить ли "
                         "«уверенность низкая».")]
        lines += [tr("Случайна ли разница — в разделе «Где конфигурации расходятся».")]
        pairs = pairs_to_compare(run)
        if pairs:
            lines += ["", tr("## Где конфигурации расходятся"), "",
                      tr("Сравнение на одних и тех же вопросах: на скольких одна конфигурация ставит правильный "
                         "фрагмент выше другой. p — вероятность получить такой перекос случайно, если конфигурации на "
                         "самом деле равны (критерий знаков); вопросы, где места совпали, не учитываются.")]
        for a, b in pairs:
            wins, losses, diff = paired(all_results[a], all_results[b], questions)
            lines += ["", pair_verdict(a, b, wins, losses, diff, n_ans)]
            if diff:
                lines += ["", "| № | " + tr("Вопрос") + f" | {tr('Место')}: {config_label(a)} | {tr('Место')}: "
                          f"{config_label(b)} | {tr('Первым')}: {config_label(a)} | {tr('Первым')}: {config_label(b)} |",
                          "|---|---|---|---|---|---|"]
                for q, ra, rb in diff[:20]:
                    fa = (all_results[a][q.n]["top"] or ["—"])[0]
                    fb = (all_results[b][q.n]["top"] or ["—"])[0]
                    lines.append(f"| {q.n} | {q.question} | {ra or f'> {K_MAX}'} | {rb or f'> {K_MAX}'} | {fa} | {fb} |")
                if len(diff) > 20:
                    lines += ["", tr("Ещё {n} — в details.csv.", n=len(diff) - 20)]

    if calib:
        b = calib["best"]
        key, idx = ("low_conf_rerank", 0) if calib["has_rerank"] else ("low_conf_lexical", 1)
        rule = (tr("С реранкером «уверенность низкая» ставится, если лучший балл реранкера ниже порога "
                   "`low_conf_rerank`.") if calib["has_rerank"] else
                tr("Реранкера нет: «уверенность низкая» ставится, если доля слов вопроса в контексте ниже порога "
                   "`low_conf_lexical` и dense с BM25 не сошлись в топ-N."))
        lines += ["", tr("## Пороги сигнала «уверенность низкая» (для текущих настроек)"), "", rule, ""]
        if calib["has_rerank"]:
            lines.append(tr("Лучший балл реранкера: на вопросах с ответом — {a}; без ответа — {b}.",
                            a=calib["rerank_answerable"], b=calib["rerank_no_answer"]))
        lines += [tr("Доля слов вопроса в контексте: с ответом — {a}; без ответа — {b}.",
                     a=calib["lexical_answerable"], b=calib["lexical_no_answer"]), "",
                  f"| {key} | {tr('Нет ответа распознан')} | {tr('Ложная тревога')} |", "|---|---|---|"]
        is_cur = lambda r: abs(r[0] - calib["current"][0]) < 1e-9 and abs(r[1] - calib["current"][1]) < 1e-9  # noqa: E731
        for row in calib["rows"]:
            _, _, det, fa, _ = row
            mark = (tr(" ⬅ сейчас") if is_cur(row) else "") + (" ★" if row is b else "")
            lines.append(f"| {row[idx]:.2f} | {det * 100:.0f} % | {fa * 100:.0f} %{mark} |")
        if is_cur(b):
            lines += ["", tr("★ — лучший баланс; текущий порог менять не нужно.")]
        else:
            lines += ["", tr("★ — лучший баланс. Чтобы применить: в config.yaml `{key}: {v}` (раздел confidence).",
                             key=key, v=f"{b[idx]:.2f}")]
        if not calib["has_rerank"]:
            lines += [tr("Без реранкера сигнал слабее: слова вопроса часто есть в базе, даже когда ответа нет. "
                         "Реранкер, даже с `weight_rerank: 0`, отличает такие вопросы заметно лучше.")]
    elif n_none == 0:
        lines += ["", tr("Пороги «уверенность низкая» не подбирались: добавьте в набор 5–10 вопросов, ответа на "
                         "которые в базе нет (колонка file пустая).")]

    lines += ["", tr("## Вопросы, где правильный фрагмент не попал в контекст ({name})", name=config_label(current)), ""]
    misses = [q for q in questions if q.answerable and (all_results[current][q.n]["rank"] or K_MAX + 1) > top_k]
    if not misses:
        lines.append(tr("Таких нет."))
    else:
        lines += [f"| № | {tr('Вопрос')} | {tr('Ожидалось')} | {tr('Место')} | {tr('Найдено первым')} |",
                  "|---|---|---|---|---|"]
        for q in misses:
            r = all_results[current][q.n]
            first = r["top"][0] if r["top"] else "—"
            lines.append(f"| {q.n} | {q.question} | {q.expected} | {r['rank'] or f'> {K_MAX}'} | {first} |")
    none_q = [q for q in questions if not q.answerable]
    if none_q:
        ccfg = dict(configs)[current]
        caught = sum(1 for q in none_q if all_results[current][q.n]["diag"].get("low_conf"))
        lines += ["", tr("## Вопросы без ответа в базе ({name})", name=config_label(current)), "",
                  tr("Сигнал «уверенность низкая» сработал на {caught} из {n}. Когда он срабатывает, модель получает "
                     "предупреждение, что ответа в базе, вероятно, нет, и меньше домысливает.", caught=caught,
                     n=len(none_q)), "",
                  f"| № | {tr('Вопрос')} | {tr('Сигнал')} | {tr('Лучший балл реранкера')} | {tr('Доля слов вопроса')} | "
                  f"{tr('Найдено первым')} |", "|---|---|---|---|---|---|"]
        for q in none_q:
            r = all_results[current][q.n]
            d = r["diag"]
            lines.append(f"| {q.n} | {q.question} | {'✓' if d.get('low_conf') else tr('✗ нет')} | {rerank_cell(d, ccfg)} | "
                         f"{d.get('lexical_cov', 0):.2f} | {(r['top'] or [tr('ничего не найдено')])[0]} |")
    lines += ["", tr("В details.csv в колонках «Место» у вопросов без ответа — сработал ли сигнал: «✓ сигнал» или "
                     "«✗ без сигнала»; «> {k}» — правильный фрагмент не найден среди первых {k}.", k=K_MAX)]
    if run.answers:
        lines += answers_report_lines(run, prev_answers)
    st_ = run.stats
    lines += ["", tr("Запросов к сервисам: эмбеддинги {e} (без ответа {ef}), реранкер {r} (с ошибкой {rf}).",
                     e=st_.get("embed_calls", 0), ef=st_.get("embed_failed", 0), r=st_.get("rerank_calls", 0),
                     rf=st_.get("rerank_failed", 0))]
    if st_.get("embed_failed"):
        lines.append(tr("⚠️ Для {n} вопросов эмбеддинг не получен — по ним работал только BM25.", n=st_["embed_failed"]))
    return lines


def pair_verdict(a, b, wins, losses, diff, n_ans):
    p = sign_test_p(wins, losses)
    if not diff:
        verdict = tr("места правильного фрагмента совпали на всех вопросах.")
    elif p < 0.05:
        verdict = tr("p = {p:.2f} — разница, скорее всего, не случайна.", p=p)
    else:
        verdict = tr("p = {p:.2f} — разница может быть случайной; чтобы её подтвердить, нужно больше вопросов "
                     "(40–60) или вопросы, на которых конфигурации расходятся.", p=p)
    return tr("**{a}** против **{b}**: выше на {wins}, ниже на {losses} из {n} вопросов; {verdict}",
              a=config_label(a), b=config_label(b), wins=wins, losses=losses, n=n_ans, verdict=verdict)


def details_rows(run):
    """details.csv: заголовок и строка на вопрос."""
    rows = [["№", tr("Вопрос"), tr("Ожидалось")] + [f"{tr('Место')}: {config_label(n)}" for n, _ in run.configs]
            + [tr("Сигнал «уверенность низкая»"), tr("Лучший балл реранкера"), tr("Доля слов вопроса в контексте"),
               tr("dense и BM25 согласны"), tr("Найдено (текущие настройки), топ-3")]]
    ccfg = dict(run.configs)[run.current]
    for q in run.questions:
        cur = run.results[run.current][q.n]
        d = cur["diag"]
        rows.append([q.n, q.question, q.expected] + [place_cell(run.results[n][q.n], q) for n, _ in run.configs]
                    + [tr("да") if d.get("low_conf") else tr("нет"), rerank_cell(d, ccfg), f"{d.get('lexical_cov', 0):.2f}",
                       tr("да") if d.get("lists_agree") else tr("нет"), " || ".join(cur["top"]) or tr("ничего не найдено")])
    return rows


def details_csv(run):
    buf = io.StringIO()
    csv.writer(buf, delimiter=";").writerows(details_rows(run))
    return "﻿" + buf.getvalue()


def summary_dict(run):
    cfg = run.cfg
    out = {"created": run.created, "top_k": run.top_k, "embed_model": cfg.embed_model,
           "rerank_model": cfg.rerank_model if cfg.rerank_enabled else None, "questions": len(run.questions),
           "current": run.current, "configs": run.summary, "prompts": run.prompts}
    if run.answers:
        out["answers"] = run.answers["summary"]
    return out


def write_reports(out_dir, run, compare=None, prev_answers=None):
    """report.md, details.csv, summary.json и questions.csv в папку out_dir. Возвращает строки отчёта."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = report_lines(run, compare, prev_answers)
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # csv уже с переводами строк \r\n; newline="" — чтобы Windows не превратил их в \r\r\n (пустые строки в Excel)
    (out_dir / "details.csv").write_text(details_csv(run), encoding="utf-8", newline="")
    (out_dir / "summary.json").write_text(json.dumps(summary_dict(run), ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "questions.csv").write_text(questions_csv(run.questions), encoding="utf-8", newline="")
    if run.answers:
        (out_dir / "answers.csv").write_text(answers_csv(run), encoding="utf-8", newline="")
    return lines


# ---------------------------------------------------------------- черновик вопросов

def nearest_quote(quote, text, min_overlap=0.6, max_words=15):
    """Модель пересказала цитату вместо дословной — берёт из фрагмента предложение, больше всего совпадающее с
    ней по основам слов (не меньше min_overlap слов цитаты), и первые max_words его слов. Иначе — пусто."""
    q_terms = set(bm25_tokenize(quote))
    if not q_terms:
        return ""
    best, best_score = "", 0.0
    for sent in re.split(r"(?<=[.!?;])\s+|\n+", text):
        if "|" in sent or sent.lstrip().startswith("#"):
            continue                                   # строки таблиц и заголовки — не цитаты
        score = len(q_terms & set(bm25_tokenize(sent))) / len(q_terms)
        if score > best_score:
            best, best_score = sent, score
    if best_score < min_overlap:
        return ""
    return " ".join(best.split()[:max_words])


def pick_fragments(snap, n, seed=7, min_chars=300, exclude=()):
    """n фрагментов поровну из каждого документа (случайно, но воспроизводимо при том же seed); exclude —
    номера фрагментов, по которым вопросы уже составлены."""
    rnd = random.Random(seed)
    by_source = {}
    skip = set(exclude)
    for pid, pd in snap.parent_store.items():
        if pid not in skip and len(pd.get("text") or "") >= min_chars:
            by_source.setdefault(pd.get("source") or "", []).append((pid, pd))
    for lst in by_source.values():
        lst.sort(key=lambda x: x[0])
        rnd.shuffle(lst)
    picked = []
    while len(picked) < n and any(by_source.values()):
        for src in sorted(by_source):
            if by_source[src] and len(picked) < n:
                picked.append(by_source[src].pop())
    return picked


def generate_questions(cfg, n, seed=7, progress=None, snap=None, exclude=()):
    """Черновик вопросов по базе: по фрагменту — вопрос и дословная цитата с ответом (вызов LLM на вопрос).
    Возвращает ([{question, file, section, contains, note, fragment, pid, quote_found}], число неудач)."""
    snap = snap or load_kb_snapshot(cfg)
    if snap is None or not snap.parent_store:
        raise ValueError(tr("База знаний пуста или не найдена ({kb_path}).", kb_path=cfg.kb_path))
    picked = pick_fragments(snap, n, seed, exclude=exclude)
    rows, failed = [], 0
    for i, (pid, pd) in enumerate(picked, 1):
        if progress:
            progress(i - 1, len(picked))
        text = pd.get("text") or ""
        raw = ask_llm(question_gen_system(), render("question_gen_user", source=pd.get("source"), text=text[:3000]), cfg,
                      temperature=0.4, max_tokens=300)
        data = extract_json(raw, kind="object") if not is_llm_error(raw) else None
        if not isinstance(data, dict) or not str(data.get("question") or "").strip():
            failed += 1
            continue
        quote = str(data.get("quote") or "").strip().strip("«»\"")
        how = "exact"
        if quote and norm_for_match(quote) not in norm_for_match(text):
            quote = nearest_quote(quote, text)
            how = "near" if quote else "none"
        elif not quote:
            how = "none"
        kind = tr("таблица") if pd.get("type") == "table" else tr("текст")
        note = tr("черновик ({kind}) — проверьте", kind=kind) + {"near": tr("; цитата подобрана по смыслу"),
                                                               "none": tr("; цитата не найдена — впишите фразу сами")}.get(how, "")
        rows.append({"question": str(data["question"]).strip(), "file": pd.get("source") or "",
                     "section": (pd.get("heading_path") or "").split(" → ")[-1], "contains": quote, "note": note,
                     "fragment": text, "pid": pid, "quote_found": how})
    if progress:
        progress(len(picked), len(picked))
    return rows, failed


# ---------------------------------------------------------------- ответы чата

# Почему ответ не засчитан. «Поиск» — нужного фрагмента не было в контексте модели (это видно и без чата, в
# метриках поиска); «модель» — фрагмент был, а ответ не тот: это то, что меняет правка промпта.
ANSWER_REASONS = {
    "error": N_("сбой модели или шлюза"),
    "search": N_("поиск: нужного фрагмента нет в контексте"),
    "no_info": N_("модель: «информации нет», хотя фрагмент в контексте"),
    "no_ref": N_("модель: нет ссылки на нужный документ"),
    "bad_ref": N_("модель: ссылки мимо найденных фрагментов"),
    "answered": N_("модель ответила, хотя ответа в базе нет"),
}

# Что пишется о прогоне ответов (summary.json → answers) и сравнивается с прошлым прогоном
ANSWER_META = {"prompts": N_("версия промптов"), "lang": N_("язык"), "llm_model": N_("модель"),
               "temperature": N_("температура"), "top_k": "top_k", "repeat": N_("повторов")}


def is_refusal(answer):
    """Ответ «в документах этого нет» — фраза chat_no_info из промпта чата (mint/prompts/<язык>.yaml), на любом
    из языков: модель отвечает на языке вопроса."""
    return is_no_info_answer(answer)


def _norm_name(s):
    """Имя документа для сравнения: без регистра, расширения и разделителей («Регламент_ИБ.docx» = «регламент иб»)."""
    s = re.sub(r"\.(?:docx?|pdf|txt|md)\b", "", (s or "").lower().replace("ё", "е"))
    return re.sub(r"[\s_\-]+", " ", s).strip()


def judge_answer(q, res):
    """Проверка одного ответа чата (результат chat.answer_question) без модели. Возвращает признаки, итог ok и
    причину ошибки reason (ключ ANSWER_REASONS) или None."""
    failed = res["error"]
    refused = not failed and is_refusal(res["answer"])
    names = [] if failed else cited_files(res["answer"], res["context"])
    wanted = [_norm_name(f) for f in q.files if _norm_name(f)]
    r = {"answer": res["answer"], "failed": failed, "refused": refused, "low_conf": bool(res.get("low_conf")),
         "n_citations": len(res.get("citations") or []), "invalid": list(res.get("citations_invalid") or []),
         "cites_expected": any(w in _norm_name(n) for n in names for w in wanted),
         "in_context": None, "contains_in_answer": None,
         "sources": list(res.get("sources") or []), "seconds": round(float(res.get("seconds") or 0.0), 1)}
    if q.answerable:
        srcs = " ".join(r["sources"]).lower()
        in_ctx = any(f.lower() in srcs for f in q.files)
        if in_ctx and q.contains:
            ctx = norm_for_match(res["context"])
            in_ctx = any(_norm(c) in ctx for c in q.contains)
        r["in_context"] = in_ctx
        if q.contains:
            ans = norm_for_match(res["answer"])
            r["contains_in_answer"] = any(_norm(c) in ans for c in q.contains)
        if failed:
            reason = "error"
        elif not in_ctx:
            reason = "search"
        elif refused:
            reason = "no_info"
        elif not r["cites_expected"]:
            reason = "no_ref"
        elif r["invalid"]:
            reason = "bad_ref"
        else:
            reason = None
        # поиск не нашёл ожидаемый фрагмент, а ответ всё равно ссылается на нужный документ — засчитывается
        if reason == "search" and r["cites_expected"] and not refused and not r["invalid"]:
            reason = None
    else:
        reason = "error" if failed else (None if refused else "answered")
    r["ok"], r["reason"] = reason is None, reason
    return r


def check_answers(cfg, questions, glossary, progress=None, repeat=1):
    """Ответ чата на каждый вопрос (repeat раз) — тем же путём, что в чате (chat.answer_question), — и проверка
    judge_answer(). Возвращает {"rows": {номер вопроса: [проверка каждого ответа]}, "summary": answers_summary()}."""
    if not cfg.top_k:                       # 0 — «по размеру базы», как в чате
        cfg = replace(cfg, top_k=kb_default_top_k(cfg))
    repeat = max(1, int(repeat or 1))
    rows, total, done = {}, len(questions) * repeat, 0
    for q in questions:
        rows[q.n] = []
        for _ in range(repeat):
            if progress:
                progress(done, total)
            t0 = time.time()
            res = answer_question(q.question, cfg, glossary)
            res["seconds"] = time.time() - t0
            rows[q.n].append(judge_answer(q, res))
            done += 1
    if progress:
        progress(total, total)
    return {"rows": rows, "summary": answers_summary(cfg, questions, rows, repeat)}


def answers_summary(cfg, questions, rows, repeat=1):
    """Счётчики по всем ответам (вопрос × повтор); сбои модели — отдельно и в доли не входят. scores — доля
    верных ответов по каждому вопросу: по ним сравниваются прогоны (compare_answers)."""
    ans = [r for q in questions if q.answerable for r in rows[q.n] if not r["failed"]]
    none = [r for q in questions if not q.answerable for r in rows[q.n] if not r["failed"]]
    with_phrase = [r for q in questions if q.answerable and q.contains for r in rows[q.n] if not r["failed"]]
    return {
        "n_answerable": len(ans), "n_no_answer": len(none),
        "failed": sum(1 for q in questions for r in rows[q.n] if r["failed"]),
        "ok_answerable": sum(1 for r in ans if r["ok"]),
        "cites_expected": sum(1 for r in ans if r["cites_expected"]),
        "clean": sum(1 for r in ans + none if not r["invalid"]),
        "false_refusal": sum(1 for r in ans if r["refused"]),
        "in_context": sum(1 for r in ans if r["in_context"]),
        "n_with_phrase": len(with_phrase), "phrase_in_answer": sum(1 for r in with_phrase if r["contains_in_answer"]),
        "honest_refusal": sum(1 for r in none if r["refused"]),
        "low_conf_no_answer": sum(1 for r in none if r["low_conf"]),
        "reasons": dict(Counter(r["reason"] for q in questions for r in rows[q.n] if r["reason"])),
        "scores": {q.question: round(sum(r["ok"] for r in rows[q.n]) / len(rows[q.n]), 3) for q in questions},
        "prompts": prompts_version(), "prompts_custom": custom_status(), "lang": get_lang(), "llm_model": cfg.llm_model,
        "temperature": cfg.temperature, "top_k": cfg.top_k, "repeat": repeat,
    }


def answer_metrics(a):
    """Главные показатели ответов: [(ключ, подпись, верно, всего, больше — лучше)]; без пустых."""
    items = [
        ("ok_answerable", N_("верный ответ"), a["ok_answerable"], a["n_answerable"], True),
        ("cites_expected", N_("ссылка на нужный документ"), a["cites_expected"], a["n_answerable"], True),
        ("false_refusal", N_("ложное «информации нет»"), a["false_refusal"], a["n_answerable"], False),
        ("honest_refusal", N_("честное «информации нет»"), a["honest_refusal"], a["n_no_answer"], True),
        ("dirty", N_("со ссылками мимо найденного"), a["n_answerable"] + a["n_no_answer"] - a["clean"],
         a["n_answerable"] + a["n_no_answer"], False),
    ]
    return [it for it in items if it[3]]


def latest_answers(runs):
    """Итоги ответов из самой свежей проверки, где проверялись ответы чата (runs — list_runs())."""
    for _folder, summary in runs:
        if isinstance(summary.get("answers"), dict) and summary["answers"].get("scores"):
            return summary["answers"]
    return None


def compare_answers(cur, prev):
    """Сравнение ответов с прошлым прогоном на общих вопросах. Возвращает словарь: better, worse, same, p
    (критерий знаков), changed [(лучше/хуже, вопрос, было, стало)], meta [(что, было, стало)] — что изменилось в
    настройках, several — изменилось больше одного параметра (язык входит в версию промптов), deltas
    {показатель: изменение доли в п.п.}."""
    better = worse = same = 0
    changed = []
    for question, score in (cur.get("scores") or {}).items():
        old = (prev.get("scores") or {}).get(question)
        if old is None:
            continue
        if score > old + 1e-9:
            better += 1
            changed.append(("better", question, old, score))
        elif score < old - 1e-9:
            worse += 1
            changed.append(("worse", question, old, score))
        else:
            same += 1
    meta = [(k, prev.get(k), cur.get(k)) for k in ANSWER_META if prev.get(k) != cur.get(k)]
    keys = {k for k, _, _ in meta}
    several = len([k for k in keys if not (k == "lang" and "prompts" in keys)]) > 1
    deltas = {}
    old_items = {key: (k, n) for key, _l, k, n, _h in answer_metrics(prev)} if prev.get("n_answerable") is not None else {}
    for key, _label, k, n, _h in answer_metrics(cur):
        if key in old_items and old_items[key][1]:
            deltas[key] = 100.0 * (k / n - old_items[key][0] / old_items[key][1])
    return {"better": better, "worse": worse, "same": same, "p": sign_test_p(better, worse), "changed": changed,
            "meta": meta, "several": several, "deltas": deltas}


def answers_verdict(c):
    """Одна строка: лучше/хуже на общих вопросах и случайна ли разница."""
    if not (c["better"] or c["worse"]):
        tail = tr("разницы нет.")
    elif c["p"] < 0.05:
        tail = tr("p = {p:.2f} — разница, скорее всего, не случайна.", p=c["p"])
    else:
        tail = tr("p = {p:.2f} — разница может быть случайной; нужно больше вопросов или повторов.", p=c["p"])
    return tr("На общих вопросах ответы лучше на {b}, хуже на {w}, без изменений — {s}; {tail}",
              b=c["better"], w=c["worse"], s=c["same"], tail=tail)


def meta_text(meta):
    return "; ".join(f"{tr(ANSWER_META[k])}: {old} → {new}" for k, old, new in meta)


def answers_report_lines(run, prev_answers=None):
    a = run.answers["summary"]
    lines = ["", tr("## Ответы чата (текущие настройки)"), "",
             tr("Каждый вопрос задан чату с текущими настройками{rep}; ответы проверены без модели: ссылки сверены с "
                "найденными фрагментами, «информации нет» — по фразе chat_no_info из промпта. Промпты: **{v}**.",
                rep=tr(", повторов: {n}", n=a["repeat"]) if a.get("repeat", 1) > 1 else "", v=a.get("prompts", "—"))
             + (" " + tr("Свои правки промптов: {v}.", v=custom_label(a["prompts_custom"])) if a.get("prompts_custom") else ""),
             ""]
    for _key, label, k, n, _h in answer_metrics(a):
        lines.append(f"- {tr(label)}: {pct(k, n)}")
    if a["n_answerable"]:
        lines.append(tr("- Нужный фрагмент был в контексте модели: {v}.", v=pct(a["in_context"], a["n_answerable"])))
    if a["failed"]:
        lines.append(tr("- ⚠️ Модель не ответила {n} раз — эти ответы не учтены.", n=a["failed"]))
    reasons = a.get("reasons") or {}
    if reasons:
        lines += ["", tr("### Где ошибки: поиск или модель"), "", f"| {tr('Причина')} | {tr('Ответов')} |", "|---|---|"]
        lines += [f"| {tr(ANSWER_REASONS[k])} | {v} |" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])]
        lines += ["", tr("«Поиск» — правьте настройки поиска (сравнение настроек выше); «модель» — промпт чата "
                         "(страница «📝 Промпты» → «Системный промпт чата») или модель.")]
    if prev_answers and prev_answers.get("scores"):        # итоги ответов старого формата (без баллов) не сравниваются
        c = compare_answers(a, prev_answers)
        lines += ["", tr("### Сравнение ответов с прошлой проверкой"), "",
                  tr("Изменилось: {what}.", what=meta_text(c["meta"]) or tr("ничего из настроек"))]
        if c["several"]:
            lines += ["", tr("⚠️ Изменилось больше одного параметра — разницу нельзя приписать чему-то одному.")]
        lines += ["", answers_verdict(c)]
        if c["changed"]:
            lines += ["", f"| {tr('Изменение')} | {tr('Вопрос')} | {tr('Было')} | {tr('Стало')} |", "|---|---|---|---|"]
            lines += [f"| {tr('лучше') if d == 'better' else tr('хуже')} | {qq.replace('|', '/')} | {old:.0%} | {new:.0%} |"
                      for d, qq, old, new in c["changed"][:30]]
    bad = [(q, i, r) for q in run.questions for i, r in enumerate(run.answers["rows"][q.n], 1) if not r["ok"]]
    if bad:
        lines += ["", tr("### Ответы с ошибками"), ""]
        for q, i, r in bad[:20]:
            rep = tr(" (повтор {i})", i=i) if a.get("repeat", 1) > 1 else ""
            lines += [f"**{q.n}. {q.question}**{rep}",
                      tr("- ожидалось: {e}; причина: {why}", e=q.expected, why=tr(ANSWER_REASONS[r["reason"]])),
                      tr("- ответ: {a}", a=" ".join(r["answer"].split())[:300]), ""]
        if len(bad) > 20:
            lines.append(tr("Ещё {n} — в answers.csv.", n=len(bad) - 20))
    return lines


def answers_csv(run):
    yn = {True: tr("да"), False: tr("нет"), None: "—"}
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["№", tr("Вопрос"), tr("Ожидалось"), tr("Повтор"), tr("Итог"), tr("Причина"), tr("Ответ чата"),
                tr("Ссылка на ожидаемый документ"), tr("Ссылки мимо найденного"), tr("«Информации нет»"),
                tr("Фрагмент в контексте"), tr("Сигнал «уверенность низкая»"), tr("Фраза в ответе"), tr("Время, с"),
                tr("Источники")])
    for q in run.questions:
        for i, r in enumerate(run.answers["rows"][q.n], 1):
            w.writerow([q.n, q.question, q.expected, i, "✓" if r["ok"] else "✗",
                        tr(ANSWER_REASONS[r["reason"]]) if r["reason"] else "—", r["answer"].strip() or "—",
                        yn[r["cites_expected"] if q.answerable else None], " ".join(r["invalid"]) or "—",
                        yn[r["refused"]], yn[r["in_context"]], yn[r["low_conf"]], yn[r["contains_in_answer"]],
                        f"{r['seconds']:.1f}", " || ".join(s.replace("📄 ", "") for s in r["sources"]) or "—"])
    return "\ufeff" + buf.getvalue()


# ---------------------------------------------------------------- таблица вопросов в интерфейсе

def is_no_answer(value):
    v = str(value or "").strip()
    return bool(v) and v in {NO_ANSWER, tr(NO_ANSWER, lang="en")}


def cell(value):
    """Ячейка таблицы как строка: None и NaN (пустые ячейки новых строк) → ""."""
    if value is None or (isinstance(value, float) and value != value):
        return ""
    return str(value).strip()


def rows_to_questions(rows):
    """Строки таблицы вопросов → ([Question], {номер строки: что не так}). Пустые и снятые галочкой строки
    пропускаются; строка без документа в прогон не входит: нужно выбрать файл или «ответа в базе нет»."""
    out, issues = [], {}
    for i, r in enumerate(rows, 1):
        text = cell(r.get("question"))
        if not text or r.get("use") is False:
            continue
        f = cell(r.get("file"))
        if not f:
            issues[i] = tr("не выбран документ")
            continue
        files = [] if is_no_answer(f) else split_alts(f)
        out.append(Question(i, text, files, split_alts(cell(r.get("section"))) if files else [],
                            split_alts(cell(r.get("contains"))) if files else [], cell(r.get("note"))))
    return out, issues


def question_rows(questions, snap):
    """[Question] (например, из прошлой проверки) → строки таблицы; неполное имя файла дополняется до имени в
    базе, если подходит ровно один документ."""
    known = known_files(snap)
    rows = []
    for q in questions:
        names = []
        for f in q.files:
            hits = [k for k in known if f.lower() in k.lower()]
            names.append(hits[0] if len(hits) == 1 else f)
        rows.append({"use": True, "question": q.question, "file": " | ".join(names) or tr(NO_ANSWER),
                     "section": " | ".join(q.sections), "contains": " | ".join(q.contains), "note": q.note})
    return rows


def markup_problems(questions, snap):
    """{номер: что не так с разметкой}: вопрос с такой разметкой не будет засчитан ни при каком поиске."""
    by_src = {}
    for pd in snap.parent_store.values():
        by_src.setdefault(pd.get("source") or "", []).append(pd)
    out = {}
    for q in questions:
        if not q.answerable:
            continue
        frags = [pd for src, lst in by_src.items() if any(f.lower() in src.lower() for f in q.files) for pd in lst]
        if not frags:
            out[q.n] = tr("документа нет в базе")
        elif not any(is_relevant(q, pd) for pd in frags):
            if q.contains and not any(is_relevant(replace(q, sections=[]), pd) for pd in frags):
                out[q.n] = tr("фраза не найдена в документе — перепишите её дословно или очистите")
            elif q.sections and not any(is_relevant(replace(q, contains=[]), pd) for pd in frags):
                out[q.n] = tr("раздел не найден в документе")
            else:
                out[q.n] = tr("фраза и раздел не встречаются в одном фрагменте")
    return out


# ---------------------------------------------------------------- сохранённые проверки

def runs_dir(cfg):
    return cfg.log_path / "eval"


def save_run(cfg, run, compare=None, prev_answers=None):
    """Отчёты проверки в папку LOG_DIR/eval/<дата_время>. Возвращает (папка, строки отчёта)."""
    out = runs_dir(cfg) / time.strftime("%Y-%m-%d_%H-%M-%S")
    return out, write_reports(out, run, compare, prev_answers)


def list_runs(cfg, limit=20):
    """Прошлые проверки, новые первыми: [(папка, summary.json)]."""
    folder = runs_dir(cfg)
    if not folder.is_dir():
        return []
    out = []
    for p in sorted((x for x in folder.iterdir() if x.is_dir()), reverse=True):
        try:
            out.append((p, json.loads((p / "summary.json").read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
        if len(out) >= limit:
            break
    return out

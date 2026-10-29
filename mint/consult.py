"""Консультант: ответ с рассуждениями модели на опоре на базу знаний — разбор проблемы и варианты решения, схема
(код Mermaid), объяснение устройства систем, сравнение вариантов. Весь сценарий — без интерфейса.

    from mint.consult import answer_consult
    res = answer_consult("Нарисуй схему прохождения входящего сообщения", cfg)
    res["answer"], res["shown"], res["diagrams"], res["aspects"], res["blocks"]

Чем отличается от чата (mint/chat.py):
  1. Разбор запроса (+1 вызов LLM): что просят (проблема, схема, объяснение, вопрос, сравнение), какие системы
     упомянуты и несколько поисковых запросов — по одному на каждую сторону вопроса (состав, взаимодействие, путь
     сообщения, настройки, мониторинг).
  2. Поиск по каждому запросу и по самому запросу пользователя (обычный гибридный поиск MINT). Найденное
     чередуется по запросам, чтобы были представлены все стороны вопроса; найденный фрагмент расширяется до
     раздела целиком (с подразделами), карточки упомянутых систем добавляются всегда. Объём — по окну модели.
  3. Ответ: модели можно предлагать своё (с пометкой 💡), факты о системах пользователя — только из базы, со
     ссылками; ответ начинается с раздела «📄 …» — как устроено сейчас. Прошлые реплики разговора — часть работы.
  4. Проверка без модели: ссылки — по всем фрагментам, которые модель видела в разговоре; пункты раздела «📄» без
     ссылки помечаются ❔ (mark_unsupported); код схем Mermaid выделяется для скачивания.

У текстов консультанта своя версия (prompts.consult_prompts_version): она пишется в отзывы, версия промптов чата
и аудита от консультанта не зависит.
"""

import logging
import re
import time
from dataclasses import replace

from .audit import is_llm_error
from .citations import check_citations, has_citation, mark_invalid
from .config import FALLBACK_LIMITS
from .expert import load_expert_materials
from .kb import load_glossary, load_kb_snapshot, parent_order
from .limits import LIMIT_SAFETY
from .passages import focus_passage, merge_adjacent
from .prompts import (
    consult_plan_messages, consult_prompts_version, consult_system_prompt, consult_user_content, render,
)
from .search import _source_header, search_parent_child
from .services import ask_llm
from .text import extract_json

logger = logging.getLogger("MINT")

KINDS = ("problem", "diagram", "explain", "question", "compare", "other")
HISTORY_ANSWER_CHARS = 6000      # прошлый ответ в истории — почти целиком: на него опираются уточнения
PLAN_DIALOG_CHARS = 600          # реплика в разборе запроса — коротко: нужен только предмет разговора
PLAN_MAX_TOKENS = 600
RESERVE_TOKENS = 700             # разметка запроса, справочник сокращений, запас
MIN_CONTEXT_CHARS = 3000
MIN_TIMEOUT = 180                # ответ консультанта длиннее ответа чата
CARDS_SHARE = 0.35               # карточки систем — не больше этой доли фрагментов
MIN_PIECE_CHARS = 1200           # раздел, который не помещается целиком, — окном не короче
UNSUPPORTED_MARK = " ❔"

_HEADING_RE = re.compile(r"^\s{0,3}(?:#{1,6}\s+\S|\*\*[^*]+\*\*:?\s*$)")
_MERMAID_RE = re.compile(r"```\s*mermaid[^\n]*\n(.*?)```", re.S | re.I)
_NOTHING_RE = re.compile(r"ничего не|не нашл|не найден|нет сведений|нет информации|не описан|nothing|not found|"
                         r"no information|not described", re.I)
_KIND_HINTS = (
    ("diagram", re.compile(r"нарисуй|схем|диаграмм|draw|diagram|chart", re.I)),
    ("problem", re.compile(r"проблем|инцидент|сбой|ошибк|не работает|медленн|тормоз|problem|issue|incident|fails?\b|"
                           r"slow", re.I)),
    ("compare", re.compile(r"сравни|сравнен|что лучше|\bили\b.*\?|compare|versus|\bvs\b", re.I)),
)


def consult_cfg(cfg):
    """Настройки запроса консультанта к модели: своя температура и длина ответа, таймаут не меньше MIN_TIMEOUT."""
    return replace(cfg, temperature=cfg.consult_temperature, max_tokens=cfg.consult_max_tokens,
                   llm_timeout=max(cfg.llm_timeout, MIN_TIMEOUT))


def guess_kind(request):
    """Что просят — по словам запроса (если разбор запроса моделью не удался)."""
    for kind, pattern in _KIND_HINTS:
        if pattern.search(request or ""):
            return kind
    return "explain"


def _words(s):
    return re.sub(r"[^\w]+", " ", (s or "").lower().replace("ё", "е")).split()


def dialog_text(history):
    """Прошлые реплики для разбора запроса — коротко: «Пользователь: …» / «Ассистент: …»."""
    return "\n".join(
        render("condense_dialog_user" if m["role"] == "user" else "condense_dialog_assistant",
               text=(m["content"] or "")[:PLAN_DIALOG_CHARS])
        for m in history or [] if m.get("content")
    )


def parse_plan(raw, request, max_queries):
    """Ответ модели на разбор запроса → {"kind", "systems", "queries", "ok"}. Первый поисковый запрос — всегда сам
    запрос пользователя: модель при переформулировке может потерять термин, сокращение или номер."""
    plan = {"kind": None, "systems": [], "queries": [], "ok": False}
    data = None if is_llm_error(raw) else extract_json(raw, kind="object")
    if isinstance(data, dict):
        kind = str(data.get("kind") or "").strip().lower()
        plan["kind"] = kind if kind in KINDS else None
        plan["systems"] = [str(s).strip() for s in (data.get("systems") or [])
                           if isinstance(s, (str, int)) and str(s).strip()][:10]
        qs = data.get("queries") or []
        plan["queries"] = [str(q).strip() for q in (qs if isinstance(qs, list) else []) if isinstance(q, str) and q.strip()]
        plan["ok"] = bool(plan["queries"]) or plan["kind"] is not None
    queries, seen = [], set()
    for q in [request] + plan["queries"][:max(0, max_queries)]:
        key = tuple(_words(q))
        if key and key not in seen:
            seen.add(key)
            queries.append(q)
    plan["queries"] = queries
    plan["kind"] = plan["kind"] or guess_kind(request)
    return plan


def plan_request(request, history, cfg):
    """Разбор запроса моделью (+1 вызов LLM): тип запроса, системы, поисковые запросы по аспектам."""
    system, user = consult_plan_messages(request, dialog_text(history), cfg.consult_queries)
    raw = ask_llm(system, user, cfg, temperature=0.0, max_tokens=PLAN_MAX_TOKENS)
    plan = parse_plan(raw, request, cfg.consult_queries)
    if not plan["ok"]:
        logger.warning(f"Консультант: разбор запроса не получился ({str(raw)[:120]!r}) — поиск по самому запросу")
    logger.info(f"🧠 Консультант: {plan['kind']}, систем {len(plan['systems'])}, поисков {len(plan['queries'])}")
    return plan


def context_budget(cfg, fixed_chars):
    """Сколько символов фрагментов поместится в запрос: окно модели минус ответ, промпт, история и запрос;
    не больше consult_context_max_chars."""
    cpt = cfg.chars_per_token or FALLBACK_LIMITS["chars_per_token"]
    window = cfg.llm_context_tokens or FALLBACK_LIMITS["llm_context_tokens"]
    room = int((window - cfg.consult_max_tokens - RESERVE_TOKENS) * cpt * LIMIT_SAFETY) - int(fixed_chars)
    return max(MIN_CONTEXT_CHARS, min(cfg.consult_context_max_chars, room))


def section_ids(found, by_source, store, order, max_chars):
    """Фрагменты раздела, в котором найден фрагмент found: тот же документ и путь заголовков — этот раздел или его
    подразделы. Раздел длиннее max_chars — окно вокруг найденного (сначала текст после него, затем до)."""
    pd = store[found["id"]]
    path = pd.get("heading_path") or ""
    own = [p for p in found["ids"] if p in store]
    if not path:
        return own
    members = [p for p in by_source.get(pd.get("source", ""), [])
               if (store[p].get("heading_path") or "") == path
               or (store[p].get("heading_path") or "").startswith(path + " → ")]
    members = sorted(set(members) | set(own), key=lambda p: order.get(p, 0))
    size = {p: len(store[p].get("text") or "") for p in members}
    if sum(size.values()) <= max_chars:
        return members
    lo = hi = members.index(found["id"])
    total = size[found["id"]]
    while True:
        grew = False
        if hi + 1 < len(members) and total + size[members[hi + 1]] <= max_chars:
            hi += 1
            total += size[members[hi]]
            grew = True
        if lo > 0 and total + size[members[lo - 1]] <= max_chars:
            lo -= 1
            total += size[members[lo]]
            grew = True
        if not grew:
            break
    return sorted(set(members[lo:hi + 1]) | set(own), key=lambda p: order.get(p, 0))


def gather_context(request, plan, cfg, glossary, budget, progress=None):
    """Фрагменты для ответа: карточки упомянутых систем, затем найденное по каждому поисковому запросу (по
    очереди: первый результат каждого запроса, затем второй…), расширенное до разделов. Возвращает словарь:
    context (текст для модели), blocks (что получила модель), aspects (что нашёл каждый поиск), chars, low_found."""
    out = {"context": "", "blocks": [], "aspects": [], "chars": 0, "low_found": True}
    snap = load_kb_snapshot(cfg)
    if snap is None or not snap.parent_store:
        return out
    store, order = snap.parent_store, parent_order(snap)
    by_source = {}
    for p, pd in store.items():
        by_source.setdefault(pd.get("source", ""), []).append(p)

    blocks, used, total = [], set(), 0

    def add(ids, text, kind, anchor=None, expanded=False):
        nonlocal total
        room = budget - total
        if room < MIN_PIECE_CHARS and blocks:
            return False
        pd = store[ids[0]]
        body = focus_passage(text, room, anchor=anchor, is_table=pd.get("type") == "table")
        blocks.append({"ids": list(ids), "source": pd.get("source", ""), "path": pd.get("heading_path") or "",
                       "kind": kind, "expanded": expanded, "chars": len(body),
                       "block": render("context_block", header=_source_header(pd, body), body=body)})
        used.update(ids)
        total += len(body)
        return True

    # 1. Карточки систем, упомянутых в запросе или в разборе запроса
    materials = load_expert_materials(cfg)
    if materials is not None and materials.cards:
        mention = " ".join([request] + plan.get("systems", []))
        for card, _n in materials.mentioned_cards(mention):
            room = int(budget * CARDS_SHARE) - total
            if room < MIN_PIECE_CHARS:
                break
            ids = [p for p in card["ids"] if p in store]
            if ids:
                add(ids, materials.card_text(card, room), "card")

    # 2. Поиск по каждому запросу
    lists = []
    for i, q in enumerate(plan["queries"], 1):
        if progress:
            progress("search", i=i, n=len(plan["queries"]), query=q)
        diag = {}
        items, _labels = search_parent_child(q, cfg, k_neighbors=max(1, cfg.consult_per_query), return_items=True,
                                             glossary=glossary, diagnostics=diag)
        items = [] if isinstance(items, str) else items
        lists.append(items)
        out["aspects"].append({"query": q, "found": [it["short"] for it in items],
                               "low_conf": bool(diag.get("low_conf")) or not items})

    # 3. По очереди из каждого поиска; найденный фрагмент — до раздела целиком
    order_found, seen = [], set()
    for r in range(max((len(x) for x in lists), default=0)):
        for items in lists:
            if r < len(items) and items[r]["id"] not in seen:
                seen.add(items[r]["id"])
                order_found.append(items[r])
    for it in order_found:
        own = [p for p in it["ids"] if p in store]
        if not own or all(p in used for p in own):
            continue
        ids = (section_ids(it, by_source, store, order, cfg.consult_section_max_chars)
               if cfg.consult_expand_sections else own)
        ids = [p for p in ids if p not in used]
        expanded = len(ids) > len([p for p in own if p not in used])
        anchor = (store[it["id"]].get("text") or "")[:200]
        groups = merge_adjacent(sorted(ids, key=lambda p: order.get(p, 0)), store, order)
        stop = False
        for gids, text in sorted(groups, key=lambda g: order.get(g[0][0], 0)):
            if not add(gids, text, "section", anchor=anchor if it["id"] in gids else None, expanded=expanded):
                stop = True
                break
        if stop:
            break

    out["blocks"] = blocks
    out["context"] = "\n\n".join(b["block"] for b in blocks)
    out["chars"] = total
    out["low_found"] = not blocks or all(a["low_conf"] for a in out["aspects"])
    return out


def mark_unsupported(text):
    """Пункты раздела «📄 …» (как устроено сейчас — по документам) без ссылки [Источник: …] помечаются ❔: модель
    могла выдать догадку за содержание документов. Строки-вступления («…:»), «ничего не нашлось», код и пункты с 💡
    не помечаются. Возвращает (текст, сколько помечено)."""
    lines = (text or "").split("\n")
    in_doc, fence, n = False, False, 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        if _HEADING_RE.match(line):
            in_doc = "📄" in s
            continue
        if not in_doc or len(s) < 25 or s.endswith(":") or "💡" in s[:8] or has_citation(s) or _NOTHING_RE.search(s):
            continue
        lines[i] = line.rstrip() + UNSUPPORTED_MARK
        n += 1
    return "\n".join(lines), n


def diagrams(text):
    """Код схем Mermaid из ответа (блоки ```mermaid)."""
    return [m.group(1).strip() for m in _MERMAID_RE.finditer(text or "") if m.group(1).strip()]


def answer_consult(request, cfg, glossary=None, history=None, prev_context="", progress=None):
    """Ответ консультанта целиком: разбор запроса → поиск по аспектам → ответ модели → проверка.

    history — прошлые реплики разговора (chat.chat_history(..., answer_chars=HISTORY_ANSWER_CHARS));
    prev_context — фрагменты, которые модель видела в прошлых репликах: ссылки на них в ответе — не ошибка;
    progress(stage, **info) — ход работы для интерфейса: "plan", "search" (i, n, query), "answer" (blocks, chars).
    Возвращает словарь: answer, shown (ссылки мимо фрагментов — ⚠️, пункты 📄 без ссылки — ❔), kind, systems,
    queries, plan_ok, aspects, blocks, context, context_chars, budget, citations, citations_invalid, unsupported,
    diagrams, low_found, error, prompts (версия текстов консультанта), seconds."""
    started = time.time()
    gl = glossary if glossary is not None else load_glossary(cfg)
    ccfg = consult_cfg(cfg)
    history = list(history or [])
    if progress:
        progress("plan")
    plan = plan_request(request, history, ccfg)
    system = consult_system_prompt()

    def fixed():
        return len(system) + len(request) + sum(len(m.get("content") or "") for m in history) + 2000

    budget = context_budget(ccfg, fixed())
    while budget <= MIN_CONTEXT_CHARS * 2 and len(history) > 2:      # окно мало — сначала короче история
        history = history[2:]
        budget = context_budget(ccfg, fixed())
    ctx = gather_context(request, plan, ccfg, gl, budget, progress=progress)
    abbr = gl.reference_block(request, ctx["context"], cfg.glossary_max_entries) if cfg.glossary_in_context else ""
    if progress:
        progress("answer", blocks=len(ctx["blocks"]), chars=ctx["chars"])
    user = consult_user_content(ctx["context"], request, plan["kind"], abbr, ctx["low_found"])
    answer = ask_llm(system, user, ccfg, history=history, guard=ccfg.llm_stream)
    error = is_llm_error(answer)
    check_ctx = ctx["context"] + ("\n\n" + prev_context if prev_context else "")
    cites = [] if error else check_citations(answer, check_ctx)
    shown, unsupported = (answer, 0) if error else mark_unsupported(mark_invalid(answer, cites))
    logger.info(f"🧠 Консультант: фрагментов {len(ctx['blocks'])} ({ctx['chars']} из {budget} симв.), "
                f"ссылок мимо {sum(1 for c in cites if not c['ok'])}, без ссылки {unsupported}, "
                f"{time.time() - started:.0f} с")
    return {
        "answer": answer, "shown": shown, "kind": plan["kind"], "systems": plan["systems"],
        "queries": plan["queries"], "plan_ok": plan["ok"], "aspects": ctx["aspects"],
        "blocks": [{k: b[k] for k in ("source", "path", "kind", "expanded", "chars")} for b in ctx["blocks"]],
        "context": ctx["context"], "context_chars": ctx["chars"], "budget": budget,
        "citations": cites, "citations_invalid": [c["text"] for c in cites if not c["ok"]],
        "unsupported": unsupported, "diagrams": [] if error else diagrams(answer),
        "low_found": ctx["low_found"], "error": error, "prompts": consult_prompts_version(),
        "seconds": round(time.time() - started, 1),
    }

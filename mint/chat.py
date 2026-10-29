"""Чат: ответ по базе знаний (весь сценарий, без интерфейса) и уточняющие вопросы с учётом истории диалога.

    from mint.chat import answer_question
    res = answer_question("Сколько хранятся журналы?", cfg)      # cfg — mint.config / mint.limits
    res["answer"], res["sources"], res["citations_invalid"]

Тем же сценарием пользуются вкладка «Чат» и проверка ответов в «Проверке качества» (mint/evaluation.py).
"""

import logging
import re
from dataclasses import replace

from .audit import is_llm_error
from .citations import check_citations, mark_invalid
from .kb import kb_default_top_k, load_glossary
from .prompts import (
    chat_system_prompt, chat_user_content, condense_system, prompts_version, render, texts_all_profiles,
)
from .search import search_parent_child
from .services import TRUNCATED_MARKERS, ask_llm
from .text import norm_for_match

logger = logging.getLogger("MINT")


CHAT_HISTORY_ANSWER_CHARS = 1200   # ответ ассистента в истории обрезается: для понимания темы этого достаточно


def chat_history(messages, turns, answer_chars=CHAT_HISTORY_ANSWER_CHARS):
    """Последние turns пар «вопрос — ответ» из сохранённых сообщений чата (без источников и ошибок); ответ
    обрезается до answer_chars (консультанту прошлые ответы нужны целиком — у него свой предел)."""
    if turns <= 0:
        return []
    pairs, i = [], len(messages) - 1
    while i >= 1 and len(pairs) < turns:
        a, q = messages[i], messages[i - 1]
        if a.get("role") == "assistant" and q.get("role") == "user":
            answer = a.get("content") or ""
            if not is_llm_error(answer):
                if len(answer) > answer_chars:
                    answer = answer[:answer_chars].rsplit(" ", 1)[0] + " …"
                pairs.append((q.get("content") or "", answer))
            i -= 2
        else:
            i -= 1
    history = []
    for q, a in reversed(pairs):
        history += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    return history


def same_question(a, b):
    """Одинаковы ли вопросы с точностью до регистра, «ё» и знаков препинания («Сколько хранятся?» = «сколько
    хранятся»): такое «переписывание» вопрос не меняет."""
    def words(s):
        return re.sub(r"[^\w]+", " ", (s or "").lower().replace("ё", "е")).split()
    return words(a) == words(b)


def condense_question(history, question, cfg):
    """Уточняющий вопрос («а для второго контура?») → самостоятельный вопрос для поиска (+1 вызов LLM).
    При сбое или странном ответе возвращается исходный вопрос."""
    if not history or not (question or "").strip():
        return question
    dialog = "\n".join(
        render("condense_dialog_user" if m["role"] == "user" else "condense_dialog_assistant", text=m["content"][:600])
        for m in history
    )
    raw = ask_llm(condense_system(), render("condense_user", dialog=dialog, question=question), cfg,
                  temperature=0.0, max_tokens=300)
    if is_llm_error(raw) or any(m in raw for m in TRUNCATED_MARKERS):
        return question
    lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip()]
    q = (lines[0] if lines else "").strip().strip('"«»').strip()
    q = re.sub(r"^(?:вопрос|переписанный вопрос|самостоятельный вопрос|question|rewritten question|standalone question)"
               r"\s*:\s*", "", q, flags=re.IGNORECASE)
    if len(q) < 3 or len(q) > max(300, 3 * len(question)) or same_question(q, question):
        return question
    if q != question:
        logger.info(f"💬 Уточняющий вопрос: «{question[:80]}» → «{q[:120]}»")
    return q


def rag_answer(question, cfg, glossary, history=None, search_question=None, diagnostics=None):
    """Ответ чата: поиск по базе, справочник сокращений и ответ модели только по найденному. Возвращает (ответ,
    контекст, источники). Если вопрос переписан по истории (search_question), поиск идёт по обоим — переписанному
    и исходному: при переписывании модель может потерять термин, сокращение или номер.
    diagnostics — словарь, который поиск заполнит сигналами уверенности."""
    search_q = search_question or question
    context, sources = search_parent_child(search_q, cfg, k_neighbors=cfg.top_k, use_multi_query=cfg.use_multi_query,
                                           annotate_low_confidence=True, glossary=glossary, diagnostics=diagnostics,
                                           also_query=question if search_q != question else None)
    abbr = glossary.reference_block(search_q, context, cfg.glossary_max_entries) if cfg.glossary_in_context else ""
    answer = ask_llm(chat_system_prompt(), chat_user_content(context, question, abbr, search_q), cfg, history=history)
    return answer, context, sources


def is_no_info_answer(text):
    """Ответ — «в документах информации нет»: фраза chat_no_info любого профиля на любом из языков (ответы из
    журналов и наборов проверки качества могли быть получены в другом профиле)."""
    t = norm_for_match(text)
    return any(norm_for_match(p) in t for p in texts_all_profiles("chat_no_info"))


def answer_question(question, cfg, glossary=None, history=None):
    """Ответ чата целиком: уточнение вопроса по истории → поиск → справочник сокращений → модель → проверка ссылок.

    history — предыдущие реплики (chat_history()); cfg.top_k = 0 — глубина по размеру базы. Возвращает словарь:
      answer            — ответ модели (так он хранится в истории диалога);
      shown             — тот же ответ, ссылки мимо контекста помечены ⚠️;
      search_query      — вопрос, по которому искали, если он переписан по истории, иначе None;
      context, sources  — что получила модель и подписи найденных фрагментов;
      citations         — проверка каждой ссылки [Источник: …]; citations_invalid — тексты неверных;
      low_conf          — сработал сигнал «уверенность низкая»;
      error             — сбой модели или шлюза (ответ начинается с «❌»);
      prompts           — версия набора промптов (prompts_version())."""
    gl = glossary if glossary is not None else load_glossary(cfg)
    if not cfg.top_k:
        cfg = replace(cfg, top_k=kb_default_top_k(cfg))
    history = history or []
    search_q = condense_question(history, question, cfg) if history else question
    diag = {}
    answer, context, sources = rag_answer(question, cfg, gl, history=history, search_question=search_q,
                                          diagnostics=diag)
    error = is_llm_error(answer)
    cites = [] if error else check_citations(answer, context)
    return {
        "answer": answer, "shown": mark_invalid(answer, cites),
        "search_query": search_q if search_q != question else None,
        "context": context, "sources": sources,
        "citations": cites, "citations_invalid": [c["text"] for c in cites if not c["ok"]],
        "low_conf": bool(diag.get("low_conf")), "error": error, "prompts": prompts_version(),
    }

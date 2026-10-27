"""Поиск: гибрид векторного поиска, BM25 и реранкера (взвешенный RRF)."""

import json
import logging
import re
import time

import numpy as np
import requests

from .bm25 import (
    BM25_RAW_STOP_WORDS, BM25_STOP_WORDS, best_window, bm25_tokenize, normalize_token, passage_around,
    query_term_weights,
)
from .i18n import tr
from .kb import l2_normalize, load_bm25_for, load_glossary, load_kb_snapshot, parent_order
from .passages import focus_passage, merge_adjacent
from .prompts import low_confidence_note, paraphrase_system, render
from .services import (
    _auth_headers, cached_request, get_query_embedding, request_cache_active, rerank_scores, strip_reasoning,
)
from .text import short_path

logger = logging.getLogger("MINT")


QUERY_ANALYSIS_MAX_CHARS = 300     # длинные запросы (фрагменты документа в аудите) не разбираются на шаблоны

_COMPOSITION_PATTERNS = [
    re.compile(r'\b(?:что входит в состав|состав|из чего состоит|компоненты|архитектура|структура|модули)\b'
               r'\s+([а-яёa-z0-9_\-\s]{2,60})'),
    re.compile(r'([а-яёa-z0-9_\-\s]{2,60})\s+(?:состав|компоненты|архитектура|структура)\b'),
    # English: "components of X", "what does X consist of", "X architecture"
    re.compile(r'\b(?:composition|components|structure|architecture|modules|subsystems|parts)\s+of\s+'
               r'(?:the\s+)?([a-z0-9_\-\s]{2,60})'),
    re.compile(r'\bwhat\s+(?:does|do|is|are)\s+([a-z0-9_\-\s]{2,60}?)\s+(?:consist|made|composed)\b'),
    re.compile(r'^([a-z0-9_\-\s]{2,60})\s+(?:components|architecture|structure|modules)\b'),
]

_TERM_PATTERNS = [
    re.compile(r'\b(?:что такое|что значит|что обозначает|расшифруй|расшифровка)\b\s+([а-яёa-z0-9_\-\s]{2,60})'),
    re.compile(r'^([а-яёa-z0-9_\-\s]{2,50})\s*-\s*это\b'),
    re.compile(r'^что за\s+([а-яёa-z0-9_\-\s]{2,50})'),
    # English: "what is X", "what does X mean", "define X", "definition of X", "X stands for"
    re.compile(r'\bwhat\s+does\s+([a-z0-9_\-\s]{2,50}?)\s+(?:mean|stand\s+for)\b'),
    re.compile(r'\b(?:what\s+is|what\s+are|what\'s|define|definition\s+of|meaning\s+of)\s+(?:an?\s+|the\s+)?'
               r'([a-z0-9_\-\s]{2,60})'),
    re.compile(r'^([a-z0-9_\-\s]{2,50})\s+stands\s+for\b'),
]

_COMPOSITION_WORDS = ["состав", "компоненты", "подсистемы", "модули", "архитектура", "структура"]

_TERM_WORDS = ["определение", "термин", "глоссарий"]

_COMPOSITION_WORDS_EN = ["composition", "components", "subsystems", "modules", "architecture", "structure"]

_TERM_WORDS_EN = ["definition", "term", "glossary"]

_QUESTION_WORDS = frozenset(
    "какой какая какое какие каков какова каково каковы опиши описать расскажи покажи дай нужен нужна "
    "нужно подробно кратко "
    "which what describe explain tell show give list briefly detail details please".split())

EXPANSION_WEIGHT = 0.3    # вес слов расширения в BM25 (у слов вопроса — 1.0)

TARGET_EXTRA_WEIGHT = 0.5  # дополнительный вес слов предмета вопроса («ФИС» в «что такое ФИС»)


def _clean_target(phrase):
    words = phrase.split()
    while words and (words[0] in BM25_RAW_STOP_WORDS or words[0] in _QUESTION_WORDS):
        words = words[1:]
    while words and (words[-1] in BM25_RAW_STOP_WORDS or words[-1] in _QUESTION_WORDS):
        words = words[:-1]
    return " ".join(words)


def analyze_query(user_query):
    """Распознаёт вопросы о составе/структуре и об определениях. Возвращает план поиска:
    {"kind", "target", "terms"}: предмет вопроса (для буста точной фразы в BM25) и дополнительные слова
    для BM25 с малым весом. Векторный поиск и реранкер получают исходный вопрос без изменений."""
    plan = {"kind": None, "target": None, "terms": []}
    clean_q = (user_query or "").strip().lower()
    if not clean_q or len(clean_q) > QUERY_ANALYSIS_MAX_CHARS:
        return plan
    q_tokens = set(bm25_tokenize(clean_q))
    latin = sum(1 for c in clean_q if "a" <= c <= "z") > sum(1 for c in clean_q if "а" <= c <= "я" or c == "ё")
    for kind, patterns, words in (("composition", _COMPOSITION_PATTERNS,
                                   _COMPOSITION_WORDS_EN if latin else _COMPOSITION_WORDS),
                                  ("term", _TERM_PATTERNS, _TERM_WORDS_EN if latin else _TERM_WORDS)):
        for pattern in patterns:
            match = pattern.search(clean_q)
            if not match:
                continue
            target = _clean_target(match.group(1).strip())
            if len(target) < 2:
                continue
            terms = [(t, TARGET_EXTRA_WEIGHT) for t in dict.fromkeys(bm25_tokenize(target))
                     if t not in BM25_STOP_WORDS]
            terms += [(t, EXPANSION_WEIGHT) for t in (normalize_token(w) for w in words) if t not in q_tokens]
            plan = {"kind": kind, "target": target, "terms": terms}
            logger.info(f"🔍 Запрос «{user_query[:60]}»: {kind}, предмет «{target}»")
            return plan
    return plan


def expand_query_multi(user_query, cfg):
    """Альтернативная формулировка запроса для повышения полноты (multi-query)."""
    return cached_request("llm", (cfg.llm_model, user_query), lambda: _expand_query_multi(user_query, cfg))


def _expand_query_multi(user_query, cfg):
    if not user_query or len(user_query) > 1200 or not cfg.llm_base or not cfg.llm_model:
        return [user_query]
    try:
        payload = {
            "model": cfg.llm_model,
            "messages": [
                {"role": "system", "content": paraphrase_system()},
                {"role": "user", "content": render("paraphrase_user", query=user_query)},
            ],
            "temperature": 0.25,
            "max_tokens": 120,
        }
        resp = requests.post(
            f"{cfg.llm_base}/chat/completions",
            headers=_auth_headers(cfg.llm_api_key),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            verify=cfg.tls_verify,
            timeout=25,
        )
        if resp.status_code == 200:
            content = strip_reasoning(resp.json()["choices"][0]["message"]["content"] or "").lstrip("-•* ").strip()
            if len(content) > 8 and content.lower() != user_query.lower():
                logger.info(f"🔍 Multi-query variant: '{content[:80]}...'")
                return [user_query, content]
    except Exception as e:
        logger.warning(f"Multi-query expansion skipped: {str(e)[:100]}")
    return [user_query]


def inner_headings(text, limit=8):
    """Заголовки внутри текста фрагмента (строки «## …»): фрагмент часто охватывает несколько подразделов."""
    out = []
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith("#"):
            h = s.lstrip("#").strip()
            if h and h not in out:
                out.append(h)
    return out[:limit]


def section_at(text, anchor):
    """Раздел, в котором стоит найденное место внутри фрагмента: последний заголовок «#…» перед anchor (текстом
    найденного child) или в его первой строке. None — место не найдено или заголовков перед ним нет."""
    probe = (anchor or "").strip()[:80]
    pos = text.find(probe) if probe else -1
    if pos < 0:
        return None
    last = None
    for line in text[:pos + len(probe.split("\n", 1)[0])].splitlines():
        h = line.strip()
        if h.startswith("#") and h.lstrip("#").strip():
            last = h.lstrip("#").strip()
    return last


def _source_header(pd, body=None):
    """Заголовок фрагмента для LLM: файл | раздел в начале | разделы внутри | таблица | страница (разметка — в
    промптах: context_section_start, context_inner_sections, context_page).
    body — текст, который реально уходит модели (после обрезки); разделы внутри берутся из него."""
    parts = [pd.get("source", "") or ""]
    path = pd.get("heading_path") or ""
    if path:
        parts.append(render("context_section_start", path=path))
    last = path.split(" → ")[-1].strip() if path else ""
    inner = [h for h in inner_headings(pd.get("text") if body is None else body) if h != last]
    if inner and pd.get("type") != "table":
        parts.append(render("context_inner_sections", sections="; ".join(inner)))
    if pd.get("type") == "table" and pd.get("section"):
        parts.append(pd["section"])
    if pd.get("page_reliable") and pd.get("page"):
        parts.append(render("context_page", page=pd["page"]))
    return " | ".join(p for p in parts if p)


def _rerank_header(pd, cfg):
    """Имя файла, раздел и таблица — в начало текста для реранкера (если включено)."""
    if not cfg.rerank_with_meta:
        return ""
    head = pd.get("source", "") or ""
    if pd.get("heading_path"):
        head += f" | {short_path(pd['heading_path'], 140)}"
    if pd.get("type") == "table" and pd.get("section"):
        head += f" | {pd['section']}"
    return head


def rerank_document(pd, cfg, term_weights, child_text=None):
    """Текст кандидата для реранкера длиной до rerank_doc_max_chars: не начало parent-фрагмента, а его самая
    релевантная часть — найденный векторным поиском child с окружением или окно с наибольшей плотностью
    слов запроса. Возвращает (текст, откуда_фрагмент)."""
    text = str(pd.get("text") or "")
    head = _rerank_header(pd, cfg)
    size = max(150, cfg.rerank_doc_max_chars - (len(head) + 1 if head else 0))
    passage, origin = None, "начало"
    if len(text) <= size:
        passage, origin = text, "целиком"
    elif child_text:
        passage = passage_around(text, child_text, size)
        if passage is None:            # child таблицы — не подстрока parent; берём его как есть
            passage = child_text[:size]
        origin = "child"
    if passage is None:
        passage, score = best_window(text, term_weights, size)
        origin = "окно по словам" if score > 0 else "начало"
    passage = passage.strip()
    return (f"{head}\n{passage}" if head else passage), origin


def _query_vector(text, cfg, dim):
    """Вектор запроса (с префиксом-инструкцией модели): (массив 1×dim, "ok") или (None, "unavailable" | "dim")."""
    vec = get_query_embedding(f"{cfg.embed_query_prefix}{text}", cfg)
    if not (isinstance(vec, list) and vec and not isinstance(vec[0], (dict, list))):
        return None, "unavailable"
    try:
        arr = l2_normalize(np.array([vec]).astype("float32"))
    except Exception:
        return None, "unavailable"
    if arr.shape[1] != dim:
        logger.error(
            f"Размерность вектора запроса ({arr.shape[1]}) не совпадает с базой ({dim}): база построена другой "
            "моделью эмбеддингов. Векторный поиск отключён до переиндексации — работаем по BM25."
        )
        return None, "dim"
    return arr, "ok"


def is_low_confidence(best_rerank, lexical_cov, lists_agree, rerank_threshold, lexical_threshold):
    """«Уверенность низкая»: с реранкером — его лучший балл ниже порога; без реранкера (best_rerank None) —
    доля слов вопроса в контексте ниже порога и dense с BM25 не сошлись. Общая для поиска и eval_search.py."""
    if best_rerank is not None:
        return best_rerank < rerank_threshold
    return lexical_cov < lexical_threshold and not lists_agree


def search_parent_child(user_query, cfg, k_neighbors=4, attempts=0, use_multi_query=False,
                        annotate_low_confidence=False, return_items=False, glossary=None, diagnostics=None,
                        also_query=None):
    """
    Hybrid Parent-Child RAG + мягкий реранк (слияние RRF). Векторный поиск и реранкер получают исходный
    вопрос; BM25 — вопрос плюс расшифровки сокращений и слова расширения с малым весом.
    Если эмбеддинги недоступны — работает только BM25.
    diagnostics — словарь, который функция заполнит сигналами уверенности (для скрипта оценки).
    also_query — второй вопрос, по которому ищется наравне с первым: в чате это вопрос пользователя как он есть,
    когда первый переписан по истории диалога. Кандидаты обоих сливаются, реранкер берёт лучший из двух баллов —
    если при переписывании потерялись термин, сокращение или номер, нужный фрагмент найдётся по исходному вопросу.
    """
    gl = glossary if glossary is not None else load_glossary(cfg)
    search_query = user_query or ""
    alternates = []          # (вопрос, вес): вторая формулировка multi-query и исходный вопрос пользователя
    if use_multi_query and attempts == 0:
        variants = expand_query_multi(search_query, cfg)
        if len(variants) > 1:
            alternates.append((variants[1], cfg.multi_query_alt_weight))
    if also_query and attempts == 0 and also_query.strip() and also_query.strip() != search_query.strip():
        also_query = also_query[:cfg.max_query_chars]
        alternates.append((also_query, 1.0))
    else:
        also_query = None

    if len(search_query) > cfg.max_query_chars:
        logger.warning(f"⚠️ КРИТИЧЕСКИЙ ОБЪЕМ: ({len(search_query)} симв.). Отсечение.")
        search_query = search_query[:cfg.max_query_chars]

    if attempts >= 3:
        logger.error("🛑 Слишком глубокое дробление запроса.")
        return tr("Временный сбой поиска. Проводится автономный анализ текста."), []

    if len(search_query) > cfg.cascade_split_chars:
        mid = len(search_query) // 2
        split_idx = search_query.find(". ", mid)
        if split_idx == -1:
            split_idx = mid
        sub_k = max(2, k_neighbors // 2)
        c1, s1 = search_parent_child(search_query[:split_idx], cfg, sub_k, attempts + 1,
                                     return_items=return_items, glossary=gl)
        c2, s2 = search_parent_child(search_query[split_idx:], cfg, sub_k, attempts + 1,
                                     return_items=return_items, glossary=gl)
        if return_items:
            merged = {}
            for chunk in (c1, c2):
                if not isinstance(chunk, str):
                    for it in chunk:
                        merged[it["id"]] = it
            return list(merged.values()), list(dict.fromkeys(s1 + s2))
        return f"{c1}\n\n{c2}", list(dict.fromkeys(s1 + s2))

    snap = load_kb_snapshot(cfg)
    if snap is None or snap.index.ntotal == 0:
        return tr("База знаний пуста."), []
    index, child_metadata, parent_store = snap.index, snap.metadata, snap.parent_store

    # --- Векторный поиск (до 3 попыток получить эмбеддинг; иначе — только BM25) ---
    query_np = None
    for attempt in range(3):
        query_np, why = _query_vector(search_query, cfg, index.d)
        if query_np is not None or why == "dim" or request_cache_active():
            break  # при другой размерности повторять бессмысленно; в кэше оценки попытки уже сделаны
        if attempt < 2:
            time.sleep(2.0)
    if query_np is None:
        logger.warning("⚠️ Эмбеддинг запроса недоступен — поиск только по BM25.")

    best_child = {}   # parent_id → текст лучшего найденного child (для реранкера)

    def _parents_from_indices(idx_row):
        order, seen_ids = [], set()
        for idx in idx_row:
            if idx == -1 or idx >= len(child_metadata):
                continue
            p = child_metadata[idx]["parent_id"]
            if p not in seen_ids and p in parent_store:
                seen_ids.add(p)
                order.append(p)
                if p not in best_child and child_metadata[idx].get("text"):
                    best_child[p] = child_metadata[idx]["text"]
        return order

    k_dense = min(cfg.initial_k, index.ntotal)
    dense_order = []
    if query_np is not None:
        _distances, indices = index.search(query_np, k=k_dense)
        main_order = _parents_from_indices(indices[0])
        dense_order = main_order
        # Вторые формулировки (multi-query, исходный вопрос): их кандидаты из FAISS тоже сливаются (RRF)
        if alternates:
            fused_dense = {}
            for r, p in enumerate(main_order, 1):
                fused_dense[p] = fused_dense.get(p, 0.0) + 1.0 / (cfg.rrf_constant + r)
            for alt_q, weight in alternates:
                alt_np, _ = _query_vector(alt_q, cfg, index.d)
                if alt_np is None:
                    logger.warning("Эмбеддинг второй формулировки вопроса недоступен — поиск без неё.")
                    continue
                _, alt_indices = index.search(alt_np, k=k_dense)
                alt_order = _parents_from_indices(alt_indices[0])
                for r, p in enumerate(alt_order, 1):
                    fused_dense[p] = fused_dense.get(p, 0.0) + weight / (cfg.rrf_constant + r)
            dense_order = sorted(fused_dense, key=fused_dense.get, reverse=True)[:cfg.initial_k]
            logger.info(f"🔍 Несколько формулировок, dense: основная={len(main_order)} "
                        f"вторых={len(alternates)} объединено={len(dense_order)}")

    dense_candidates = [(p, parent_store[p]) for p in dense_order]

    # --- BM25: вопрос + расшифровки сокращений + слова расширения (малый вес); фраза — предмет вопроса ---
    plan = analyze_query(search_query)
    extra_terms = gl.bm25_terms(search_query) + plan["terms"]
    sparse_candidates = []
    bm25_engine, bm25_parent_ids = load_bm25_for(cfg, parent_store)
    if bm25_engine is not None:
        bm25_scores = bm25_engine.get_scores(search_query, extra_terms=extra_terms, phrase=plan["target"])
        for alt_q, weight in alternates:
            try:
                alt_scores = bm25_engine.get_scores(alt_q, extra_terms=gl.bm25_terms(alt_q))
                bm25_scores = np.maximum(bm25_scores, alt_scores * weight)
            except Exception:
                pass
        top_bm25 = np.argsort(bm25_scores)[::-1][:cfg.bm25_top_k]
        sparse_candidates = [
            (bm25_parent_ids[i], parent_store[bm25_parent_ids[i]])
            for i in top_bm25 if bm25_scores[i] > 0 and bm25_parent_ids[i] in parent_store
        ]

    logger.info(f"🔎 ГИБРИДНЫЙ ПОИСК: '{search_query[:50]}...'"
                + (f" и '{also_query[:50]}...'" if also_query else "")
                + f" (dense {len(dense_candidates)}, BM25 {len(sparse_candidates)})")

    # --- 1. Базовые ранги dense и BM25 (по parent_id) ---
    dense_rank = {p_id: r for r, (p_id, _) in enumerate(dense_candidates, 1)}
    sparse_rank = {p_id: r for r, (p_id, _) in enumerate(sparse_candidates, 1)}
    weights = cfg.rrf_weights

    def _rrf_term(rank, weight):
        return weight / (cfg.rrf_constant + rank) if rank else 0.0

    # канал с весом 0 отключён: его кандидаты не участвуют в отборе
    pool = (set(dense_rank) if weights["dense"] > 0 else set()) | (set(sparse_rank) if weights["bm25"] > 0 else set())
    base_scores = {
        p_id: _rrf_term(dense_rank.get(p_id), weights["dense"]) + _rrf_term(sparse_rank.get(p_id), weights["bm25"])
        for p_id in pool
    }
    base_order = sorted(base_scores, key=base_scores.get, reverse=True)[:cfg.rerank_top_k]
    if not base_order:
        if diagnostics is not None:
            diagnostics.update({"low_conf": True, "best_rerank": None, "lexical_cov": 0.0, "lists_agree": False,
                                "dense": query_np is not None, "reranked": 0})
        return tr("В базе знаний ничего не найдено."), []

    # --- 2. Реранкер как один из голосов (необязательный): ВСЕ кандидаты, по релевантному фрагменту ---
    rerank_query = gl.enrich_query(search_query[:cfg.rerank_query_max_chars], max_chars=cfg.rerank_query_max_chars)
    rerank_ids, rerank_docs = [], []
    # веса слов вопроса: реранкеру и обрезке длинного фрагмента — самое релевантное место, а не начало
    term_weights = query_term_weights(search_query + (" " + also_query if also_query else ""), extra_terms,
                                      idf=bm25_engine.idf if bm25_engine is not None else None)
    if cfg.rerank_enabled:
        for p_id in base_order:
            doc, _origin = rerank_document(parent_store[p_id], cfg, term_weights, best_child.get(p_id))
            if not doc.strip():
                continue
            rerank_ids.append(p_id)
            rerank_docs.append(doc)

    raw_rerank = {}
    rerank_queries = [rerank_query] + ([gl.enrich_query(also_query[:cfg.rerank_query_max_chars],
                                                         max_chars=cfg.rerank_query_max_chars)] if also_query else [])
    for rq in rerank_queries:           # с исходным вопросом — лучший балл пары из двух
        scores = rerank_scores(rq, rerank_docs, cfg) if rerank_docs else None
        if scores:
            for p_id, s in zip(rerank_ids, scores):
                if s is not None:
                    raw_rerank[p_id] = max(s, raw_rerank.get(p_id, s))

    # Голос реранкера учитывается, только если он уверен (балл >= min_rerank_score).
    voting = sorted(((p, s) for p, s in raw_rerank.items() if s >= cfg.min_rerank_score),
                    key=lambda kv: kv[1], reverse=True)
    rerank_rank = {p_id: r for r, (p_id, _) in enumerate(voting, 1)}

    final_scores = {p_id: base_scores[p_id] + _rrf_term(rerank_rank.get(p_id), weights["rerank"])
                    for p_id in base_order}
    ranked_ids = sorted(final_scores, key=final_scores.get, reverse=True)

    # --- 3. Отбор top-k с дедупликацией ---
    selected, seen_keys, deferred, table_count = [], set(), [], {}
    for p_id in ranked_ids:
        if len(selected) >= k_neighbors:
            break
        pd = parent_store[p_id]
        key = (pd.get("source", ""), (pd.get("text") or "")[:80])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        # мягкий лимит: части одной таблицы не должны вытеснять остальные документы
        if cfg.max_table_parts and pd.get("type") == "table":
            table_key = (pd.get("source", ""), (pd.get("section") or "").split(" (часть")[0])
            if table_count.get(table_key, 0) >= cfg.max_table_parts:
                deferred.append(p_id)
                continue
            table_count[table_key] = table_count.get(table_key, 0) + 1
        selected.append(p_id)
    for p_id in deferred:
        if len(selected) >= k_neighbors:
            break
        selected.append(p_id)

    # --- 4. Контекст: соседние фрагменты склеиваются; длинный — обрезается вокруг найденного места ---
    rank_in = {p: i for i, p in enumerate(selected)}
    parents_out, sources_out, items = [], [], []
    for ids, text in merge_adjacent(selected, parent_store, parent_order(snap)):
        p_id = min(ids, key=rank_in.get)             # самый релевантный участник группы
        pd = parent_store[ids[0]]                     # первый по тексту: его раздел — в начале блока
        if len(ids) > 1:
            pd = {**pd, "text": text}
        src = pd.get("source", "")
        path = pd.get("heading_path") or ""
        anchor = best_child.get(p_id) or next((best_child[p] for p in ids if p in best_child), None)
        body = focus_passage(text, cfg.smart_truncate_chars * len(ids), anchor=anchor, term_weights=term_weights,
                             is_table=pd.get("type") == "table")
        block = render("context_block", header=_source_header(pd, body), body=body)
        parents_out.append(block)
        # человеку — раздел, где найдено место (модели в заголовке блока — раздел в начале и разделы внутри)
        label_path = section_at(text, anchor) or parent_store[p_id].get("heading_path") or path
        short = f"📄 {src}" + (f" › {short_path(label_path)}" if label_path else "")
        label = short
        if cfg.show_source_details:
            d_rank = dense_rank.get(p_id)
            b_rank = sparse_rank.get(p_id)
            parts = [
                tr("итог {v:.4f}", v=final_scores[p_id]),
                f"dense #{d_rank}" if d_rank else "dense —",
                f"BM25 #{b_rank}" if b_rank else "BM25 —",
            ]
            if p_id in raw_rerank:
                r_score = raw_rerank[p_id]
                parts.append(f"rerank {r_score:.2f} ✓" if p_id in rerank_rank else tr("rerank {r_score:.2f} (не учтён)", r_score=r_score))
            else:
                parts.append("rerank —")
            if pd.get("type") == "table":
                parts.append(tr("таблица"))
            if len(ids) > 1:
                parts.append(tr("склеено соседних фрагментов: {n}", n=len(ids)))
            label += " (" + " · ".join(parts) + ")"
        elif p_id in raw_rerank:
            label += f" (rerank: {raw_rerank[p_id]:.2f})"
        sources_out.append(label)
        items.append({"id": p_id, "ids": list(ids), "source": src, "path": path, "block": block, "short": short,
                      "label": label})

    # --- 5. Сигнал уверенности ---
    # Есть баллы реранкера — решает он: он оценивает смысл пары «вопрос — фрагмент» и лучше всего отличает
    # вопросы, ответа на которые в базе нет. Доля слов вопроса в контексте и согласие dense с BM25 на таких
    # вопросах обычно высокие (слова темы в базе есть, ответа — нет), поэтому в паре с реранкером они гасили
    # сигнал. Без реранкера — эти два признака вместе.
    best_rerank = max(raw_rerank.values()) if raw_rerank else None
    ctx_terms = set(bm25_tokenize("\n".join(parents_out)))

    def _coverage(q):
        terms = {t for t in bm25_tokenize(q) if t not in BM25_STOP_WORDS and len(t) >= 3}
        return (len(terms & ctx_terms) / len(terms)) if terms else 1.0

    lexical_cov = max(_coverage(q) for q in [search_query] + ([also_query] if also_query else []))
    top_dense = {p for p, r in dense_rank.items() if r <= cfg.low_conf_agree_top}
    top_sparse = {p for p, r in sparse_rank.items() if r <= cfg.low_conf_agree_top}
    lists_agree = bool((top_dense & top_sparse) & set(selected))
    low_conf = is_low_confidence(best_rerank, lexical_cov, lists_agree, cfg.low_conf_rerank, cfg.low_conf_lexical)
    logger.info(f"📊 conf: best_rerank={best_rerank} lexical={lexical_cov:.2f} agree={lists_agree} "
                f"low={low_conf} selected={len(selected)} dense={'on' if query_np is not None else 'off'}")
    if diagnostics is not None:
        diagnostics.update({"low_conf": low_conf, "best_rerank": best_rerank, "lexical_cov": lexical_cov,
                            "lists_agree": lists_agree, "dense": query_np is not None, "reranked": len(raw_rerank)})

    if return_items:
        return items, sources_out

    context = "\n\n".join(parents_out)
    if low_conf and annotate_low_confidence:
        context = low_confidence_note() + context
    return context, sources_out

"""Обращения к сервисам: LLM, эмбеддинги, реранкер (OpenAI-совместимые API)."""

import contextvars
import json
import logging
import random
import re
import threading
import time
from contextlib import contextmanager

import requests

from .cache import _process_cache
from .config import FALLBACK_LIMITS, extra_body
from .i18n import tr

logger = logging.getLogger("MINT")


_TLS_STATE = {"system_store": None}


def apply_tls_policy(cfg):
    """Доверять корпоративным сертификатам из хранилища ОС, если файл CA_BUNDLE_PATH не найден.

    requests по умолчанию проверяет сертификаты по своему набору (certifi), где нет внутреннего CA компании.
    В Linux MINT берёт системный файл /etc/ssl/certs/ca-certificates.crt; в Windows такого файла нет, и
    вместо него подключается хранилище сертификатов Windows через пакет truststore (если установлен).
    Действует на весь процесс, выполняется один раз. Возвращает описание для панели и самопроверки."""
    if cfg.ssl_insecure:
        return tr("проверка сертификатов отключена (SSL_INSECURE=1)")
    if cfg.tls_verify is not True:
        return tr("сертификаты: {tls_verify}", tls_verify=cfg.tls_verify)
    if _TLS_STATE["system_store"] is None:
        try:
            import truststore
            truststore.inject_into_ssl()
            _TLS_STATE["system_store"] = True
            logger.info("TLS: сертификаты проверяются по хранилищу ОС (truststore).")
        except Exception:
            _TLS_STATE["system_store"] = False
    if _TLS_STATE["system_store"]:
        return tr("сертификаты: хранилище ОС (truststore)")
    return (tr("сертификаты: набор certifi — внутренний CA компании в нём не найдётся; укажите CA_BUNDLE_PATH "
               "или установите пакет truststore"))


def _auth_headers(key):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _parse_embedding_json(res_json):
    if isinstance(res_json, dict):
        data = res_json.get("data")
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict) and "embedding" in first:
                return first["embedding"]
            if isinstance(first, list):
                return first
        if "embedding" in res_json:
            return res_json["embedding"]
    if isinstance(res_json, list) and res_json:
        if isinstance(res_json[0], dict) and "embedding" in res_json[0]:
            return res_json[0]["embedding"]
        if isinstance(res_json[0], list):
            return res_json[0]
        return res_json
    return None


def _embed_input(text, cfg):
    """Не отправляем модели эмбеддингов больше, чем она принимает (лимит рассчитан по её окну)."""
    text = text or ""
    if cfg.embed_input_max_chars and len(text) > cfg.embed_input_max_chars:
        return text[:cfg.embed_input_max_chars]
    return text


_REQUEST_CACHE = contextvars.ContextVar("mint_request_cache", default=None)


@contextmanager
def request_cache():
    """Одинаковые запросы к эмбеддингам, реранкеру и перефразированию внутри блока уходят один раз, повторы —
    из памяти. Нужен оценке поиска: одни и те же вопросы прогоняются в нескольких конфигурациях. Действует
    только в текущем потоке (сеансе Streamlit), другие пользователи его не видят. Возвращает счётчики запросов."""
    store = {"embed_calls": 0, "embed_failed": 0, "rerank_calls": 0, "rerank_failed": 0, "llm_calls": 0}
    token = _REQUEST_CACHE.set({"stats": store, "values": {}})
    try:
        yield store
    finally:
        _REQUEST_CACHE.reset(token)


def request_cache_active():
    return _REQUEST_CACHE.get() is not None


def cached_request(kind, key, fn, attempts=1):
    """fn() через кэш request_cache(), если он включён; неудача (None) повторяется до attempts раз и тоже
    запоминается — повторять её в других конфигурациях бессмысленно."""
    cache = _REQUEST_CACHE.get()
    if cache is None:
        return fn()
    values, stats = cache["values"], cache["stats"]
    if (kind, key) not in values:
        value = None
        for attempt in range(attempts):
            stats[f"{kind}_calls"] = stats.get(f"{kind}_calls", 0) + 1
            value = fn()
            if value is not None:
                break
            if attempt + 1 < attempts:
                time.sleep(1.0 * (attempt + 1))
        if value is None:
            stats[f"{kind}_failed"] = stats.get(f"{kind}_failed", 0) + 1
        values[(kind, key)] = value
    return values[(kind, key)]


def get_query_embedding(text, cfg):
    return cached_request("embed", (cfg.embed_url, cfg.embed_model, text),
                          lambda: _get_query_embedding(text, cfg), attempts=3)


def _get_query_embedding(text, cfg):
    if not cfg.embed_url:
        return None
    try:
        response = requests.post(
            cfg.embed_url,
            json={"input": _embed_input(text, cfg), "model": cfg.embed_model},
            headers=_auth_headers(cfg.embed_key),
            verify=cfg.tls_verify,
            timeout=30,
        )
        if response.status_code in (429, 502, 503, 504):
            return None
        if response.status_code == 200:
            return _parse_embedding_json(response.json())
        return None
    except Exception:
        return None


def _embeddings_in_input_order(data_field):
    """Векторы из поля data в порядке входных текстов. По спецификации OpenAI у каждого элемента есть
    index — номер входного текста; порядок самих элементов API не гарантирует (шлюзы, собирающие ответ из
    параллельных запросов, его меняют). Без index — порядок как в ответе."""
    n = len(data_field)
    idx = [item.get("index") if isinstance(item, dict) else None for item in data_field]
    out = [None] * n
    if all(isinstance(i, int) and 0 <= i < n for i in idx) and len(set(idx)) == n:
        for i, item in zip(idx, data_field):
            out[i] = item.get("embedding")
        return out
    return [item.get("embedding") if isinstance(item, dict) else None for item in data_field]


def get_query_embeddings_batch(texts, cfg, batch_size=None):
    if not texts:
        return []
    batch_size = max(1, int(batch_size or cfg.embed_batch_size))
    result_vectors = [None] * len(texts)

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        batch_indices = list(range(start, min(start + batch_size, len(texts))))
        try:
            response = requests.post(
                cfg.embed_url,
                json={"input": [_embed_input(t, cfg) for t in batch], "model": cfg.embed_model},
                headers=_auth_headers(cfg.embed_key),
                verify=cfg.tls_verify,
                timeout=60,
            )
            if response.status_code == 200:
                res_json = response.json()
                data_field = res_json.get("data") if isinstance(res_json, dict) else None
                if isinstance(data_field, list) and len(data_field) == len(batch):
                    for bidx, emb in zip(batch_indices, _embeddings_in_input_order(data_field)):
                        if emb is not None:
                            result_vectors[bidx] = emb
                    continue
            for bidx, b_text in zip(batch_indices, batch):
                vec = get_query_embedding(b_text, cfg)
                if vec is not None:
                    result_vectors[bidx] = vec
        except Exception:
            for bidx, b_text in zip(batch_indices, batch):
                vec = get_query_embedding(b_text, cfg)
                if vec is not None:
                    result_vectors[bidx] = vec

    return result_vectors


def _rerank_request(query, docs, cfg):
    """Один запрос к реранкеру. Понимает ответы {"results": [{"index", "relevance_score"}]} и [{"index", "score"}]."""
    return cached_request("rerank", (cfg.rerank_url, cfg.rerank_model, query, tuple(docs)),
                          lambda: _rerank_request_uncached(query, docs, cfg))


def _rerank_request_uncached(query, docs, cfg):
    try:
        response = requests.post(
            cfg.rerank_url,
            headers=_auth_headers(cfg.rerank_key),
            json={"model": cfg.rerank_model, "query": query, "documents": docs},
            timeout=cfg.request_timeout,
            verify=cfg.tls_verify,
        )
        if response.status_code != 200:
            logger.error(
                f"Rerank HTTP {response.status_code}: {(response.text or '')[:400]} | "
                f"docs={len(docs)} chars={sum(len(d) for d in docs)} qlen={len(query)}"
            )
            return None
        data = response.json()
        results = data.get("results", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        scores = [None] * len(docs)
        for item in results:
            if not isinstance(item, dict):
                continue
            oi = item.get("index", -1)
            score = item.get("relevance_score", item.get("score", 0))
            if isinstance(oi, int) and 0 <= oi < len(docs):
                scores[oi] = float(score or 0)
        return scores
    except Exception as e:
        logger.warning(f"⚠️ Реранкер недоступен ({str(e)[:120]}). Работаем на dense+BM25.")
        return None


def rerank_scores(query, docs, cfg):
    """Баллы реранкера по документам (None для неоценённых) или None, если реранкер не задан/недоступен.
    Документы, не поместившиеся в один запрос (rerank_max_docs, rerank_char_budget — ограничения шлюза),
    уходят следующими запросами: реранкер оценивает каждую пару «запрос — документ» независимо,
    поэтому баллы из разных запросов сравнимы."""
    if not cfg.rerank_url or not docs:
        return None
    batches, cur, total = [], [], 0
    max_docs = max(1, int(cfg.rerank_max_docs))
    for i, d in enumerate(docs):
        if cur and (len(cur) >= max_docs or total + len(d) > cfg.rerank_char_budget):
            batches.append(cur)
            cur, total = [], 0
        cur.append(i)
        total += len(d)
    if cur:
        batches.append(cur)
    scores, any_ok = [None] * len(docs), False
    for batch in batches:
        res = _rerank_request(query, [docs[i] for i in batch], cfg)
        if res is None:
            if any_ok:   # часть кандидатов с баллами, часть без — порядок исказится; не используем ничего
                logger.warning("⚠️ Реранкер ответил ошибкой на часть запросов — его баллы в этом поиске не учтены.")
            return None
        any_ok = True
        for i, sc in zip(batch, res):
            scores[i] = sc
    if len(batches) > 1:
        logger.info(f"🎯 Реранк: {len(docs)} док. в {len(batches)} запросах")
    return scores if any_ok else None


def probe_reranker(cfg):
    """(код, описание): код None — реранкер не подключён, 0 — нет связи, иначе HTTP-код."""
    if not cfg.rerank_url:
        return None, tr("не подключён (необязательно)")
    try:
        res = requests.post(
            cfg.rerank_url,
            json={"model": cfg.rerank_model, "query": "проверка связи",
                  "documents": ["тестовый документ для проверки связи"]},
            headers=_auth_headers(cfg.rerank_key),
            timeout=5,
            verify=cfg.tls_verify,
        )
        code = int(res.status_code)
        return code, (tr("доступен") if code == 200 else describe_http_status(code, cfg.rerank_url))
    except Exception as e:
        return 0, describe_request_error(e, cfg.rerank_url)


_REASONING_BLOCK_RE = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE)

_REASONING_OPEN_RE = re.compile(r"^\s*<(think|thinking|reasoning)>", re.IGNORECASE)

_REASONING_CLOSE_RE = re.compile(r"</(think|thinking|reasoning)>", re.IGNORECASE)


def strip_reasoning(text):
    """Убирает рассуждения моделей вида DeepSeek-R1 / Qwen3 (<think>…</think>), если шлюз отдаёт их в тексте
    ответа. Иначе строки рассуждений («- может быть…») попадают в замечания аудита и ломают разбор JSON."""
    if not text:
        return ""
    t = _REASONING_BLOCK_RE.sub("", text)
    closes = list(_REASONING_CLOSE_RE.finditer(t))
    if closes:                       # открывающий тег съел шаблон чата — остался только закрывающий
        t = t[closes[-1].end():]
    elif _REASONING_OPEN_RE.match(t):  # рассуждения не закончились (ответ обрезан внутри них)
        t = ""
    return t.strip()


# Выключить рассуждения перед ответом — стандартный параметр шаблона чата в vLLM и SGLang: Qwen 3, GLM —
# enable_thinking, DeepSeek V3.1+ — thinking. Шаблоны других моделей лишние ключи не замечают; шлюз, который
# таких параметров не знает и отклоняет запрос, получает его повторно без них (и MINT это запоминает).
NO_REASONING_PARAMS = {"chat_template_kwargs": {"enable_thinking": False, "thinking": False}}
# Включатель рассуждений — для аудита с рассуждениями (audit_reasoning, reasoning_on): у части моделей (DeepSeek на
# vLLM) рассуждения по умолчанию выключены, у других (Qwen) включены — включатель делает одинаково.
REASONING_PARAMS = {"chat_template_kwargs": {"enable_thinking": True, "thinking": True}}
_REASONING_ON = contextvars.ContextVar("mint_reasoning_on", default=False)


@contextmanager
def reasoning_on(enabled=True):
    """Запросы внутри блока — с включателем рассуждений (если не выключены настройкой llm_no_reasoning и шлюз
    принимает параметр). Контекст копируется в потоки parallel_map."""
    token = _REASONING_ON.set(bool(enabled))
    try:
        yield
    finally:
        _REASONING_ON.reset(token)


def reasoning_blocked_by_extra_body(cfg):
    """Свои параметры запроса (llm_extra_body) выключают рассуждения — они важнее включателя."""
    kwargs = extra_body(cfg).get("chat_template_kwargs")
    return isinstance(kwargs, dict) and any(kwargs.get(k) is False for k in ("enable_thinking", "thinking"))

_UNKNOWN_PARAM_WORDS = ("chat_template_kwargs", "enable_thinking", "thinking", "unrecognized", "unknown",
                        "not permitted", "extra_forbidden", "additional properties", "unexpected")


def _gateway(cfg, model):
    """Что MINT узнал о шлюзе и модели за время работы процесса: reasoning — модель присылала рассуждения,
    no_switch — шлюз не принимает параметр выключения рассуждений."""
    return _process_cache().setdefault("llm_gateway", {}).setdefault((cfg.llm_base, model), {})


def model_reasons(cfg, model=None):
    """Модель присылала рассуждения перед ответом (замечено в ответах шлюза за время работы MINT)."""
    return bool(_gateway(cfg, model or cfg.llm_model).get("reasoning"))


def _merge_params(*parts):
    out = {}
    for part in parts:
        for k, v in (part or {}).items():
            out[k] = {**out[k], **v} if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _request_extras(cfg, model):
    """Дополнительные поля запроса: выключатель рассуждений (если включён и шлюз его принимает) и свои
    параметры llm_extra_body (они важнее)."""
    switch = (NO_REASONING_PARAMS if cfg.llm_no_reasoning else REASONING_PARAMS if _REASONING_ON.get() else {})
    if _gateway(cfg, model).get("no_switch"):
        switch = {}
    user = {k: v for k, v in extra_body(cfg).items() if k not in ("model", "messages", "stream")}
    return _merge_params(switch, user), bool(switch)


def _note_reasoning(cfg, model, message, usage, raw_content, content):
    """Запоминает, что модель рассуждает: поле reasoning_content / reasoning, токены рассуждений, <think>."""
    details = (usage or {}).get("completion_tokens_details") or {}
    if (message.get("reasoning_content") or message.get("reasoning") or (details.get("reasoning_tokens") or 0) > 0
            or len(raw_content.strip()) > len(content)):
        state = _gateway(cfg, model)
        if not state.get("reasoning"):
            logger.info(f"Модель '{model}' присылает рассуждения перед ответом")
        state["reasoning"] = True


def timeout_message(cfg, model, seconds):
    """Сообщение о таймауте: что поменять в настройках."""
    msg = tr("❌ [ТАЙМАУТ MINT]: модель не ответила за {llm_timeout} с. Увеличьте «Таймаут ответа LLM» в "
             "«Экспертных настройках» (раздел «Языковая модель»).", llm_timeout=seconds)
    if not cfg.llm_no_reasoning and model_reasons(cfg, model):
        msg += " " + tr("Модель рассуждает перед ответом — включите там же «Выключить рассуждения модели».")
    elif not cfg.llm_no_reasoning:
        msg += " " + tr("Если модель рассуждает перед ответом — включите там же «Выключить рассуждения модели».")
    return msg


# Пометка обрезанного ответа на обоих языках интерфейса (см. ask_llm)
TRUNCATED_MARKERS = ("⚠️ Ответ обрезан", "⚠️ Answer truncated")


# Ответ потоком (аудит): MINT сам обрывает ответ, который вышел далеко за лимит длины (шлюз может max_tokens не
# соблюдать) или зациклился (средние модели на длинном ответе начинают повторять одни и те же строки).
STREAM_CHARS_PER_TOKEN = 5      # потолок ответа в символах = max_tokens × 5 (с запасом: символов на токен меньше)
STREAM_CHECK_EVERY = 1500       # проверка длины и повторов — через столько новых символов
LOOP_WINDOW, LOOP_REPEATS = 40, 3   # строка, повторённая 3 раза среди последних 40 строк, — зацикливание


def _visible_answer(text):
    """Ответ без рассуждений в начале (<think>…</think>): длина и повторы считаются только по ответу."""
    if text.lstrip().startswith("<think>"):
        end = text.find("</think>")
        return text[end + len("</think>"):] if end != -1 else ""
    return text


# поле JSON с коротким значением («"verdict": "НАЙДЕНО",», «"found": [3, 7],») — в ответе-JSON с переносами строк
# оно повторяется у каждого объекта, это не зацикливание
_JSON_FIELD_RE = re.compile(r'^"[^"\n]{1,40}"\s*:\s*(?:"[^"\n]{0,40}"|-?\d+(?:\.\d+)?|true|false|null|\[[\d,\s]*\])\s*,?$')


def _loop_key(line):
    """Строка для поиска зацикливания (без номера и маркера); None — не считается: короткая или поле JSON."""
    key = re.sub(r"^\s*(?:[-•*–—]|\d{1,3}[.)])?\s*", "", line).strip().lower()
    if len(key) <= 20 or _JSON_FIELD_RE.match(key):
        return None
    return key


def answer_loops(text, window=LOOP_WINDOW, repeats=LOOP_REPEATS):
    """Модель зациклилась: одна и та же строка (без номера и маркера) несколько раз среди последних строк."""
    lines = [k for k in (_loop_key(ln) for ln in (text or "").split("\n")) if k][-window:]
    return bool(lines) and max(lines.count(ln) for ln in set(lines)) >= repeats


def _read_stream(response, deadline, max_chars):
    """Ответ потоком (Server-Sent Events, как у OpenAI) → (текст, рассуждения были, finish_reason, usage, обрыв).
    обрыв: "length" — ответ длиннее max_chars, "loop" — зациклился, "time" — вышло время, "" — закончился сам."""
    parts, reasoning, finish, usage, total, checked = [], False, None, None, 0, 0
    for raw in response.iter_lines():
        if not raw:
            continue
        line = raw.decode("utf-8", "replace").strip() if isinstance(raw, bytes) else str(raw).strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            obj = json.loads(data)
        except ValueError:
            continue
        choice = (obj.get("choices") or [{}])[0] or {}
        delta = choice.get("delta") or choice.get("message") or {}
        if delta.get("reasoning_content") or delta.get("reasoning"):
            reasoning = True
        piece = delta.get("content") or ""
        if piece:
            parts.append(piece)
            total += len(piece)
        finish = choice.get("finish_reason") or finish
        usage = obj.get("usage") or usage
        cut = ""
        if time.time() > deadline:
            cut = "time"
        elif total - checked >= STREAM_CHECK_EVERY:
            checked = total
            visible = _visible_answer("".join(parts))
            if max_chars and len(visible) > max_chars:
                cut = "length"
            elif answer_loops(visible):
                cut = "loop"
        if cut:
            response.close()                  # шлюз (vLLM и др.) прекращает генерацию, когда клиент отключился
            return "".join(parts), reasoning, finish, usage, cut
    return "".join(parts), reasoning, finish, usage, ""


def _trim_cut(content, cut):
    """Оборванный ответ: без недописанной последней строки, а зациклившийся — без повторов."""
    if not cut:
        return content
    lines = content.split("\n")
    if len(lines) > 1:
        lines = lines[:-1]                    # последняя строка оборвана на полуслове
    seen, out = set(), []
    for ln in lines:
        key = _loop_key(ln)
        if key and key in seen and cut == "loop":
            continue
        seen.add(key)
        out.append(ln)
    return "\n".join(out).strip()


# ---------- HTTP 429: шлюз просит реже ----------
# Ответ 429 — «слишком много запросов, зайдите позже». Пауза общая для всех потоков (аудит шлёт запросы
# параллельно): пока она идёт, новые запросы ждут, а не добивают лимит. Длина паузы — сколько просит шлюз
# (Retry-After), иначе 5, 10, 20, 40 с; на 429 — не меньше RATE_LIMIT_ATTEMPTS попыток при любом llm_retries.
RATE_LIMIT_ATTEMPTS = 4
RATE_LIMIT_WAIT_MAX = 60
_rate_lock = threading.Lock()
_rate = {"until": 0.0, "count": 0, "paused": 0.0}


def _retry_after(response):
    """Сколько секунд шлюз просит подождать (Retry-After — секунды или дата); None — не сказал."""
    value = (response.headers.get("Retry-After") or "").strip()
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
    except Exception:
        return None


def _note_rate_limit(response, attempt):
    """429: продлить общую паузу."""
    delay = _retry_after(response)
    if delay is None:
        delay = 5.0 * (2 ** attempt) + random.uniform(0, 2)
    delay = min(RATE_LIMIT_WAIT_MAX, delay)
    with _rate_lock:
        now = time.time()
        until = now + delay
        _rate["paused"] += max(0.0, until - max(_rate["until"], now))
        _rate["until"] = max(_rate["until"], until)
        _rate["count"] += 1
    logger.warning(f"HTTP 429: шлюз просит реже — общая пауза {delay:.1f} с")


def _wait_rate_limit():
    """Перед запросом: если идёт общая пауза после 429 — дождаться её конца."""
    while True:
        with _rate_lock:
            left = _rate["until"] - time.time()
        if left <= 0:
            return
        time.sleep(min(left, 1.0))


def rate_limit_stats():
    """Сколько раз шлюз ответил 429 и сколько секунд длились общие паузы (с запуска программы)."""
    with _rate_lock:
        return {"count": _rate["count"], "paused": _rate["paused"]}


# ---------- Сырые ответы модели ----------
# Что спросили и что модель ответила, слово в слово, — для разбора спорных мест: видно, что написала модель, до того
# как MINT разобрал ответ на замечания. Пишется только внутри record_answers (аудит, перепроверка, сверка с
# эталоном); контекст копируется в потоки parallel_map, так что параллельные запросы попадают в тот же список.
_RAW = contextvars.ContextVar("mint_raw_answers", default=None)
_RAW_LABEL = contextvars.ContextVar("mint_raw_label", default="")


@contextmanager
def record_answers(store):
    """Каждый запрос к модели внутри блока дописывается в список store: {label, started, seconds, model, system,
    user, answer}."""
    token = _RAW.set((store, threading.Lock()))
    try:
        yield store
    finally:
        _RAW.reset(token)


@contextmanager
def answer_label(label):
    """Какая проверка спрашивает модель — подпись запросов внутри блока в списке сырых ответов. Вложенная подпись
    дописывается к внешней: «Проход 2 · Часть 3/7»."""
    outer = _RAW_LABEL.get()
    token = _RAW_LABEL.set(f"{outer} · {label}" if outer and label else (label or outer))
    try:
        yield
    finally:
        _RAW_LABEL.reset(token)


def ask_llm(system_prompt, user_content, cfg, model=None, temperature=None, max_tokens=None, history=None,
            guard=False):
    """Запрос к LLM с повторами. Ошибки возвращаются строкой, начинающейся с «❌».
    history — предыдущие реплики диалога [{"role": "user"|"assistant", "content": ...}].
    guard — ответ потоком с обрывом (llm_stream): слишком длинный (max_tokens × STREAM_CHARS_PER_TOKEN символов —
    шлюз может лимит не соблюдать) или зациклившийся ответ MINT обрывает сам и возвращает то, что успело прийти;
    шлюз, который поток не принимает, получает обычный запрос (и MINT это запоминает)."""
    rec = _RAW.get()
    started = time.time()
    answer = _ask_llm(system_prompt, user_content, cfg, model=model, temperature=temperature, max_tokens=max_tokens,
                      history=history, guard=guard)
    if rec is not None:
        store, lock = rec
        with lock:
            store.append({"label": _RAW_LABEL.get(), "started": started, "seconds": round(time.time() - started, 1),
                          "model": model or cfg.llm_model, "system": system_prompt or "", "user": user_content or "",
                          "answer": answer if isinstance(answer, str) else str(answer)})
    return answer


def _ask_llm(system_prompt, user_content, cfg, model=None, temperature=None, max_tokens=None, history=None,
             guard=False):
    """Запрос к LLM с повторами (см. ask_llm)."""
    history = [m for m in (history or []) if m.get("content")]
    chosen_model = model or cfg.llm_model
    chosen_temp = cfg.temperature if temperature is None else temperature
    chosen_tokens = int(cfg.max_tokens if max_tokens is None else max_tokens)

    if not cfg.llm_base:
        return tr("❌ [ОШИБКА НАСТРОЙКИ]: не задан LLM_API_URL в файле .env.")
    if not chosen_model:
        return tr("❌ [ОШИБКА НАСТРОЙКИ]: не выбрана модель — задайте LLM_MODEL в .env или выберите модель в "
                  "панели.")

    # Проверка «помещается ли запрос в окно модели» — только когда окно известно (не типовое значение).
    if cfg.llm_context_known and cfg.llm_context_tokens:
        cpt = cfg.chars_per_token or FALLBACK_LIMITS["chars_per_token"]
        hist_chars = sum(len(m["content"]) for m in history)
        est_input = int((len(system_prompt) + len(user_content) + hist_chars) / cpt) + 50 + 10 * len(history)
        room = cfg.llm_context_tokens - est_input
        if room < 256:
            logger.warning(f"Запрос ≈{est_input} токенов не помещается в окно {cfg.llm_context_tokens}")
            return (
                tr("❌ [КОНТЕКСТ НЕ ПОМЕЩАЕТСЯ]: запрос ≈ {est_input} токенов при окне модели {llm_context_tokens}. "
                   "Уменьшите глубину поиска (Top-K) или размеры фрагментов.", est_input=est_input, llm_context_tokens=cfg.llm_context_tokens)
            )
        if room < chosen_tokens:
            logger.warning(f"max_tokens уменьшен {chosen_tokens} → {room}: иначе ответ не помещается в окно")
            chosen_tokens = room

    payload = {
        "model": chosen_model,
        "messages": (
            [{"role": "system", "content": system_prompt}]
            + [{"role": m["role"], "content": m["content"]} for m in history]
            + [{"role": "user", "content": user_content}]
        ),
        "temperature": chosen_temp,
        "max_tokens": chosen_tokens,
    }
    extras, with_switch = _request_extras(cfg, chosen_model)
    stream = bool(guard and cfg.llm_stream and not _gateway(cfg, chosen_model).get("no_stream"))
    if stream:
        payload["stream"] = True
    max_chars = chosen_tokens * STREAM_CHARS_PER_TOKEN
    target_url = f"{cfg.llm_base}/chat/completions"
    utf8_payload = json.dumps({**payload, **extras}, ensure_ascii=False).encode("utf-8")
    headers = _auth_headers(cfg.llm_api_key)

    max_retries = max(1, int(cfg.llm_retries))
    base_delay = 2.0
    llm_timeout = int(cfg.llm_timeout)
    limited = 0                     # сколько раз подряд шлюз ответил 429

    for attempt in range(max(max_retries, RATE_LIMIT_ATTEMPTS)):
        if attempt >= max_retries and not limited:
            break
        try:
            _wait_rate_limit()
            logger.info(
                f"🧠 ИИ-КОНВЕЙЕР: попытка {attempt + 1}/{max_retries} → '{chosen_model}' (timeout={llm_timeout}s)"
            )
            started = time.time()
            response = requests.post(target_url, headers=headers, data=utf8_payload,
                                     verify=cfg.tls_verify, timeout=llm_timeout, stream=stream)

            if stream and response.status_code in (400, 422):
                # шлюз мог не принять ответ потоком — тот же запрос обычным; получилось — запомнить
                logger.warning(f"Ответ потоком: HTTP {response.status_code} — повтор обычным запросом")
                stream = False
                payload.pop("stream", None)
                utf8_payload = json.dumps({**payload, **extras}, ensure_ascii=False).encode("utf-8")
                started = time.time()
                response = requests.post(target_url, headers=headers, data=utf8_payload,
                                         verify=cfg.tls_verify, timeout=llm_timeout)
                if response.status_code == 200:
                    _gateway(cfg, chosen_model)["no_stream"] = True
                    logger.warning("Шлюз не принимает ответ потоком: дальше обычные запросы")

            if response.status_code in (401, 403):
                return tr("❌ [ОШИБКА ДОСТУПА]: шлюз вернул {status_code}. Проверьте LLM_API_KEY.", status_code=response.status_code)

            if (response.status_code in (400, 422) and with_switch
                    and any(w in (response.text or "").lower() for w in _UNKNOWN_PARAM_WORDS)):
                # шлюз не знает параметра выключения рассуждений — повтор без него, запомнить
                _gateway(cfg, chosen_model)["no_switch"] = True
                logger.warning(f"Шлюз не принимает выключатель рассуждений ({response.status_code}): запросы без него")
                extras, with_switch = _request_extras(cfg, chosen_model)
                utf8_payload = json.dumps({**payload, **extras}, ensure_ascii=False).encode("utf-8")
                response = requests.post(target_url, headers=headers, data=utf8_payload,
                                         verify=cfg.tls_verify, timeout=llm_timeout)
                if response.status_code in (400, 422):        # дело было не в выключателе — вернуть как было
                    _gateway(cfg, chosen_model).pop("no_switch", None)

            if response.status_code == 429:
                limited += 1
                if attempt >= max(max_retries, RATE_LIMIT_ATTEMPTS) - 1:
                    return (tr("❌ [ОШИБКА ИНФРАСТРУКТУРЫ MINT]: лимиты/шлюз после {max_retries} попыток (HTTP {status_code}).", max_retries=attempt + 1, status_code=429))
                _note_rate_limit(response, limited - 1)
                continue
            limited = 0
            if response.status_code in (502, 503, 504):
                if attempt >= max_retries - 1:
                    return (tr("❌ [ОШИБКА ИНФРАСТРУКТУРЫ MINT]: лимиты/шлюз после {max_retries} попыток (HTTP {status_code}).", max_retries=attempt + 1, status_code=response.status_code))
                delay = (base_delay * (2 ** attempt)) + random.uniform(0, 1)
                logger.warning(f"HTTP {response.status_code}, retry через {delay:.1f}s")
                time.sleep(delay)
                continue

            if (response.status_code == 200 and stream
                    and "text/event-stream" in (response.headers.get("Content-Type") or "").lower()):
                raw_content, reasoning, finish, usage, cut = _read_stream(response, started + llm_timeout, max_chars)
                content = strip_reasoning(raw_content)
                _note_reasoning(cfg, chosen_model, {"reasoning_content": "1" if reasoning else ""}, usage,
                                raw_content, content)
                if cut == "time" and len(content) < 200:
                    raise requests.exceptions.Timeout()
                if cut:
                    logger.warning(f"Ответ модели оборван MINT ({cut}): {len(raw_content)} симв. за "
                                   f"{time.time() - started:.0f} с")
                    content = _trim_cut(content, cut)
                elif finish == "length" and not content:
                    return (tr("❌ [ОТВЕТ ОБРЕЗАН]: модель израсходовала лимит {chosen_tokens} токенов (вероятно, на "
                               "рассуждения) и не дала ответа. Увеличьте «Макс. длину ответа модели» в блоке «Модели и лимиты» "
                               "или выберите модель без рассуждений.", chosen_tokens=chosen_tokens))
                return content

            if response.status_code == 200:
                res_json = response.json()
                if isinstance(res_json, dict) and res_json.get("choices"):
                    choice = res_json["choices"][0]
                    message = choice.get("message") or {}
                    raw_content = message.get("content") or ""
                    content = strip_reasoning(raw_content)
                    _note_reasoning(cfg, chosen_model, message, res_json.get("usage"), raw_content, content)
                    if choice.get("finish_reason") == "length":
                        logger.warning(f"Ответ модели обрезан лимитом max_tokens={chosen_tokens}")
                        if not content:
                            return (tr("❌ [ОТВЕТ ОБРЕЗАН]: модель израсходовала лимит {chosen_tokens} токенов (вероятно, на "
                                       "рассуждения) и не дала ответа. Увеличьте «Макс. длину ответа модели» в блоке «Модели и лимиты» "
                                       "или выберите модель без рассуждений.", chosen_tokens=chosen_tokens))
                        content += (tr("\n\n⚠️ Ответ обрезан: достигнут лимит длины ответа ({chosen_tokens} токенов). Увеличьте «Макс. "
                                       "длину ответа модели» в блоке «Модели и лимиты».", chosen_tokens=chosen_tokens))
                    return content
                return tr("❌ [ОШИБКА СТРУКТУРЫ]: Некорректный формат JSON-ответа от модели.")

            hint = (" " + tr("Проверьте свои параметры запроса (llm_extra_body / LLM_EXTRA_BODY).")
                    if response.status_code in (400, 422) and extra_body(cfg) else "")
            return tr("❌ [ОШИБКА ШЛЮЗА]: Сервер вернул код {status_code}: {v}", status_code=response.status_code, v=(response.text or '')[:200]) + hint

        except requests.exceptions.Timeout:
            limited = 0
            logger.warning(f"⏱ LLM timeout ({llm_timeout}s), попытка {attempt + 1}/{max_retries}")
            if attempt >= max_retries - 1:
                return timeout_message(cfg, chosen_model, llm_timeout)
            time.sleep(base_delay)
        except Exception as e:
            limited = 0
            logger.warning(f"LLM error: {str(e)[:150]}, попытка {attempt + 1}")
            if attempt >= max_retries - 1:
                return tr("❌ [СЕТЕВОЙ СБОЙ MINT]: Не удалось достучаться до модели ИИ ({v}).", v=str(e))
            time.sleep((base_delay * (2 ** attempt)) + random.uniform(0, 1))

    return tr("❌ [ОШИБКА]: Запрос к языковой модели аварийно завершен.")


def describe_request_error(e, url=""):
    """Человеческое описание сбоя HTTP-запроса: что проверить администратору."""
    host = ""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc
    except Exception:
        pass
    if isinstance(e, requests.exceptions.SSLError):
        return (tr("ошибка сертификата TLS — укажите в .env CA_BUNDLE_PATH (корпоративный сертификат) или, только "
                   "во внутренней сети, SSL_INSECURE=1"))
    if isinstance(e, requests.exceptions.Timeout):
        return tr("сервер {host} не ответил вовремя", host=host)
    if isinstance(e, requests.exceptions.ConnectionError):
        return tr("нет соединения с {v}: адрес неверен, сервер выключен или закрыт сетью", v=host or url)
    if isinstance(e, requests.exceptions.InvalidURL) or isinstance(e, requests.exceptions.MissingSchema):
        return tr("неверный адрес «{url}» — нужен вид https://host/v1", url=url)
    return str(e)[:160]


def describe_http_status(code, url=""):
    if code in (401, 403):
        return tr("HTTP {code}: доступ запрещён — проверьте ключ (LLM_API_KEY / EMBED_API_KEY / RERANK_API_KEY)", code=code)
    if code == 404:
        return tr("HTTP 404: по адресу {url} ничего нет — проверьте адрес в .env", url=url)
    return f"HTTP {code}"

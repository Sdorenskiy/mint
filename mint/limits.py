"""Лимиты моделей и расчёт зависимых параметров (размеры фрагментов, объём контекста)."""

import json
import logging
import math
import re
from dataclasses import replace

import requests

from .config import DEFAULTS, FALLBACK_LIMITS, SETTING_NAMES, Settings
from .i18n import N_, tr
from .prompts import prompt_extra_chars
from .services import _auth_headers, describe_http_status, describe_request_error

logger = logging.getLogger("MINT")


LIMIT_LABELS = {
    "llm_context_tokens": N_("Окно контекста LLM, токенов"),
    "embed_max_tokens": N_("Вход модели эмбеддингов, токенов"),
    "rerank_max_tokens": N_("Вход реранкера (запрос + документ), токенов"),
    "chars_per_token": N_("Символов текста на токен"),
}

LIMIT_SAFETY = 0.85            # запас: символы → токены считаются с допуском

CHAT_RESERVE_TOKENS = 800      # системный промпт, вопрос, справочник сокращений, разметка

AUDIT_RESERVE_CHARS = 3500     # промпт аудита, критерии проверки, черновик замечаний

# Свои правки промптов длиннее умолчания уменьшают место под фрагменты: запас растёт на разницу в длине
CHAT_PROMPT_KEYS = ("chat_system", "chat_no_info")
AUDIT_PROMPT_KEYS = ("audit_system", "audit_focus_default", "critique_system", "review_system")

HEADING_RESERVE_CHARS = 250    # путь заголовков перед child-фрагментом во входе эмбеддинга


DERIVED_FIELDS = (
    "smart_truncate_chars", "parent_size", "parent_overlap", "child_size", "child_overlap",
    "section_embed_chars", "audit_query_chars", "audit_map_size", "audit_context_max_chars",
    "review_context_max_chars", "rerank_query_max_chars", "rerank_doc_max_chars",
)

DERIVED_LABELS = {
    "smart_truncate_chars": N_("Фрагмент в контексте чата"),
    "parent_size": N_("Parent-фрагмент (индексация)"),
    "parent_overlap": N_("Перекрытие parent"),
    "child_size": N_("Child-фрагмент (индексация)"),
    "child_overlap": N_("Перекрытие child"),
    "section_embed_chars": N_("Раздел документа для эмбеддинга (вкладка 3)"),
    "audit_query_chars": N_("Запрос к базе из раздела документа"),
    "audit_map_size": N_("Раздел документа на одну проверку"),
    "audit_context_max_chars": N_("Нормативный контекст в аудите"),
    "review_context_max_chars": N_("Фрагменты новой редакции на замечание"),
    "rerank_query_max_chars": N_("Запрос для реранкера"),
    "rerank_doc_max_chars": N_("Фрагмент документа для реранкера"),
}


# Префиксы для моделей эмбеддингов, обученных с инструкцией (подбираются по имени модели, если не заданы
# в config.yaml). Документам Qwen3 и e5-instruct префикс не нужен — смена модели на них не требует
# переиндексации из-за префикса; e5, nomic, FRIDA префикс документа меняют (MINT предложит переиндексацию).
EMBED_TASK = ("Given a question or a fragment of a document under review, retrieve passages from "
              "corporate regulations and architecture documents that are relevant to it")

EMBED_PREFIX_PRESETS = [
    # (шаблон имени модели, префикс запроса, префикс документа, название)
    (r"qwen3[-_ ]?embed|gte[-_]qwen", f"Instruct: {EMBED_TASK}\nQuery:", "", "Qwen3-Embedding"),
    (r"e5.*instruct", f"Instruct: {EMBED_TASK}\nQuery: ", "", "multilingual-e5-instruct"),
    (r"(^|[^a-z0-9])e5([^a-z0-9]|$)", "query: ", "passage: ", "e5"),
    (r"nomic[-_]embed", "search_query: ", "search_document: ", "nomic-embed"),
    (r"frida|rosberta", "search_query: ", "search_document: ", "FRIDA / ru-en-RoSBERTa"),
]


def embed_prefix_preset(model):
    """(префикс запроса, префикс документа, название модели) по имени модели эмбеддингов."""
    name = (model or "").lower()
    for pattern, q_prefix, d_prefix, label in EMBED_PREFIX_PRESETS:
        if re.search(pattern, name):
            return q_prefix, d_prefix, label
    return "", "", ""


def _int_or_none(v):
    try:
        v = int(v)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


_CTX_KEYS = ("max_model_len", "context_length", "max_context_length", "context_window",
             "max_input_tokens", "max_seq_len", "max_sequence_length", "n_ctx")


def context_from_model_info(info):
    """Окно модели из описания в /models (vLLM: max_model_len; OpenRouter: context_length; LM Studio и др.)."""
    if not isinstance(info, dict):
        return None
    for k in _CTX_KEYS:
        v = _int_or_none(info.get(k))
        if v:
            return v
    for nested in ("meta", "metadata", "details", "model_info", "top_provider"):
        v = context_from_model_info(info.get(nested))
        if v:
            return v
    return None


def _models_url_for(endpoint_url, suffixes):
    base = (endpoint_url or "").rstrip("/")
    for s in suffixes:
        if base.endswith(s):
            return base[:-len(s)].rstrip("/") + "/models"
    return None


def _fetch_models_info(url, key, cfg, timeout=10, errors=None):
    """Список моделей с …/models. Причину неудачи добавляет в errors (если передан список)."""
    if not url:
        return []
    try:
        r = requests.get(url, headers=_auth_headers(key), verify=cfg.tls_verify, timeout=timeout)
        if r.status_code != 200:
            reason = describe_http_status(r.status_code, url)
        else:
            try:
                data = r.json()
                items = data.get("data") if isinstance(data, dict) else data
                return [m for m in (items or []) if isinstance(m, dict)]
            except ValueError:
                reason = tr("ответ не похож на OpenAI-совместимый API (не JSON)")
    except Exception as e:
        reason = describe_request_error(e, url)
    logger.warning(f"GET {url}: {reason}")
    if errors is not None:
        errors.append(reason)
    return []


def detect_server_info(cfg):
    """Что можно узнать у серверов бесплатно: список моделей LLM, их окна, лимиты эмбеддингов и реранкера."""
    out = {"llm_models": [], "llm_context": {}, "embed_max_tokens": None, "rerank_max_tokens": None,
           "llm_error": ""}
    if cfg.llm_base:
        errs = []
        for m in _fetch_models_info(f"{cfg.llm_base}/models", cfg.llm_api_key, cfg, errors=errs):
            mid = m.get("id")
            if mid:
                out["llm_models"].append(str(mid))
                ctx = context_from_model_info(m)
                if ctx:
                    out["llm_context"][str(mid)] = ctx
        out["llm_error"] = errs[0] if errs else ""
    for field, url, key, model, suffixes in (
        ("embed_max_tokens", cfg.embed_url, cfg.embed_key, cfg.embed_model, ("/embeddings", "/embed")),
        ("rerank_max_tokens", cfg.rerank_url, cfg.rerank_key, cfg.rerank_model, ("/rerank",)),
    ):
        for m in _fetch_models_info(_models_url_for(url, suffixes), key, cfg):
            if str(m.get("id")) == model:
                out[field] = context_from_model_info(m)
                break
    out["llm_models"] = sorted(set(out["llm_models"]))
    return out


CPT_SAMPLE = (
    "Требования к информационной безопасности: при передаче персональных данных между подсистемами "
    "применяется шифрование по ГОСТ; журналы событий хранятся не менее трёх лет, доступ к ним "
    "разграничивается по ролям, а время восстановления сервиса не превышает четырёх часов. "
)

CPT_SAMPLE_EN = (
    "Information security requirements: personal data transferred between subsystems is encrypted; "
    "event logs are kept for at least three years, access to them is role-based, and the service "
    "recovery time does not exceed four hours. "
)


def _llm_prompt_tokens(text, cfg, model):
    r = requests.post(
        f"{cfg.llm_base}/chat/completions",
        headers=_auth_headers(cfg.llm_api_key),
        data=json.dumps({"model": model, "messages": [{"role": "user", "content": text}],
                         "max_tokens": 1, "temperature": 0}, ensure_ascii=False).encode("utf-8"),
        verify=cfg.tls_verify, timeout=30,
    )
    if r.status_code != 200:
        return None
    return _int_or_none((r.json().get("usage") or {}).get("prompt_tokens"))


def _embed_prompt_tokens(text, cfg):
    r = requests.post(cfg.embed_url, json={"input": text, "model": cfg.embed_model},
                      headers=_auth_headers(cfg.embed_key), verify=cfg.tls_verify, timeout=30)
    if r.status_code != 200:
        return None
    data = r.json()
    usage = data.get("usage") if isinstance(data, dict) else None
    return _int_or_none((usage or {}).get("prompt_tokens"))


def measure_chars_per_token(cfg, model, lang=None):
    """Измеряет «символов на токен» на тексте языка базы знаний (lang — из kb_language): 'ru' — на русском,
    'en' — на английском. Для смешанной или пустой базы (lang=None, 'mixed') — на обоих и берёт меньшее
    значение: размеры фрагментов, рассчитанные по нему, безопасны для документов на любом из языков (русский
    текст обычно «дороже» в токенах). Возвращает (значение, источник) или (None, None)."""
    samples = {"ru": (CPT_SAMPLE,), "en": (CPT_SAMPLE_EN,)}.get(lang, (CPT_SAMPLE, CPT_SAMPLE_EN))
    results = [r for r in (_measure_cpt(cfg, model, sample) for sample in samples) if r[0]]
    return min(results) if results else (None, None)


def _measure_cpt(cfg, model, sample):
    """«Символов на токен» по двум запросам разной длины (служебные токены взаимно вычитаются).
    Сначала у LLM (max_tokens=1), затем у сервиса эмбеддингов."""
    short, long_ = sample, sample * 4
    probes = []
    if cfg.llm_base and model:
        probes.append(("LLM", lambda t: _llm_prompt_tokens(t, cfg, model)))
    if cfg.embed_url:
        probes.append((tr("эмбеддинги"), lambda t: _embed_prompt_tokens(t, cfg)))
    for label, fn in probes:
        try:
            t1, t2 = fn(short), fn(long_)
        except Exception:
            continue
        if t1 and t2 and t2 > t1:
            cpt = (len(long_) - len(short)) / (t2 - t1)
            if 1.0 <= cpt <= 8.0:
                return round(cpt, 2), label
    return None, None


def resolve_model_limits(cfg, server_info, measured_cpt, manual):
    """Лимиты моделей с источником. Порядок: вручную (панель) > config.yaml > сервер/измерение > типовое."""
    detected = {
        "llm_context_tokens": (server_info.get("llm_context") or {}).get(cfg.llm_model),
        "embed_max_tokens": server_info.get("embed_max_tokens"),
        "rerank_max_tokens": server_info.get("rerank_max_tokens"),
        "chars_per_token": measured_cpt,
    }
    out = {}
    for name, fallback in FALLBACK_LIMITS.items():
        if manual.get(name):
            out[name] = (manual[name], N_("вручную"))
        elif name in cfg.explicit_fields and getattr(cfg, name):
            out[name] = (getattr(cfg, name), "config.yaml")
        elif detected.get(name):
            out[name] = (detected[name], N_("измерено") if name == "chars_per_token" else N_("сервер"))
        else:
            out[name] = (fallback, N_("типовое значение"))
    return out


def _derive(cfg, choose):
    """Расчёт зависимых параметров по лимитам моделей. choose(поле, авто, потолок) возвращает итог
    (авто, из config.yaml или вручную) — следующие расчёты опираются на итоговые значения."""
    cpt = cfg.chars_per_token or FALLBACK_LIMITS["chars_per_token"]

    def chars(tokens):
        return max(0, int(tokens * cpt * LIMIT_SAFETY))

    d = DEFAULTS
    out = {}
    top_k = max(1, cfg.top_k or 5)

    # Чат: top_k фрагментов + ответ + промпт должны помещаться в окно (запас — с учётом своих правок промптов)
    chat_reserve = CHAT_RESERVE_TOKENS + math.ceil(prompt_extra_chars(CHAT_PROMPT_KEYS) / cpt)
    chat_budget = chars(cfg.llm_context_tokens - cfg.max_tokens - chat_reserve)
    ceil = chat_budget // top_k
    out["smart_truncate_chars"] = choose("smart_truncate_chars", min(d.smart_truncate_chars, max(500, ceil)), ceil)

    # Индексация: parent рассчитан на 5 фрагментов в контексте; child — на вход модели эмбеддингов
    ceil = chat_budget // 5
    parent = out["parent_size"] = choose("parent_size", min(d.parent_size, max(300, ceil)), ceil)
    out["parent_overlap"] = choose("parent_overlap", min(d.parent_overlap, parent // 5), parent // 5)
    embed_chars = chars(cfg.embed_max_tokens)
    ceil = embed_chars - HEADING_RESERVE_CHARS - len(cfg.embed_doc_prefix)
    child = out["child_size"] = choose("child_size", min(d.child_size, max(100, ceil)), ceil)
    out["child_overlap"] = choose("child_overlap", min(d.child_overlap, child // 2), child // 2)
    ceil = embed_chars - len(cfg.embed_doc_prefix)
    out["section_embed_chars"] = choose("section_embed_chars", min(d.section_embed_chars, max(300, ceil)), ceil)
    ceil = embed_chars - len(cfg.embed_query_prefix)
    out["audit_query_chars"] = choose("audit_query_chars", min(d.audit_query_chars, max(300, ceil)), ceil)

    # Аудит и контроль исправлений: раздел документа + нормы + промпт + ответ
    llm_budget = chars(cfg.llm_context_tokens - cfg.max_tokens) - AUDIT_RESERVE_CHARS - prompt_extra_chars(AUDIT_PROMPT_KEYS)
    ceil = int(llm_budget * 0.3)
    audit_map = out["audit_map_size"] = choose("audit_map_size", min(d.audit_map_size, max(1000, ceil)), ceil)
    ceil = llm_budget - audit_map
    norms = out["audit_context_max_chars"] = choose(
        "audit_context_max_chars", min(d.audit_context_max_chars, max(1000, ceil)), ceil)
    ceil = llm_budget - norms - 1000
    out["review_context_max_chars"] = choose(
        "review_context_max_chars", min(d.review_context_max_chars, max(1000, ceil)), ceil)

    # Реранкер: пара «запрос + документ» должна помещаться во вход модели
    pair = chars(cfg.rerank_max_tokens)
    ceil = pair // 3
    q = out["rerank_query_max_chars"] = choose(
        "rerank_query_max_chars", min(d.rerank_query_max_chars, max(200, ceil)), ceil)
    ceil = pair - q
    out["rerank_doc_max_chars"] = choose("rerank_doc_max_chars", min(d.rerank_doc_max_chars, max(200, ceil)), ceil)
    return out


def resolve_settings(base: Settings, limits: dict, manual: dict):
    """Итоговые настройки сеанса: config.yaml + изменения в панели + лимиты моделей + расчёт.
    Возвращает (Settings, info): info[поле] = {value, auto, ceiling, source} для рассчитываемых полей."""
    vals = {k: v for k, v in manual.items()
            if k in SETTING_NAMES and k not in DERIVED_FIELDS and k not in FALLBACK_LIMITS}
    for name, (value, _src) in limits.items():
        vals[name] = value
    vals["llm_context_known"] = limits["llm_context_tokens"][1] != "типовое значение"
    cfg = replace(base, **vals)

    # Префиксы эмбеддингов: config.yaml > по имени модели
    q_prefix, d_prefix, preset = embed_prefix_preset(cfg.embed_model)
    prefix_vals, sources = {}, []
    for field, auto_value in (("embed_query_prefix", q_prefix), ("embed_doc_prefix", d_prefix)):
        if field in base.explicit_fields:
            sources.append("config.yaml")
        else:
            prefix_vals[field] = auto_value
            sources.append(tr("авто: {preset}", preset=preset) if preset else tr("не нужен"))
    prefix_vals["embed_prefix_source"] = sources[0] if sources[0] == sources[1] else " / ".join(sources)
    cfg = replace(cfg, **prefix_vals)

    info = {}

    def choose(field, auto, ceiling):
        if field in manual:
            value, source = manual[field], N_("вручную")
        elif field in base.explicit_fields:
            value, source = getattr(base, field), "config.yaml"
        else:
            value, source = auto, N_("авто")
        info[field] = {"value": value, "auto": auto, "ceiling": ceiling, "source": source}
        return value

    derived = _derive(cfg, choose)
    cpt = cfg.chars_per_token or FALLBACK_LIMITS["chars_per_token"]
    derived["embed_input_max_chars"] = int(cfg.embed_max_tokens * cpt * LIMIT_SAFETY)
    return replace(cfg, **derived), info


def limits_warnings(info):
    out = []
    for field, i in info.items():
        label = DERIVED_LABELS.get(field, field)
        if i["source"] != "авто" and i["ceiling"] is not None and i["value"] > i["ceiling"]:
            out.append(tr("«{label}» = {value} ({source}) больше рассчитанного потолка {v}: текст может не поместиться во "
                          "вход модели.", label=tr(label), value=i['value'], source=tr(i['source']), v=max(0, i['ceiling'])))
        elif i["source"] == "авто" and i["ceiling"] is not None and i["auto"] > i["ceiling"]:
            out.append(tr("«{label}»: модели слишком мало места (потолок {v}), взят минимум {auto}. Возьмите модель с "
                          "бо́льшим окном или уменьшите Top-K / длину ответа.", label=tr(label), v=max(0, i['ceiling']), auto=i['auto']))
    return out

"""Отзывы пользователей: оценки 👍/👎 и комментарии к ответам чата, аудиту и контролю исправлений.

Каждая оценка — одна строка JSON в LOG_DIR/feedback.jsonl (по умолчанию ~/mint_logs). Файл остаётся на
компьютере пользователя; чтобы передать отзывы разработчику, его скачивают кнопкой в боковой панели.
В строке — вопрос, ответ, источники, настройки прогона и версия промптов (prompts): этого хватает, чтобы
воспроизвести случай и сравнить оценки до и после правки промптов.
Поэтому файл содержит фрагменты ваших документов — пересылайте его только туда, куда можно их пересылать.
"""
import json
import logging
import threading
import time
import uuid
from collections import Counter

from .i18n import get_lang, tr
from .prompts import custom_status
from .version import MINT_VERSION

logger = logging.getLogger("MINT")

FEEDBACK_FILE = "feedback.jsonl"
MAX_TEXT_CHARS = 20000         # длиннее — обрезается (заключение аудита обычно короче)
_LOCK = threading.Lock()       # сеансы Streamlit — потоки одного процесса

RATINGS = {"up": "👍", "down": "👎"}


def feedback_path(cfg):
    return cfg.log_path / FEEDBACK_FILE


def new_feedback_id():
    return uuid.uuid4().hex[:12]


def settings_snapshot(cfg):
    """Настройки, от которых зависит ответ: язык (промптов), модели и параметры поиска. Версия промптов, при
    которых получен результат, — в поле prompts самого отзыва (её записывает сценарий в момент ответа)."""
    return {
        "lang": get_lang(),
        "prompts_custom": custom_status(),          # свои правки промптов: {ключ: "file" | "session"}
        "llm_model": cfg.llm_model,
        "embed_model": cfg.embed_model,
        "rerank_model": cfg.rerank_model if cfg.rerank_url else "",
        "temperature": cfg.temperature,
        "llm_no_reasoning": cfg.llm_no_reasoning,
        "top_k": cfg.top_k,
        "use_multi_query": cfg.use_multi_query,
        "weight_rerank": cfg.weight_rerank if cfg.rerank_url else None,
        "chat_history_turns": cfg.chat_history_turns,
        "consult": {k: getattr(cfg, k) for k in ("consult_queries", "consult_per_query", "consult_expand_sections",
                                                 "consult_section_max_chars", "consult_context_max_chars",
                                                 "consult_max_tokens", "consult_temperature", "consult_history_turns")},
        "glossary_in_context": cfg.glossary_in_context,
        "use_self_critique": cfg.use_self_critique,
        "parent_size": cfg.parent_size,
        "child_size": cfg.child_size,
        "audit_map_size": cfg.audit_map_size,
        "audit_context_max_chars": cfg.audit_context_max_chars,
    }


def _clip(value):
    if isinstance(value, str) and len(value) > MAX_TEXT_CHARS:
        return value[:MAX_TEXT_CHARS] + tr("… [обрезано, всего {n_value} симв.]", n_value=len(value))
    return value


def record_feedback(cfg, kind, rating, item_id, context=None, comment=""):
    """Записывает оценку. kind — "chat" | "consult" | "audit" | "review"; rating — "up" | "down" | "comment"
    (комментарий к уже поставленной оценке, связан с ней по item_id). Возвращает True, если записано."""
    entry = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mint_version": MINT_VERSION,
        "id": item_id,
        "kind": kind,
        "rating": rating,
        "comment": (comment or "").strip(),
        **{k: _clip(v) for k, v in (context or {}).items()},
        "settings": settings_snapshot(cfg),
    }
    path = feedback_path(cfg)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK, open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info(f"Отзыв записан: {kind} {RATINGS.get(rating, rating)} ({item_id})")
        return True
    except OSError as e:
        logger.error(f"Не удалось записать отзыв в {path}: {e}")
        return False


def read_feedback(cfg):
    """Все записи файла отзывов (повреждённые строки пропускаются)."""
    path = feedback_path(cfg)
    if not path.is_file():
        return []
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def feedback_summary(rows):
    """Счётчики по последней оценке каждого элемента: {"chat": {"up": 3, "down": 1}, ...}, комментарии."""
    last = {}
    comments = 0
    for r in rows:
        if r.get("rating") in RATINGS:
            last[(r.get("kind"), r.get("id"))] = r["rating"]
        if r.get("comment"):
            comments += 1
    summary = {}
    for (kind, _id), rating in last.items():
        summary.setdefault(kind, Counter())[rating] += 1
    return {k: dict(v) for k, v in summary.items()}, comments

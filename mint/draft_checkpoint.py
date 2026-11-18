"""Durable, private checkpoints for verified requirement extraction in Word drafts.

Unlike the in-process cache for search indexes, these small JSON files survive
Streamlit sessions and restarts. No original document or API key is written here;
verified quotations are retained locally because they are needed for reuse.
"""

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path

from .prompts import render

logger = logging.getLogger("MINT")
CACHE_VERSION = 1


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _text_hash(text):
    return _digest(text)


def _identity(cfg, source, markdown):
    """Only reuse results when the source and extraction semantics match.

    An unspecified model name cannot be pinned: the gateway can select another
    model between runs, so persistence is disabled in that case.
    """
    model = str(getattr(cfg, "llm_model", "") or "").strip()
    if not model or getattr(cfg, "log_path", None) is None:
        return None
    key = str(getattr(cfg, "llm_api_key", "") or "")
    data = {
        "version": CACHE_VERSION,
        "source": source,
        "source_hash": _text_hash(markdown),
        "model": model,
        "gateway": str(getattr(cfg, "llm_base", getattr(cfg, "llm_url", ""))),
        "credential_hash": _digest(key),
        "tokens": min(3800, max(1500, int(cfg.max_tokens))),
        "context_tokens": getattr(cfg, "llm_context_tokens", 0),
        "chars_per_token": getattr(cfg, "chars_per_token", 0),
        "no_reasoning": getattr(cfg, "llm_no_reasoning", True),
        "extra_body": getattr(cfg, "llm_extra_body", ""),
        "system_prompt": render("draft_system"),
        "extract_prompt": render("draft_extract"),
    }
    return _digest(json.dumps(data, sort_keys=True, ensure_ascii=False))


class DraftExtractCheckpoint:
    """One namespace per exact source + model + extraction prompt + settings."""

    def __init__(self, cfg, source, markdown):
        self.directory = None
        identity = _identity(cfg, source, markdown)
        if identity is None:
            return
        path = Path(cfg.log_path) / "draft_extract_checkpoints" / identity
        try:
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            # The checkpoint directory contains quotations from user documents.
            path.parent.chmod(0o700)
            path.chmod(0o700)
        except OSError as exc:
            logger.warning("Контрольные точки разбора оснований недоступны: %s", exc)
            return
        self.directory = path

    def _path(self, index):
        return self.directory / f"{index:06d}.json"

    def load(self, index, section, text):
        """Return validated quotes, including [], or None when a call is required."""
        if self.directory is None:
            return None
        try:
            row = json.loads(self._path(index).read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            return None
        if (not isinstance(row, dict) or row.get("version") != CACHE_VERSION
                or row.get("index") != index or row.get("section") != section
                or row.get("text_hash") != _text_hash(text)):
            return None
        quotes = row.get("quotes")
        normalized = " ".join(text.split())
        if (not isinstance(quotes, list) or any(
                not isinstance(q, str) or not q.strip() or " ".join(q.split()) not in normalized
                for q in quotes)):
            return None
        return quotes

    def save(self, index, section, text, quotes):
        """Atomic replacement: a crash cannot turn a partial write into a hit."""
        if self.directory is None:
            return
        row = {"version": CACHE_VERSION, "index": index, "section": section,
               "text_hash": _text_hash(text), "quotes": quotes}
        tmp = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.directory,
                                             prefix=".writing-", delete=False) as out:
                tmp = Path(out.name)
                os.chmod(tmp, 0o600)
                json.dump(row, out, ensure_ascii=False)
                out.flush()
                os.fsync(out.fileno())
            os.replace(tmp, self._path(index))
        except OSError as exc:
            logger.warning("Не удалось сохранить фрагмент основания %d: %s", index, exc)
            if tmp is not None:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass

    def clear(self):
        """Explicitly discard prior extraction results for this source/identity."""
        if self.directory is None:
            return
        try:
            for path in self.directory.glob("*.json"):
                if path.stem.isdecimal():
                    path.unlink()
        except OSError as exc:
            logger.warning("Не удалось очистить контрольные точки основания: %s", exc)

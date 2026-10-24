"""Сохранённые аудиты: каждый аудит — папка LOG_DIR/audits/<id> на компьютере пользователя. Аудит можно открыть
позже (заключение, лог, документ с замечаниями, разбор экспертом) — и разобрать замечания не в тот же день.

В папке аудита:
    meta.json      — файл, время, модель, версия MINT и промптов, настройки прогона, число замечаний
    report.md      — заключение;  log.md — лог проверки;  raw.md.gz — сырые ответы модели (сжаты)
    result.json    — замечания (для сверки с эталоном и вердикта);  rows.json — строки разбора
    review.json    — разбор экспертом (отметки, свои замечания);  document.docx — проверенный документ (.docx)

Папки остаются только на этом компьютере: в них цитаты и копия документа.

    aid = save_audit(cfg, res, "Документ.docx", doc_bytes=data, settings={"use_kb": True})
    for meta in list_audits(cfg): ...
    saved = load_audit(cfg, aid)       # {"meta", "report", "log_md", "result", "rows", "review"}
    save_review(cfg, aid, review)
"""

import gzip
import json
import logging
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from .expert_review import review_progress, review_rows
from .version import MINT_VERSION

logger = logging.getLogger("MINT")

AUDITS_DIR = "audits"
_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}$")
# замечание в result.json — только поля, нужные сверке с эталоном, вердикту и документу с замечаниями
_FINDING_FIELDS = ("severity", "text", "quote", "sections", "origins", "source", "check", "focus_item", "point_kind",
                   "unverified")


def audits_root(cfg):
    return Path(cfg.log_path) / AUDITS_DIR


def new_audit_id():
    """Идентификатор аудита: время запуска и случайный хвост — папки сортируются по времени."""
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


def _dir(cfg, aid):
    if not _ID_RE.match(aid or ""):
        raise ValueError(f"bad audit id: {aid!r}")
    return audits_root(cfg) / aid


def _write(path, data):
    """Запись через временный файл: оборванная запись не портит прежний файл."""
    tmp = path.with_name(path.name + ".tmp")
    if isinstance(data, (bytes, bytearray)):
        tmp.write_bytes(data)
    else:
        tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)


def _json(data):
    return json.dumps(data, ensure_ascii=False, indent=1, default=str)


def _light(f):
    return {k: f[k] for k in _FINDING_FIELDS if k in f}


def save_audit(cfg, res, filename, doc_bytes=None, settings=None, raw_md="", aid=None):
    """Сохраняет итог run_audit (или перепроверки — тогда aid прежний: разбор эксперта остаётся). → id аудита."""
    aid = aid or new_audit_id()
    folder = _dir(cfg, aid)
    folder.mkdir(parents=True, exist_ok=True)
    rows = review_rows(res)
    meta = {
        "id": aid, "time": time.strftime("%Y-%m-%d %H:%M"), "file": filename, "mint": MINT_VERSION,
        "created": (load_meta(cfg, aid) or {}).get("created") or time.time(),     # перепроверка — место в списке
        "model": cfg.llm_model, "prompts": res.get("prompts", ""), "sections": res.get("sections", 0),
        "failed": len(res.get("failed_sections") or []), "findings": len(rows),
        "main": sum(1 for r in rows if r["block"] in ("main", "point")),
        "document_mode": res.get("document_mode", ""), "doc_type": res.get("doc_type", ""),
        "basis": [d["source"] for d in ((res.get("basis") or {}).get("docs") or [])],
        "special": res.get("special", ""), "criteria": res.get("focus", ""),
        **(settings or {}),
    }
    result = {"findings": [_light(f) for f in res.get("findings") or []],
              "unverified": [_light(f) for f in res.get("unverified") or []],
              "failed_sections": [list(x) for x in res.get("failed_sections") or []],
              **{k: res.get(k) for k in ("sections", "special", "focus", "prompts", "document_mode", "doc_type")}}
    _write(folder / "meta.json", _json(meta))
    _write(folder / "report.md", res.get("report") or "")
    _write(folder / "log.md", res.get("log_md") or "")
    _write(folder / "result.json", _json(result))
    _write(folder / "rows.json", _json(rows))
    if raw_md:
        _write(folder / "raw.md.gz", gzip.compress(raw_md.encode("utf-8")))
    if doc_bytes:
        _write(folder / "document.docx", bytes(doc_bytes))
    if not (folder / "review.json").exists():
        save_review(cfg, aid, {"marks": {}, "added": []}, rows=rows)
    return aid


def _read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def list_audits(cfg):
    """Сохранённые аудиты, новые сверху: meta с прогрессом разбора (meta["progress"])."""
    root = audits_root(cfg)
    if not root.is_dir():
        return []
    out = []
    for folder in root.iterdir():
        if not folder.is_dir() or not _ID_RE.match(folder.name):
            continue
        meta = _read_json(folder / "meta.json", None)
        if not isinstance(meta, dict):
            continue
        review = _read_json(folder / "review.json", {})
        meta["progress"] = review.get("progress") or {}
        meta["reviewed"] = review.get("updated", "")
        out.append(meta)
    return sorted(out, key=lambda m: (m.get("created") or 0, m["id"]), reverse=True)


def load_meta(cfg, aid):
    meta = _read_json(_dir(cfg, aid) / "meta.json", None)
    return meta if isinstance(meta, dict) else None


def load_audit(cfg, aid):
    """Аудит с диска: {"meta", "report", "log_md", "result", "rows", "review"}; None — нет такого."""
    folder = _dir(cfg, aid)
    meta = _read_json(folder / "meta.json", None)
    if not isinstance(meta, dict):
        return None

    def text(name):
        try:
            return (folder / name).read_text(encoding="utf-8")
        except OSError:
            return ""

    return {"meta": meta, "report": text("report.md"), "log_md": text("log.md"),
            "result": _read_json(folder / "result.json", {}), "rows": _read_json(folder / "rows.json", []),
            "review": _read_json(folder / "review.json", {}) or {"marks": {}, "added": []}}


def load_raw(cfg, aid):
    try:
        return gzip.decompress((_dir(cfg, aid) / "raw.md.gz").read_bytes()).decode("utf-8")
    except (OSError, ValueError, EOFError):
        return ""


def load_document(cfg, aid):
    try:
        return (_dir(cfg, aid) / "document.docx").read_bytes()
    except OSError:
        return None


def save_review(cfg, aid, review, rows=None):
    """Записывает разбор эксперта (с прогрессом — для списка аудитов)."""
    folder = _dir(cfg, aid)
    if rows is None:
        rows = _read_json(folder / "rows.json", [])
    data = {"marks": dict((review or {}).get("marks") or {}), "added": list((review or {}).get("added") or []),
            "updated": time.strftime("%Y-%m-%d %H:%M")}
    data["progress"] = review_progress(rows, data)
    _write(folder / "review.json", _json(data))
    return data


def delete_audit(cfg, aid):
    shutil.rmtree(_dir(cfg, aid), ignore_errors=True)

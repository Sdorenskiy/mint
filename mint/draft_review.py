"""Local, explicitly saved expert review of a real generated Word draft.

Reuse Mint's existing draft requirement IDs and the manual-verdict approach of
expert_review. No new LLM judge. This module never uploads document contents.
"""
import hashlib
import json
import os
import time
import uuid
from pathlib import Path

from .version import MINT_VERSION

DIR = "draft_reviews"
VERDICTS = ("", "covered", "missing", "distorted", "not_applicable")
FORMAT = "mint-draft-review/1"


def fingerprint(input_key):
    """Same input template/source versions across model or prompt changes."""
    blob = json.dumps(input_key, ensure_ascii=False, default=str, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _root(cfg):
    return Path(cfg.log_path) / DIR


def _folder(cfg, run_id):
    if not isinstance(run_id, str) or len(run_id) != 32 or any(x not in "0123456789abcdef" for x in run_id):
        raise ValueError("invalid draft review ID")
    return _root(cfg) / run_id


def _write_json(path, obj):
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex[:8] + ".tmp")
    try:
        with tmp.open("x", encoding="utf-8") as out:
            os.chmod(tmp, 0o600)
            json.dump(obj, out, ensure_ascii=False, indent=2)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_run(cfg, input_key, filename, sources, result, prompt_signature=""):
    """Take one immutable local snapshot. Never overwrite a previous attempt."""
    root = _root(cfg)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    run_id = uuid.uuid4().hex
    folder = _folder(cfg, run_id)
    folder.mkdir(mode=0o700)
    meta = {"id": run_id, "time": time.strftime("%Y-%m-%d %H:%M"),
            "input_fingerprint": fingerprint(input_key), "file": filename,
            "sources": list(sources), "mint": MINT_VERSION, "model": str(getattr(cfg, "llm_model", "")),
            "prompt_signature": prompt_signature,
            "metrics": result.get("metrics") or {}}
    rows = [{"id": row["id"], "source": row["source"], "section": row["section"],
             "quote": row["quote"], "linked": row["id"] in result.get("used", set())}
            for row in result.get("requirements", [])]
    generated = [{"field": row.get("field", ""), "status": row.get("status", ""),
                  "text": row.get("text", ""), "refs": row.get("refs", [])}
                 for row in result.get("results", [])]
    _write_json(folder / "run.json", {"meta": meta, "requirements": rows, "generated": generated})
    _write_json(folder / "review.json", {"marks": {}, "missed_extraction": [], "unsupported_claims": []})
    return run_id


def load_run(cfg, run_id):
    folder = _folder(cfg, run_id)
    data, review = _read(folder / "run.json"), _read(folder / "review.json")
    if not isinstance(data, dict) or not isinstance(review, dict):
        return None
    return {**data, "review": review}


def list_runs(cfg):
    root = _root(cfg)
    if not root.is_dir():
        return []
    runs = []
    for folder in root.iterdir():
        if not folder.is_dir():
            continue
        try:
            saved = load_run(cfg, folder.name)
        except ValueError:
            continue
        if saved:
            runs.append(saved["meta"])
    return sorted(runs, key=lambda item: (item["time"], item["id"]), reverse=True)


def save_marks(cfg, run_id, marks, missed_extraction=(), unsupported_claims=()):
    """Reject unknown row IDs/invalid verdicts and store reviews atomically."""
    run = load_run(cfg, run_id)
    if run is None:
        raise ValueError("review does not exist")
    known = {r["id"] for r in run["requirements"]}
    if not isinstance(marks, dict) or not set(marks) <= known:
        raise ValueError("unknown requirement ID")
    if not all(v in VERDICTS for v in marks.values()):
        raise ValueError("unknown review verdict")
    missing = [str(x).strip() for x in missed_extraction if str(x).strip()]
    unsupported = [str(x).strip() for x in unsupported_claims if str(x).strip()]
    if any(len(x) > 4000 for x in missing + unsupported):
        raise ValueError("review text too long")
    data = {"marks": marks, "missed_extraction": missing,
            "unsupported_claims": unsupported, "updated": time.strftime("%Y-%m-%d %H:%M")}
    _write_json(_folder(cfg, run_id) / "review.json", data)
    return data


def summary(run):
    """Quality indicators are MANUALLY reviewed extraction coverage, not true recall."""
    marks = run["review"].get("marks") or {}
    counts = {v: sum(marks.get(row["id"], "") == v for row in run["requirements"]) for v in VERDICTS}
    added_missing = len(run["review"].get("missed_extraction") or [])
    unsupported = len(run["review"].get("unsupported_claims") or [])
    applicable = counts["covered"] + counts["missing"] + counts["distorted"] + added_missing
    return {"total_extracted": len(run["requirements"]), "reviewed": len(run["requirements"]) - counts[""],
            "applicable_reviewed": applicable,
            "covered": counts["covered"], "missing": counts["missing"] + added_missing,
            "distorted": counts["distorted"], "not_applicable": counts["not_applicable"],
            "unreviewed": counts[""], "missed_extraction": added_missing,
            "unsupported_claims": unsupported,
            "coverage_of_reviewed_applicable": round(counts["covered"] / applicable, 4) if applicable else None}


def export_summary(run):
    """No filenames, source quotes, draft text or model credentials; share only aggregated stats."""
    meta = run["meta"]
    return {"format": FORMAT, "mint": meta["mint"], "model": meta["model"],
            "prompt_signature": meta["prompt_signature"], "input_fingerprint": meta["input_fingerprint"],
            "metrics": meta.get("metrics") or {}, "summary": summary(run),
            "caveat": "Manual review of extracted source items, not proof of complete document quality or true recall."}


def compare(first, second):
    """Only an identical input fingerprint, and only aggregate human-rated outcomes."""
    if first["meta"]["input_fingerprint"] != second["meta"]["input_fingerprint"]:
        raise ValueError("Different template or source versions")
    a, b = summary(first), summary(second)
    return {"before": a, "after": b,
            "covered_delta": b["covered"] - a["covered"],
            "missed_delta": b["missing"] - a["missing"],
            "unsupported_delta": b["unsupported_claims"] - a["unsupported_claims"],
            "caveat": "Differences in reviewed scope or extraction may invalidate direct quality comparisons."}

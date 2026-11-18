"""Offline, labelled quality benchmark for documentary evidence and draft coverage.

This is a MEASUREMENT tool, not another audit/LLM checker. It invokes Mint's
existing evidence gate and the draft's existing candidate calculation.

Synthetic fixtures and scripted model output exercise the rules deterministically.
They do NOT estimate real-world precision/recall of an LLM on user documents.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

from .evidence import quoted, verify_comparison

EVALUATION_VERSION = "document-quality-v1"


def load_cases(path):
    """Read independently labelled JSONL; reject silent omission/duplicate cases."""
    rows = []
    seen = set()
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"].strip():
            raise ValueError(f"{path}:{line_no}: every case needs a nonempty ID")
        if row["id"] in seen:
            raise ValueError(f"{path}:{line_no}: duplicate case ID {row['id']}")
        seen.add(row["id"])
        rows.append(row)
    if not rows:
        raise ValueError(f"{path}: no labelled cases")
    return rows


def dataset_fingerprint(*datasets):
    """The exact texts and labels matter, not merely their case count."""
    canonical = json.dumps(datasets, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def classification(rows):
    """Confusion matrix for one binary question. Zero denominator => undefined, not 100%."""
    tp = sum(bool(x["gold"]) and bool(x["predicted"]) for x in rows)
    fp = sum(not x["gold"] and bool(x["predicted"]) for x in rows)
    fn = sum(bool(x["gold"]) and not x["predicted"] for x in rows)
    tn = sum(not x["gold"] and not x["predicted"] for x in rows)
    return {"total": len(rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(tp / (tp + fp), 4) if tp + fp else None,
            "recall": round(tp / (tp + fn), 4) if tp + fn else None}


def checked_predictions(cases, supplied):
    """Require one full model payload for each exact test ID; do not silently fill gaps."""
    expected = {c["id"] for c in cases}
    if supplied is None:
        return {c["id"]: c["model"] for c in cases}
    if not isinstance(supplied, list):
        raise ValueError("Predictions must be JSONL rows")
    provided = {}
    for r in supplied:
        if not isinstance(r, dict) or not isinstance(r.get("id"), str):
            raise ValueError("Each prediction needs an id")
        if r["id"] in provided:
            raise ValueError(f"Duplicate prediction for {r['id']}")
        if not isinstance(r.get("model"), dict):
            raise ValueError(f"Missing full model comparison for {r['id']}")
        provided[r["id"]] = r["model"]
    if expected != set(provided):
        raise ValueError(f"Predictions do not match dataset IDs: missing={sorted(expected-set(provided))}; "
                         f"extra={sorted(set(provided)-expected)}")
    return provided


def evidence_results(cases, predictions=None):
    """Run the existing Mint evidence gate on 40 labelled pairs."""
    provided = checked_predictions(cases, predictions)
    rows = []
    for case in cases:
        if case.get("mode") not in {"audit", "draft"} or not isinstance(case.get("gold_conflict"), bool):
            raise ValueError(f"{case.get('id')}: missing mode or independent binary label")
        model = provided[case["id"]]
        result = verify_comparison(case["claim"], case["norm"], model)
        status = result["status"]
        rows.append({"id": case["id"], "mode": case["mode"], "group": case["group"],
                     "gold": case["gold_conflict"], "predicted": status == "conflict",
                     "status": status, "expected_status": case.get("expected_status", ""),
                     "quote_pair_valid": quoted(model.get("claim_quote"), case["claim"]) and
                                         quoted(model.get("norm_quote"), case["norm"])})
    groups = {key: classification([r for r in rows if r["group"] == key])
              for key in sorted({r["group"] for r in rows})}
    modes = {mode: classification([r for r in rows if r["mode"] == mode]) for mode in ("audit", "draft")}
    return {"scores": classification(rows), "groups": groups, "modes": modes,
            "statuses": dict(sorted(Counter(r["status"] for r in rows).items())),
            "grounded_pairs": sum(r["quote_pair_valid"] for r in rows),
            "errors": [{"id": r["id"], "group": r["group"], "gold": r["gold"],
                        "status": r["status"]} for r in rows if r["predicted"] != r["gold"]],
            "cases": rows}


def coverage_results(cases):
    """Judge review *candidates*, not claims of verified omissions.

    The gold 'applicable/reflected' labels are deliberately independent of
    selected/used: referencing a source ID does not guarantee faithful coverage.
    """
    from .template_draft import unresolved_candidates

    rows = []
    for case in cases:
        items = case.get("requirements")
        if not isinstance(items, list) or not items:
            raise ValueError(f"{case.get('id')}: empty requirements list")
        ids = [r["id"] for r in items]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{case.get('id')}: duplicate requirement IDs")
        selected = [r["id"] for r in items if r["selected"]]
        used = {r["id"] for r in items if r["used"]}
        if not used <= set(selected):
            raise ValueError(f"{case.get('id')}: used references were not in section candidates")
        plan = {case["section"]: {"selected_ids": selected}}
        pending = set(unresolved_candidates(plan, used)[case["section"]])
        for requirement in items:
            if not all(isinstance(requirement[k], bool) for k in ("applicable", "reflected", "selected", "used")):
                raise ValueError(f"{case['id']}: invalid boolean label")
            rows.append({"id": f"{case['id']}:{requirement['id']}", "section": case["section"],
                         "gold": requirement["applicable"] and not requirement["reflected"],
                         "predicted": requirement["id"] in pending})
    return {"scores": classification(rows), "cases": rows,
            "errors": [{"id": r["id"], "gold": r["gold"], "candidate": r["predicted"]}
                       for r in rows if r["predicted"] != r["gold"]]}


def evaluate(evidence_cases, coverage_cases, predictions=None):
    """One comparable report with exact dataset fingerprint and explicit caveats."""
    names = [c["id"] for c in evidence_cases + coverage_cases]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate IDs across evidence and coverage datasets")
    result = {"version": EVALUATION_VERSION, "dataset_sha256": dataset_fingerprint(evidence_cases, coverage_cases),
              "dataset_kind": "synthetic", "prediction_mode": "scripted" if predictions is None else "supplied",
              "limitations": [
                  "Scripted responses do not measure LLM or retrieval quality.",
                  "Correct quotations and a model's applicability explanation do not prove legal applicability.",
                  "Unresolved source IDs are review candidates, not confirmed omissions.",
                  "No production documents or actual gateway calls are included.",
              ]}
    result["evidence"] = evidence_results(evidence_cases, predictions)
    result["coverage"] = coverage_results(coverage_cases)
    return result


def compare_reports(current, baseline):
    """Only paired identical cases with identical method and prediction mode."""
    for key in ("version", "dataset_sha256", "dataset_kind", "prediction_mode"):
        if current.get(key) != baseline.get(key):
            raise ValueError(f"Incompatible reports: {key}")
    out = {}
    for name in ("evidence", "coverage"):
        old = baseline[name]["scores"]
        new = current[name]["scores"]
        old_cases = {x["id"]: x for x in baseline[name]["cases"]}
        new_cases = {x["id"]: x for x in current[name]["cases"]}
        if old_cases.keys() != new_cases.keys() or old["total"] != new["total"]:
            raise ValueError(f"Incompatible case set: {name}")
        improved = [k for k in new_cases if old_cases[k]["predicted"] != old_cases[k]["gold"]
                    and new_cases[k]["predicted"] == new_cases[k]["gold"]]
        worsened = [k for k in new_cases if old_cases[k]["predicted"] == old_cases[k]["gold"]
                    and new_cases[k]["predicted"] != new_cases[k]["gold"]]
        out[name] = {"tp_delta": new["tp"] - old["tp"], "fp_delta": new["fp"] - old["fp"],
                     "fn_delta": new["fn"] - old["fn"], "improved_ids": sorted(improved),
                     "worsened_ids": sorted(worsened)}
    return out

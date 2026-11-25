"""Pre-decomposition review: draft summaries and explicit expert scope.

A summary is a navigation aid, not new evidence. Original records and model
decisions remain intact. Expert notes guide derivation but cannot authorize
unsupported facts or bypass its independent checks.
"""
from collections import Counter
import hashlib
import json

from .draft_checkpoint import _identity
from .draft_function_analysis import _compact, _valid_refs
from .draft_progress import tracked
from .prompts import prompts_version
from .template_draft import DraftError, _candidate_budget, _numbers_supported, _text

MAX_NOTE = 800
MAX_SUMMARY = 2400


def input_identity(cfg, prepared, profile):
    data = {"hashes": prepared["hashes"], "roles": prepared["roles"],
            "context": prepared["context"], "profile": profile,
            "kb": str(cfg.kb_path), "prompt_version": prompts_version(),
            "model_identity": _identity(cfg, "", "", stage="target_derivation")}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def summarize_needs(cfg, groups, records, decisions, state, context, emit, ask):
    """Bounded review summaries covering all model-supported change candidates.

    On error or partial/invalid refs, show original quotes instead. All source
    records remain available, including items not included in a summary.
    """
    budget = _candidate_budget(cfg)
    def payload(group, ids):
        refs = list(dict.fromkeys(k for rid in ids for k in
                    decisions[rid].get("state_refs", []) + decisions[rid].get("reference_refs", [])
                    + decisions[rid].get("dossier_refs", [])))
        return {"context": context, "function": group["function"],
                "needs": [_compact(records[rid]) for rid in ids],
                "decisions": {rid: decisions[rid] for rid in ids},
                "evidence": [_compact(state[k]) for k in refs]}

    def size(value):
        return len(json.dumps(value, ensure_ascii=False))

    jobs = []
    for group in groups:
        batch = []
        for rid in group["requirement_ids"]:
            if decisions[rid]["change"] == "already_supported":
                continue
            if batch and (len(batch) >= 8 or size(payload(group, batch + [rid])) > budget):
                jobs.append((group, batch))
                batch = []
            batch.append(rid)
        if batch:
            jobs.append((group, batch))
    summaries = {g["id"]: [] for g in groups}
    counts = Counter()
    for group, ids in tracked(emit, "target_summary", jobs):
        data = payload(group, ids)
        row = {"need_refs": list(ids), "text": "", "status": "context_limit",
               "evidence_refs": []}
        if size(data) <= budget:
            try:
                reply = ask(cfg, "target_summary", data)
            except DraftError:
                row["status"] = "error"
            else:
                allowed = {r["id"] for r in data["evidence"]}
                need_refs = _valid_refs(reply, "need_refs", set(ids))
                refs = _valid_refs(reply, "evidence_refs", allowed)
                text = _text(reply, "text")
                if (need_refs is not None and set(need_refs) == set(ids)
                        and refs is not None and text and len(text) <= MAX_SUMMARY
                        and _numbers_supported(text, need_refs + refs, {**records, **state})):
                    row.update(text=text, status="draft", evidence_refs=refs)
                else:
                    row["status"] = "invalid"
        # Empty text is intentional: UI renders the original records verbatim.
        summaries[group["id"]].append(row)
        counts[row["status"]] += 1
    return summaries, dict(counts)


def review_scope(collected, selection=None, notes=None):
    """Only accept known, verified change candidates. Never modify evidence.

    None is the automatic mode; an explicit set (even empty) is an expert
    decision. Existing-state items stay available to included groups.
    """
    decisions = collected["decisions"]
    available = {rid for g in collected["groups"] for rid in g["requirement_ids"]
                 if decisions[rid]["change"] != "already_supported"}
    selected = available if selection is None else set(selection)
    if not selected <= available:
        raise ValueError("Unknown or unverified requirement selection")
    notes = {} if notes is None else notes
    allowed_groups = {g["id"] for g in collected["groups"]
                      if selected.intersection(g["requirement_ids"])}
    if (not isinstance(notes, dict) or set(notes) - allowed_groups
            or any(not isinstance(v, str) or len(v) > MAX_NOTE for v in notes.values())):
        raise ValueError("Invalid expert notes")
    if selection is None and notes:
        raise ValueError("Expert notes require explicit scope")
    included = [{**g, "requirement_ids": [rid for rid in g["requirement_ids"]
                  if rid in selected or decisions[rid]["change"] == "already_supported"]}
                for g in collected["groups"]
                if selected.intersection(g["requirement_ids"])]
    return included, {"mode": "automatic" if selection is None else "expert",
                      "included": sorted(selected), "excluded": sorted(available - selected),
                      "notes": {k: v.strip() for k, v in notes.items() if v.strip()}}

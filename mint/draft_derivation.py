"""Experimental V2 derivation of target-specific requirements.

Need and current-state evidence have distinct roles. A source-backed allocation
is a proposal, not permission to invent implementation choices. A second model
assessment is useful evidence for review, never an expert approval.
"""
from collections import Counter
import json

from .document_context import confirm_context
from .draft_function_analysis import _compact, _unique_answers, _valid_refs, names_target, is_target
from .draft_registry import obligation_candidates
from .template_draft import (DraftError, _json, _numbers_supported,
                             _record_draft_diagnostic, _text, _candidate_budget)

_MAX_ITEMS = 6
_MAX_TEXT = 1200


def _proposal(row, rid, allocation, records, constraint_ids, target):
    """Validate structural provenance, not semantic entailment."""
    text, actor, reason = (_text(row, key) for key in ("text", "actor", "reason"))
    mode = _text(row, "mode")
    need = _valid_refs(row, "need_refs", {rid})
    state = _valid_refs(row, "state_refs", set(allocation["state_refs"]))
    constraints = _valid_refs(row, "constraint_refs", constraint_ids)
    if (mode not in {"explicit", "derived"} or not text or len(text) > _MAX_TEXT
            or not is_target(actor, target) or not reason
            or need != [rid] or not state or constraints is None):
        return None
    refs = need + state + constraints
    if not _numbers_supported(text, refs, records):
        return None
    return {"text": text, "actor": target, "mode": mode, "reason": reason,
            "need_refs": need, "state_refs": state, "constraint_refs": constraints}


def validate_candidates(reply, rid, allocation, records, target):
    """Reuse the same structural gate for initial and repaired decompositions."""
    items = reply.get("requirements")
    if (_text(reply, "status") != "proposed" or not isinstance(items, list)
            or not 1 <= len(items) <= _MAX_ITEMS
            or any(not isinstance(item, dict) for item in items)):
        return [], "invalid_response"
    candidates = [_proposal(item, rid, allocation, records, set(), target) for item in items]
    if any(item is None for item in candidates):
        return [], "invalid_proposal"
    texts = [" ".join(item["text"].split()).casefold() for item in candidates]
    if len(set(texts)) != len(texts):
        return [], "duplicate_proposal"
    return candidates, ""


def _assessment(cfg, candidate, records, target):
    """Separate assessment of attribution, support and invented decisions.

    Explicit true booleans are required. An ambiguous or incomplete response
    remains unverified even when the proposed text itself is plausible.
    """
    refs = candidate["need_refs"] + candidate["state_refs"] + candidate["constraint_refs"]
    try:
        answer = _json(cfg, "requirement_assessment", {
            "target": target, "candidate": candidate,
            "evidence": [_compact(records[rid]) for rid in refs],
        })
    except DraftError:
        return "assessment_error"
    return _assessment_verdict(candidate, answer)


def _assessment_verdict(candidate, answer):
    checks = ("supported", "correct_actor", "no_new_decisions")
    candidate["assessment_reason"] = _text(answer, "reason")[:_MAX_TEXT]
    if type(answer.get("repairable")) is bool:
        candidate["repairable"] = answer["repairable"]
    if all(answer.get(key) is True for key in checks) and _text(answer, "reason"):
        return "model_supported"
    if any(answer.get(key) is False for key in checks):
        return "needs_review"
    return "assessment_incomplete"


def assess_candidates(cfg, candidates, records, target, emit):
    """Evaluate independent candidates in small bounded batches; never share verdicts."""
    def payload(candidate):
        refs = candidate["need_refs"] + candidate["state_refs"] + candidate["constraint_refs"]
        return {"id": candidate["id"], "candidate": candidate,
                "evidence": [_compact(records[rid]) for rid in refs]}

    def assess(batch):
        if not batch:
            return
        if len(batch) == 1:
            candidate = batch[0]
            emit("requirement_assessment", int(candidate["id"][1:]))
            candidate["assessment"] = _assessment(cfg, candidate, records, target)
            return
        emit("requirement_assessment", int(batch[-1]["id"][1:]))
        allowed = {candidate["id"]: candidate for candidate in batch}
        try:
            rows = _json(cfg, "requirement_assessment", {
                "target": target, "items": [payload(candidate) for candidate in batch]})
        except DraftError:
            for candidate in batch:
                candidate["assessment"] = "assessment_error"
            return
        # Reuse the same individual semantic checks; reject missing and repeated ids.
        replies, duplicates = {}, set()
        for row in rows.get("items", []) if isinstance(rows.get("items"), list) else []:
            if not isinstance(row, dict):
                continue
            rid = _text(row, "id")
            if rid in allowed:
                if rid in replies:
                    duplicates.add(rid)
                replies[rid] = row
        for rid, candidate in allowed.items():
            candidate["assessment"] = (_assessment_verdict(candidate, replies[rid])
                                       if rid in replies and rid not in duplicates
                                       else "assessment_incomplete")

    batch = []
    budget = _candidate_budget(cfg)
    for candidate in candidates:
        proposed = batch + [candidate]
        if batch and (len(proposed) > 4 or len(json.dumps(
                {"target": target, "items": [payload(c) for c in proposed]},
                ensure_ascii=False)) > budget):
            assess(batch)
            batch = []
        batch.append(candidate)
    assess(batch)


def derive_requirements(cfg, records, analysis, context, emit):
    """Produce reviewable platform-requirement candidates and explicit gaps.

    Only functional obligations assigned to the target enter
    the first pilot. Other actors are not silently promoted. Cross-cutting
    candidates have not yet been allocated and are never passed as authority.
    The result retains a disposition for every functional obligation and
    all pending cross-cutting, open-question and untyped IDs.
    """
    target = confirm_context(context)["target"]
    obligations = obligation_candidates(records)
    functional = {rid: row for rid, row in obligations.items()
                  if row["kind"] == "functional"}
    dispositions = dict.fromkeys(functional, "allocation_unresolved")
    proposed, questions = [], []
    unexpected = calls = 0
    for rid, need in functional.items():
        allocation = analysis.get("allocations", {}).get(rid, {})
        if allocation.get("status") != "proposed":
            continue
        category = allocation.get("category")
        if category == "other" or (category == "interaction" and not is_target(allocation.get("actor", ""), target)):
            dispositions[rid] = "external_proposal"
            continue
        if category not in {"target", "shared", "interaction"}:
            continue
        # Do not trust IDs from a stale/inconsistent intermediate artifact.
        allowed_state = {k for k, row in records.items()
                         if row["kind"] == "current_state"
                         and row["typing_status"] == "classified"}
        state_refs = _valid_refs(allocation, "state_refs", allowed_state)
        direct = (allocation.get("direct") is True and category == "target"
                  and names_target(need["quote"], target))
        if state_refs is None or (not state_refs and not direct):
            dispositions[rid] = "invalid_allocation_evidence"
            continue
        if category in {"target", "interaction"} and not is_target(allocation.get("actor", ""), target):
            dispositions[rid] = "invalid_allocation_actor"
            continue
        if direct and not state_refs:
            # Preserve the original explicit obligation rather than inventing
            # a refinement without architecture. Independent assessment and
            # the section-wide need coverage gate still apply.
            item = {"id": "P" + str(len(proposed) + 1),
                    "text": need["quote"], "actor": target, "mode": "explicit",
                    "reason": allocation["reason"], "need_refs": [rid],
                    "state_refs": [], "constraint_refs": []}
            proposed.append(item)
            dispositions[rid] = "pending_assessment"
            continue
        calls += 1
        emit("requirement_derivation", calls)
        answers, statuses, extra = _unique_answers(cfg, "requirement_derivation", {
            "target": target, "items": [_compact(need)],
            "allocation": allocation,
            "current_state": [_compact(records[k]) for k in state_refs],
            # Cross-cutting applicability is unresolved in phase 2.
            "constraints": [],
        }, [rid])
        unexpected += extra
        if rid not in answers:
            dispositions[rid] = statuses[rid]
            continue
        reply = answers[rid]
        status = _text(reply, "status")
        if status == "open_question":
            question = _text(reply, "question")
            if question and len(question) <= _MAX_TEXT:
                questions.append({"need_id": rid, "question": question})
                dispositions[rid] = "open_question"
            else:
                dispositions[rid] = "invalid_response"
            continue
        candidates, error = validate_candidates(reply, rid, allocation, records, target)
        if error:
            dispositions[rid] = error
            continue
        for item in candidates:
            item["id"] = "P" + str(len(proposed) + 1)
            proposed.append(item)
        dispositions[rid] = "pending_assessment"

    assess_candidates(cfg, proposed, records, target, emit)
    per_need = {}
    for item in proposed:
        per_need.setdefault(item["need_refs"][0], []).append(item["assessment"])
    for rid, verdicts in per_need.items():
        dispositions[rid] = ("model_supported_candidates" if
                             all(v == "model_supported" for v in verdicts) else "needs_review")

    _record_draft_diagnostic("requirement_derivation", {
        "requests": calls, "unexpected_rows": unexpected,
        "disposition_counts": dict(Counter(dispositions.values())),
        "assessment_counts": dict(Counter(row["assessment"] for row in proposed)),
    })
    return {"requirements": proposed, "dispositions": dispositions,
            "generated_questions": questions,
            "cross_cutting_ids": list(analysis.get("cross_cutting_ids", [])),
            "open_question_ids": list(analysis.get("open_question_ids", [])),
            "untyped_ids": list(analysis.get("untyped_ids", []))}

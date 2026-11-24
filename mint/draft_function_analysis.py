"""Experimental V2 function grouping and evidence-backed responsibility proposals.

Every functional obligation gets a disposition, even on incomplete model output.
Groups are batch-local provisional units, not proof of complete functional analysis.
Reuse the registry, scope vocabulary, ranked source candidates and model gateway.
"""
from collections import Counter
import json
import re

from .draft_checkpoint import DraftStageCheckpoint
from .document_context import confirm_context, context_search_terms
from .draft_registry import obligation_candidates
from .requirement_scope import CATEGORIES
from .template_draft import (DraftError, _batches, _candidate_budget, _candidates,
                             _json, _records, _record_draft_diagnostic, _text)

_GROUP_LIMIT = 8


def _unique_answers(cfg, stage, payload, allowed):
    """A missing or repeated ID cannot yield a usable model decision."""
    statuses = dict.fromkeys(allowed, "missing_response")
    accepted = {}
    unexpected = 0
    try:
        rows = _records(_json(cfg, stage, payload), "items")
    except DraftError:
        return {}, dict.fromkeys(allowed, "batch_error"), 0
    for row in rows:
        rid = _text(row, "id")
        if rid not in statuses:
            unexpected += 1
            continue
        if statuses[rid] != "missing_response":
            statuses[rid] = "duplicate_response"
            accepted.pop(rid, None)
            continue
        statuses[rid] = "received"
        accepted[rid] = row
    return accepted, statuses, unexpected


def _compact(row):
    return {key: row[key] for key in ("id", "source", "section", "quote", "kind", "source_role")}


def _group_functions(cfg, functional, context, emit, budget, *, reset_cache=False):
    groups, dispositions = [], {}
    unexpected = calls = cache_hits = 0
    checkpoint = DraftStageCheckpoint(cfg, "function_group")
    values = list(functional.values())
    for offset in range(0, len(values), _GROUP_LIMIT):
        for batch in _batches(values[offset:offset + _GROUP_LIMIT],
                              lambda r: r["quote"] + r["section"] + r["source"],
                              size=budget):
            calls += 1
            emit("function_group", calls)
            allowed = {row["id"]: row for row in batch}
            payload = {"context": context, "items": [_compact(row) for row in batch]}
            cached = None if reset_cache else checkpoint.load(payload)
            if (cached is not None and set(cached) == set(allowed)
                    and all(cached.get(anchor) == anchor for anchor in cached.values())):
                cache_hits += 1
                replies = {rid: {"id": rid, "group": anchor} for rid, anchor in cached.items()}
                status, extra = dict.fromkeys(allowed, "received"), 0
            else:
                replies, status, extra = _unique_answers(cfg, "function_group", payload, allowed)
            unexpected += extra
            # Each group anchor must itself be a valid self-assigned input ID.
            anchors = {rid for rid, row in replies.items() if _text(row, "group") == rid}
            by_anchor = {}
            for rid in allowed:
                if rid not in replies:
                    continue
                anchor = _text(replies[rid], "group")
                if anchor not in anchors:
                    status[rid] = "invalid_group"
                else:
                    status[rid] = "grouped"
                    by_anchor.setdefault(anchor, []).append(rid)
            for anchor, ids in by_anchor.items():
                groups.append({"id": "G" + str(len(groups) + 1),
                               "anchor_id": anchor, "requirement_ids": ids})
            dispositions.update(status)
            if all(value == "grouped" for value in status.values()):
                checkpoint.save(payload, {rid: _text(row, "group") for rid, row in replies.items()})
    _record_draft_diagnostic("function_group", {
        "batches": calls, "cache_hits": cache_hits, "unexpected_rows": unexpected, "groups": len(groups),
        "status_counts": dict(Counter(dispositions.values())),
    })
    return groups, dispositions


def _valid_refs(row, key, allowed):
    refs = row.get(key)
    if (not isinstance(refs, list) or
            any(not isinstance(rid, str) or rid not in allowed for rid in refs)
            or len(refs) != len(set(refs))):
        return None
    return refs


def target_names(target):
    """Only aliases explicitly included by the user in the confirmed target."""
    names = [target] if target else []
    match = re.fullmatch(r"(.+?)\s*\(([A-ZА-ЯЁ0-9][A-ZА-ЯЁ0-9 -]{1,29})\)", target or "")
    if match:
        names.extend((match.group(1).strip(), match.group(2).strip()))
    return tuple(dict.fromkeys(names))


def is_target(actor, target):
    return bool(actor and any(actor.casefold() == name.casefold() for name in target_names(target)))


def names_target(quote, target):
    """Conservative literal guard, not proof that the target is the actor."""
    return any(re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", quote, re.I)
               for name in target_names(target))



def _allocation_candidates(query, queries, state, budget):
    """Reuse BM25 and reserve part of the evidence budget for each obligation."""
    if not state or budget <= 0:
        return []
    if sum(len(row["quote"]) + 95 for row in state.values()) <= budget:
        return list(state.values())
    selected, used = {}, 0
    def add(rows):
        nonlocal used
        for row in rows:
            cost = len(row["quote"]) + 95
            if row["id"] not in selected and used + cost <= budget:
                selected[row["id"]] = row
                used += cost
    each = budget // (2 * max(1, len(queries)))
    for need in queries:
        add(_candidates(need, state, size=each))
    add(_candidates(query, state, size=budget))
    return list(selected.values())


def analyze_functions(cfg, records, context, emit, *, reset_cache=False):
    """Return provisional groups, per-obligation allocations and all unresolved IDs.

    Context is human-confirmed. Evidence links show which source records were
    selected; a plausible model explanation is NOT independent semantic proof.
    Nonfunctional/constraint candidates and open questions remain separately
    visible; bounded retrieval can omit relevant context and cannot certify
    completeness. Nothing here renders Word or approves a new obligation.
    """
    context = confirm_context(context)
    candidates = obligation_candidates(records)
    functional = {rid: row for rid, row in candidates.items() if row["kind"] == "functional"}
    cross_cutting = {rid: row for rid, row in candidates.items() if row["kind"] != "functional"}
    state = {rid: row for rid, row in records.items()
             if row["kind"] == "current_state" and row["typing_status"] == "classified"}
    questions = {rid: row for rid, row in records.items()
                 if row["kind"] == "open_question" and row["typing_status"] == "classified"}
    # Keep grouping compact. Allocate a larger budget to actual evidence, not instructions.
    total_budget = _candidate_budget(cfg)
    budget = min(4000, total_budget // 2)
    groups, dispositions = _group_functions(cfg, functional, context, emit, budget, reset_cache=reset_cache)
    allocations = {rid: {"status": "not_grouped", "category": "uncertain",
                         "actor": "", "reason": "", "state_refs": []} for rid in functional}
    unexpected = 0
    context_limited_groups = expanded_groups = 0

    def evidence_payload(ids, state_cap):
        base = {"context": context, "items": [_compact(functional[rid]) for rid in ids],
                "target_names": list(target_names(context["target"]))}
        if len(json.dumps(base, ensure_ascii=False)) > total_budget:
            return None
        query = " ".join([context_search_terms(context)] +
                         [functional[rid]["quote"] for rid in ids])
        remaining = max(0, total_budget - len(json.dumps(base, ensure_ascii=False)) - 256)
        state_rows = _allocation_candidates(query, [functional[rid]["quote"] for rid in ids],
                                            state, min(state_cap, remaining * 3 // 4))
        cross_rows = _candidates(query, cross_cutting, size=min(budget // 2, remaining // 8))
        question_rows = _candidates(query, questions, size=min(budget // 2, remaining // 8))
        payload = {**base, "current_state": [_compact(row) for row in state_rows],
                   "constraints": [_compact(row) for row in cross_rows],
                   "open_questions": [_compact(row) for row in question_rows]}
        # Candidate estimates omit JSON metadata; enforce the actual bound.
        while len(json.dumps(payload, ensure_ascii=False)) > total_budget:
            removable = payload["open_questions"] or payload["constraints"] or payload["current_state"]
            if not removable:
                return None
            removable.pop()
        return payload

    def allocate(ids, payload, index):
        nonlocal unexpected
        allowed_state = {row["id"] for row in payload["current_state"]}
        emit("function_allocation", index)
        answers, statuses, extra = _unique_answers(cfg, "function_allocation", payload, ids)
        unexpected += extra
        decisions = {}
        for rid in ids:
            result = {"status": statuses[rid], "category": "uncertain",
                      "actor": "", "reason": "", "state_refs": []}
            decisions[rid] = result
            if rid not in answers:
                continue
            row = answers[rid]
            category, actor, reason = (_text(row, k) for k in ("category", "actor", "reason"))
            refs = _valid_refs(row, "state_refs", allowed_state)
            if category not in CATEGORIES or refs is None or not reason:
                result["status"] = "invalid_response"
                continue
            if category == "uncertain":
                result.update(status="explicit_uncertain", reason=reason, state_refs=refs,
                              needs_more_state=row.get("needs_more_state") is True)
                continue
            same_actor = is_target(actor, context["target"])
            direct = (row.get("direct") is True and category == "target" and same_actor
                      and names_target(functional[rid]["quote"], context["target"]))
            if not actor or (not refs and not direct) or (category == "target" and not same_actor) or (
                    category == "other" and same_actor):
                result["status"] = "unsupported_assignment"
                continue
            result.update(status="proposed", category=category,
                          actor=context["target"] if same_actor else actor,
                          reason=reason, state_refs=refs)
            if direct:
                result["direct"] = True
        return decisions

    for index, group in enumerate(groups, 1):
        ids = group["requirement_ids"]
        payload = evidence_payload(ids, 10000)
        if payload is None:
            for rid in ids:
                allocations[rid]["status"] = "allocation_context_limit"
            continue
        allowed_state = {row["id"] for row in payload["current_state"]}
        group.update(state_candidate_ids=[row["id"] for row in payload["current_state"]],
                     cross_cutting_candidate_ids=[row["id"] for row in payload["constraints"]],
                     question_candidate_ids=[row["id"] for row in payload["open_questions"]],
                     context_limited=(len(allowed_state) < len(state) or
                                      len(payload["constraints"]) < len(cross_cutting) or
                                      len(payload["open_questions"]) < len(questions)))
        context_limited_groups += int(group["context_limited"])
        if not allowed_state and not any(names_target(functional[rid]["quote"], context["target"])
                                         for rid in ids):
            for rid in ids:
                allocations[rid]["status"] = "no_state_evidence"
            continue
        allocations.update(allocate(ids, payload, index))
        # Only retry genuine evidence gaps, with new evidence and a smaller set
        # of obligations. Never repeat a failed/malformed technical response.
        pending = [rid for rid in ids if allocations[rid].get("needs_more_state")]
        if pending and len(allowed_state) < len(state):
            expanded = evidence_payload(pending, 16000)
            if expanded is not None:
                expanded_ids = {row["id"] for row in expanded["current_state"]}
                if expanded_ids - allowed_state:
                    expanded_groups += 1
                    group["expanded_state_candidate_ids"] = [row["id"] for row in expanded["current_state"]]
                    retry = allocate(pending, expanded, index)
                    for rid, result in retry.items():
                        if result["status"] in {"proposed", "explicit_uncertain"}:
                            allocations[rid] = result
                    group["expansion_status_counts"] = dict(Counter(row["status"] for row in retry.values()))
    _record_draft_diagnostic("function_allocation", {
        "unexpected_rows": unexpected, "context_limited_groups": context_limited_groups,
        "expanded_groups": expanded_groups,
        "status_counts": dict(Counter(row["status"] for row in allocations.values())),
        "cross_cutting_pending": len(cross_cutting), "open_questions": len(questions),
    })
    return {"groups": groups, "grouping": dispositions, "allocations": allocations,
            "cross_cutting_ids": list(cross_cutting), "open_question_ids": list(questions),
            "untyped_ids": [rid for rid, row in records.items()
                            if row["typing_status"] not in {"classified", "structural"}]}

"""Evidence-first analysis before Word. Reuses the existing source registry and hybrid search.

The profile is a reviewable hypothesis, not an authority for new obligations.
Every original fragment is screened; retrieval ranks supporting evidence and
never substitutes for the original. All outputs are local, not expert approval.
"""
from collections import Counter
import hashlib
import json
import re

from .document_context import confirm_context
from .draft_progress import tracked
from .draft_references import ReferenceMap
from .draft_dossiers import collect_dossiers, merge_dossier_quotes, dossier_context, summarize_dossiers
from .draft_checkpoint import DraftStageCheckpoint
from .draft_function_analysis import _compact, _unique_answers, _valid_refs, is_target, names_target
from .draft_registry import build_registry, OBLIGATION_KINDS
from .draft_derivation import assess_candidates
from .glossary import Glossary
from .kb import load_kb_snapshot, source_path
from .search import search_parent_child
from .template_draft import (DraftError, _batches, _candidate_budget, _json,
                             _load_draft_sources, _measure_draft, _normalized, _candidates,
                             _numbers_supported, _record_draft_diagnostic,
                             _source_chunks, _text)
from .i18n import tr

SECTION_ROLES = frozenset({"need", "interface", "metric", "architecture", "constraint",
                           "business", "reference", "unknown"})
DECISIONS = frozenset({"new", "change", "already_supported", "external", "unknown",
                       "explicit"})
_MAX_PROFILE = 20
_MAX_TEXT = 1200


def _payload_size(payload):
    return len(json.dumps(payload, ensure_ascii=False))


def _bounded_rows(rows, budget):
    """Never silently truncate an original quotation; retain candidate order."""
    used, selected = 0, []
    for row in rows:
        cost = _payload_size(row) + 2
        if used + cost <= budget:
            selected.append(row)
            used += cost
    return selected


def _map_sources(documents, roles):
    spans, sections = {}, {}
    for name, markdown in documents:
        for index, (path, text) in enumerate(_source_chunks(markdown, full_path=True), 1):
            key = (name, path)
            if key not in sections:
                sections[key] = {"id": "S" + str(len(sections) + 1), "source": name,
                                 "section": path, "source_role": roles.get(name, "unspecified"),
                                 "sample": text[:600], "role": "unknown"}
            sid = "F" + str(len(spans) + 1)
            spans[sid] = {"id": sid, "source": name, "section": path, "fragment": index,
                          "text": text, "section_id": sections[key]["id"]}
    return spans, {s["id"]: s for s in sections.values()}


def _classify_sections(cfg, sections, context, emit):
    rows = [{k: v for k, v in row.items() if k != "role"} for row in sections.values()]
    batches = list(_batches(rows, lambda row: json.dumps(row, ensure_ascii=False),
                            size=min(5000, _candidate_budget(cfg) // 2)))
    for index, batch in enumerate(tracked(emit, "target_section_map", batches), 1):
        emit("target_section_map", index)
        ids = [r["id"] for r in batch]
        replies, _, _ = _unique_answers(cfg, "target_section_map",
                                         {"context": context, "items": batch}, ids)
        for rid, row in replies.items():
            role = _text(row, "role")
            # Neutral prompt code; keep the existing internal role vocabulary.
            if role == "arch":
                role = "architecture"
            if role in SECTION_ROLES:
                sections[rid]["role"] = role


class OriginalEvidence:
    """Hybrid retrieval gives original-span hints. No index text becomes evidence.

    Legacy indices without hashes are labelled unverified, stale known revisions
    are excluded by the search kernel. Exact overlap links hints to original spans.
    A source absent from the index is still screened in full.
    """
    def __init__(self, cfg, spans, hashes):
        self.cfg, self.spans, self.hashes = cfg, spans, hashes
        self.snapshot = load_kb_snapshot(cfg)
        self.counts = Counter()
        self._find_cache = {}
        self.by_source = {}
        for sid, span in spans.items():
            self.by_source.setdefault(span["source"], []).append(sid)
        self.normalized = {sid: _normalized(row["text"]) for sid, row in spans.items()}
        self.revisions = Counter()
        indexed_sources = {row.get("source") for row in self.snapshot.parent_store.values()} if self.snapshot else set()
        for source, digest in hashes.items():
            indexed = (self.snapshot.documents or {}).get(source, {}).get("source_sha256") if self.snapshot else None
            status = ("missing" if source not in indexed_sources else
                      "unverified" if not indexed else "matched" if indexed == digest else "stale")
            self.revisions[status] += 1

    def find(self, query, sources=None, k=6):
        selected = set(self.hashes) if sources is None else set(sources) & set(self.hashes)
        if not selected or self.snapshot is None:
            self.counts["no_index"] += 1
            return []
        key = (query, tuple(sorted(selected)), k)
        if key in self._find_cache:
            self.counts["cache_hits"] += 1
            return list(self._find_cache[key])
        self.counts["queries"] += 1
        diagnostics = {}
        items, _ = search_parent_child(query[:min(600, self.cfg.max_query_chars,
                                                  self.cfg.cascade_split_chars)], self.cfg,
                                       k_neighbors=k, return_items=True, glossary=Glossary({}, {}),
                                       allow_sources=selected, expected_hashes=self.hashes,
                                       snapshot=self.snapshot, quiet=True, diagnostics=diagnostics)
        self.counts["dense_queries"] += int(diagnostics.get("dense") is True)
        self.counts["reranked_queries"] += int(bool(diagnostics.get("reranked")))
        self.counts["low_confidence"] += int(diagnostics.get("low_conf") is True)
        found = {}
        for item in items if isinstance(items, list) else []:
            for pid in item["ids"]:
                parent = self.snapshot.parent_store.get(pid, {})
                source = parent.get("source")
                if source not in selected:
                    continue
                # Multiple matching lines can identify the original span; never
                # use the search block's generated header as evidence.
                lines = [_normalized(line) for line in parent.get("text", "").splitlines()
                         if len(_normalized(line)) >= 35 and not line.startswith("#")]
                parent_text = _normalized(parent.get("text", ""))
                for sid in self.by_source.get(source, []):
                    original = self.normalized[sid]
                    if (parent_text and len(parent_text) >= 35 and parent_text in original
                            or len(original) >= 35 and original in parent_text
                            or any(line in original for line in lines)):
                        found[sid] = self.spans[sid]
        self.counts["matched_spans"] += len(found)
        if not found:
            self.counts["no_match"] += 1
        self._find_cache[key] = tuple(found)
        return list(found)


def _profile_candidates(cfg, spans, sections, roles, evidence, context, emit):
    preferred = {s for s, role in roles.items() if role in {"architecture", "mixed"}}
    # Do not exclude other selected sources: architecture can be in a mixed FT.
    queries = [context["target"] + " " + value for value in
               ("architecture components functions", "interfaces input output responsibility",
                "назначение функции компоненты границы", "интерфейсы обмен входы выходы")]
    ids = {}
    lookups = [(query, scope) for query in queries
               for scope in ([preferred, None] if preferred else [None])]
    for query, scope in tracked(emit, "target_profile_search", lookups):
        for sid in evidence.find(query, scope):
            ids[sid] = None
    # Full original sections supply evidence even with missing/stale index.
    for sid, span in spans.items():
        if sections[span["section_id"]]["role"] == "architecture":
            ids[sid] = None
    if not ids:
        pool = {sid: {"id": sid, "source": s["source"], "section": s["section"],
                      "quote": s["text"]} for sid, s in spans.items()}
        for row in _candidates(" ".join(queries), pool, size=_candidate_budget(cfg)):
            ids[row["id"]] = None
    return _bounded_rows((spans[sid] for sid in ids),
                         max(0, _candidate_budget(cfg) - _payload_size(context) - 1000))


def _validate_profile(answer, allowed):
    result = []
    for row in answer.get("functions", []) if isinstance(answer.get("functions"), list) else []:
        if not isinstance(row, dict):
            continue
        name = _text(row, "name")[:180]
        description = _text(row, "description")[:600]
        refs = _valid_refs(row, "refs", allowed)
        if not name or not description or not refs:
            continue
        if any(p["name"].casefold() == name.casefold() for p in result):
            continue
        result.append({"id": "C" + str(len(result) + 1), "name": name,
                       "description": description, "refs": refs})
        if len(result) >= _MAX_PROFILE:
            break
    return result


@_measure_draft
def prepare_target_analysis(cfg, sources, roles, context, progress=None):
    """Stage A/B: read actual originals, map sections, propose a bounded profile."""
    emit = progress or (lambda *_: None)
    context = confirm_context(context)
    issues, hashes, word_metadata = [], {}, {}
    documents = _load_draft_sources(cfg, sources, issues, source_hashes=hashes, emit=emit,
                                    word_metadata=word_metadata)
    spans, sections = _map_sources(documents, roles)
    references = ReferenceMap(documents, spans, emit, word_metadata)
    _classify_sections(cfg, sections, context, emit)
    evidence = OriginalEvidence(cfg, spans, hashes)
    candidates = _profile_candidates(cfg, spans, sections, roles, evidence, context, emit)
    profile = []
    for _ in tracked(emit, "target_profile", [1] if candidates else []):
        emit("target_profile", 1)
        try:
            answer = _json(cfg, "target_profile", {"context": context, "evidence": candidates})
            profile = _validate_profile(answer, {r["id"] for r in candidates})
        except DraftError:
            pass
    return {"documents": documents, "hashes": hashes, "spans": spans, "sections": sections,
            "profile": profile, "issues": issues, "context": context, "roles": dict(roles),
            "references": references,
            "profile_retrieval": dict(evidence.counts), "index_revisions": dict(evidence.revisions)}


def _metric_fields(reply, row, state, refs):
    """Keep quantitative values and units verbatim. Semantic attribution is reviewed separately."""
    data = reply.get("metric")
    if data is None:
        return None
    if not isinstance(data, dict):
        return False
    fields = ("subject", "value", "unit", "conditions", "level", "current_value", "target_value")
    metric = {k: _text(data, k)[:300] for k in fields}
    if not metric["subject"] or not metric["value"] or not metric["unit"] or metric["level"] not in {"current", "target", "unknown"}:
        return False
    need = _normalized(row["quote"])
    evidence = [need] + [_normalized(state[k]["quote"]) for k in refs]
    if _normalized(metric["value"]) not in need or _normalized(metric["unit"]) not in need:
        return False
    for key in ("current_value", "target_value"):
        if metric[key] and not any(_normalized(metric[key]) in quote for quote in evidence):
            return False
    return metric


def _validate_decision(reply, rid, records, allowed, profile, target):
    """A target claim needs explicit original need evidence; derived change needs state."""
    row = records[rid]
    category = _text(reply, "category")
    status = _text(reply, "change")
    actor = _text(reply, "actor")
    reason = _text(reply, "reason")[:_MAX_TEXT]
    component = _text(reply, "component")[:180]
    function = _text(reply, "function")[:180]
    refs = _valid_refs(reply, "state_refs", allowed)
    result = {"category": "uncertain", "change": "unknown", "reason": reason,
              "status": "invalid_response", "state_refs": [], "function": "", "component": ""}
    if category not in {"target", "shared", "interaction", "other", "uncertain"}:
        return {**result, "validation_code": "category"}
    if status not in DECISIONS:
        return {**result, "validation_code": "change"}
    if refs is None:
        return {**result, "validation_code": "refs"}
    if not reason:
        return {**result, "validation_code": "reason"}
    if category == "uncertain" or status == "unknown":
        return {**result, "status": "missing_evidence", "state_refs": refs}
    if category == "other" or category == "interaction" and not is_target(actor, target):
        if status == "external" and actor and not is_target(actor, target):
            return {**result, "status": "proposed", "category": category,
                    "change": "external", "actor": actor, "state_refs": refs}
        return {**result, "status": "wrong_actor"}
    if not is_target(actor, target) or status == "external":
        return {**result, "status": "wrong_actor"}
    if not function or (function not in profile and function != "new"):
        return {**result, "validation_code": "function"}
    if status in {"change", "new", "already_supported"} and not refs:
        return {**result, "status": "missing_evidence"}
    if status == "explicit" and (category != "target" or not names_target(row["quote"], target) or not _text(reply, "direct_quote")
                                 or _normalized(_text(reply, "direct_quote")) not in _normalized(row["quote"])):
        return {**result, "status": "missing_evidence"}
    label = _text(reply, "function_name")[:180] if function == "new" else profile[function]["name"]
    if not label:
        return {**result, "validation_code": "function_name"}
    metric = _metric_fields(reply, row, allowed, refs)
    if metric is False or (row.get("section_role") == "metric" and row["kind"] == "nonfunctional" and metric is None):
        return {**result, "status": "missing_metric_evidence"}
    decision = {"status": "proposed", "category": category, "change": status, "actor": target,
                "reason": reason, "function": function, "function_name": label,
                "component": component, "state_refs": refs}
    if metric is not None:
        decision["metric"] = metric
    return decision


def _search_records(cfg, evidence, records, group, query):
    """Reuse original-span lookup, not a new ranker. State pool includes exact
    quotes even if the typing model missed a current-state classification.
    """
    hits = evidence.find(query)
    positions = {(evidence.spans[sid]["source"], evidence.spans[sid]["fragment"]) for sid in hits}
    pool = []
    for rid, row in records.items():
        if rid in group:
            continue
        if any((span["source"], span["fragment"]) in positions for span in row.get("source_spans", [])):
            pool.append(_compact(row))
    # Existing lexical fallback over the same original spans, not a new index.
    # Use it even on degraded/legacy indices, so a missed retrieval is not a veto.
    fallback = {sid: {"id": sid, "source": s["source"], "section": s["section"],
                      "quote": s["text"]} for sid, s in evidence.spans.items()}
    for row in _candidates(query, fallback, size=min(5000, _candidate_budget(cfg) // 3)):
        if row["id"] not in hits:
            hits.append(row["id"])
            evidence.counts["fallback_spans"] += 1
    # Exact original fragments missed by extraction remain available as local
    # evidence with original span IDs, rather than being silently dropped.
    for sid in hits:
        span = evidence.spans[sid]
        pool.append({"id": sid, "source": span["source"], "section": span["section"],
                     "quote": span["text"], "kind": "uncertain", "source_role": "unspecified"})
    return pool


def _verify_decisions(cfg, decisions, records, state, context, emit, *, reset_cache=False):
    """Review bounded batches independently. Cache exact successful verdicts,
    with model/prompt/payload identity; never promote incomplete responses.
    """
    pending = [rid for rid, d in decisions.items() if d["status"] == "proposed"]
    budget = _candidate_budget(cfg)
    cache = DraftStageCheckpoint(cfg, "target_verify")
    stats = Counter()
    completed = 0
    emit("target_verify_total", len(pending))

    def review(items):
        nonlocal completed
        if not items:
            return
        payload = {"context": context, "items": items}
        if reset_cache:
            cache.clear(payload)
        allowed = {item["id"] for item in items}
        cached = None if reset_cache else cache.load(payload)
        if cached and set(cached) == allowed and all(v.strip() for v in cached.values()):
            for rid, reason in cached.items():
                decisions[rid].update(status="model_supported", review_reason=reason)
            stats["cache_hits"] += len(items)
        else:
            replies, statuses, _ = _unique_answers(cfg, "target_verify", payload, allowed)
            accepted = {}
            for rid in allowed:
                d = decisions[rid]
                reply = replies.get(rid)
                if reply is None:
                    d["status"] = "review_error" if statuses[rid] == "batch_error" else "needs_review"
                    stats["invalid_verdicts"] += 1
                    continue
                checks = ("correct_actor", "change_supported", "conditions_preserved")
                reason = _text(reply, "reason")[:_MAX_TEXT]
                d["status"] = "model_supported" if all(reply.get(k) is True for k in checks) and reason else "needs_review"
                d["review_reason"] = reason
                if d["status"] == "model_supported":
                    accepted[rid] = reason
            if set(accepted) == allowed:
                cache.save(payload, accepted)
            stats["batches"] += 1
        completed += len(items)
        emit("target_verify_done", completed)

    batch = []
    for rid in pending:
        d = decisions[rid]
        item = {"id": rid, "need": _compact(records[rid]), "decision": d,
                "evidence": [state[k] for k in dict.fromkeys(d["state_refs"] + d.get("reference_refs", []) + d.get("dossier_refs", []))]}
        if _payload_size({"context": context, "items": [item]}) > budget:
            d["status"] = "review_context_limit"
            completed += 1
            emit("target_verify_done", completed)
            continue
        if batch and (len(batch) >= 4 or _payload_size({"context": context, "items": batch + [item]}) > budget):
            review(batch)
            batch = []
        batch.append(item)
    review(batch)
    return stats


def _group_decisions(decisions):
    """Global grouping by confirmed profile ID, or exact normalized new-function label.
    Unresolved alternative new-function names remain separate for expert review.
    """
    grouped = {}
    for rid, d in decisions.items():
        if d["status"] != "model_supported" or d["change"] in {"external", "unknown"}:
            continue
        key = d["function"] if d["function"] != "new" else "new:" + _normalized(d["function_name"]).casefold()
        grouped.setdefault(key, []).append(rid)
    return [{"id": "G" + str(i), "function": decisions[ids[0]]["function_name"],
             "requirement_ids": ids} for i, ids in enumerate(grouped.values(), 1)]


def _proposals(cfg, groups, decisions, records, state, context, emit):
    proposed, questions, outcomes = [], [], {}
    budget = _candidate_budget(cfg)
    # Keep global group IDs. Subdivide only the model payload if necessary.
    def make_payload(group, ids):
        refs = list(dict.fromkeys(ref for rid in ids for ref in decisions[rid]["state_refs"] + decisions[rid].get("reference_refs", []) + decisions[rid].get("dossier_refs", [])))
        return {"context": context, "function": group["function"],
                "needs": [_compact(records[rid]) for rid in ids],
                "decisions": {rid: decisions[rid] for rid in ids},
                "state": [state[k] for k in refs]}
    batches = []
    for group in groups:
        batch = []
        for rid in group["requirement_ids"]:
            if batch and _payload_size(make_payload(group, batch + [rid])) > budget:
                batches.append((group, batch))
                batch = []
            batch.append(rid)
        if batch:
            batches.append((group, batch))
    for group, ids in tracked(emit, "target_derivation", batches):
        changes = [rid for rid in ids if decisions[rid]["change"] != "already_supported"]
        if not changes:
            continue
        refs = list(dict.fromkeys(ref for rid in ids for ref in decisions[rid]["state_refs"] + decisions[rid].get("reference_refs", []) + decisions[rid].get("dossier_refs", [])))
        payload = make_payload(group, ids)
        if _payload_size(payload) > budget:
            outcomes.update(dict.fromkeys(changes, "group_context_limit"))
            continue
        emit("target_derivation", len(outcomes) + 1)
        try:
            reply = _json(cfg, "target_derivation", payload)
        except DraftError:
            outcomes.update(dict.fromkeys(changes, "batch_error"))
            continue
        candidates = []
        for item in reply.get("requirements", []) if isinstance(reply.get("requirements"), list) else []:
            if not isinstance(item, dict):
                continue
            text = _text(item, "text")
            need_refs = _valid_refs(item, "need_refs", set(changes))
            state_refs = _valid_refs(item, "state_refs", set(refs))
            metric_refs = _valid_refs(item, "metric_refs", set(ids))
            if not text or len(text) > _MAX_TEXT or not need_refs or state_refs is None or metric_refs is None:
                continue
            kind = _text(item, "kind")
            if kind not in {"functional", "interface", "metric", "constraint"} or not _text(item, "reason"):
                continue
            if not is_target(_text(item, "actor"), context["target"]):
                continue
            if any(records[k]["kind"] not in {"nonfunctional", "constraint"} for k in metric_refs):
                continue
            explicit = all(decisions[k]["change"] == "explicit" for k in need_refs)
            allowed_state = set(ref for rid in need_refs for ref in decisions[rid]["state_refs"] + decisions[rid].get("reference_refs", []) + decisions[rid].get("dossier_refs", []))
            if not set(state_refs) <= allowed_state:
                continue
            if not explicit and not state_refs:
                continue
            if explicit and not state_refs and (len(need_refs) != 1 or
                                                _normalized(text) != _normalized(records[need_refs[0]]["quote"])):
                continue
            if not _numbers_supported(text, need_refs + state_refs + metric_refs, {**records, **state}):
                continue
            candidates.append({"id": "P" + str(len(proposed) + len(candidates) + 1),
                               "text": text, "actor": context["target"],
                               "mode": "explicit" if explicit else "derived",
                               "need_refs": need_refs, "state_refs": state_refs,
                               "constraint_refs": metric_refs, "reason": _text(item, "reason"),
                               "group": group["id"], "kind": kind})
        proposed.extend(candidates)
        for rid in changes:
            outcomes[rid] = "pending_assessment" if any(rid in c["need_refs"] for c in candidates) else "coverage_gap"
        for row in reply.get("questions", []) if isinstance(reply.get("questions"), list) else []:
            if isinstance(row, dict) and _text(row, "id") in changes and _text(row, "question"):
                questions.append({"need_id": row["id"], "question": _text(row, "question")[:_MAX_TEXT]})
    # Merge identical text within a function while preserving all evidence links.
    consolidated = {}
    for candidate in proposed:
        key = (candidate["group"], candidate["kind"], candidate["mode"], _normalized(candidate["text"]).casefold())
        if key not in consolidated:
            consolidated[key] = candidate
        else:
            original = consolidated[key]
            for field in ("need_refs", "state_refs", "constraint_refs"):
                original[field] = list(dict.fromkeys(original[field] + candidate[field]))
    proposed = list(consolidated.values())
    for index, candidate in enumerate(proposed, 1):
        candidate["id"] = "P" + str(index)
        candidate["quality_gate"] = True
    # Existing independent candidate assessor; no additional Word renderer.
    assess_candidates(cfg, proposed, {**records, **state}, context["target"], emit)
    for rid in outcomes:
        rows = [c for c in proposed if rid in c["need_refs"]]
        if rows:
            outcomes[rid] = ("model_supported_candidates" if all(c["assessment"] == "model_supported" for c in rows)
                             else "needs_review")
    # Independent group-level coverage check, not just candidate-level support.
    for index, (group, batch) in enumerate(tracked(emit, "target_coverage", batches), 1):
        ids = [rid for rid in batch if outcomes.get(rid) == "model_supported_candidates"]
        if not ids:
            continue
        rows = [c for c in proposed if c["group"] == group["id"] and c["assessment"] == "model_supported"
                and set(c["need_refs"]) & set(ids)]
        linked = {rid: decisions[rid].get("reference_refs", []) + decisions[rid].get("dossier_refs", []) for rid in ids}
        refs = list(dict.fromkeys([k for row in rows for k in row["state_refs"] + row["constraint_refs"]]
                                  + [k for refs in linked.values() for k in refs]))
        payload = {"context": context, "items": [_compact(records[rid]) for rid in ids],
                   "proposals": rows, "evidence": [_compact(({**records, **state})[k]) for k in refs],
                   "reference_status": linked}
        if _payload_size(payload) > budget:
            outcomes.update(dict.fromkeys(ids, "review_context_limit"))
            continue
        emit("target_coverage", index)
        answers, statuses, _ = _unique_answers(cfg, "target_coverage", payload, ids)
        for rid in ids:
            row = answers.get(rid, {})
            outcomes[rid] = ("model_covered" if row.get("covered") is True and _text(row, "reason")
                             else "coverage_gap" if rid in answers else statuses[rid])
    return proposed, questions, outcomes


@_measure_draft
def analyze_target_registry(cfg, prepared, approved_profile, progress=None, *, reset_cache=False):
    """Stage C/D; explicit profile confirmation, no DOCX generation."""
    emit = progress or (lambda *_: None)
    context = prepared["context"]
    # Verify originals have not changed between profile and analysis.
    for source, digest in prepared["hashes"].items():
        try:
            current = hashlib.sha256(source_path(cfg, source).read_bytes()).hexdigest()
        except OSError:
            current = None
        if current != digest:
            raise DraftError(tr("Одно из оснований изменилось. Запустите сборку заново."))
    profile = {p["id"]: p for p in approved_profile}
    offered = {p["id"]: p for p in prepared["profile"]}
    if any(offered.get(k) != p for k, p in profile.items()):
        raise ValueError("Invalid profile")
    spans, sections = prepared["spans"], prepared["sections"]
    chunks = {name: [] for name, _ in prepared["documents"]}
    priority = {"interface": 0, "need": 1, "metric": 2, "architecture": 3, "constraint": 4}
    for span in sorted(spans.values(), key=lambda s: priority.get(sections[s["section_id"]]["role"], 5)):
        chunks[span["source"]].append((span["fragment"], span["section"], span["text"]))
    issues = list(prepared["issues"])
    fragment_status = {}
    focus = {"context": context, "functions": [{"id": p["id"], "name": p["name"]}
                                                for p in profile.values()]}
    references = prepared["references"]
    # Include referenced originals for comprehension, never as a source of
    # quotations attributed to the current fragment. Reuse source revision
    # hashes to invalidate extraction if any linked source changed.
    reference_contexts = {}
    for sid, span in tracked(emit, "reference_context", spans.items()):
        if not references.edges.get(sid):
            continue
        related, gaps = references.related([sid], budget=max(0, min(5000,
            _candidate_budget(cfg) - len(span["text"]) - _payload_size(focus) - 1000)))
        if related or gaps:
            reference_contexts[(span["source"], span["fragment"])] = {"items": related, "gaps": gaps}
    revision = hashlib.sha256(json.dumps({"version": 1, "hashes": prepared["hashes"]}, sort_keys=True).encode()).hexdigest()
    evidence = OriginalEvidence(cfg, spans, prepared["hashes"])
    dossiers, dossier_counts = collect_dossiers(cfg, evidence, references, profile, context, emit, _json,
                                               reset_cache=reset_cache)
    original_ids = set()
    def supplement(records):
        original_ids.update(records)
        dossier_counts["supplemental_records"] = merge_dossier_quotes(
            records, dossiers, spans, prepared["documents"])
    registry = build_registry(cfg, prepared["documents"], {k: v for k, v in prepared["roles"].items()
                                                            if k in prepared["hashes"]}, issues, emit,
                              reset_cache=reset_cache, focus=focus, prepared_chunks=chunks,
                              fragment_status=fragment_status, reference_contexts=reference_contexts,
                              reference_revision=revision, supplement=supplement)
    records = registry["requirements"]
    roles_by_section = {(s["source"], s["section"]): s["role"] for s in sections.values()}
    for row in records.values():
        row["section_role"] = roles_by_section.get((row["source"], row["section"]), "unknown")
    original_records = {rid: row for rid, row in records.items() if rid in original_ids}
    dossier_positions, dossier_ids = dossier_context(records, dossiers)
    decisions, state = {}, {}
    reference_counts = Counter()
    linked_by_need = {}
    obligations = [row for row in records.values() if row["kind"] in OBLIGATION_KINDS
                   and row["typing_status"] == "classified"]
    # Bounded per-record evidence, plus profile sources that are actual originals.
    # This intentionally prioritizes accuracy over call-count optimization.
    for index, row in enumerate(tracked(emit, "target_allocation", obligations), 1):
        rid = row["id"]
        emit("target_allocation", index)
        query = context["target"] + " " + row["quote"]
        roots = [references.positions.get((p["source"], p["fragment"])) for p in row.get("source_spans", [])]
        linked, gaps = references.related(roots, quote=row["quote"], budget=min(6000, _candidate_budget(cfg) // 2))
        reference_counts.update(gaps)
        if linked or gaps:
            linked_by_need[rid] = {"items": linked, "gaps": gaps}
        linked_pool = [{"id": r["id"], "source": r["source"], "section": r["section"],
                        "quote": r["quote"], "kind": "reference", "source_role": "unspecified"}
                       for r in linked]
        # Preserve the original retrieval path. The dossier is supplemental.
        original_pool = _search_records(cfg, evidence, original_records, {rid}, query)
        pool = linked_pool + original_pool
        for p in profile.values():
            for sid in p["refs"]:
                s = spans[sid]
                pool.append({"id": sid, "source": s["source"], "section": s["section"],
                             "quote": s["text"], "kind": "uncertain", "source_role": "unspecified"})
        unique = {}
        for item in pool:
            unique.setdefault(item["id"], item)
        pool = list(unique.values())
        base = {"context": context, "profile": focus["functions"],
                "items": [{**_compact(row), "section_role": row["section_role"]}]}
        if linked or gaps:
            base["reference_status"] = {"linked_ids": [r["id"] for r in linked], "gaps": gaps}
        budget = _candidate_budget(cfg)
        if _payload_size(base) > budget:
            decisions[rid] = {"status": "allocation_context_limit", "change": "unknown",
                              "category": "uncertain", "state_refs": [], "reason": ""}
            continue
        remaining = max(0, budget - _payload_size(base) - 300)
        matched_functions = set()
        for pos in row.get("source_spans", []):
            matched_functions.update(dossier_positions.get((pos["source"], pos["fragment"]), set()))
        # Supplemental quotes must not displace evidence already selected by
        # the original search. Append only in genuinely unused context.
        pool = _bounded_rows(pool, remaining)
        selected_ids = {r["id"] for r in pool} | {rid}
        extras = [_compact(records[k]) for pid in sorted(matched_functions)
                  for k in dossier_ids[pid] if k not in selected_ids]
        unique_extras = {r["id"]: r for r in extras}
        free = max(0, remaining - sum(_payload_size(r) + 2 for r in pool))
        pool.extend(_bounded_rows(unique_extras.values(), free))
        # Evidence is a view over existing registry/source spans; no second search index.
        supplied = {r["id"] for r in pool}
        if linked or gaps:
            omitted = sum(r["id"] not in supplied for r in linked)
            if omitted:
                reference_counts["budget_limit"] += omitted
                gaps["budget_limit"] = gaps.get("budget_limit", 0) + omitted
            base["reference_status"] = {"linked_ids": [r["id"] for r in linked if r["id"] in supplied], "gaps": gaps}
        # Missing parts of an explicit reference are not silently treated as covered.
        if any(value for key, value in gaps.items() if key != "cycle"):
            decisions[rid] = {"status": "reference_unresolved", "change": "unknown",
                              "category": "uncertain", "state_refs": [], "reason": "",
                              "reference_refs": base["reference_status"]["linked_ids"],
                              "reference_gaps": gaps}
            state.update({r["id"]: r for r in pool})
            continue
        state.update({r["id"]: r for r in pool})
        answers, statuses, _ = _unique_answers(cfg, "target_allocation", {**base, "evidence": pool}, [rid])
        if rid not in answers:
            decisions[rid] = {"status": statuses[rid], "change": "unknown", "category": "uncertain",
                              "state_refs": [], "reason": ""}
            continue
        decisions[rid] = _validate_decision(answers[rid], rid, records, {r["id"]: r for r in pool}, profile,
                                            context["target"])
        decision = decisions[rid]
        if decision["status"] == "proposed" and decision.get("function") in dossier_ids:
            # Keep additional function evidence separate from current-state assertions.
            fact_rows = [_compact(records[k]) for k in dossier_ids[decision["function"]]
                         if k in supplied and k != rid and k not in decision["state_refs"]]
            decision["dossier_refs"] = [r["id"] for r in _bounded_rows(fact_rows, min(2500, budget // 5))]
        if linked or gaps:
            decisions[rid]["reference_refs"] = base["reference_status"]["linked_ids"]
            decisions[rid]["reference_gaps"] = gaps
    verification_counts = _verify_decisions(cfg, decisions, records, state, context, emit, reset_cache=reset_cache)
    groups = _group_decisions(decisions)
    proposals, questions, outcomes = _proposals(cfg, groups, decisions, records, state, context, emit)
    # Every extracted record has a visible disposition; "external" is verified separately.
    for rid, row in records.items():
        decision = decisions.get(rid)
        outcomes.setdefault(rid, (decision["change"] if decision["status"] == "model_supported"
                                  else decision["status"]) if decision else
                            "open_question" if row["kind"] == "open_question" else
                            "context_only" if row["kind"] != "uncertain" else "untyped")
    diagnostics = {"section_roles": dict(Counter(r["role"] for r in sections.values())),
                   "fragment_status": dict(Counter(fragment_status.values())),
                   "profile_functions": len(profile), "groups": len(groups),
                   "decisions": dict(Counter(d["status"] for d in decisions.values())),
                   "changes": dict(Counter(d["change"] for d in decisions.values())),
                   "outcomes": dict(Counter(outcomes.values())),
                   "record_kinds": dict(Counter(r["kind"] for r in records.values())),
                   "index_revisions": dict(evidence.revisions),
                   "retrieval": dict(evidence.counts), "profile_retrieval": prepared["profile_retrieval"]}
    dossier_counts.update(summarize_dossiers(dossiers, decisions, outcomes, proposals))
    diagnostics["dossiers"] = dict(dossier_counts)
    diagnostics["verification"] = dict(verification_counts)
    diagnostics["allocation_validation"] = dict(Counter(d["validation_code"] for d in decisions.values() if "validation_code" in d))
    diagnostics["references"] = dict(references.counts)
    diagnostics["reference_gaps"] = dict(reference_counts)
    diagnostics["verified_metrics"] = sum(d["status"] == "model_supported" and "metric" in d for d in decisions.values())
    diagnostics["proposal_kinds"] = dict(Counter(p["kind"] for p in proposals))
    diagnostics["proposal_assessments"] = dict(Counter(p["assessment"] for p in proposals))
    diagnostics["source_read_errors"] = len(prepared["issues"])
    _record_draft_diagnostic("target_registry", diagnostics)
    # Confirm original revision again after long model processing.
    for source, digest in prepared["hashes"].items():
        try:
            current = hashlib.sha256(source_path(cfg, source).read_bytes()).hexdigest()
        except OSError:
            current = None
        if current != digest:
            raise DraftError(tr("Одно из оснований изменилось. Запустите сборку заново."))
    return {"requirements": records, "state_evidence": state, "groups": groups,
            "metrics_registry": {rid: d["metric"] for rid, d in decisions.items()
                                 if d["status"] == "model_supported" and "metric" in d},
            "decisions": decisions, "proposals": proposals, "questions": questions,
            "linked_by_need": linked_by_need, "dossiers": dossiers, "approved_profile": list(profile.values()),
            "dispositions": outcomes, "fragment_status": fragment_status, "issues": issues,
            "diagnostics": diagnostics, "requires_expert_review": True}

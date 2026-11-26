"""Evidence-first analysis before Word. Reuses the existing source registry and hybrid search.

The profile is a reviewable hypothesis, not an authority for new obligations.
Every original fragment is screened; retrieval ranks supporting evidence and
never substitutes for the original. All outputs are local, not expert approval.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import re

from .document_context import confirm_context
from .draft_progress import tracked
from .draft_target_review import input_identity, summarize_needs, review_scope
from .draft_references import ReferenceMap
from .draft_dossiers import collect_dossiers, merge_dossier_quotes, dossier_context, summarize_dossiers
from .draft_checkpoint import DraftStageCheckpoint
from .draft_function_analysis import _compact, _unique_answers, _valid_refs, is_target, names_target
from .draft_registry import build_registry, OBLIGATION_KINDS
from .requirement_scope import classify as classify_scope
from .draft_derivation import assess_candidates
from .glossary import Glossary
from .kb import load_kb_snapshot, source_path
from .search import search_parent_child
from .template_draft import (DraftError, _batches, _candidate_budget, _json,
                             _load_draft_sources, _measure_draft, _normalized, _candidates,
                             _numbers_supported, _record_draft_diagnostic,
                             _source_chunks, _text, MAX_CHARS)
from .i18n import tr

SECTION_ROLES = frozenset({"need", "interface", "metric", "architecture", "constraint",
                           "business", "reference", "unknown"})
DECISIONS = frozenset({"new", "change", "already_supported", "external", "unknown",
                       "explicit"})
_MAX_PROFILE_BATCH = 20
_MAX_PROFILE = 40
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


def _map_sources(documents, roles, *, prefix="", max_chars=MAX_CHARS):
    spans, sections = {}, {}
    for name, markdown in documents:
        for index, (path, text, table) in enumerate(_source_chunks(markdown, full_path=True, table_context=True, max_chars=max_chars), 1):
            key = (name, path)
            if key not in sections:
                sections[key] = {"id": prefix + "S" + str(len(sections) + 1), "source": name,
                                 "section": path, "source_role": roles.get(name, "unspecified"),
                                 "sample": text[:600], "role": "unknown"}
            sid = prefix + "F" + str(len(spans) + 1)
            spans[sid] = {"id": sid, "source": name, "section": path, "fragment": index,
                          "text": text, "section_id": sections[key]["id"]}
            if table:
                spans[sid]["table_context"] = table
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
        item = {"id": "C" + str(len(result) + 1), "name": name,
                "description": description, "refs": refs}
        parent = _text(row, "parent_name")[:180]
        if parent and _normalized(parent).casefold() != _normalized(name).casefold():
            item["parent_name"] = parent
        result.append(item)
        if len(result) >= _MAX_PROFILE_BATCH:
            break
    return result


def _propose_profile(cfg, candidates, context, emit, *, reference=False, from_requirements=False):
    """Keep a failed/empty response distinct from a verified citation set."""
    status = "no_candidates"
    profile = []
    for _ in tracked(emit, "target_profile", [1] if candidates else []):
        emit("target_profile", 1)
        try:
            payload = {"context": context, "evidence": candidates}
            if reference:
                payload["purpose"] = "reference_current_state"
            elif from_requirements:
                payload["purpose"] = "requirements_analysis"
            answer = _json(cfg, "target_profile", payload)
        except DraftError:
            status = "model_error"
        else:
            rows = answer.get("functions") if isinstance(answer, dict) else None
            if not isinstance(rows, list):
                status = "invalid_response"
            elif not rows:
                status = "no_functions"
            else:
                profile = _validate_profile(answer, {r["id"] for r in candidates})
                status = ("found" if len(profile) == len(rows) else "partial" if profile
                          else "invalid_response")
    return profile, status


@_measure_draft
def prepare_target_analysis(cfg, sources, roles, context, progress=None, *, reference_sources=(), discover_profile=True):
    """Separate original bases from optional, user-scoped wiki context.

    References are evidence for current-state interpretation only, never
    inputs to extraction or a second obligation registry.
    """
    emit = progress or (lambda *_: None)
    context = confirm_context(context)
    sources = list(dict.fromkeys(sources))
    reference_sources = list(dict.fromkeys(reference_sources))
    if set(sources) & set(reference_sources):
        raise ValueError("Basis and reference scopes must be disjoint")
    # First pilot: explicitly bounded source scope, no scanning the whole wiki.
    if len(reference_sources) > 8:
        raise ValueError("Reference scope exceeds eight documents")
    issues, hashes, word_metadata = [], {}, {}
    documents = _load_draft_sources(cfg, sources, issues, source_hashes=hashes, emit=emit,
                                    word_metadata=word_metadata)
    spans, sections = _map_sources(documents, roles)
    references = ReferenceMap(documents, spans, emit, word_metadata)
    _classify_sections(cfg, sections, context, emit)
    evidence = OriginalEvidence(cfg, spans, hashes)
    candidates = _profile_candidates(cfg, spans, sections, roles, evidence, context, emit) if discover_profile else []
    profile, profile_status = (_propose_profile(cfg, candidates, context, emit) if discover_profile
                               else ([], "no_candidates"))
    reference_hashes, reference_issues, reference_spans = {}, [], {}
    reference_candidates, reference_retrieval = [], {}
    reference_status = "disabled"
    if reference_sources:
        try:
            reference_documents = _load_draft_sources(cfg, reference_sources, reference_issues,
                                                      source_hashes=reference_hashes, emit=emit)
        except DraftError:
            reference_status = "source_error"
        else:
            reference_spans, reference_sections = _map_sources(reference_documents, {}, prefix="B",
                max_chars=max(500, min(MAX_CHARS, _candidate_budget(cfg) // 5 - 600)))
            ref_evidence = OriginalEvidence(cfg, reference_spans, reference_hashes)
            reference_candidates = (_profile_candidates(cfg, reference_spans, reference_sections, {},
                                                       ref_evidence, context, emit) if discover_profile else [])
            reference_retrieval = dict(ref_evidence.counts)
            ref_profile, reference_status = (_propose_profile(cfg, reference_candidates, context, emit,
                                                               reference=True) if discover_profile else ([], "no_candidates"))
            # Preserve A-only hints and their IDs, even for overlapping names.
            # Separate B rows so the user can judge their own source evidence.
            for row in ref_profile:
                profile.append({**row, "id": "B" + row["id"], "origin": "reference"})
    return {"documents": documents, "hashes": hashes, "spans": spans, "sections": sections,
            "profile": profile, "profile_status": profile_status, "issues": issues,
            "context": context, "roles": dict(roles), "references": references,
            "reference_sources": reference_sources, "reference_hashes": reference_hashes,
            "reference_spans": reference_spans, "reference_candidates": reference_candidates,
            "reference_issues": reference_issues, "reference_status": reference_status,
            "reference_retrieval": reference_retrieval,
            "profile_retrieval": dict(evidence.counts), "index_revisions": dict(evidence.revisions)}


def _metric_pair(row, subject, value, unit):
    """Conservative exact value/unit association in one clause or table row.

    This is a mechanical guard, not proof of semantic level/conditions; the
    independent reviewer still checks those. Ambiguous multi-value clauses
    require more precise source evidence.
    """
    value, unit, subject = map(_normalized, (value, unit, subject))
    if not value or not unit or not subject:
        return False
    number = r"(?<![\w.,])" + re.escape(value) + r"(?![\d.,])"
    measure = re.compile(number + r"\s*(?:\|\s*)?" + re.escape(unit) + r"(?!\w)", re.I)
    subject_pattern = re.compile(r"(?<!\w)" + re.escape(subject) + r"(?!\w)", re.I)
    table = row.get("table_context") or {}
    header = table.get("header", "")
    def cells(line):
        return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
    for line in row["quote"].splitlines():
        if header and line.strip().startswith("|"):
            labels, values = cells(header), cells(line)
            if len(labels) == len(values):
                # A common layout stores the quantity and unit in separate cells.
                # Accept only an unambiguous, explicitly labelled pair in this row;
                # never borrow the unit from another row or infer a target level.
                value_labels = {"значение", "величина", "value", "quantity"}
                unit_labels = {"единица", "единица измерения", "ед. изм.", "ед. изм",
                               "ед. измерения", "unit", "unit of measure", "measurement unit"}
                value_cols = [i for i, label in enumerate(labels) if _normalized(label).casefold() in value_labels]
                unit_cols = [i for i, label in enumerate(labels) if _normalized(label).casefold() in unit_labels]
                if len(value_cols) == len(unit_cols) == 1:
                    vi, ui = value_cols[0], unit_cols[0]
                    subject_cells = [cell for i, cell in enumerate(values)
                                     if i not in (vi, ui) and subject_pattern.search(cell)]
                    if (len(subject_cells) == 1 and _normalized(values[vi]) == value
                            and _normalized(values[ui]).casefold() == unit.casefold()):
                        return True
                subject_in_header = any(subject_pattern.search(label) for label in labels)
                for label, cell in zip(labels, values):
                    if not (subject_pattern.search(label) if subject_in_header else subject_pattern.search(line)):
                        continue
                    if measure.search(cell) or (re.search(number, cell) and
                            re.search(r"(?<!\w)" + re.escape(unit) + r"(?!\w)", label, re.I)):
                        return True
                # Do not reinterpret the whole table row as a prose clause.
                continue
        for clause in re.split(r";|(?<=[.!?])\s+", _normalized(line)):
            for match in measure.finditer(clause):
                # Subject and quantity must be in the same clause; a different
                # intervening quantity of the same unit is ambiguous.
                subjects = list(subject_pattern.finditer(clause[:match.start()]))
                if subjects:
                    between = clause[subjects[-1].end():match.start()]
                    other = re.search(r"\d+(?:[.,]\d+)?\s*" + re.escape(unit) + r"(?!\w)", between, re.I)
                    if not other:
                        return True
    return False


def _metric_fields(reply, row, state, refs):
    """Require literal quantities and units together; never promote B to A."""
    data = reply.get("metric")
    if data is None:
        return None
    if not isinstance(data, dict):
        return False
    fields = ("subject", "value", "unit", "conditions", "level", "current_value", "target_value")
    metric = {k: _text(data, k)[:300] for k in fields}
    if not metric["subject"] or not metric["value"] or not metric["unit"] or metric["level"] not in {"current", "target", "unknown"}:
        return False
    evidence = [row] + [state[k] for k in refs]
    basis = [r for r in evidence if r.get("source_role") != "reference_context"]
    def supported(value, candidates):
        return any(_metric_pair(r, metric["subject"], value, metric["unit"]) for r in candidates)
    if not supported(metric["value"], [row]):
        return False
    for key, candidates in (("current_value", evidence), ("target_value", basis)):
        if metric[key] and not supported(metric[key], candidates):
            return False
    return metric


def _characteristic_verdict(reply, record, facet, anchors):
    """Validate a characteristic separately from obligations and implementation.

    The original R record remains the only statement. Structured values may
    only be literal selections from it or explicitly cited original anchors.
    """
    result = {"status": "needs_review"}
    reason = _text(reply, "reason")[:_MAX_TEXT]
    if reason:
        result["reason"] = reason
    refs = _valid_refs(reply, "anchor_refs", anchors)
    relation = _text(reply, "relation")
    if (not reason or refs is None or relation not in {"target", "interaction", "other", "uncertain"}
            or any(type(reply.get(k)) is not bool for k in
                   ("facet_supported", "function_supported", "target_involved", "conditions_preserved"))):
        return {**result, "status": "invalid_response"}
    if (relation not in {"target", "interaction"} or not all(reply[k] for k in
            ("facet_supported", "function_supported", "target_involved", "conditions_preserved"))):
        return result
    if record.get("source_role") == "reference_context":
        return result
    evidence = [record] + [anchors[k] for k in refs]
    fields = {}
    for key in ("flow", "source_party", "destination_party"):
        value = reply.get(key, "")
        if not isinstance(value, str) or len(value) > 300:
            return {**result, "status": "invalid_response"}
        value = value.strip()
        if value and not any(_normalized(value) in _normalized(
                r["quote"] + "\n" + (r.get("table_context") or {}).get("header", "")) for r in evidence):
            return {**result, "status": "invalid_response"}
        if value:
            fields[key] = value
    if facet in {"performance", "capacity"}:
        metric = _metric_fields(reply, record, {}, [])
        if metric is False or metric is None:
            return {**result, "status": "missing_metric_evidence"}
        # No current/target value can be borrowed from another flow.
        if metric["conditions"] and _normalized(metric["conditions"]) not in _normalized(
                record["quote"] + "\n" + (record.get("table_context") or {}).get("header", "")):
            return {**result, "status": "missing_metric_evidence"}
        fields["metric"] = metric
    return {**result, "status": "model_supported", "relation": relation, "anchor_refs": refs, **fields}


def _review_characteristics(cfg, dossiers, records, profile, spans, context, emit):
    """Review existing dossier facts in bounded batches; no extra registry/index.

    Only A originals enter this stage. A supported characteristic is not a
    supported requirement, implementation claim or expert decision.
    """
    budget = _candidate_budget(cfg)
    counts = Counter()
    jobs = []
    for pid, dossier in dossiers.items():
        p = profile[pid]
        anchors = {}
        for rid in p.get("record_refs", []):
            if rid in records and records[rid].get("source_role") != "reference_context":
                anchors[rid] = _compact(records[rid])
        for sid in p.get("refs", []):
            if sid in spans:
                s = spans[sid]
                anchors[sid] = {"id": sid, "source": s["source"], "section": s["section"],
                                "quote": s["text"],
                                **({"table_context": s["table_context"]} if s.get("table_context") else {})}
        base = {"context": context, "function": {"id": pid, "name": p["name"], "description": p["description"]}}
        rows = _bounded_rows(anchors.values(), min(4000, budget // 4))[:4]
        if len(rows) < len(anchors):
            counts["anchor_limit"] += len(anchors) - len(rows)
        base["anchors"] = rows
        allowed = {r["id"]: r for r in rows}
        pending = []
        for facet, entry in dossier["facets"].items():
            for fact in entry["facts"]:
                counts["candidates"] += 1
                rid = fact.get("record_id")
                record = records.get(rid)
                if (record is None or record.get("source_role") == "reference_context"
                        or _normalized(fact.get("quote", "")) != _normalized(record["quote"])):
                    fact["review"] = {"status": "missing_evidence"}
                    counts["missing_evidence"] += 1
                    continue
                # Local response ID only, never a new source record.
                item = {"id": "D" + str(counts["candidates"]), "facet": facet, "record": _compact(record)}
                if _payload_size({**base, "items": [item]}) > budget:
                    fact["review"] = {"status": "context_limit"}
                    counts["context_limit"] += 1
                    continue
                if pending and (len(pending) >= 6 or _payload_size({**base, "items": [x[0] for x in pending] + [item]}) > budget):
                    jobs.append((base, allowed, pending))
                    pending = []
                pending.append((item, fact))
        if pending:
            jobs.append((base, allowed, pending))
    for base, anchors, batch in tracked(emit, "target_characteristic_review", jobs):
        payload = {**base, "items": [item for item, _ in batch]}
        replies, statuses, unexpected = _unique_answers(cfg, "target_characteristic_review", payload,
                                                       [item["id"] for item, _ in batch])
        counts["batches"] += 1
        counts["unexpected_responses"] += unexpected
        for item, fact in batch:
            key = item["id"]
            review = (_characteristic_verdict(replies[key], item["record"], item["facet"], anchors)
                      if key in replies else {"status": statuses[key]})
            fact["review"] = review
            counts[review["status"]] += 1
            if review["status"] == "model_supported":
                counts["supported_" + item["facet"]] += 1
                if "metric" in review:
                    counts["supported_metrics"] += 1
    return counts


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
    if category == "uncertain":
        return {**result, "status": "missing_evidence", "state_refs": refs}
    if category == "other" or category == "interaction" and not is_target(actor, target):
        if status == "external" and actor and not is_target(actor, target):
            return {**result, "status": "proposed", "category": category,
                    "change": "external", "actor": actor, "state_refs": refs}
        return {**result, "status": "wrong_actor", "actor_validation": (
            "external_actor_is_target" if is_target(actor, target) else
            "missing_actor" if not actor else "external_change_mismatch")}
    if not is_target(actor, target) or status == "external":
        return {**result, "status": "wrong_actor", "actor_validation": (
            "missing_actor" if not actor else "target_actor_mismatch" if not is_target(actor, target)
            else "target_change_external")}
    # A system-wide constraint is not a functional capability.
    if not function and row["kind"] in {"nonfunctional", "constraint"}:
        function = "system_wide"
    if function == "system_wide" and row["kind"] not in {"nonfunctional", "constraint"}:
        return {**result, "validation_code": "function"}
    if function not in profile and function not in {"new", "system_wide"}:
        return {**result, "validation_code": "function"}
    # A missing current-state citation must not erase the proposed owner.
    change_gap = status in {"change", "new", "already_supported"} and not refs
    if change_gap:
        status = "unknown"
    # Direct textual evidence must be exact. If the direct claim is malformed,
    # leave the responsibility hypothesis for separate verification instead of
    # certifying the explicit requirement as ready for derivation.
    if status == "explicit" and (category != "target" or not names_target(row["quote"], target) or not _text(reply, "direct_quote")
                                 or _normalized(_text(reply, "direct_quote")) not in _normalized(row["quote"])):
        return {**result, "status": "missing_evidence"}
    label = (tr("Общесистемные требования") if function == "system_wide" else
             _text(reply, "function_name")[:180] if function == "new" else profile[function]["name"])
    if not label:
        return {**result, "validation_code": "function_name"}
    metric = _metric_fields(reply, row, allowed, refs)
    metric_gap = metric is False or (row.get("section_role") == "metric" and row["kind"] == "nonfunctional" and metric is None)
    decision = {"status": "proposed", "category": category, "change": status, "actor": target,
                "reason": reason, "function": function, "function_name": label,
                "component": component if status != "unknown" else "", "state_refs": refs,
                "applicability_status": "proposed", "change_status": "unresolved" if status == "unknown" else "proposed"}
    decision["implementation_status"] = "unknown" if status in {"unknown", "explicit"} else "proposed"
    if change_gap:
        decision["change_gap"] = "missing_evidence"
    if metric_gap:
        decision["metric_gap"] = True
        decision["metric_validation"] = "invalid" if metric is False else "missing"
    elif metric is not None:
        decision["metric"] = metric
    return decision


def _metric_diagnostics(records, decisions):
    """Numeric stage funnel; candidates are not verified metrics or measured recall."""
    counts = Counter()
    for rid, row in records.items():
        d = decisions.get(rid)
        candidate = (row.get("section_role") == "metric"
                     or any(f.get("facet") in {"performance", "capacity"}
                            for f in row.get("dossier_facets", []))
                     or bool(d and ("metric" in d or d.get("metric_gap"))))
        if not candidate:
            continue
        counts["candidate_records"] += 1
        if d is None:
            counts["not_allocated"] += 1
        elif "metric" in d:
            counts["mechanically_supported"] += 1
            counts["verified" if d.get("status") == "model_supported" else "review_unconfirmed"] += 1
        elif d.get("metric_validation") == "invalid":
            counts["rejected"] += 1
        elif d.get("metric_validation") == "missing":
            counts["missing"] += 1
        else:
            counts["no_metric_decision"] += 1
    return dict(counts)


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
                     "quote": span["text"], "kind": "uncertain", "source_role": "unspecified",
                     **({"table_context": span["table_context"]} if span.get("table_context") else {})})
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
                d = decisions[rid]
                d.update(status="model_supported", review_reason=reason, applicability_status="model_supported",
                         function_status="model_supported" if d.get("function") and d.get("change") != "external" else "not_applicable",
                         change_status="unresolved" if d.get("change") == "explicit" else "model_supported",
                         implementation_status="unknown" if d.get("change") in {"explicit", "external"} else "model_supported")
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
                reason = _text(reply, "reason")[:_MAX_TEXT]
                actor_ok = reply.get("correct_actor") is True and bool(reason)
                if not actor_ok:
                    stats["actor_rejected" if reply.get("correct_actor") is False else "actor_verdict_incomplete"] += 1
                conditions_ok = reply.get("conditions_preserved") is True
                change_ok = reply.get("change_supported") is True and d.get("change") != "unknown"
                reference_gap = any(v for k, v in d.get("reference_gaps", {}).items() if k != "cycle")
                d["applicability_status"] = "model_supported" if actor_ok else "needs_review"
                requires_function = bool(d.get("function")) and d.get("change") != "external"
                function_ok = not requires_function or reply.get("correct_function") is True
                d["function_status"] = ("not_applicable" if not requires_function else
                                        "model_supported" if function_ok and actor_ok else "needs_review")
                d["change_status"] = "model_supported" if actor_ok and function_ok and change_ok and conditions_ok and not reference_gap and not d.get("metric_gap") else "unresolved"
                d["review_reason"] = reason
                if actor_ok and not function_ok:
                    # Ownership alone is not proof of the functional grouping.
                    # Keep the original decision visible, but never send it to
                    # the wrong group for derivation.
                    d["status"] = "needs_review"
                    d["proposed_change"] = d.get("change", "unknown")
                    d["change"] = "unknown"
                    d["component"] = ""
                    d["implementation_status"] = "unknown"
                elif d["change_status"] == "model_supported":
                    d["status"] = "model_supported"
                    d["implementation_status"] = "unknown" if d.get("change") in {"explicit", "external"} else "model_supported"
                    if d.get("change") == "explicit":
                        d["change_status"] = "unresolved"
                    accepted[rid] = reason
                elif actor_ok and d.get("category") in {"target", "shared", "interaction"}:
                    # Keep supported responsibility but block claims about implementation.
                    d["status"] = "applicability_supported"
                    d["proposed_change"] = d.get("change", "unknown")
                    d["change"] = "unknown"
                    d["component"] = ""
                    d["implementation_status"] = "unknown"
                else:
                    d["status"] = "needs_review"
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
        if d["status"] not in {"model_supported", "applicability_supported"} or d["change"] == "external":
            continue
        if not d.get("function"):
            continue
        key = d["function"] if d["function"] != "new" else "new:" + _normalized(d["function_name"]).casefold()
        grouped.setdefault(key, []).append(rid)
    return [{"id": "G" + str(i), "function": decisions[ids[0]]["function_name"],
             "requirement_ids": ids} for i, ids in enumerate(grouped.values(), 1)]


def _proposals(cfg, groups, decisions, records, state, context, emit, *, notes=None):
    proposed, questions, outcomes = [], [], {}
    budget = _candidate_budget(cfg)
    # Keep global group IDs. Subdivide only the model payload if necessary.
    def make_payload(group, ids):
        refs = list(dict.fromkeys(ref for rid in ids for ref in decisions[rid]["state_refs"] + decisions[rid].get("reference_refs", []) + decisions[rid].get("dossier_refs", [])))
        payload = {"context": context, "function": group["function"],
                "needs": [_compact(records[rid]) for rid in ids],
                "decisions": {rid: decisions[rid] for rid in ids},
                "state": [state[k] for k in refs]}
        if notes and notes.get(group["id"]):
            payload["expert_guidance"] = notes[group["id"]]
        return payload
    batches = []
    for group in groups:
        batch = []
        for rid in group["requirement_ids"]:
            if decisions[rid]["change"] == "unknown":
                outcomes[rid] = "implementation_unknown"
                continue
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
            # A number from B is not authority for a new quantitative target.
            numeric_refs = need_refs + [k for k in state_refs if state[k].get("source_role") != "reference_context"] + metric_refs
            if not _numbers_supported(text, numeric_refs, {**records, **state}):
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


def _verify_originals(cfg, prepared):
    """Reject stale source bytes at both sides of the review boundary."""
    for source, digest in {**prepared["hashes"], **prepared.get("reference_hashes", {})}.items():
        try:
            current = hashlib.sha256(source_path(cfg, source).read_bytes()).hexdigest()
        except OSError:
            current = None
        if current != digest:
            raise DraftError(tr("Одно из оснований изменилось. Запустите сборку заново."))

def _recover_profile_batch(cfg, rows, context):
    """One bounded recovery round, preserving every validated original link.

    The shared JSON client already retries malformed JSON. For an exhausted
    call, try two smaller independent inputs at most; for a valid but malformed
    contract retry once. Never retry a legitimate empty answer or recurse.
    """
    noop = lambda *_: None
    proposed, initial = _propose_profile(cfg, rows, context, noop, from_requirements=True)
    counts = Counter()
    if initial not in {"model_error", "invalid_response", "partial"}:
        return proposed, initial, counts
    counts["initial_" + initial] += 1
    if initial == "model_error" and len(rows) < 2:
        return proposed, initial, counts
    counts["retry_attempted"] += 1
    if initial == "model_error":
        middle = len(rows) // 2
        batches = [rows[:middle], rows[middle:]]
    else:
        batches = [rows]
    statuses = []
    combined = {}
    def merge(items):
        for p in items:
            key = _normalized(p["name"]).casefold()
            if key not in combined:
                combined[key] = {**p, "refs": list(p["refs"])}
            else:
                refs = combined[key]["refs"]
                refs.extend(rid for rid in p["refs"] if rid not in refs)
                old = combined[key]
                if p.get("parent_name") and not old.get("parent_conflict"):
                    if old.get("parent_name") and _normalized(old["parent_name"]).casefold() != _normalized(p["parent_name"]).casefold():
                        old.pop("parent_name", None)
                        old["parent_conflict"] = True
                    else:
                        old["parent_name"] = p["parent_name"]
    merge(proposed)
    for batch in batches:
        counts["retry_batches"] += 1
        items, status = _propose_profile(cfg, batch, context, noop, from_requirements=True)
        statuses.append(status)
        merge(items)
    if all(s in {"found", "no_functions"} for s in statuses) and (combined or initial != "partial"):
        counts["retry_recovered"] += 1
        final = "found" if combined else "no_functions"
    else:
        counts["retry_exhausted"] += 1
        final = "partial" if combined else ("model_error" if "model_error" in statuses else "invalid_response")
    return list(combined.values()), final, counts


def _functions_from_records(cfg, records, references, spans, context, emit, *, existing=()):
    """Discover bounded functional hypotheses from the independent scan.
    Keep each original R-ID; one record can support several functions.
    A capped or incomplete discovery is not a completeness claim.
    """
    rows = [{"id": rid, "source": r["source"], "section": r["section"], "text": r["quote"], **({"table_context": r["table_context"]} if r.get("table_context") else {})}
            for rid, r in records.items()]
    budget = max(0, _candidate_budget(cfg) - _payload_size(context) - 1000)
    functions = {_normalized(p["name"]).casefold(): p for p in existing}
    counts = Counter()
    batches = list(_batches(rows, lambda r: json.dumps(r, ensure_ascii=False), size=max(1, budget)))
    for batch in tracked(emit, "target_function_discovery", batches):
        bounded = _bounded_rows(batch, budget)
        counts["context_limit"] += len(batch) - len(bounded)
        proposed, status, recovery = _recover_profile_batch(cfg, bounded, context)
        counts.update(recovery)
        counts[status] += 1
        for p in proposed:
            key = _normalized(p["name"]).casefold()
            if key not in functions:
                if len(functions) >= _MAX_PROFILE:
                    counts["context_limit"] += 1
                    counts["profile_cap_omitted"] += 1
                    continue
                functions[key] = {"id": "C" + str(len(functions) + 1), "name": p["name"],
                                  "description": p["description"], "refs": [], "record_refs": []}
            item = functions[key]
            if p.get("parent_conflict"):
                item.pop("parent_name", None)
                item["parent_conflict"] = True
            elif p.get("parent_name") and not item.get("parent_conflict"):
                if item.get("parent_name") and _normalized(item["parent_name"]).casefold() != _normalized(p["parent_name"]).casefold():
                    item.pop("parent_name", None)
                    item["parent_conflict"] = True
                else:
                    item["parent_name"] = p["parent_name"]
            for rid in p["refs"]:
                if rid not in item["record_refs"]:
                    item["record_refs"].append(rid)
                for pos in records[rid].get("source_spans", []):
                    sid = references.positions.get((pos["source"], pos["fragment"]))
                    if sid in spans and sid not in item["refs"]:
                        item["refs"].append(sid)
    return {p["id"]: p for p in functions.values()}, counts


def function_hierarchy(profile):
    """Display-only parent hypotheses: exact unambiguous name, no self/cycles.
    Never change primary allocation, original IDs or scope selection.
    """
    by_name = {}
    for pid, p in profile.items():
        if p.get("origin") != "reference":
            by_name.setdefault(_normalized(p["name"]).casefold(), []).append(pid)
    parents, counts = {}, Counter()
    for pid, p in profile.items():
        if p.get("origin") == "reference":
            continue
        if p.get("parent_conflict"):
            counts["conflicting_parent"] += 1
            continue
        if not p.get("parent_name"):
            continue
        matches = by_name.get(_normalized(p["parent_name"]).casefold(), [])
        if len(matches) != 1 or matches[0] == pid:
            counts["unresolved_parent"] += 1
            continue
        parents[pid] = matches[0]
    cyclic = set()
    for pid in parents:
        path, cur = [], pid
        while cur in parents and cur not in path:
            path.append(cur)
            cur = parents[cur]
        if cur in path:
            cyclic.update(path[path.index(cur):])
    for pid in cyclic:
        parents.pop(pid, None)
    counts["cycle_parent"] = len(cyclic)
    counts["linked_subfunctions"] = len(parents)
    return parents, counts


def _allocation_profile_rows(profile, candidate_ids, budget, base):
    """Reserve evidence space when a large profile would crowd out originals."""
    rows = [{"id": p["id"], "name": p["name"]} for p in profile.values()]
    if _payload_size({**base, "profile": rows}) <= budget // 2:
        return rows
    candidates = set(candidate_ids)
    ordered = [r for r in rows if r["id"] in candidates] + [r for r in rows if r["id"] not in candidates]
    available = max(0, budget // 2 - _payload_size({**base, "profile": []}) - 100)
    return _bounded_rows(ordered, available)


@_measure_draft
def _collect_target_requirements(cfg, prepared, approved_profile=None, progress=None, *, reset_cache=False, summaries=True,
                                preview_only=False, preview=None, selected_functions=None):
    """Collect original needs; optionally pause after independent scan for scope selection."""
    emit = progress or (lambda *_: None)
    context = prepared["context"]
    _verify_originals(cfg, prepared)
    automatic_functions = approved_profile is None
    profile = {p["id"]: p for p in (approved_profile or [])}
    offered = {p["id"]: p for p in prepared["profile"]}
    if any(offered.get(k) != p for k, p in profile.items()):
        raise ValueError("Invalid profile")
    if preview_only and (not automatic_functions or preview is not None or selected_functions is not None):
        raise ValueError("Invalid preview request")
    if preview is not None:
        if (not automatic_functions or preview.get("phase") != "function_preview"
                or preview.get("input_identity") != input_identity(cfg, prepared, preview["approved_profile"])):
            raise ValueError("Stale function preview")
        profile = deepcopy({p["id"]: p for p in preview["approved_profile"]})
        if selected_functions is None or not set(selected_functions) <= set(profile):
            raise ValueError("Invalid function selection")
    elif selected_functions is not None:
        raise ValueError("Function selection requires a preview")
    selected = set(selected_functions or [])
    spans, sections = prepared["spans"], prepared["sections"]
    chunks = {name: [] for name, _ in prepared["documents"]}
    priority = {"interface": 0, "need": 1, "metric": 2, "architecture": 3, "constraint": 4}
    for span in sorted(spans.values(), key=lambda s: priority.get(sections[s["section_id"]]["role"], 5)):
        chunks[span["source"]].append((span["fragment"], span["section"], span["text"]))
    issues = list(preview["issues"] if preview is not None else prepared["issues"])
    fragment_status = dict(preview["fragment_status"]) if preview is not None else {}
    # Preliminary functions are supplemental retrieval hints, not an
    # input to the independent full scan of original requirements.
    base_profile = {pid: p for pid, p in profile.items() if p.get("origin") != "reference"}
    function_counts = Counter(preview["profile_status"] if preview is not None else {})
    extraction_focus = {"context": context, "functions": []}
    references = prepared["references"]
    # Include referenced originals for comprehension, never as a source of
    # quotations attributed to the current fragment. Reuse source revision
    # hashes to invalidate extraction if any linked source changed.
    reference_contexts = {}
    for sid, span in tracked(emit, "reference_context", spans.items() if preview is None else []):
        if not references.edges.get(sid):
            continue
        related, gaps = references.related([sid], budget=max(0, min(5000,
            _candidate_budget(cfg) - len(span["text"]) - _payload_size(extraction_focus) - 1000)))
        if related or gaps:
            reference_contexts[(span["source"], span["fragment"])] = {"items": related, "gaps": gaps}
    revision = hashlib.sha256(json.dumps({"version": 2, "hashes": prepared["hashes"]}, sort_keys=True).encode()).hexdigest()
    evidence = OriginalEvidence(cfg, spans, prepared["hashes"])
    dossiers, dossier_counts = {}, Counter()
    original_ids = set()
    def supplement(records):
        # build_registry calls this only after extracting original records.
        # Keep the existing merge/typing pipeline; never replace originals.
        original_ids.update(records)
        if not records and fragment_status and all(v in {"failed", "invalid_quote"} for v in fragment_status.values()):
            raise DraftError(tr("Не удалось извлечь ни одной достоверной записи: повторите разбор оснований."))
        if automatic_functions and preview is None:
            discovered, counts = _functions_from_records(cfg, records, references, spans, context, emit)
            base_profile.update(discovered)
            profile.update(discovered)
            function_counts.update(counts)
        if preview_only:
            return
        search_profile = (base_profile if preview is None else
                          {pid: p for pid, p in base_profile.items() if pid in selected})
        found, counts = collect_dossiers(cfg, evidence, references, search_profile, context, emit, _json,
                                         reset_cache=reset_cache)
        dossiers.update(found)
        dossier_counts.update(counts)
        dossier_counts["supplemental_records"] = merge_dossier_quotes(
            records, dossiers, spans, prepared["documents"])
        # One bounded follow-up only for newly discovered original citations.
        # A new function gets the same dossier analysis, without a recursive loop.
        added = {rid: r for rid, r in records.items() if rid not in original_ids}
        if automatic_functions and added:
            prior = set(base_profile)
            discovered, counts = _functions_from_records(cfg, added, references, spans, context, emit,
                                                          existing=base_profile.values())
            base_profile.update(discovered)
            profile.update(discovered)
            function_counts.update(counts)
            new_functions = {pid: p for pid, p in discovered.items() if pid not in prior}
            if new_functions and preview is None:
                more, counts = collect_dossiers(cfg, evidence, references, new_functions, context, emit, _json,
                                                reset_cache=reset_cache)
                dossier_counts.update(counts)
                dossier_counts["supplemental_records"] += merge_dossier_quotes(
                    records, more, spans, prepared["documents"])
                dossiers.update(more)
    registry = build_registry(cfg, prepared["documents"], {k: v for k, v in prepared["roles"].items()
                                                            if k in prepared["hashes"]}, issues, emit,
                              reset_cache=reset_cache, focus=extraction_focus, prepared_chunks=chunks,
                              fragment_status=fragment_status, reference_contexts=reference_contexts,
                              reference_revision=revision, supplement=supplement,
                              table_contexts={(s["source"], s["fragment"]): s["table_context"]
                                              for s in spans.values() if s.get("table_context")},
                              initial_records=preview["requirements"] if preview is not None else None)
    records = registry["requirements"]
    roles_by_section = {(s["source"], s["section"]): s["role"] for s in sections.values()}
    for row in records.values():
        row["section_role"] = roles_by_section.get((row["source"], row["section"]), "unknown")
    if preview_only:
        obligations = {rid: _compact(row) for rid, row in records.items()
                       if row["kind"] in OBLIGATION_KINDS and row["typing_status"] == "classified"}
        preliminary = classify_scope(cfg, obligations, context, issues, emit)
        applicability = {rid: row["applicability"] for rid, row in preliminary.items()}
        links = {rid: [pid for pid, p in base_profile.items() if rid in p.get("record_refs", [])]
                 for rid in records}
        _verify_originals(cfg, prepared)
        return {"phase": "function_preview", "requirements": records, "approved_profile": list(profile.values()),
                "function_links": links, "applicability": applicability, "issues": issues,
                "profile_status": dict(function_counts), "fragment_status": fragment_status,
                "input_identity": input_identity(cfg, prepared, list(profile.values()))}
    original_records = {rid: row for rid, row in records.items() if rid in original_ids}
    dossier_positions, dossier_ids = dossier_context(records, dossiers)
    characteristic_counts = _review_characteristics(cfg, dossiers, records, base_profile, spans, context, emit)
    decisions, state = {}, {}
    # B candidates are exact original spans, never inserted into records.
    # Rank only the already retrieved bounded pool; no extra query per need.
    wiki_pool = {r["id"]: {"id": r["id"], "source": r["source"], "section": r["section"],
                           "quote": r["text"], "kind": "uncertain", "source_role": "reference_context",
                           **({"table_context": r["table_context"]} if r.get("table_context") else {})}
                 for r in prepared.get("reference_candidates", [])}
    wiki_counts = Counter()
    if automatic_functions and prepared.get("reference_spans"):
        ref_evidence = OriginalEvidence(cfg, prepared["reference_spans"], prepared["reference_hashes"])
        ref_pool = {sid: {"id": sid, "source": row["source"], "section": row["section"],
                          "quote": row["text"], "kind": "uncertain", "source_role": "reference_context",
                          **({"table_context": row["table_context"]} if row.get("table_context") else {})}
                    for sid, row in ref_evidence.spans.items()}
        for p in base_profile.values():
            if preview is not None and p["id"] not in selected:
                continue
            query = context["target"] + " " + p["name"] + " " + p["description"]
            hits = ref_evidence.find(query)
            lexical = [r["id"] for r in _candidates(query, ref_pool, size=min(5000, _candidate_budget(cfg)//3))]
            for sid in dict.fromkeys(hits + lexical):
                wiki_pool[sid] = ref_pool[sid]
            wiki_counts["function_searches"] += 1
        # If discovery failed, the same bounded lexical retrieval still
        # runs per requirement below, without introducing B obligations.
        if not wiki_pool:
            # Degraded lexical route even when function-level retrieval found no fit.
            wiki_pool.update(ref_pool)
    reference_counts = Counter()
    retry_counts = Counter()
    actor_counts = Counter()
    profile_budget_counts = Counter()
    linked_by_need = {}
    obligations = [row for row in records.values() if row["kind"] in OBLIGATION_KINDS
                   and row["typing_status"] == "classified"]
    # All original obligations are still assessed; selecting a function limits
    # expensive dossier searches, not the integrity of the original registry.
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
                        "quote": r["quote"], "kind": "reference", "source_role": "unspecified",
                        **({"table_context": r["table_context"]} if r.get("table_context") else {})}
                       for r in linked]
        # Preserve the original retrieval path. The dossier is supplemental.
        original_pool = _search_records(cfg, evidence, original_records, {rid}, query)
        pool = linked_pool + original_pool
        for p in base_profile.values():
            for sid in p["refs"]:
                s = spans[sid]
                pool.append({"id": sid, "source": s["source"], "section": s["section"],
                             "quote": s["text"], "kind": "uncertain", "source_role": "unspecified",
                             **({"table_context": s["table_context"]} if s.get("table_context") else {})})
        unique = {}
        for item in pool:
            unique.setdefault(item["id"], item)
        pool = list(unique.values())
        base = {"context": context, "items": [{**_compact(row), "section_role": row["section_role"]}]}
        # Prior links are exact original IDs or dossier facts, not authority.
        # Pass them as hints rather than silently forcing the selected function.
        candidate_ids = [pid for pid, p in base_profile.items()
                         if rid in p.get("record_refs", []) or rid in dossier_ids.get(pid, [])]
        if candidate_ids:
            base["items"][0]["candidate_function_ids"] = candidate_ids
        if linked or gaps:
            base["reference_status"] = {"linked_ids": [r["id"] for r in linked], "gaps": gaps}
        budget = _candidate_budget(cfg)
        base["profile"] = _allocation_profile_rows(base_profile, candidate_ids, budget, base)
        omitted = len(base_profile) - len(base["profile"])
        if omitted:
            profile_budget_counts["limited_allocations"] += 1
            profile_budget_counts["omitted_profile_entries"] += omitted
            offered_ids = {p["id"] for p in base["profile"]}
            profile_budget_counts["omitted_candidate_entries"] += len(set(candidate_ids) - offered_ids)
            if candidate_ids:
                base["items"][0]["candidate_function_ids"] = [pid for pid in candidate_ids if pid in offered_ids]
        if _payload_size(base) > budget:
            if prepared.get("reference_sources"):
                wiki_counts["allocation_budget_limit"] += 1
            decisions[rid] = {"status": "allocation_context_limit", "change": "unknown",
                              "category": "uncertain", "state_refs": [], "reason": ""}
            continue
        remaining = max(0, budget - _payload_size(base) - 300)
        matched_functions = set()
        for pos in row.get("source_spans", []):
            matched_functions.update(dossier_positions.get((pos["source"], pos["fragment"]), set()))
        # Supplemental quotes must not displace evidence already selected by
        # the original search. Append only in genuinely unused context.
        # Reserve room for actual B evidence before unrelated A hits fill the
        # payload. Explicit linked originals take precedence over B.
        linked_rows = _bounded_rows(linked_pool, remaining)
        linked_cost = sum(_payload_size(r) + 2 for r in linked_rows)
        wiki_budget = min(max(0, remaining - linked_cost), budget // 5) if wiki_pool else 0
        reserved_wiki = _bounded_rows(_candidates(query, wiki_pool, size=wiki_budget), wiki_budget) if wiki_budget else []
        wiki_cost = sum(_payload_size(r) + 2 for r in reserved_wiki)
        pool = _bounded_rows(pool, remaining - wiki_cost)
        selected_ids = {r["id"] for r in pool} | {rid}
        extras = [_compact(records[k]) for pid in sorted(matched_functions)
                  for k in dossier_ids[pid] if k not in selected_ids]
        unique_extras = {r["id"]: r for r in extras}
        free = max(0, remaining - wiki_cost - sum(_payload_size(r) + 2 for r in pool))
        pool.extend(_bounded_rows(unique_extras.values(), free))
        # Evidence is a view over existing registry/source spans; no second search index.
        # Keep B explicitly labelled and separate from obligations.
        allocation_profile = {p["id"]: base_profile[p["id"]] for p in base["profile"]}
        if wiki_pool:
            free = max(0, remaining - sum(_payload_size(r) + 2 for r in pool))
            # Add B hints only together with supporting spans.
            extra_budget = min(free, budget // 5)
            wiki = reserved_wiki or _bounded_rows(_candidates(query, wiki_pool, size=extra_budget), extra_budget)
            wiki_ids = {r["id"] for r in wiki}
            spare = max(0, extra_budget - sum(_payload_size(r) + 2 for r in wiki))
            hints = _bounded_rows(({"id": p["id"], "name": p["name"]} for p in profile.values()
                                   if p.get("origin") == "reference" and set(p["refs"]) <= wiki_ids), spare)
            base["profile"].extend(hints)
            allocation_profile.update({p["id"]: profile[p["id"]] for p in hints})
            pool.extend(wiki)
            wiki_counts["needs_with_context"] += int(bool(wiki))
            wiki_counts["spans_supplied"] += len(wiki)
            if not wiki:
                wiki_counts["allocation_budget_limit"] += 1
        elif prepared.get("reference_sources"):
            wiki_counts["allocation_no_candidates"] += 1
        supplied = {r["id"] for r in pool}
        if linked or gaps:
            omitted = sum(r["id"] not in supplied for r in linked)
            if omitted:
                reference_counts["budget_limit"] += omitted
                gaps["budget_limit"] = gaps.get("budget_limit", 0) + omitted
            base["reference_status"] = {"linked_ids": [r["id"] for r in linked if r["id"] in supplied], "gaps": gaps}
        # Incomplete links are explicit evidence gaps, not a reason to skip
        # attribution. The independent reviewer cannot certify change/coverage
        # while a required linked clause is unresolved.
        state.update({r["id"]: r for r in pool})
        # Retry an invalid ID/schema once, not a semantic uncertainty or gateway outage.
        payload = {**base, "evidence": pool}
        retry_kind = ""
        for attempt in range(2):
            retry_payload = ({"retry_actor": retry_kind} if retry_kind and retry_kind != "contract"
                             else {"retry_contract": True})
            answers, statuses, _ = _unique_answers(cfg, "target_allocation",
                payload if not attempt else {**payload, **retry_payload}, [rid])
            if rid not in answers:
                decision = {"status": statuses[rid], "change": "unknown", "category": "uncertain",
                            "state_refs": [], "reason": ""}
            else:
                decision = _validate_decision(answers[rid], rid, records, {r["id"]: r for r in pool},
                                              allocation_profile, context["target"])
            malformed = decision["status"] in {"invalid_response", "missing_response", "duplicate_response"}
            actor_issue = decision.get("actor_validation")
            if actor_issue:
                actor_counts[actor_issue] += 1
            if attempt:
                if retry_kind == "contract":
                    retry_counts["recovered" if not malformed and decision["status"] != "batch_error" else "exhausted"] += 1
                else:
                    actor_counts["retry_proposed" if decision["status"] == "proposed" else
                                 "retry_unresolved"] += 1
                break
            if malformed:
                retry_kind = "contract"
                retry_counts["attempted"] += 1
            elif actor_issue:
                retry_kind = actor_issue
                actor_counts["retry_attempted"] += 1
            else:
                break
        decisions[rid] = decision
        if decision["status"] == "proposed" and decision.get("function") in dossier_ids:
            # Keep additional function evidence separate from current-state assertions.
            fact_rows = [_compact(records[k]) for k in dossier_ids[decision["function"]]
                         if k in supplied and k != rid and k not in decision["state_refs"]]
            decision["dossier_refs"] = [r["id"] for r in _bounded_rows(fact_rows, min(2500, budget // 5))]
        if linked or gaps:
            decisions[rid]["reference_refs"] = base["reference_status"]["linked_ids"]
            decisions[rid]["reference_gaps"] = gaps
    verification_counts = _verify_decisions(cfg, decisions, records, state, context, emit, reset_cache=reset_cache)
    # Allocation can identify another function missed by discovery. Make it
    # an unselected scope candidate using only verified original R/F links.
    if preview is not None:
        by_name = {_normalized(p["name"]).casefold(): p for p in base_profile.values()}
        for rid, decision in decisions.items():
            if (decision.get("status") not in {"model_supported", "applicability_supported"}
                    or decision.get("function") != "new"):
                continue
            name = decision["function_name"]
            key = _normalized(name).casefold()
            p = by_name.get(key)
            if p is None:
                if len(base_profile) >= _MAX_PROFILE:
                    function_counts["context_limit"] += 1
                    function_counts["profile_cap_omitted"] += 1
                    continue
                pid = "C" + str(len(base_profile) + 1)
                p = {"id": pid, "name": name, "description": name, "refs": [], "record_refs": []}
                base_profile[pid] = profile[pid] = by_name[key] = p
            if rid not in p["record_refs"]:
                p["record_refs"].append(rid)
            for pos in records[rid].get("source_spans", []):
                sid = references.positions.get((pos["source"], pos["fragment"]))
                if sid in spans and sid not in p["refs"]:
                    p["refs"].append(sid)
            decision["function"] = p["id"]
            decision["function_name"] = p["name"]
    groups = _group_decisions(decisions)
    # Independent evidence-backed candidate links; primary verified allocation
    # still governs derivation. Shared records are not copied into other groups.
    function_links = {rid: [] for rid in records}
    for pid, p in base_profile.items():
        for rid in p.get("record_refs", []):
            function_links[rid].append(pid)
        for rid in dossier_ids.get(pid, []):
            if pid not in function_links[rid]:
                function_links[rid].append(pid)
    for rid, d in decisions.items():
        if d.get("status") in {"model_supported", "applicability_supported"} and d.get("function") in base_profile:
            if d["function"] not in function_links[rid]:
                function_links[rid].append(d["function"])
    review_summaries, summary_counts = (summarize_needs(cfg, groups, records, decisions, state, context, emit, _json)
                                       if summaries else ({}, {}))
    proposals, questions, outcomes = [], [], {}
    for g in groups:
        for rid in g["requirement_ids"]:
            if decisions[rid]["change"] == "unknown":
                outcomes[rid] = "implementation_unknown"
            elif decisions[rid]["change"] != "already_supported":
                outcomes[rid] = "awaiting_decomposition"
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
    diagnostics["characteristic_review"] = dict(characteristic_counts)
    diagnostics["dossier_priority"] = dict(Counter(
        f"{facet}_{row['status']}" for dossier in dossiers.values()
        for facet, row in dossier["facets"].items()
        if facet in {"data_categories", "data_content", "direction", "security", "data_constraints",
                     "performance", "capacity"}))
    diagnostics["profile_status"] = (dict(function_counts) if automatic_functions else
                                     {prepared.get("profile_status", "no_candidates"): 1})
    wiki_status = prepared.get("reference_status", "disabled")
    if automatic_functions and wiki_status not in {"disabled", "source_error"}:
        wiki_status = "found" if wiki_pool else "no_candidates"
    diagnostics["wiki_status"] = {wiki_status: 1}
    diagnostics["wiki_context"] = {**wiki_counts, "sources": len(prepared.get("reference_hashes", {})),
                                   "read_errors": len(prepared.get("reference_issues", []))}
    diagnostics["scope_selection"] = {"selected": len(selected), "offered": len(preview["approved_profile"])} if preview is not None else {}
    diagnostics["preliminary_applicability"] = dict(Counter(a["category"] for a in preview["applicability"].values())) if preview is not None else {}
    diagnostics["function_links"] = {"linked_records": sum(bool(ids) for ids in function_links.values()),
                                      "shared_records": sum(len(ids) > 1 for ids in function_links.values()),
                                      "unlinked_records": sum(not ids for ids in function_links.values())}
    diagnostics["function_review"] = dict(Counter(d.get("function_status", "unresolved")
                                                  for d in decisions.values()))
    # Counts are over known candidate links, not a semantic recall estimate.
    scope_counts = Counter()
    for rid, ids in function_links.items():
        if not selected.intersection(ids) or rid not in decisions:
            continue
        scope_counts["candidate_obligations"] += 1
        d = decisions[rid]
        if d.get("status") in {"model_supported", "applicability_supported"} and d.get("function") in selected:
            scope_counts["selected_primary"] += 1
        elif d.get("status") == "model_supported" and d.get("change") == "external":
            scope_counts["external"] += 1
        elif d.get("status") in {"model_supported", "applicability_supported"}:
            scope_counts["other_primary"] += 1
        else:
            scope_counts["unresolved"] += 1
    diagnostics["selected_link_coverage"] = dict(scope_counts)
    diagnostics["summaries"] = summary_counts
    diagnostics["verification"] = dict(verification_counts)
    diagnostics["allocation_retry"] = dict(retry_counts)
    diagnostics["actor_validation"] = dict(actor_counts)
    diagnostics["profile_budget"] = dict(profile_budget_counts)
    diagnostics["function_hierarchy"] = dict(function_hierarchy(profile)[1])
    diagnostics["applicability"] = dict(Counter(d.get("applicability_status", "unresolved") for d in decisions.values()))
    diagnostics["implementation"] = dict(Counter(d.get("implementation_status", "unknown") for d in decisions.values()))
    diagnostics["allocation_validation"] = dict(Counter(d["validation_code"] for d in decisions.values() if "validation_code" in d))
    diagnostics["references"] = dict(references.counts)
    diagnostics["reference_gaps"] = dict(reference_counts)
    diagnostics["verified_metrics"] = sum(d["status"] == "model_supported" and "metric" in d for d in decisions.values())
    diagnostics["metric_funnel"] = _metric_diagnostics(records, decisions)
    diagnostics["proposal_kinds"] = dict(Counter(p["kind"] for p in proposals))
    diagnostics["proposal_assessments"] = dict(Counter(p["assessment"] for p in proposals))
    diagnostics["source_read_errors"] = len(prepared["issues"])
    _record_draft_diagnostic("target_registry", diagnostics)
    _verify_originals(cfg, prepared)
    return {"requirements": records, "state_evidence": state, "groups": groups,
            "metrics_registry": {rid: d["metric"] for rid, d in decisions.items()
                                 if d["status"] == "model_supported" and "metric" in d},
            "decisions": decisions, "proposals": proposals, "questions": questions,
            "linked_by_need": linked_by_need, "dossiers": dossiers, "approved_profile": list(profile.values()),
            "automatic_functions": automatic_functions, "function_links": function_links,
            "selected_functions": sorted(selected) if preview is not None else None,
            "preliminary_applicability": preview["applicability"] if preview is not None else {},
            "reference_candidates": [r for r in state.values() if r.get("source_role") == "reference_context"],
            "dispositions": outcomes, "fragment_status": fragment_status, "issues": issues,
            "diagnostics": diagnostics, "requires_expert_review": True,
            "phase": "collected", "summaries": review_summaries,
            "input_identity": input_identity(cfg, prepared, list(profile.values()))}

def extend_function_preview(cfg, prepared, preview, collected):
    """Reopen function scope with additive citations, never approve new functions."""
    _verify_originals(cfg, prepared)
    if (preview.get("phase") != "function_preview" or collected.get("phase") != "collected"
            or preview["input_identity"] != input_identity(cfg, prepared, preview["approved_profile"])
            or collected["input_identity"] != input_identity(cfg, prepared, collected["approved_profile"])):
        raise ValueError("Stale function scope")
    if any(rid not in collected["requirements"] or
           any(row[k] != collected["requirements"][rid][k] for k in ("source", "section", "quote"))
           for rid, row in preview["requirements"].items()):
        raise ValueError("Original scope records changed")
    updated = deepcopy(preview)
    updated["approved_profile"] = deepcopy(collected["approved_profile"])
    updated["requirements"] = deepcopy(collected["requirements"])
    updated["function_links"] = deepcopy(collected["function_links"])
    updated["profile_status"] = deepcopy(collected.get("diagnostics", {}).get("profile_status", preview["profile_status"]))
    for rid, row in updated["requirements"].items():
        if row.get("kind") not in OBLIGATION_KINDS or rid in updated["applicability"]:
            continue
        d = collected["decisions"].get(rid, {})
        known = d.get("applicability_status") == "model_supported"
        updated["applicability"][rid] = {"category": d.get("category", "uncertain") if known else "uncertain",
                                         "actor": d.get("actor", "") if known else "",
                                         "reason": d.get("review_reason", "") if known else ""}
    updated["input_identity"] = input_identity(cfg, prepared, updated["approved_profile"])
    return updated


def _combine_metrics(prior, result):
    previous, current = prior["metrics"], result["metrics"]
    stages = deepcopy(previous["stages"])
    for name, row in current["stages"].items():
        stats = stages.setdefault(name, {"llm_calls": 0, "llm_seconds": 0.0})
        for field in ("llm_calls", "llm_seconds"):
            stats[field] += row[field]
    current["stages"] = stages
    current["total_seconds"] += previous["total_seconds"]
    current["diagnostics"] = {**previous["diagnostics"], **current["diagnostics"]}
    return result

def collect_target_requirements(cfg, prepared, approved_profile=None, progress=None, *, reset_cache=False,
                                summaries=True, preview_only=False, preview=None, selected_functions=None):
    result = _collect_target_requirements(cfg, prepared, approved_profile, progress, reset_cache=reset_cache,
                                          summaries=summaries, preview_only=preview_only, preview=preview,
                                          selected_functions=selected_functions)
    return _combine_metrics(preview, result) if preview is not None else result


@_measure_draft
def _decompose_target_requirements(cfg, prepared, collected, selection, notes, progress):
    if collected.get("phase") != "collected" or collected.get("input_identity") != input_identity(
            cfg, prepared, collected["approved_profile"]):
        raise ValueError("Collected requirements no longer match inputs")
    _verify_originals(cfg, prepared)
    groups, review = review_scope(collected, selection, notes)
    result = deepcopy(collected)
    records, decisions, state = result["requirements"], result["decisions"], result["state_evidence"]
    emit = progress or (lambda *_: None)
    # Keep the original decision graph for traceability. Excluded need IDs
    # cannot re-enter derivation or coverage as supplemental R-ID evidence.
    excluded = set(review["excluded"])
    derivation_decisions = deepcopy(decisions)
    for decision in derivation_decisions.values():
        for field in ("state_refs", "reference_refs", "dossier_refs"):
            if field in decision:
                decision[field] = [rid for rid in decision[field] if rid not in excluded]
    derivation_state = {rid: row for rid, row in state.items() if rid not in excluded}
    proposals, questions, outcomes = _proposals(cfg, groups, derivation_decisions, records, derivation_state,
                                                prepared["context"], emit, notes=review["notes"])
    dispositions = result["dispositions"]
    for rid in review["excluded"]:
        dispositions[rid] = "expert_excluded"
    for rid in review["included"]:
        dispositions[rid] = outcomes.get(rid, "coverage_gap")
    result.update(phase="decomposed", proposals=proposals, questions=questions, review=review)
    diagnostics = result["diagnostics"]
    diagnostics["outcomes"] = dict(Counter(dispositions.values()))
    diagnostics["proposal_kinds"] = dict(Counter(p["kind"] for p in proposals))
    diagnostics["proposal_assessments"] = dict(Counter(p["assessment"] for p in proposals))
    diagnostics["review_scope"] = {"included": len(review["included"]), "excluded": len(review["excluded"]),
                                   "notes": len(review["notes"])}
    diagnostics["dossiers"].update(summarize_dossiers(result["dossiers"], decisions, dispositions, proposals))
    _record_draft_diagnostic("target_registry", diagnostics)
    _verify_originals(cfg, prepared)
    return result


def decompose_target_requirements(cfg, prepared, collected, progress=None, *, selection=None, notes=None):
    """Resume without rescanning or allocating. Combine compute time only."""
    result = _decompose_target_requirements(cfg, prepared, collected, selection, notes, progress)
    return _combine_metrics(collected, result)


def analyze_target_registry(cfg, prepared, approved_profile, progress=None, *, reset_cache=False):
    """Automatic path uses the very same collection and decomposition stages."""
    collected = collect_target_requirements(cfg, prepared, approved_profile, progress,
                                            reset_cache=reset_cache, summaries=False)
    return decompose_target_requirements(cfg, prepared, collected, progress)

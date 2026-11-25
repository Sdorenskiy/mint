"""Experimental typed registry for Draft V2, not the active Word generator.

Reuse validated extraction and its checkpoints. A type decision is not semantic
verification or applicability. Preserve all evidence and unsuccessful decisions
for review; do not discard a citation merely because it is not an obligation.
"""
from collections import Counter
import re

from .draft_checkpoint import DraftStageCheckpoint

from .template_draft import (DraftError, _batches, _json, _records, _requirements,
                             _record_draft_diagnostic, _text)

SOURCE_ROLES = frozenset({"need", "architecture", "normative", "mixed", "unspecified"})
KINDS = frozenset({"functional", "nonfunctional", "constraint", "definition",
                   "current_state", "open_question", "reference", "non_requirement",
                   "uncertain"})
OBLIGATION_KINDS = frozenset({"functional", "nonfunctional", "constraint"})
# Only clear contents entries (heading AND dotted leader/page number).
# Avoid blanket deletion of all text under a heading or all numbered lines.
_CONTENTS = re.compile(r"^(?:table of contents|contents|оглавление|содержание)$", re.I)
_LEADER = re.compile(r"\.{3,}\s*\d+\s*$")
_BATCH_LIMIT = 12


def _toc_entry(row):
    return bool(_CONTENTS.fullmatch(row["section"].strip()) and
                _LEADER.search(row["quote"]) and "\n" not in row["quote"])


def _type_records(cfg, records, emit, *, reset_cache=False):
    """Assign one type per ID, failing closed on malformed/duplicate answers."""
    pending = []
    for row in records.values():
        row["kind"] = "uncertain"
        row["typing_status"] = "missing_response"
        if _toc_entry(row):
            row.update(kind="non_requirement", typing_status="structural")
        else:
            pending.append({key: row[key] for key in
                            ("id", "source", "section", "quote", "source_role")})

    groups = failed_groups = unknown_rows = duplicate_rows = cache_hits = 0
    checkpoint = DraftStageCheckpoint(cfg, "registry_type")
    for offset in range(0, len(pending), _BATCH_LIMIT):
        for batch in _batches(pending[offset:offset + _BATCH_LIMIT],
                              lambda r: r["quote"] + r["section"] + r["source"]):
            groups += 1
            emit("registry_type", groups)
            allowed = {row["id"] for row in batch}
            payload = {"items": batch}
            if reset_cache:
                checkpoint.clear(payload)
            cached = None if reset_cache else checkpoint.load(payload)
            if (cached is not None and set(cached) == set(allowed)
                    and all(kind in KINDS - {"uncertain"} for kind in cached.values())):
                cache_hits += 1
                for rid, kind in cached.items():
                    records[rid].update(kind=kind, typing_status="classified")
                continue
            try:
                answers = _records(_json(cfg, "registry_type", payload), "items")
            except DraftError:
                failed_groups += 1
                for rid in allowed:
                    records[rid]["typing_status"] = "batch_error"
                continue
            seen = set()
            for answer in answers:
                rid = _text(answer, "id")
                if rid not in allowed:
                    unknown_rows += 1
                    continue
                row = records[rid]
                if rid in seen:
                    duplicate_rows += 1
                    row.update(kind="uncertain", typing_status="duplicate_response")
                    continue
                seen.add(rid)
                kind = _text(answer, "kind")
                if kind not in KINDS:
                    row["typing_status"] = "invalid_kind"
                    continue
                row.update(kind=kind, typing_status=(
                    "explicit_uncertain" if kind == "uncertain" else "classified"))
            if all(records[rid]["typing_status"] == "classified" for rid in allowed):
                checkpoint.save(payload, {rid: records[rid]["kind"] for rid in allowed})

    _record_draft_diagnostic("registry_type", {
        "groups": groups, "failed_groups": failed_groups, "cache_hits": cache_hits,
        "unknown_rows": unknown_rows, "duplicate_rows": duplicate_rows,
        "kind_counts": dict(Counter(row["kind"] for row in records.values())),
        "status_counts": dict(Counter(row["typing_status"] for row in records.values())),
    })


def build_registry(cfg, documents, source_roles, issues, emit, *, reset_cache=False,
                   focus=None, prepared_chunks=None, fragment_status=None):
    """Build the minimal V2 registry from parsed selected originals.

    Source roles are supplied by the caller (not inferred from filenames).
    Missing roles stay unspecified. Roles never establish a new obligation.
    Fragment indices and revision hashes refer to parsed Markdown, not original
    Word offsets or page numbers. IDs are stable within one run. The caller may
    wrap the pipeline with the existing per-run metrics decorator.
    """
    documents = list(documents)
    names = [name for name, _ in documents]
    if len(names) != len(set(names)):
        raise ValueError("Registry source names must be unique")
    if set(source_roles) - set(names) or any(role not in SOURCE_ROLES
                                               for role in source_roles.values()):
        raise ValueError("Invalid registry source role")
    kwargs = {} if focus is None else dict(focus=focus, prepared_chunks=prepared_chunks,
                                           fragment_status=fragment_status)
    records, chunks = _requirements(cfg, documents, issues, emit,
                                    reset_cache=reset_cache, include_provenance=True, **kwargs)
    for row in records.values():
        row["source_role"] = source_roles.get(row["source"], "unspecified")
    _type_records(cfg, records, emit, reset_cache=reset_cache)
    return {"requirements": records, "chunks": chunks}


def obligation_candidates(records):
    """Candidates for later applicability/derivation, not confirmed obligations."""
    return {rid: row for rid, row in records.items()
            if row["kind"] in OBLIGATION_KINDS and row["typing_status"] == "classified"}

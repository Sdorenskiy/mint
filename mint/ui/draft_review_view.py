"""Read-only projections for the V2 review screen. No model or search calls.

A candidate relationship is never promoted to primary allocation. Each R-ID
has one display bucket; the existing core review_scope remains authoritative.
"""
from collections import defaultdict
import json

from ..template_draft import _normalized
from ..version import MINT_VERSION


def review_view(result):
    records = result["requirements"]
    decisions = result["decisions"]
    profile = {p["id"]: p for p in result.get("approved_profile", [])}
    selection = result.get("selected_functions")
    explicit = selection is not None
    selected = list(dict.fromkeys(selection if explicit else profile))
    selected_set = set(selected)
    by_name = defaultdict(list)
    for pid, p in profile.items():
        by_name[p["name"]].append(pid)
    sections = {pid: [] for pid in selected}
    cross, outside, candidates, unallocated = [], [], [], []
    assigned = set()
    primary_ids = set()

    for group in result["groups"]:
        buckets = defaultdict(list)
        for rid in group["requirement_ids"]:
            if rid in assigned or rid not in records:
                continue
            assigned.add(rid)
            d = decisions[rid]
            pid = d.get("function")
            # Compatibility for saved results without the function ID.
            if not pid and len(by_name[group["function"]]) == 1:
                pid = by_name[group["function"]][0]
            if pid == "system_wide":
                bucket = ("cross", "")
            elif not explicit:
                bucket = ("selected", pid or group["id"])
            elif pid in selected_set:
                bucket = ("selected", pid)
            else:
                bucket = ("outside", pid or group["id"])
            buckets[bucket].append(rid)
        for (kind, pid), ids in buckets.items():
            row = {"id": group["id"], "function": group["function"], "ids": ids,
                   "ready": [rid for rid in ids if decisions[rid]["status"] == "model_supported"
                             and decisions[rid]["change"] not in {"unknown", "already_supported", "external"}],
                   "context": [rid for rid in ids if decisions[rid]["change"] == "already_supported"]}
            if kind == "selected":
                sections.setdefault(pid, []).append(row)
                primary_ids.update(ids)
            elif kind == "cross":
                cross.append(row)
                primary_ids.update(ids)
            else:
                outside.append(row)

    # Candidate links that were not confirmed as primary for this scope.
    # Outside primary allocations stay outside, even if also linked to selection.
    for rid in records:
        if (rid not in decisions and records[rid].get("kind") not in {"uncertain", "functional", "nonfunctional", "constraint"}) or rid in primary_ids:
            continue
        linked = selected_set.intersection(result.get("function_links", {}).get(rid, []))
        if rid in assigned:
            continue
        if linked:
            candidates.append(rid)
        else:
            unallocated.append(rid)
    return {"selected": selected, "sections": sections, "cross": cross, "outside": outside,
            "candidates": candidates, "unallocated": unallocated, "profile": profile,
            "primary_ids": primary_ids, "explicit": explicit}


def evidence_rows(rid, prepared, result):
    """Deduplicate only exact citations from the same source/section/table.
    Preserve roles, distinct table occurrences and all reference IDs.
    """
    records, state = result["requirements"], result.get("state_evidence", {})
    d = result["decisions"].get(rid, {})
    related = result.get("linked_by_need", {}).get(rid, {})
    rows = {}

    def add(ref, row, role):
        if not row:
            return
        quote = row.get("quote", row.get("text", ""))
        if not quote:
            return
        key = (row.get("source"), row.get("section"), _normalized(quote),
               (row.get("table_context") or {}).get("occurrence"))
        item = rows.setdefault(key, {"row": row, "quote": quote, "ids": [], "roles": []})
        if ref not in item["ids"]:
            item["ids"].append(ref)
        if role not in item["roles"]:
            item["roles"].append(role)

    def get(ref):
        return records.get(ref) or state.get(ref) or prepared.get("spans", {}).get(ref)

    add(rid, records.get(rid), "original")
    for field, role in (("state_refs", "state"), ("reference_refs", "reference"), ("dossier_refs", "dossier")):
        for ref in d.get(field, []):
            row = get(ref)
            add(ref, row, "wiki" if row and row.get("source_role") == "reference_context" else role)
    for item in related.get("items", []):
        add(item["id"], item, "reference")
    return list(rows.values())


# A private, inert UI snapshot, not a trusted input to analysis or approval.
# No pickle, executable state, model settings, document bytes or source paths
# beyond the displayed citations; JSON is only rendered in a read-only panel.
SNAPSHOT_FORMAT = "mint-review-view/1"
MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024
_SNAPSHOT_FIELDS = ("requirements", "decisions", "groups", "approved_profile", "selected_functions",
                    "function_links", "dossiers", "metrics_registry", "state_evidence", "linked_by_need",
                    "dispositions", "diagnostics", "questions", "issues")


def review_snapshot(prepared, result):
    data = {"format": SNAPSHOT_FORMAT, "mint": MINT_VERSION,
            "prepared": {"context": prepared.get("context", {}), "spans": {}},
            "result": {k: result[k] for k in _SNAPSHOT_FIELDS if k in result}}
    # Only otherwise unavailable spans referenced by existing decisions.
    refs = {ref for d in result["decisions"].values()
            for field in ("state_refs", "reference_refs", "dossier_refs") for ref in d.get(field, [])}
    data["prepared"]["spans"] = {ref: prepared.get("spans", {})[ref] for ref in refs
                                 if ref not in result["requirements"] and ref not in result.get("state_evidence", {})
                                 and ref in prepared.get("spans", {})}
    raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Review snapshot too large")
    return raw


def load_review_snapshot(raw):
    if not raw or len(raw) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Invalid review snapshot size")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("format") != SNAPSHOT_FORMAT:
        raise ValueError("Unknown review snapshot format")
    result, prepared = data["result"], data["prepared"]
    if not isinstance(result, dict) or not isinstance(prepared, dict):
        raise ValueError("Invalid review snapshot")
    for key in ("requirements", "decisions", "function_links", "dossiers", "metrics_registry",
                "state_evidence", "linked_by_need"):
        if not isinstance(result.get(key, {}), dict):
            raise ValueError("Invalid review map")
    for key in ("groups", "approved_profile"):
        if not isinstance(result.get(key), list):
            raise ValueError("Invalid review list")
    if result.get("selected_functions") is not None and not isinstance(result["selected_functions"], list):
        raise ValueError("Invalid selection")
    review_view(result)  # validate the projection before display
    return prepared, result

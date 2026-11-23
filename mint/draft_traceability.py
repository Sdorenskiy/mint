"""Two views of the same evidence: Word section → source, and source → Word.

No extra retrieval or LLM calls. A verbatim output anchor proves only that
a passage exists in generated text, not semantic coverage of a whole requirement.
"""


def build_traceability(result):
    requirements = result.get("requirements", [])
    by_id = {r["id"]: r for r in requirements if r.get("id")}
    records = {rid: {"id": rid, "source": req.get("source", ""),
                     "source_section": req.get("section", ""), "quote": req.get("quote", ""),
                     "applicability": req.get("applicability", {}).get("category", "unassessed"),
                     "actor": req.get("applicability", {}).get("actor", ""),
                     "scope_reason": req.get("applicability", {}).get("reason", ""),
                     "anchored": [], "cited_without_anchor": [], "candidate_sections": []}
               for rid, req in by_id.items()}
    for section, plan in result.get("section_plan", {}).items():
        for rid in plan.get("selected_ids", []):
            if rid in records and section not in records[rid]["candidate_sections"]:
                records[rid]["candidate_sections"].append(section)

    for change in result.get("results", []):
        section = change.get("section") or ""
        field = change.get("field") or ""
        kind = change.get("kind") or "field"
        refs = [rid for rid in change.get("refs", []) if rid in records]
        confirmed = set(change.get("confirmed_refs", []))
        for rid in refs:
            evidence = {"section": section or "—", "field": field, "kind": kind,
                        "text": change.get("text", ""), "status": change.get("status", "")}
            key = "anchored" if rid in confirmed else "cited_without_anchor"
            records[rid][key].append(evidence)
    rows = []
    for req in requirements:
        rid = req.get("id")
        if rid not in records:
            continue
        row = records[rid]
        category = row["applicability"]
        if row["anchored"]:
            row["coverage"] = "output_anchor"
        elif row["cited_without_anchor"]:
            row["coverage"] = "cited_without_anchor"
        elif category in {"other", "interaction"}:
            row["coverage"] = "external"
        elif category == "uncertain":
            row["coverage"] = "scope_uncertain"
        elif row["candidate_sections"]:
            row["coverage"] = "candidate_only"
        else:
            row["coverage"] = "not_selected"
        rows.append(row)
    return rows


def by_word_section(rows, result):
    """Only sections tied to actual generated output or its candidate plan."""
    names = list(result.get("section_plan", {}))
    for row in rows:
        for item in row["anchored"] + row["cited_without_anchor"]:
            section = item["section"]
            if section not in names:
                names.append(section)
    return {section: [row for row in rows if section in row["candidate_sections"] or
                      any(item["section"] == section for item in
                          row["anchored"] + row["cited_without_anchor"])]
            for section in names}


def by_basis_document(rows, source_names=()):
    names = list(dict.fromkeys(source_names))
    for row in rows:
        if row["source"] not in names:
            names.append(row["source"])
    return {name: [row for row in rows if row["source"] == name] for name in names}


def trace_counts(rows):
    """Counts of extracted quotes, not a claim that extraction itself was complete."""
    return {
        "extracted": len(rows),
        "anchored": sum(row["coverage"] == "output_anchor" for row in rows),
        "pending": sum(row["coverage"] in {"cited_without_anchor", "candidate_only",
                                             "not_selected", "scope_uncertain"} for row in rows),
        "external": sum(row["coverage"] == "external" for row in rows),
    }

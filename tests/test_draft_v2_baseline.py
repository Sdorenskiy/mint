"""Fictional V2 characterization, using the actual legacy path and scripted LLM replies.

Normal mode reports known gaps without treating them as fixed.
--strict turns the target invariants into an acceptance gate.
No external calls, work data or persisted user documents.
"""
import argparse
import io
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from docx import Document

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import template_draft as draft
from mint.i18n import set_lang
from mint.requirement_scope import category_of

# Independently authored fixture: a fictional public-library locker reservation.
NOISE = "4.1 Reservation overview ........ 5"
NEED = "Visitors must receive a confirmation of a locker reservation."
OWNER = "The Reservation Desk owns visitor notifications."
EXTERNAL = "The Locker Inventory service allocates the locker."
SHARED = "All reservation services must record rejected reservations."
UNKNOWN = "The timeout for confirmation is to be agreed."
OMITTED = "The Reservation Desk must keep the reservation identifier."
SOURCES = {
    "fictional_brief.md": f"# Contents\n{NOISE}\n# Functions\n{NEED}\n{SHARED}\n{UNKNOWN}\n",
    "fictional_architecture.md": f"# Responsibilities\n{OWNER}\n{EXTERNAL}\n{OMITTED}\n",
}
# This is the independently specified expected platform obligation, not a
# copied quote from either source. A timeout value is not established.
GOLD_PLATFORM_TEXT = "The Reservation Desk must send confirmation of a locker reservation to the visitor."
GOLD_EVIDENCE = (NEED, OWNER)
SECTION = "Functional requirements"
CONTEXT = {"target": "Reservation Desk", "objective": "Locker reservation",
           "scope": "Visitor notifications", "participants": "Locker Inventory"}


def scripted_model(_system, user, *_args, **_kwargs):
    data = json.loads(user)
    if "source" in data:
        # Adversarial but valid exact quotations, including an index entry.
        return json.dumps({"requirements": [{"quote": line} for line in data["text"].splitlines()
                                             if line.strip()]})
    if "context" in data and "requirements" in data:
        rows = []
        for req in data["requirements"]:
            quote = req["quote"]
            if quote == OMITTED:
                # Well-formed JSON with one silently missing ID.
                continue
            category, actor = {
                NEED: ("target", "Reservation Desk"),
                OWNER: ("target", "Reservation Desk"),
                EXTERNAL: ("other", "Locker Inventory"),
                SHARED: ("shared", "All reservation services"),
                UNKNOWN: ("uncertain", ""),
                NOISE: ("other", ""),
            }[quote]
            rows.append({"id": req["id"], "category": category, "actor": actor,
                         "reason": "Explicitly unresolved timeout" if quote == UNKNOWN
                         else "Scripted classification for fictional case"})
        return json.dumps({"items": rows})
    if "blocks" in data:
        return json.dumps({"fields": [], "fixed": []})
    if "field" in data:
        by_quote = {r["quote"]: r["id"] for r in data["requirements"]}
        if all(q in by_quote for q in GOLD_EVIDENCE):
            refs = [by_quote[q] for q in GOLD_EVIDENCE]
            return json.dumps({"status": "filled", "text": GOLD_PLATFORM_TEXT, "refs": refs,
                               "coverage": {rid: GOLD_PLATFORM_TEXT for rid in refs}})
        return json.dumps({"status": "missing", "text": "", "refs": []})
    if "claims" in data:
        return json.dumps({"supported": True, "status": "unchecked"})
    raise AssertionError("Unexpected model call in synthetic baseline")


def run_case():
    set_lang("en")
    doc = Document()
    doc.add_heading(SECTION, level=1)
    doc.add_paragraph("")
    doc.add_paragraph("")
    doc.add_heading("Acceptance", level=1)
    original = io.BytesIO()
    doc.save(original)
    with TemporaryDirectory() as root:
        cfg = SimpleNamespace(kb_path=Path(root), log_path=Path(root) / "logs",
                              llm_model="fictional", max_tokens=1800, max_query_chars=900,
                              llm_context_tokens=12000, chars_per_token=2.5,
                              draft_extract_parallel=1)
        for name, content in SOURCES.items():
            path = draft.source_path(cfg, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        with patch.object(draft, "ask_llm", side_effect=scripted_model), patch.object(
                draft, "search_parent_child", return_value=([], [])):
            result = draft.create_draft(original.getvalue(), cfg, list(SOURCES), context=CONTEXT)

    by_quote = {row["quote"]: row for row in result["requirements"]}
    # Non-negotiable baseline invariants, not expected failures.
    assert all(q in by_quote for q in (NEED, OWNER, EXTERNAL, SHARED, UNKNOWN, OMITTED))
    assert all(row["quote"] in SOURCES[row["source"]] for row in result["requirements"])
    assert category_of(by_quote[EXTERNAL]) == "other"
    assert category_of(by_quote[NEED]) == "target"
    assert category_of(by_quote[SHARED]) == "shared"
    assert category_of(by_quote[UNKNOWN]) == "uncertain"
    assert by_quote[EXTERNAL]["id"] not in result["used"]
    assert by_quote[UNKNOWN]["id"] not in result["used"]

    output = Document(io.BytesIO(result["docx"]))
    texts = [p.text for p in output.paragraphs]
    start = texts.index(SECTION)
    end = texts.index("Acceptance")
    section_text = "\n".join(texts[start + 1:end]).strip()
    metrics = result["metrics"]
    extraction = metrics["extraction"]
    assert metrics["run_id"]
    assert extraction["completed"] == extraction["total"] == result["chunks"]
    assert extraction["cache_hits"] == 0
    assert extraction["cache_misses"] == extraction["total"]
    assert metrics["stages"]["extract"]["llm_calls"] == extraction["cache_misses"]
    assert metrics["stages"]["scope"]["llm_calls"] >= 1
    # Aspirational contract checks. A current limitation is not a successful
    # quality test. Only exact named gates may be reported as known gaps.
    gates = {
        "exclude_index_entries": NOISE not in by_quote,
        "distinguish_missing_classification": (
            by_quote[OMITTED]["applicability"].get("processing_status") == "missing_response"
            and by_quote[UNKNOWN]["applicability"].get("processing_status") == "classified"),
        "nonempty_function_section": bool(section_text),
        "derived_obligation_with_both_sources": (
            GOLD_PLATFORM_TEXT in section_text and
            any({by_quote[q]["id"] for q in GOLD_EVIDENCE} <= set(row.get("refs", []))
                for row in result["results"] if GOLD_PLATFORM_TEXT in row.get("text", ""))),
    }
    return gates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Require all target invariants")
    args = parser.parse_args()
    gates = run_case()
    for name, ok in gates.items():
        print(f"{'PASS' if ok else 'KNOWN GAP'}: {name}")
    gaps = [name for name, ok in gates.items() if not ok]
    print(f"ИТОГ: synthetic V2 baseline; {len(gaps)} known gaps; not real-model evaluation")
    return 1 if args.strict and gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Characterize known legacy gaps before replacing the drafting algorithm.

All inputs and model replies are fictional. Passing these tests establishes
a baseline and accurate diagnostics, not successful document generation.
The legacy-gap assertions must be replaced by positive acceptance tests
when that path is retired.
"""
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
from mint import requirement_scope as scope
from mint.i18n import set_lang

set_lang("ru")

TARGET = "Library kiosk"
CONTEXT = {"target": TARGET, "objective": "Book collection", "scope": "Collection",
           "participants": "Catalogue service"}
SECTION = "Functional requirements"
NEED = "The library must let a reader collect a reserved book."
ARCHITECTURE = "The Library kiosk scans reservation codes via a local scanner."
EXTERNAL = "The Catalogue service owns reservation validity decisions."
CROSS_CUTTING = "All participating services must record failed operations."
CONTENTS = "4. Book collection ........ 12"
OTHER = "The Archive service retains historic catalogue exports."
UNKNOWN = "The designated component shall display the result."
GOLD = {
    "need": NEED,
    "architecture": ARCHITECTURE,
    "external": EXTERNAL,
    "shared": CROSS_CUTTING,
    "other": OTHER,
    "unknown": UNKNOWN,
    "not_requirement": CONTENTS,
    "open_question": "How long may the kiosk wait for a catalogue reply?",
}


def test_legacy_empty_section_and_extraction_baseline():
    doc = Document()
    doc.add_heading(SECTION, level=1)
    doc.add_paragraph("")
    doc.add_paragraph("")
    doc.add_heading("Other information", level=1)
    doc.add_paragraph("Fixed text.")
    buf = io.BytesIO()
    doc.save(buf)
    with TemporaryDirectory() as tmp:
        cfg = SimpleNamespace(kb_path=Path(tmp), max_query_chars=1000,
                              max_tokens=1600, draft_extract_parallel=1)
        for name, content in (
            ("needs.md", "# Contents\n" + CONTENTS + "\n# Needs\n" + NEED + "\n" + CROSS_CUTTING),
            ("architecture.md", "# Responsibilities\n" + ARCHITECTURE + "\n" + EXTERNAL
             + "\n" + OTHER + "\n" + UNKNOWN),
        ):
            path = draft.source_path(cfg, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        def fake_json(_cfg, stage, payload):
            if stage == "layout":
                return {"fields": [], "fixed": []}
            if stage == "extract":
                # A valid verbatim quote need not be a meaningful requirement.
                return {"requirements": [{"quote": line} for line in payload["text"].splitlines()
                                         if line.strip()]}
            if stage == "scope":
                decisions = {
                    NEED: ("target", TARGET),
                    ARCHITECTURE: ("target", TARGET),
                    CROSS_CUTTING: ("shared", "All participating services"),
                    EXTERNAL: ("interaction", "Catalogue service"),
                    OTHER: ("other", "Archive service"),
                    UNKNOWN: ("uncertain", ""),
                }
                return {"items": [
                    {"id": r["id"], "category": decisions[r["quote"]][0],
                     "actor": decisions[r["quote"]][1], "reason": "Synthetic classification"}
                    for r in payload["requirements"] if r["quote"] in decisions
                ]}
            raise AssertionError("Unexpected stage: " + stage)

        with patch.object(draft, "_json", side_effect=fake_json), patch.object(
                scope, "_json", side_effect=fake_json):
            result = draft.create_draft(buf.getvalue(), cfg, ["needs.md", "architecture.md"],
                                        context=CONTEXT)
        by_quote = {r["quote"]: r for r in result["requirements"]}
        diag = result["metrics"]["diagnostics"]
        assert NEED in by_quote and ARCHITECTURE in by_quote
        assert len(by_quote) == 7
        assert diag["extraction"]["accepted_records"] == 7
        assert diag["scope"]["decisions"][by_quote[CONTENTS]["id"]] == "missing_response"
        assert diag["scope"]["decisions"][by_quote[UNKNOWN]["id"]] == "explicit_uncertain"
        # These are documented *legacy limitations*, not desired behavior:
        assert CONTENTS in by_quote
        assert SECTION not in result["section_plan"]
        assert not result["used"]
        out = Document(io.BytesIO(result["docx"]))
        assert [p.text for p in out.paragraphs][1:3] == ["", ""]
        assert any(p.text == "Fixed text." for p in out.paragraphs)


def test_scope_diagnostics_preserve_existing_decisions():
    reqs = {"R" + str(i): {"id": "R" + str(i), "quote": "Synthetic item " + str(i)}
            for i in range(1, 9)}
    rows = [
        {"id": "R1", "category": "target", "actor": TARGET, "reason": "Obligation"},
        {"id": "R1", "category": "invalid"},
        {"id": "R2", "category": "uncertain"},
        {"id": "R3", "category": "target", "actor": TARGET},
        {"id": "R4", "category": "target", "actor": "", "reason": "No actor"},
        {"id": "R5", "category": "not-a-category"},
        {"id": "R7", "category": "other", "reason": "External obligation"},
        {"id": "unknown", "category": "target", "actor": TARGET, "reason": "Unknown ID"},
    ]

    @draft._measure_draft
    def run():
        issues = []
        classified = scope.classify(SimpleNamespace(), reqs, CONTEXT, issues, lambda *_: None)
        return {"classified": classified, "issues": issues}

    with patch.object(scope, "_json", return_value={"items": rows}):
        result = run()
    d = result["metrics"]["diagnostics"]["scope"]
    assert d["decisions"] == {
        "R1": "classified", "R2": "explicit_uncertain", "R3": "missing_reason",
        "R4": "missing_actor", "R5": "invalid_category", "R6": "missing_response",
        "R7": "classified", "R8": "missing_response",
    }
    assert sum(d["decision_counts"].values()) == len(reqs)
    assert d["duplicate_rows"] == d["unexpected_rows"] == 1
    assert set(scope.partition(result["classified"], CONTEXT)[0]) == {"R1"}
    assert scope.category_of(result["classified"]["R7"]) == "other"

    with patch.object(scope, "_json", side_effect=draft.DraftError("bad reply")):
        failed = run()
    assert failed["metrics"]["diagnostics"]["scope"]["decision_counts"] == {"batch_error": 8}
    assert failed["metrics"]["run_id"] != result["metrics"]["run_id"]
    assert all(scope.category_of(r) == "uncertain" for r in failed["classified"].values())
    serialized = json.dumps(result["metrics"])
    assert TARGET not in serialized and "Synthetic item" not in serialized
    assert "Unknown ID" not in serialized


if __name__ == "__main__":
    test_legacy_empty_section_and_extraction_baseline()
    test_scope_diagnostics_preserve_existing_decisions()
    print("ИТОГ: baseline legacy gaps, scope response diagnostics, run identity")

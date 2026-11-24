"""Full experimental V2 chain with real DOCX rendering and scripted LLM."""
import io
import sys
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from docx import Document

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import draft_derivation as derivation
from mint import draft_function_analysis as analysis
from mint import draft_registry as registry
from mint import draft_section_pilot as pilot
from mint import template_draft as draft
from mint.prompts import default_prompts

NEED = "Visitors must receive confirmation of reservations."
OWNER = "The Reservation Desk owns visitor notifications."
EXTERNAL_NEED = "The Locker Inventory must allocate lockers."
EXTERNAL_OWNER = "The Locker Inventory owns locker allocation."
SHARED = "All reservation services must log rejected reservations."
QUESTION = "The confirmation timeout is to be agreed."
OUTPUT = "The Reservation Desk must send reservation confirmation to visitors."
CONTEXT = {"target": "Reservation Desk", "objective": "Locker reservation",
           "scope": "Visitor notifications", "participants": "Locker Inventory"}
ROLES = {"needs.md": "need", "roles.md": "architecture"}
TYPES = {NEED: "functional", EXTERNAL_NEED: "functional", OWNER: "current_state",
         EXTERNAL_OWNER: "current_state", SHARED: "nonfunctional", QUESTION: "open_question"}


def template():
    doc = Document()
    doc.add_paragraph("Unchanged front matter")
    doc.add_heading("Contents", level=1)
    doc.add_paragraph("")
    doc.add_heading("Functional obligations", level=1)
    doc.add_paragraph(" ")
    doc.add_paragraph("", style="Normal")
    doc.add_heading("Fixed information", level=1)
    doc.add_paragraph("Unchanged body")
    doc.add_heading("Tables", level=1)
    doc.add_table(rows=1, cols=1).cell(0, 0).text = "Unchanged table"
    doc.add_heading("Signatures", level=1)
    doc.add_paragraph("Signature placeholder")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def run(coverage):
    raw = template()
    sections = pilot.pilot_sections(raw)
    assert len(sections) == 1 and sections[0]["title"] == "Functional obligations"
    with TemporaryDirectory() as tmp:
        cfg = SimpleNamespace(kb_path=Path(tmp) / "kb", log_path=Path(tmp) / "logs",
                              llm_model="synthetic", max_query_chars=1000, max_tokens=1800,
                              llm_context_tokens=12000, chars_per_token=2.5, draft_extract_parallel=1)
        for name, text in (("needs.md", "# Needs\n" + "\n".join([NEED, EXTERNAL_NEED, SHARED, QUESTION])),
                           ("roles.md", "# Roles\n" + "\n".join([OWNER, EXTERNAL_OWNER]))):
            path = draft.source_path(cfg, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

        def model(_cfg, stage, payload):
            if stage == "extract":
                return {"requirements": [{"quote": line} for line in payload["text"].splitlines()
                                         if line.strip()]}
            if stage == "registry_type":
                return {"items": [{"id": r["id"], "kind": TYPES[r["quote"]]}
                                  for r in payload["items"]]}
            if stage == "function_group":
                return {"items": [{"id": r["id"], "group": r["id"]} for r in payload["items"]]}
            if stage == "function_allocation":
                items = []
                for r in payload["items"]:
                    external = r["quote"] == EXTERNAL_NEED
                    owner = EXTERNAL_OWNER if external else OWNER
                    ref = next(x["id"] for x in payload["current_state"] if x["quote"] == owner)
                    items.append({"id": r["id"], "category": "other" if external else "target",
                                  "actor": "Locker Inventory" if external else CONTEXT["target"],
                                  "state_refs": [ref], "reason": "Fictional ownership"})
                return {"items": items}
            if stage == "requirement_derivation":
                need = payload["items"][0]
                assert need["quote"] == NEED
                return {"items": [{"id": need["id"], "status": "proposed", "requirements": [{
                    "text": OUTPUT, "actor": CONTEXT["target"], "mode": "derived",
                    "need_refs": [need["id"]], "state_refs": [payload["current_state"][0]["id"]],
                    "constraint_refs": [], "reason": "Need and owner"}]}]}
            if stage == "requirement_assessment":
                assert {row["quote"] for row in payload["evidence"]} == {NEED, OWNER}
                return {"supported": True, "correct_actor": True, "no_new_decisions": True,
                        "reason": "Both sources support it"}
            if stage == "pilot_coverage":
                assert payload["section"] == "Functional obligations"
                assert payload["requirements"][0]["text"] == OUTPUT
                return coverage
            raise AssertionError(stage)

        with ExitStack() as stack:
            for module in (draft, registry, analysis, derivation, pilot):
                stack.enter_context(patch.object(module, "_json", side_effect=model))
            result = pilot.create_section_pilot(raw, cfg, list(ROLES), ROLES, CONTEXT,
                                                sections[0]["index"])
    original = Document(io.BytesIO(raw))
    out = Document(io.BytesIO(result["docx"]))
    assert out.paragraphs[0].text == original.paragraphs[0].text
    assert out.paragraphs[2].text == ""  # contents untouched
    assert any(p.text == "Unchanged body" for p in out.paragraphs)
    assert out.tables[0].cell(0, 0).text == "Unchanged table"
    assert out.paragraphs[-1].text == "Signature placeholder"
    assert result["requires_expert_review"] is True
    return result, out


def test_complete_chain():
    result, out = run({"section_relevant": True, "covered": True, "reason": "Synthetic coverage"})
    assert result["pilot_status"] == "partial_draft"
    assert out.paragraphs[4].text == " "
    assert out.paragraphs[5].text == OUTPUT
    assert out.paragraphs[5].style.name == "Normal"
    assert out.paragraphs[6].text == "Fixed information"
    by_quote = {row["quote"]: row["id"] for row in result["requirements"]}
    assert result["section_dispositions"][by_quote[NEED]] == "model_covered"
    assert result["section_dispositions"][by_quote[EXTERNAL_NEED]] == "external_proposal"
    assert result["derivation"]["cross_cutting_ids"] == [by_quote[SHARED]]
    assert result["derivation"]["open_question_ids"] == [by_quote[QUESTION]]
    assert set(result["results"][0]["refs"]) == {by_quote[NEED], by_quote[OWNER]}
    anchored = {row["id"] for row in result["traceability"] if row["anchored"]}
    assert anchored == {by_quote[NEED], by_quote[OWNER]}
    assert result["metrics"]["diagnostics"]["pilot_section"]["inserted"] == 1


def test_coverage_gap_and_invalid_section():
    for reply, expected in (
        ({"section_relevant": True, "covered": False, "reason": "Omitted condition"}, "coverage_gap"),
        ({"section_relevant": False, "covered": True, "reason": "Wrong section"}, "out_of_section_proposal"),
        ({"section_relevant": True, "covered": "true", "reason": "Invalid boolean"}, "review_incomplete"),
    ):
        result, out = run(reply)
        assert result["pilot_status"] == "empty_draft"
        assert out.paragraphs[5].text == ""
        assert expected in result["section_dispositions"].values()
        assert not result["used"] and not result["results"]
    with patch.object(pilot, "_load_draft_sources", side_effect=AssertionError("unsafe section")):
        try:
            pilot.create_section_pilot(template(), None, [], {}, CONTEXT, 1)
            raise AssertionError("contents accepted")
        except draft.DraftError:
            pass


def test_prompt_contract():
    for lang in ("ru", "en"):
        prompt = default_prompts(lang)["draft_pilot_coverage"]
        assert all(key in prompt for key in ("section_relevant", "covered", "reason"))


if __name__ == "__main__":
    test_complete_chain()
    test_coverage_gap_and_invalid_section()
    test_prompt_contract()
    print("ИТОГ: end-to-end V2 Word pilot, section preservation, traceability and coverage gaps")

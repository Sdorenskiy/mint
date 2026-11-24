"""Full experimental V2 chain with real DOCX rendering and scripted LLM."""
import io
import sys
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement

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


def template(*, instructions=False):
    doc = Document()
    doc.add_paragraph("Unchanged front matter")
    doc.add_heading("Contents", level=1)
    doc.add_paragraph("")
    doc.add_heading("Functional obligations", level=1)
    doc.add_paragraph(" ")
    if instructions:
        doc.add_paragraph("[Describe the required functions")
        doc.add_paragraph("and specify the interactions.]")
        doc.add_paragraph("Example: fictional example")
    else:
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


def run(coverage, *, repair_text=None, reject_first=False, instructions=False):
    attempts = {"repair": 0, "assessment": 0, "coverage": 0}
    raw = template(instructions=instructions)
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
                if "repair" in payload:
                    attempts["repair"] += 1
                    assert attempts["repair"] == 1
                    assert payload["repair"]["feedback"]["status"] in {"coverage_gap", "needs_review"}
                    assert payload["repair"]["previous"][0]["text"] == OUTPUT
                    if reject_first:
                        assert payload["repair"]["previous"][0]["reason"] == "Incorrect attribution"
                    else:
                        assert payload["repair"]["feedback"]["reason"] == "Omitted condition"
                return {"items": [{"id": need["id"], "status": "proposed", "requirements": [{
                    "text": repair_text if "repair" in payload and repair_text else OUTPUT,
                    "actor": CONTEXT["target"], "mode": "derived",
                    "need_refs": [need["id"]], "state_refs": [payload["current_state"][0]["id"]],
                    "constraint_refs": [], "reason": "Need and owner"}]}]}
            if stage == "requirement_assessment":
                assert {row["quote"] for row in payload["evidence"]} == {NEED, OWNER}
                attempts["assessment"] += 1
                if reject_first and attempts["assessment"] == 1:
                    return {"supported": True, "correct_actor": False, "no_new_decisions": True,
                            "reason": "Incorrect attribution"}
                return {"supported": True, "correct_actor": True, "no_new_decisions": True,
                        "reason": "Both sources support it"}
            if stage == "pilot_coverage":
                assert payload["section"] == "Functional obligations"
                attempts["coverage"] += 1
                assert payload["requirements"][0]["text"] == (
                    repair_text if attempts["repair"] and repair_text else OUTPUT)
                if isinstance(coverage, list):
                    return coverage[attempts["coverage"] - 1]
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


def test_repair_and_revalidation():
    gap = {"section_relevant": True, "covered": False, "reason": "Omitted condition"}
    ok = {"section_relevant": True, "covered": True, "reason": "Complete"}
    corrected = "The Reservation Desk must provide confirmation of reservations to visitors."
    result, out = run([gap, ok], repair_text=corrected)
    assert out.paragraphs[5].text == corrected
    assert result["derivation"]["requirements"][0]["text"] == corrected
    assert result["results"][0]["proposal_ids"] == [result["derivation"]["requirements"][0]["id"]]
    assert result["metrics"]["diagnostics"]["pilot_section"]["repair_attempts"] == 1
    assert result["metrics"]["diagnostics"]["pilot_section"]["repair_successes"] == 1
    result, out = run(gap, repair_text="The Reservation Desk must send confirmation in 30 seconds.")
    assert not result["results"] and out.paragraphs[5].text == ""
    assert next(iter(result["repairs"].values()))["status"] == "invalid_proposal"
    result, out = run(ok, repair_text=corrected, reject_first=True)
    assert out.paragraphs[5].text == corrected
    assert result["metrics"]["diagnostics"]["pilot_section"]["repair_successes"] == 1


def test_template_instructions():
    ok = {"section_relevant": True, "covered": True, "reason": "Complete"}
    result, out = run(ok, instructions=True)
    texts = [p.text for p in out.paragraphs]
    assert OUTPUT in texts
    assert not any("Describe the required" in text or "specify the interactions" in text
                   or "fictional example" in text for text in texts)
    assert result["results"][0]["text"] == OUTPUT
    gap = {"section_relevant": False, "covered": True, "reason": "Wrong section"}
    result, out = run(gap, instructions=True)
    texts = [p.text for p in out.paragraphs]
    assert "[Describe the required functions" in texts
    assert "and specify the interactions.]" in texts
    assert "Example: fictional example" in texts
    assert not result["results"]


def test_section_detection_and_safe_writing():
    doc = Document()
    custom = doc.styles.add_style("Synthetic subsection", WD_STYLE_TYPE.PARAGRAPH)
    custom.base_style = doc.styles["Heading 2"]
    doc.add_paragraph("Unchanged front")
    doc.add_paragraph("7.1 Functions")
    doc.add_paragraph("7.2 Quality")
    doc.add_paragraph(" ", style="Normal")
    doc.add_paragraph("Inherited heading", style=custom)
    doc.add_paragraph("[Describe the requirements.]")
    doc.add_heading("Fixed section", level=1)
    doc.add_paragraph("Указанные требования должны выполняться.")
    doc.add_heading("Reference", level=1)
    doc.add_paragraph("[12]")
    doc.add_heading("Protected", level=1)
    doc.add_table(rows=1, cols=1).cell(0, 0).text = "Keep this"
    doc.add_heading("8. Contents", level=1)
    doc.add_heading("Blank with a section break", level=1)
    blank = doc.add_paragraph("")
    ppr = blank._p.get_or_add_pPr()
    ppr.append(OxmlElement("w:sectPr"))
    doc.add_heading("Final", level=1)
    doc.add_paragraph("Keep this too.")
    buf = io.BytesIO()
    doc.save(buf)
    options = {row["title"]: row for row in pilot.pilot_section_options(buf.getvalue())}
    assert options["7.1 Functions"]["status"] == "empty"
    assert options["7.2 Quality"]["status"] == "empty"
    assert options["Inherited heading"]["status"] == "instruction"
    assert options["Fixed section"]["status"] == "fixed_content"
    assert options["Reference"]["status"] == "fixed_content"
    assert options["Protected"]["status"] == "protected"
    assert options["8. Contents"]["status"] == "protected"
    assert options["Blank with a section break"]["status"] == "empty"
    targets = pilot._section_targets(doc)
    target = targets[options["7.1 Functions"]["index"]]
    anchor = pilot._write_section(target, doc, ["First", "Second"])
    assert anchor.text == "First" and anchor.style.name == "Normal"
    texts = [p.text for p in doc.paragraphs]
    assert texts[:5] == ["Unchanged front", "7.1 Functions", "First", "Second", "7.2 Quality"]
    assert "Указанные требования должны выполняться." in texts
    assert "[12]" in texts
    assert doc.tables[0].cell(0, 0).text == "Keep this"


def test_missing_evidence_skips_repair():
    result, out = run({"section_relevant": True, "covered": False,
                       "reason": "Insufficient evidence", "repairable": False})
    assert not result["results"] and not result["repairs"]
    assert result["metrics"]["diagnostics"]["pilot_section"]["repair_skipped_missing_evidence"] == 1
    assert out.paragraphs[5].text == ""


def test_prompt_contract():
    for lang in ("ru", "en"):
        prompt = default_prompts(lang)["draft_pilot_coverage"]
        assert all(key in prompt for key in ("section_relevant", "covered", "reason"))


if __name__ == "__main__":
    test_complete_chain()
    test_coverage_gap_and_invalid_section()
    test_repair_and_revalidation()
    test_template_instructions()
    test_section_detection_and_safe_writing()
    test_missing_evidence_skips_repair()
    test_prompt_contract()
    print("ИТОГ: end-to-end V2 Word pilot, section preservation, traceability and coverage gaps")

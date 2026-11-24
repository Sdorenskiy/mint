"""Offline V2 registry tests: fictional data, real extraction, scripted typing."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import draft_registry as registry
from mint import template_draft as draft
from mint.i18n import set_lang
from mint.prompts import default_prompts

set_lang("en")

NEED = "Visitors must receive confirmation of a locker reservation."
OWNER = "The Reservation Desk owns visitor notifications."
EXTERNAL = "The Locker Inventory service allocates lockers."
SHARED = "All reservation services must record rejected reservations."
QUESTION = "The timeout for confirmation is to be agreed."
NOISE = "4.1 Reservation overview ........ 5"
DEFINITION = "A reservation is a temporary claim on a locker."
DOCS = [
    ("brief.md", f"# Contents\n{NOISE}\n# Needs\n{NEED}\n{SHARED}\n{QUESTION}\n{DEFINITION}"),
    ("architecture.md", f"# Responsibilities\n{OWNER}\n{EXTERNAL}\n{SHARED}"),
]
ROLES = {"brief.md": "need", "architecture.md": "architecture"}
EXPECTED = {
    NEED: "functional", OWNER: "current_state", EXTERNAL: "current_state",
    SHARED: "nonfunctional", QUESTION: "open_question", DEFINITION: "definition",
    NOISE: "non_requirement",
}
# The future derivation must link both distinct sources, and must not invent a timeout.
GOLD_DERIVATION = ("The Reservation Desk must send confirmation of a locker reservation to the visitor.",
                   (NEED, OWNER))


def test_registry_with_real_extraction_and_cache():
    with TemporaryDirectory() as tmp:
        cfg = SimpleNamespace(log_path=Path(tmp), llm_model="synthetic",
                              max_tokens=1600, draft_extract_parallel=1)
        def extract(_cfg, stage, payload):
            assert stage == "extract"
            lines = payload["text"].splitlines()
            # Duplicate an exact quotation within a fragment.
            return {"requirements": [{"quote": line} for line in lines + lines[:1] if line]}

        def type_model(_cfg, stage, payload):
            assert stage == "registry_type"
            assert len(payload["items"]) <= 12
            assert all(row["quote"] != NOISE for row in payload["items"])
            return {"items": [{"id": row["id"], "kind": EXPECTED[row["quote"]]}
                              for row in payload["items"]]}

        @draft._measure_draft
        def run():
            return registry.build_registry(cfg, DOCS, ROLES, [], lambda *_: None)

        with patch.object(draft, "_json", side_effect=extract), patch.object(
                registry, "_json", side_effect=type_model):
            result = run()
        records = result["requirements"]
        assert len(records) == 8  # shared obligation has two separate sources
        assert list(records) == [f"R{i}" for i in range(1, 9)]
        assert all(row["kind"] == EXPECTED[row["quote"]] for row in records.values())
        shared = [r for r in records.values() if r["quote"] == SHARED]
        assert {r["source"] for r in shared} == set(ROLES)
        assert {r["source_role"] for r in shared} == {"need", "architecture"}
        for row in records.values():
            assert len(row["source_spans"]) == 1
            span = row["source_spans"][0]
            assert span["quote"] == row["quote"] and span["quote"] in dict(DOCS)[span["source"]]
            assert span["fragment"] >= 1 and len(span["revision"]) == 64
        candidates = registry.obligation_candidates(records)
        assert {r["quote"] for r in candidates.values()} == {NEED, SHARED}
        assert any(r["quote"] == OWNER for r in records.values())
        assert all(any(r["quote"] == q for r in records.values()) for q in GOLD_DERIVATION[1])
        assert result["metrics"]["diagnostics"]["registry_type"]["status_counts"] == {
            "structural": 1, "classified": 7}
        with patch.object(draft, "_json", side_effect=AssertionError("cache not reused")), patch.object(
                registry, "_json", side_effect=AssertionError("typing cache not reused")):
            again = run()
        assert again["requirements"] == records
        assert again["metrics"]["diagnostics"]["registry_type"]["cache_hits"] > 0
        assert again["metrics"]["diagnostics"]["extraction"]["cache_hits"] == result["chunks"]


def test_model_errors_are_not_obligations():
    rows = {f"R{i}": {"id": f"R{i}", "source": "fiction.md", "section": "Needs",
                     "quote": f"Fictional item {i}", "source_role": "unspecified"}
            for i in range(1, 7)}
    response = {"items": [{"id": "R1", "kind": "functional"},
                          {"id": "R2", "kind": "uncertain"},
                          {"id": "R3", "kind": "bogus"},
                          {"id": "R4", "kind": "functional"},
                          {"id": "R4", "kind": "current_state"},
                          {"id": "R6", "kind": "definition"},
                          {"id": "unknown", "kind": "functional"}]}
    with patch.object(registry, "_json", return_value=response):
        registry._type_records(None, rows, lambda *_: None)
    assert {rid: r["typing_status"] for rid, r in rows.items()} == {
        "R1": "classified", "R2": "explicit_uncertain", "R3": "invalid_kind",
        "R4": "duplicate_response", "R5": "missing_response", "R6": "classified"}
    assert set(registry.obligation_candidates(rows)) == {"R1"}
    with patch.object(registry, "_json", side_effect=draft.DraftError("failed")):
        registry._type_records(None, rows, lambda *_: None)
    assert all(r["typing_status"] == "batch_error" for r in rows.values())
    assert not registry.obligation_candidates(rows)


def test_contract_and_input():
    for lang in ("ru", "en"):
        prompt = default_prompts(lang)["draft_registry_type"]
        assert all(kind in prompt for kind in registry.KINDS)
    # Do not send unvalidated role assignments to the model.
    for docs, roles in ((DOCS + DOCS[:1], ROLES), (DOCS, {"brief.md": "invented"}),
                        (DOCS, {"unknown.md": "need"})):
        with patch.object(registry, "_requirements", side_effect=AssertionError("unexpected extraction")):
            try:
                registry.build_registry(None, docs, roles, [], lambda *_: None)
                raise AssertionError("invalid input accepted")
            except ValueError:
                pass


if __name__ == "__main__":
    test_registry_with_real_extraction_and_cache()
    test_model_errors_are_not_obligations()
    test_contract_and_input()
    print("ИТОГ: typed registry, preserved evidence, cache, fail-closed type decisions")

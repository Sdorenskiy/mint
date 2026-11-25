"""Offline checkpoint-1 regression tests. Fictional sources; not a real-model quality benchmark."""
import hashlib
import json
import sys
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import draft_target_analysis as target
from mint import draft_function_analysis as function
from mint import draft_registry as registry
from mint import draft_derivation as derivation
from mint import template_draft as draft
from mint.draft_pilot_report import target_registry_export
from mint.kb import source_path
from mint.prompts import default_prompts

CONTEXT = {"target": "Relay Service (RS)", "objective": "Reservation messaging", "scope": "", "participants": "Desk"}
NEED = "Visitors must receive an acknowledgement of a reservation."
EXTERNAL = "Desk must allocate a locker; Relay Service receives the event."
CURRENT = "Relay Service sends cancellation notices only; acknowledgements are not implemented."
METRIC = "Relay Service must send 20 messages per second."
DATA = "Relay Service must transfer reservation identifiers and contact categories."
DONE = "Relay Service must send cancellation notices."
DIRECT = "Relay Service must reject an empty event."
NEED2 = "Acknowledgement must include the reservation identifier."
UNSURE = "The retention interval shall be agreed."
TYPES = {NEED: "functional", EXTERNAL: "functional", CURRENT: "current_state",
         METRIC: "nonfunctional", DATA: "functional", DONE: "functional", DIRECT: "functional",
         NEED2: "functional", UNSURE: "open_question"}


def config(tmp):
    return SimpleNamespace(kb_path=Path(tmp) / "kb", log_path=Path(tmp) / "logs",
                           llm_model="synthetic", max_tokens=1800, llm_context_tokens=12000,
                           chars_per_token=2.5, draft_extract_parallel=1, max_query_chars=1000,
                           cascade_split_chars=1000)


def test_validators():
    row = {"id": "R1", "quote": METRIC, "kind": "nonfunctional", "section_role": "metric"}
    records = {"R1": row}
    state = {"F1": {"quote": CURRENT}}
    profile = {"C1": {"name": "Messaging"}}
    base = {"category": "target", "actor": CONTEXT["target"], "change": "change",
            "function": "C1", "component": "Relay", "state_refs": ["F1"],
            "reason": "supported", "metric": {"subject": "Relay Service", "value": "20",
            "unit": "messages per second", "conditions": "", "level": "target",
            "current_value": "", "target_value": "20"}}
    cases = [
        ({}, "proposed"),
        ({"actor": "RS"}, "proposed"),
        ({"actor": "Relay Service"}, "proposed"),
        ({"actor": "Desk"}, "wrong_actor"),
        ({"category": "bogus"}, "invalid_response"),
        ({"category": "uncertain"}, "missing_evidence"),
        ({"change": "unknown"}, "missing_evidence"),
        ({"change": "bogus"}, "invalid_response"),
        ({"state_refs": ["F999"]}, "invalid_response"),
        ({"state_refs": ["F1", "F1"]}, "invalid_response"),
        ({"state_refs": "F1"}, "invalid_response"),
        ({"state_refs": []}, "missing_evidence"),
        ({"reason": ""}, "invalid_response"),
        ({"function": "C99"}, "invalid_response"),
        ({"function": ""}, "invalid_response"),
        ({"function": "new"}, "invalid_response"),
        ({"function": "new", "function_name": "New messaging"}, "proposed"),
        ({"change": "already_supported"}, "proposed"),
        ({"change": "new"}, "proposed"),
        ({"category": "other", "actor": "Desk", "change": "external"}, "proposed"),
        ({"category": "other", "actor": CONTEXT["target"], "change": "external"}, "wrong_actor"),
        ({"category": "interaction", "actor": "Desk", "change": "external"}, "proposed"),
        ({"category": "interaction", "actor": "RS"}, "proposed"),
        ({"category": "shared"}, "proposed"),
        ({"change": "external"}, "wrong_actor"),
        ({"change": "explicit", "state_refs": [], "direct_quote": METRIC}, "proposed"),
        ({"change": "explicit", "state_refs": [], "direct_quote": "invented"}, "missing_evidence"),
        ({"change": "explicit", "state_refs": []}, "missing_evidence"),
        ({"metric": None}, "missing_metric_evidence"),
        ({"metric": "bad"}, "missing_metric_evidence"),
    ]
    for change, expected in cases:
        actual = target._validate_decision({**base, **change}, "R1", records, state, profile, CONTEXT["target"])
        assert actual["status"] == expected, (change, actual, expected)
    for change in ({"value": "99"}, {"unit": "seconds per request"}, {"subject": ""},
                   {"target_value": "9999"}, {"level": "future"}, {"current_value": "777"}):
        actual = target._validate_decision({**base, "metric": {**base["metric"], **change}},
                                           "R1", records, state, profile, CONTEXT["target"])
        assert actual["status"] == "missing_metric_evidence", actual
    assert len(cases) + 6 == 36


def test_original_evidence():
    docs = [("a.md", "# A\n## B\n" + NEED), ("b.md", "# Current\n" + CURRENT)]
    spans, sections = target._map_sources(docs, {})
    assert list(sections.values())[0]["section"] == "A › B"
    parent = {"source": "a.md", "text": NEED}
    snap = SimpleNamespace(parent_store={"p": parent, "foreign": {"source": "private.md", "text": NEED}},
                           documents={"a.md": {"source_sha256": "a"}, "b.md": {"source_sha256": "old"}})
    with patch.object(target, "load_kb_snapshot", return_value=snap), patch.object(
            target, "search_parent_child", return_value=([{"ids": ["p", "foreign"]}], [])) as search:
        evidence = target.OriginalEvidence(config("/tmp"), spans, {"a.md": "a", "b.md": "b"})
        assert evidence.revisions == {"matched": 1, "missing": 1}
        assert evidence.find("query") == ["F1"]
        kwargs = search.call_args.kwargs
        assert kwargs["allow_sources"] == {"a.md", "b.md"}
        assert kwargs["expected_hashes"] == {"a.md": "a", "b.md": "b"}
        assert kwargs["quiet"] is True


def test_registry_end_to_end():
    with TemporaryDirectory() as tmp:
        cfg = config(tmp)
        docs = {"needs.md": "# Business\n" + EXTERNAL + "\n# Interfaces\n" + NEED + "\n" + DIRECT +
                "\n" + DONE + "\n# Metrics\n" + METRIC + "\n" + UNSURE,
                "design.md": "# Current\n" + CURRENT,
                "extra.md": "# Interfaces\n" + NEED2 + "\n" + DATA}
        roles = {"needs.md": "need", "design.md": "architecture", "extra.md": "need"}
        for name, content in docs.items():
            path = source_path(cfg, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        def model(_cfg, stage, payload):
            if stage == "target_section_map":
                mapping = {"Business": "business", "Interfaces": "interface",
                           "Metrics": "metric", "Current": "arch"}
                return {"items": [{"id": r["id"], "role": mapping[r["section"]]} for r in payload["items"]]}
            if stage == "target_profile":
                state = next(r for r in payload["evidence"] if CURRENT in r["text"])
                return {"functions": [{"name": "Messaging", "description": CURRENT, "refs": [state["id"]]}]}
            if stage == "target_dossier":
                # Simulate a precise secondary retrieval result, without replacing full scan.
                return {"items": [{"span_id": r["id"], "facet": facet, "quote": quote}
                                  for facet, quote in (("performance", METRIC), ("data_categories", DATA))
                                  for r in payload["evidence"] if quote in r["text"] and facet in payload["facets"]]}
            if stage == "target_extract":
                assert payload["focus"]["context"]["target"] == CONTEXT["target"]
                return {"requirements": [{"quote": x} for x in payload["text"].splitlines() if x and x not in {DATA, METRIC}]}
            if stage == "registry_type":
                return {"items": [{"id": r["id"], "kind": TYPES[r["quote"]]} for r in payload["items"]]}
            if stage == "target_allocation":
                r = payload["items"][0]
                state = next(x["id"] for x in payload["evidence"] if CURRENT in x["quote"])
                change = "already_supported" if r["quote"] == DONE else "explicit" if r["quote"] == DIRECT else "change"
                result = {"id": r["id"], "category": "target", "actor": "RS", "change": change,
                          "function": "C1", "state_refs": [state] if change != "explicit" else [],
                          "reason": "fictional evidence", "component": "Relay",
                          "direct_quote": r["quote"] if change == "explicit" else ""}
                if r["quote"] == EXTERNAL:
                    result.update(category="other", actor="Desk", change="external", state_refs=[])
                if r["quote"] == METRIC:
                    result["metric"] = {"subject": "Relay Service", "value": "20", "unit": "messages per second",
                                        "level": "target", "target_value": "20"}
                return {"items": [result]}
            if stage == "target_verify":
                return {"items": [{"id": r["id"], "correct_actor": True, "change_supported": True,
                                   "conditions_preserved": True, "reason": "verified"} for r in payload["items"]]}
            if stage == "target_summary":
                return {"text": " ".join(r["quote"] for r in payload["needs"]),
                        "need_refs": [r["id"] for r in payload["needs"]], "evidence_refs": []}
            if stage == "target_derivation":
                items = []
                for r in payload["needs"]:
                    d = payload["decisions"][r["id"]]
                    if d["change"] == "already_supported":
                        continue
                    text = r["quote"]
                    if text == NEED:
                        text = "Relay Service must send an acknowledgement of a reservation to visitors."
                    if text == NEED2:
                        text = "Relay Service must include the reservation identifier in the acknowledgement."
                    items.append({"text": text, "actor": "RS", "kind": "metric" if r["quote"] == METRIC else "functional",
                                  "need_refs": [r["id"]], "state_refs": d["state_refs"], "metric_refs": [],
                                  "reason": "fictional support"})
                return {"requirements": items}
            if stage == "requirement_assessment":
                yes = {"supported": True, "correct_actor": True, "no_new_decisions": True, "reason": "supported",
                       "complete": True, "unambiguous": True, "verifiable": True}
                return {"items": [{"id": r["id"], **yes} for r in payload["items"]]} if "items" in payload else yes
            if stage == "target_coverage":
                return {"items": [{"id": r["id"], "covered": True, "reason": "covered"} for r in payload["items"]]}
            raise AssertionError(stage)

        with ExitStack() as stack:
            for module in (target, draft, registry, function, derivation):
                stack.enter_context(patch.object(module, "_json", side_effect=model))
            stack.enter_context(patch.object(target, "load_kb_snapshot", return_value=None))
            prepared = target.prepare_target_analysis(cfg, list(docs), roles, CONTEXT)
            assert len(prepared["profile"]) == 1
            collected = target.collect_target_requirements(cfg, prepared, prepared["profile"])
            assert collected["phase"] == "collected" and not collected["proposals"]
            assert all(r["status"] == "draft" for rows in collected["summaries"].values() for r in rows)
            assert "target_derivation" not in collected["metrics"]["stages"]
            original = json.dumps(collected["dispositions"], sort_keys=True)
            ids = [rid for rid, status in collected["dispositions"].items() if status == "awaiting_decomposition"]
            excluded = next(rid for rid in ids if collected["requirements"][rid]["quote"] == DATA)
            with patch.object(target, "build_registry", side_effect=AssertionError("repeated extraction")), patch.object(
                    target, "_verify_decisions", side_effect=AssertionError("repeated allocation")):
                reviewed = target.decompose_target_requirements(cfg, prepared, collected,
                    selection=[rid for rid in ids if rid != excluded], notes={"G1": "Use original evidence only."})
                assert reviewed["dispositions"][excluded] == "expert_excluded"
                assert not any(excluded in p["need_refs"] for p in reviewed["proposals"])
                assert reviewed["review"]["notes"]["G1"] == "Use original evidence only."
                assert json.dumps(collected["dispositions"], sort_keys=True) == original
                assert reviewed["review"]["mode"] == "expert"
                result = target.decompose_target_requirements(cfg, prepared, collected)
            assert result["phase"] == "decomposed" and result["review"]["mode"] == "automatic"
            by_quote = {row["quote"]: rid for rid, row in result["requirements"].items()}
            assert result["dispositions"][by_quote[EXTERNAL]] == "external"
            assert result["dispositions"][by_quote[DONE]] == "already_supported"
            assert result["dispositions"][by_quote[UNSURE]] == "open_question"
            assert all(result["dispositions"][by_quote[q]] == "model_covered" for q in (NEED, NEED2, DIRECT, METRIC, DATA))
            assert len(result["groups"]) == 1
            assert len(result["requirements"]) == len(TYPES)
            assert result["diagnostics"]["dossiers"]["supplemental_records"] == 2
            assert result["dossiers"]["C1"]["facets"]["data_categories"]["facts"]
            assert result["dossiers"]["C1"]["facets"]["performance"]["coverage"][by_quote[METRIC]] == "model_covered"
            assert result["diagnostics"]["verification"]["batches"] < len(result["decisions"])
            assert result["metrics_registry"][by_quote[METRIC]]["unit"] == "messages per second"
            assert len(result["fragment_status"]) == len(prepared["spans"])
            assert "docx" not in result
            safe = target_registry_export(prepared, result)
            payload = json.dumps(safe, ensure_ascii=False, allow_nan=False)
            assert all(private not in payload for private in (NEED, CURRENT, METRIC, "needs.md", "Messaging", "Relay Service"))
            assert safe["counts"]["verified_metrics"] == 1
            source_path(cfg, "extra.md").write_text("changed", encoding="utf-8")
            try:
                target.decompose_target_requirements(cfg, prepared, collected)
                raise AssertionError("stale collected input accepted")
            except draft.DraftError:
                pass
            try:
                target.analyze_target_registry(cfg, prepared, prepared["profile"])
                raise AssertionError("changed original accepted")
            except draft.DraftError:
                pass


if __name__ == "__main__":
    test_validators()
    test_original_evidence()
    test_registry_end_to_end()
    for lang in ("ru", "en"):
        prompts = default_prompts(lang)
        for stage in ("target_section_map", "target_profile", "target_extract", "target_allocation",
                      "target_verify", "target_summary", "target_derivation", "target_coverage"):
            assert "draft_" + stage in prompts
    print("ИТОГ: 36 contract cases, original evidence, target registry pipeline and privacy")

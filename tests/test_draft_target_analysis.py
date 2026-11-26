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
from mint import requirement_scope as scope
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
    # A reference-only numerical value must not become a new target value.
    wiki = {"BF1": {"quote": "Historical service capacity: 999 messages per second.",
                    "source_role": "reference_context"}}
    proposed = {**base, "state_refs": ["BF1"], "metric": {**base["metric"], "target_value": "999"}}
    assert target._validate_decision(proposed, "R1", records, wiki, profile, CONTEXT["target"])["status"] == "missing_metric_evidence"


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


def test_profile_status():
    cfg = config("/tmp")
    candidates = [{"id": "F1", "text": CURRENT}]
    for answer, status in (({}, "invalid_response"), ({"functions": []}, "no_functions"),
                           ({"functions": [{"name": "x", "description": "x", "refs": ["F99"]}]}, "invalid_response"),
                           ({"functions": [{"name": "x", "description": "x", "refs": ["F1"]}]}, "found")):
        with patch.object(target, "_json", return_value=answer):
            _, actual = target._propose_profile(cfg, candidates, CONTEXT, lambda *_: None)
            assert actual == status, (answer, actual)
    with patch.object(target, "_json", side_effect=draft.DraftError("simulated")):
        assert target._propose_profile(cfg, candidates, CONTEXT, lambda *_: None) == ([], "model_error")
    with patch.object(target, "_json", side_effect=AssertionError("unexpected LLM call")):
        assert target._propose_profile(cfg, [], CONTEXT, lambda *_: None) == ([], "no_candidates")


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

        stages = []
        def model(_cfg, stage, payload):
            stages.append(stage)
            if stage == "target_section_map":
                mapping = {"Business": "business", "Interfaces": "interface",
                           "Metrics": "metric", "Current": "arch"}
                return {"items": [{"id": r["id"], "role": mapping[r["section"]]} for r in payload["items"]]}
            if stage == "target_profile":
                if payload.get("purpose") == "requirements_analysis":
                    rows = payload["evidence"]
                    refs = [r["id"] for r in rows if r["text"] in {NEED, NEED2, DIRECT, DONE, CURRENT}]
                    functions = [{"name": "Messaging", "description": "Relay messages", "refs": refs}] if refs else []
                    other = [r["id"] for r in rows if r["text"] in {NEED2, DATA}]
                    if other:
                        functions.append({"name": "Data exchange", "description": "Exchange reservation data", "refs": other})
                    return {"functions": functions}
                state = next(r for r in payload["evidence"] if CURRENT in r["text"])
                return {"functions": [{"name": "Messaging", "description": CURRENT, "refs": [state["id"]]}]}
            if stage == "target_dossier":
                # Simulate a precise secondary retrieval result, without replacing full scan.
                return {"items": [{"span_id": r["id"], "facet": facet, "quote": quote}
                                  for facet, quote in (("performance", METRIC), ("data_categories", DATA))
                                  for r in payload["evidence"] if quote in r["text"] and facet in payload["facets"]]}
            if stage == "target_extract":
                assert payload["focus"]["context"]["target"] == CONTEXT["target"]
                assert payload["focus"]["functions"] == []
                assert "999" not in payload["text"]
                return {"requirements": [{"quote": x} for x in payload["text"].splitlines() if x and x not in {DATA, METRIC}]}
            if stage == "registry_type":
                return {"items": [{"id": r["id"], "kind": TYPES[r["quote"]]} for r in payload["items"]]}
            if stage == "scope":
                return {"items": [{"id": r["id"], "category": "other" if r["quote"] == EXTERNAL else "target",
                                   "actor": "Desk" if r["quote"] == EXTERNAL else "RS", "reason": "fixture"}
                                  for r in payload["requirements"]]}
            if stage == "target_allocation":
                r = payload["items"][0]
                state = next(x["id"] for x in payload["evidence"] if CURRENT in x["quote"])
                if r["quote"] == NEED:
                    state = next((x["id"] for x in payload["evidence"] if x.get("source_role") == "reference_context"), state)
                change = "already_supported" if r["quote"] == DONE else "explicit" if r["quote"] == DIRECT else "change"
                result = {"id": r["id"], "category": "target", "actor": "RS", "change": change,
                          "function": "C1", "state_refs": [state] if change != "explicit" else [],
                          "reason": "fictional evidence", "component": "Relay",
                          "direct_quote": r["quote"] if change == "explicit" else ""}
                if not payload["profile"]:
                    result.update(function="new", function_name="Messaging")
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
            for module in (target, draft, registry, function, derivation, scope):
                stack.enter_context(patch.object(module, "_json", side_effect=model))
            stack.enter_context(patch.object(target, "load_kb_snapshot", return_value=None))
            prepared = target.prepare_target_analysis(cfg, list(docs), roles, CONTEXT)
            assert len(prepared["profile"]) == 1
            with patch.object(target, "_proposals", side_effect=AssertionError("premature decomposition")):
                collected = target.collect_target_requirements(cfg, prepared, prepared["profile"])
            assert "target_extract" in stages and "target_dossier" in stages
            assert max(i for i, stage in enumerate(stages) if stage == "target_extract") < stages.index("target_dossier")
            assert collected["phase"] == "collected" and not collected["proposals"]
            assert all(r["status"] == "draft" for rows in collected["summaries"].values() for r in rows)
            assert "target_derivation" not in collected["metrics"]["stages"]
            original = json.dumps(collected["dispositions"], sort_keys=True)
            ids = [rid for rid, status in collected["dispositions"].items() if status == "awaiting_decomposition"]
            excluded = next(rid for rid in ids if collected["requirements"][rid]["quote"] == DATA)
            with patch.object(target, "build_registry", side_effect=AssertionError("repeated extraction")), patch.object(
                    target, "_verify_decisions", side_effect=AssertionError("repeated allocation")):
                # Explicitly exercise an excluded requirement also appearing in the
                # supplemental evidence graph. It stays in the original snapshot.
                from copy import deepcopy
                review_input = deepcopy(collected)
                included = next(rid for rid in ids if rid != excluded)
                review_input["decisions"][included].setdefault("dossier_refs", []).append(excluded)
                review_input["state_evidence"][excluded] = review_input["requirements"][excluded]
                with patch.object(target, "_proposals", wraps=target._proposals) as derive:
                    reviewed = target.decompose_target_requirements(cfg, prepared, review_input,
                        selection=[rid for rid in ids if rid != excluded], notes={"G1": "Use original evidence only."})
                _, _, derived_decisions, _, derived_state, *_ = derive.call_args.args
                assert excluded not in derived_state
                assert all(excluded not in d.get(field, []) for d in derived_decisions.values()
                           for field in ("state_refs", "reference_refs", "dossier_refs"))
                assert excluded in reviewed["decisions"][included]["dossier_refs"]
                assert excluded in review_input["state_evidence"]
                assert reviewed["dispositions"][excluded] == "expert_excluded"
                assert not any(excluded in p[field] for p in reviewed["proposals"]
                               for field in ("need_refs", "state_refs", "constraint_refs"))
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
            with patch.object(target, "summarize_needs", side_effect=AssertionError("unnecessary summary call")):
                automatic = target.analyze_target_registry(cfg, prepared, prepared["profile"])
            assert automatic["phase"] == "decomposed" and automatic["review"]["mode"] == "automatic"
            assert automatic["summaries"] == {} and "target_summary" not in automatic["metrics"]["stages"]
            assert automatic["dispositions"] == result["dispositions"]
            # Reference documents are searched separately and never become needs.
            wiki_path = source_path(cfg, "wiki.md")
            wiki_path.write_text("# Current\n" + CURRENT + "\nHistorical capacity: 999 messages per second.", encoding="utf-8")
            wiki_prepared = target.prepare_target_analysis(cfg, list(docs), roles, CONTEXT,
                                                            reference_sources=["wiki.md"])
            assert wiki_prepared["documents"] == prepared["documents"]
            assert wiki_prepared["hashes"] == prepared["hashes"]
            assert wiki_prepared["reference_status"] == "found"
            assert wiki_prepared["profile"][0] == prepared["profile"][0]
            assert wiki_prepared["profile"][1]["origin"] == "reference"
            assert set(wiki_prepared["spans"]).isdisjoint(wiki_prepared["reference_spans"])
            with patch.object(target, "build_registry", wraps=target.build_registry) as build:
                wiki_collected = target.collect_target_requirements(cfg, wiki_prepared, wiki_prepared["profile"])
            assert all(name != "wiki.md" for name, _ in build.call_args.args[1])
            assert wiki_collected["requirements"] == collected["requirements"]
            assert all(r["source"] != "wiki.md" for r in wiki_collected["requirements"].values())
            assert any(r["source_role"] == "reference_context" for r in wiki_collected["state_evidence"].values())
            assert any(k.startswith("BF") for k in wiki_collected["decisions"][by_quote[NEED]]["state_refs"])
            assert wiki_collected["diagnostics"]["wiki_context"]["sources"] == 1
            wiki_result = target.decompose_target_requirements(cfg, wiki_prepared, wiki_collected)
            assert all(not rid.startswith("BF") for p in wiki_result["proposals"] for rid in p["need_refs"] + p["constraint_refs"])
            assert "wiki.md" not in json.dumps(target_registry_export(wiki_prepared, wiki_result))
            # Main wizard path: no discovery before the independent extraction.
            stages.clear()
            automatic_prepared = target.prepare_target_analysis(cfg, list(docs), roles, CONTEXT,
                reference_sources=["wiki.md"], discover_profile=False)
            assert not automatic_prepared["profile"] and "target_profile" not in stages
            auto = target.collect_target_requirements(cfg, automatic_prepared, reset_cache=True, summaries=False)
            assert auto["automatic_functions"] and not auto["summaries"]
            assert max(i for i, stage in enumerate(stages) if stage == "target_extract") < stages.index("target_profile")
            assert stages.index("target_profile") < stages.index("target_dossier")
            assert {p["name"] for p in auto["approved_profile"]} == {"Messaging", "Data exchange"}
            assert {r["quote"] for r in collected["requirements"].values()} <= {r["quote"] for r in auto["requirements"].values()}
            assert len(auto["function_links"][by_quote[NEED2]]) >= 2
            assert auto["diagnostics"]["wiki_context"]["function_searches"] == 2
            assert all(row["source"] != "wiki.md" for row in auto["requirements"].values())
            assert len(auto["fragment_status"]) == len(prepared["spans"])
            auto_result = target.decompose_target_requirements(cfg, automatic_prepared, auto)
            assert auto_result["phase"] == "decomposed"
            assert auto_result["function_links"] == auto["function_links"]
            # Wizard path: only the full typed scan and preliminary applicability
            # run before the user picks functions. No dossier or allocation yet.
            stages.clear()
            preview = target.collect_target_requirements(cfg, automatic_prepared, reset_cache=True,
                                                         summaries=False, preview_only=True)
            assert preview["phase"] == "function_preview"
            assert "scope" in stages and "target_extract" in stages and "registry_type" in stages
            assert not {"target_dossier", "target_allocation", "target_verify"} & set(stages)
            assert preview["applicability"][by_quote[EXTERNAL]]["category"] == "other"
            ids = {p["name"]: p["id"] for p in preview["approved_profile"]}
            assert set(ids) == {"Messaging", "Data exchange"}
            original_preview = deepcopy(preview)
            stages.clear()
            with patch.object(target, "collect_dossiers", wraps=target.collect_dossiers) as deep:
                scoped = target.collect_target_requirements(cfg, automatic_prepared, preview=preview,
                                                            selected_functions=[ids["Messaging"]], summaries=False)
            assert deep.call_count == 1
            assert set(deep.call_args.args[3]) == {ids["Messaging"]}
            assert "target_extract" not in stages and "scope" not in stages
            assert scoped["selected_functions"] == [ids["Messaging"]]
            assert scoped["diagnostics"]["wiki_context"]["function_searches"] == 1
            assert scoped["diagnostics"]["scope_selection"] == {"selected": 1, "offered": 2}
            assert set(preview["requirements"]) <= set(scoped["requirements"])
            assert all(scoped["requirements"][rid]["quote"] == row["quote"]
                       for rid, row in preview["requirements"].items())
            assert scoped["preliminary_applicability"] == preview["applicability"]
            assert preview == original_preview
            assert set(preview["metrics"]["stages"]) <= set(scoped["metrics"]["stages"])
            try:
                target.collect_target_requirements(cfg, automatic_prepared, preview=preview,
                                                   selected_functions=["C999"])
                raise AssertionError("invalid function accepted")
            except ValueError:
                pass
            stages.clear()
            empty = target.collect_target_requirements(cfg, automatic_prepared, preview=preview,
                                                       selected_functions=[], summaries=False)
            assert "target_extract" not in stages and "target_dossier" not in stages
            assert set(empty["requirements"]) == set(preview["requirements"])
            assert not empty["dossiers"] and empty["selected_functions"] == []
            wiki_path.write_text("changed", encoding="utf-8")
            try:
                target.decompose_target_requirements(cfg, wiki_prepared, wiki_collected)
                raise AssertionError("stale reference accepted")
            except draft.DraftError:
                pass
            try:
                target.prepare_target_analysis(cfg, list(docs), roles, CONTEXT, reference_sources=["needs.md"])
                raise AssertionError("overlapping scope accepted")
            except ValueError:
                pass
            # No function profile is a valid degraded path; full original scan still runs.
            no_profile = {**prepared, "profile": [], "profile_status": "model_error"}
            with patch.object(target, "build_registry", wraps=target.build_registry) as build:
                direct_only = target.collect_target_requirements(cfg, no_profile, [])
            assert build.call_args.kwargs["focus"] == {"context": prepared["context"], "functions": []}
            assert direct_only["fragment_status"].keys() == collected["fragment_status"].keys()
            assert DIRECT in {r["quote"] for r in direct_only["requirements"].values()}
            assert direct_only["diagnostics"]["profile_status"] == {"model_error": 1}
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
    test_profile_status()
    test_registry_end_to_end()
    for lang in ("ru", "en"):
        prompts = default_prompts(lang)
        for stage in ("target_section_map", "target_profile", "target_extract", "target_allocation",
                      "target_verify", "target_summary", "target_derivation", "target_coverage"):
            assert "draft_" + stage in prompts
    print("ИТОГ: 36 contract cases, original evidence, target registry pipeline and privacy")

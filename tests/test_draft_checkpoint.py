"""Crash-safe Word draft extraction checkpoints: no network required."""
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import template_draft as draft
from mint.draft_checkpoint import DraftExtractCheckpoint
from mint.i18n import set_lang

set_lang("ru")


def config(directory, model="mock-v1"):
    return SimpleNamespace(
        log_path=Path(directory), llm_model=model, llm_base="https://example.invalid/v1",
        llm_api_key="test-secret", max_tokens=1800, llm_context_tokens=8192,
        chars_per_token=2.5, llm_no_reasoning=True, llm_extra_body=""
    )


def test_reuse_and_restart():
    with TemporaryDirectory() as directory:
        cfg = config(directory)
        docs = [("first.md", "# Раздел\nТребование А.\nТребование Б.\n")]
        events = []
        calls = []

        def fake_json(_cfg, _stage, payload):
            calls.append(payload["text"])
            return {"requirements": [{"quote": "Требование А."}]}

        with patch.object(draft, "_json", side_effect=fake_json):
            req1, count1 = draft._requirements(cfg, docs, [], lambda *e: events.append(e))
            req2, count2 = draft._requirements(cfg, docs, [], lambda *e: events.append(e))
            assert count1 == count2 == 1
            assert req1 == req2
            assert len(calls) == 1
            assert ("extract_total", 1) in events
            assert ("extract_cached", 1) in events
            assert ("extract_done", 1) in events

            # Explicit force-refresh avoids stale results even with unchanged sources.
            draft._requirements(cfg, docs, [], lambda *_: None, reset_cache=True)
            assert len(calls) == 2

        cp = DraftExtractCheckpoint(cfg, docs[0][0], docs[0][1])
        assert cp.load(1, "Раздел", "Требование А.\nТребование Б.") == ["Требование А."]

        # No quotations are logged to file names, only to private checkpoint content.
        checkpoints = list(Path(directory).rglob("*.json"))
        assert len(checkpoints) == 1
        assert "test-secret" not in checkpoints[0].read_text(encoding="utf-8")
        # Windows uses NTFS ACLs; st_mode is a synthetic POSIX value there.
        if os.name == "posix":
            assert checkpoints[0].stat().st_mode & 0o077 == 0


def test_partial_recovery():
    with TemporaryDirectory() as directory:
        cfg = config(directory)
        docs = [("first.md", "# A\nFirst valid.\n# B\nSecond valid.")]
        calls = []
        error = []

        def fail_second(_cfg, _stage, payload):
            calls.append(payload["section"])
            if payload["section"] == "B":
                raise draft.DraftError("temporary error")
            return {"requirements": [{"quote": "First valid."}]}

        with patch.object(draft, "_json", side_effect=fail_second):
            requirements, count = draft._requirements(cfg, docs, error, lambda *_: None)
        assert count == 2 and len(requirements) == 1
        assert sorted(calls) == ["A", "B"] and error  # LLM requests may begin in either order

        calls.clear()

        def succeed(_cfg, _stage, payload):
            calls.append(payload["section"])
            return {"requirements": [{"quote": "Second valid."}]}

        with patch.object(draft, "_json", side_effect=succeed):
            requirements, count = draft._requirements(cfg, docs, [], lambda *_: None)
        assert len(requirements) == 2
        assert calls == ["B"]  # first chunk survived interrupted run

        # A different model must never consume a prior model's checkpoint.
        with patch.object(draft, "_json", side_effect=succeed):
            draft._requirements(config(directory, "new-model"), docs, [], lambda *_: None)
        assert calls[0] == "B" and sorted(calls[1:]) == ["A", "B"]


def test_invalid_and_corrupt_checkpoints():
    with TemporaryDirectory() as directory:
        cfg = config(directory)
        source = "# Test\nGrounded text."
        cp = DraftExtractCheckpoint(cfg, "x.md", source)
        assert cp.load(1, "Test", "Grounded text.") is None
        cp.save(1, "Test", "Grounded text.", [])
        assert cp.load(1, "Test", "Grounded text.") == []
        cp.save(1, "Test", "Grounded text.", ["Grounded text."])
        assert cp.load(1, "Test", "Grounded text.") == ["Grounded text."]
        assert cp.load(1, "Test", "DIFFERENT") is None
        path = next(cp.directory.glob("*.json"))
        path.write_text('{"quotes":["Injected!"]}', encoding="utf-8")
        assert cp.load(1, "Test", "Grounded text.") is None

        # An invalid citation is not reused on the next attempt.
        docs = [("x.md", source)]
        with patch.object(draft, "_json", return_value={"requirements": [{"quote": "Not actually here"}]}):
            problems = []
            draft._requirements(cfg, docs, problems, lambda *_: None)
            assert problems
        assert cp.load(1, "Test", "Grounded text.") is None


if __name__ == "__main__":
    test_reuse_and_restart()
    test_partial_recovery()
    test_invalid_and_corrupt_checkpoints()
    print("ИТОГ: контрольные точки, возобновление, изоляция модели, сбои и цитаты проверены")

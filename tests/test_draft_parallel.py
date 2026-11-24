"""Bounded parallel extraction uses the real checkpoint and progress paths, with a fake LLM."""
import json
import threading
import time
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import template_draft as draft
from mint.i18n import set_lang

set_lang("ru")


def test_bounded_extraction():
    with TemporaryDirectory() as tmp:
        cfg = SimpleNamespace(log_path=Path(tmp), llm_model="synthetic",
                              llm_api_key="not-a-secret", llm_base="https://example.invalid/v1",
                              max_tokens=1600, llm_context_tokens=8192, chars_per_token=2.5,
                              llm_no_reasoning=True, llm_extra_body="", draft_extract_parallel=3)
        docs = [("fictional_guide.md", "\n".join(
            "# Глава " + str(i) + "\nСистема должна сохранять запись номер " + str(i) + " в течение 5 дней."
            for i in range(1, 9)))]
        lock = threading.Lock()
        state = {"running": 0, "peak": 0, "calls": 0}
        events = []

        def fake_llm(_sys, user, *_args, **_kwargs):
            data = json.loads(user)
            with lock:
                state["running"] += 1
                state["calls"] += 1
                state["peak"] = max(state["peak"], state["running"])
            time.sleep(0.035)
            with lock:
                state["running"] -= 1
            return json.dumps({"requirements": [{"quote": data["text"].strip()}]}, ensure_ascii=False)

        @draft._measure_draft
        def run(parallel, reset=False):
            cfg.draft_extract_parallel = parallel
            issues = []
            events.clear()
            items, chunks = draft._requirements(cfg, docs, issues,
                                                 lambda stage, index: events.append((stage, index)),
                                                 reset_cache=reset)
            return {"items": items, "chunks": chunks, "issues": issues}

        with patch.object(draft, "ask_llm", side_effect=fake_llm):
            started = time.perf_counter()
            parallel = run(3)
            t_parallel = time.perf_counter() - started
            assert parallel["chunks"] == 8 and len(parallel["items"]) == 8 and not parallel["issues"]
            assert state["peak"] >= 2 and state["peak"] <= 3
            assert [x["id"] for x in parallel["items"].values()] == ["R" + str(i) for i in range(1, 9)]
            assert [x["section"] for x in parallel["items"].values()] == [
                "Глава " + str(i) for i in range(1, 9)]
            assert parallel["metrics"]["stages"]["extract"]["llm_calls"] == 8
            assert parallel["metrics"]["stages"]["extract"]["llm_seconds"] > parallel["metrics"]["total_seconds"]
            assert [i for stage, i in events if stage == "extract_done"] == list(range(1, 9))
            assert len([x for x in events if x[0] == "extract_elapsed"]) == 8

            before = state["calls"]
            cached = run(3)
            assert state["calls"] == before and cached["items"] == parallel["items"]
            assert cached["metrics"]["stages"] == {}
            assert [i for stage, i in events if stage == "extract_cached"] == list(range(1, 9))

            state["peak"] = 0
            started = time.perf_counter()
            serial = run(1, reset=True)
            t_serial = time.perf_counter() - started
            assert serial["items"] == parallel["items"]
            assert state["peak"] == 1 and serial["metrics"]["stages"]["extract"]["llm_calls"] == 8
            assert serial["metrics"]["total_seconds"] >= t_parallel
            print(f"Искусственная задержка: параллельно {t_parallel:.2f} с, "
                  f"последовательно {t_serial:.2f} с (не бенчмарк шлюза).")
            # Override bad concurrency settings; the cap must always hold.
            state["peak"] = 0
            capped = run(60, reset=True)
            assert capped["items"] == serial["items"] and 1 < state["peak"] <= 4

        # A failed chunk is not checkpointed; following successful chunks remain reusable.
        failed = {"first": True}
        def flaky(_sys, user, *_args, **_kwargs):
            data = json.loads(user)
            if "номер 3" in data["text"] and failed["first"]:
                failed["first"] = False
                return json.dumps({"requirements": [{"quote": "отсутствующий текст"}]})
            return json.dumps({"requirements": [{"quote": data["text"].strip()}]}, ensure_ascii=False)
        with patch.object(draft, "ask_llm", side_effect=flaky):
            one = run(2, reset=True)
            assert len(one["items"]) == 7 and len(one["issues"]) == 1
            two = run(2)
            assert len(two["items"]) == 8 and not two["issues"]
            assert two["metrics"]["stages"]["extract"]["llm_calls"] == 1


def test_slow_earliest_request_does_not_idle_other_worker():
    """A later completion starts another request before the earliest finishes."""
    with TemporaryDirectory() as tmp:
        cfg = SimpleNamespace(log_path=Path(tmp), llm_model="synthetic",
                              llm_api_key="not-a-secret", llm_base="https://example.invalid/v1",
                              max_tokens=1600, llm_context_tokens=8192, chars_per_token=2.5,
                              llm_no_reasoning=True, llm_extra_body="", draft_extract_parallel=2)
        docs = [("fictional_guide.md", "\n".join(
            "# Section " + str(i) + "\nRequirement number " + str(i) + " must be met."
            for i in range(1, 9)))]
        first_started = threading.Event()
        release_first = threading.Event()
        fourth_started = threading.Event()
        lock = threading.Lock()
        running = {"now": 0, "peak": 0}
        events, result_box, errors = [], {}, []

        def fake_llm(_sys, user, *_args, **_kwargs):
            data = json.loads(user)
            number = int(data["text"].split("Requirement number ")[1].split(" ")[0])
            with lock:
                running["now"] += 1
                running["peak"] = max(running["peak"], running["now"])
            try:
                if number == 1:
                    first_started.set()
                    if not release_first.wait(10):
                        raise RuntimeError("first fake LLM request timed out")
                if number == 4:
                    fourth_started.set()
                return json.dumps({"requirements": [{"quote": data["text"]}]})
            finally:
                with lock:
                    running["now"] -= 1

        def run():
            try:
                issues = []
                items, count = draft._requirements(cfg, docs, issues,
                                                  lambda *event: events.append(event))
                result_box.update(items=items, count=count, issues=issues)
            except BaseException as exc:
                errors.append(exc)

        with patch.object(draft, "ask_llm", side_effect=fake_llm):
            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            try:
                assert first_started.wait(5), "the first request did not start"
                assert fourth_started.wait(5), (
                    "idle worker was not refilled while the first request was still running")
                # Progress is completion-based, although the final IDs are source-ordered.
                assert any(event[0] == "extract_done" and event[1] >= 2 for event in events)
            finally:
                release_first.set()
                thread.join(12)
            assert not thread.is_alive(), "extraction thread did not finish"
            assert not errors, errors

        assert running["peak"] == 2
        assert result_box["count"] == 8 and not result_box["issues"]
        assert [row["section"] for row in result_box["items"].values()] == [
            "Section " + str(i) for i in range(1, 9)]
        assert list(result_box["items"]) == ["R" + str(i) for i in range(1, 9)]
        assert [event[1] for event in events if event[0] == "extract_done"] == list(range(1, 9))
        # Reusing the same checkpoints must keep the same evidence and ordering.
        with patch.object(draft, "ask_llm", side_effect=AssertionError("cache was not reused")):
            repeat, count = draft._requirements(cfg, docs, [], lambda *_: None)
            assert count == 8 and repeat == result_box["items"]


if __name__ == "__main__":
    test_bounded_extraction()
    test_slow_earliest_request_does_not_idle_other_worker()
    print("ИТОГ: параллельные фрагменты, нет простоя за медленным запросом, стабильные ID, прогресс, кэш, лимит потоков")

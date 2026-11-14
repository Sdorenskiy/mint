"""[unit/integration] Incomplete model replies must never look complete (no live model)."""
import json
import os
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness

W = harness.make_project(prefix="mint_completion_")
os.environ.update(LLM_API_URL="http://127.0.0.1:9/v1", LLM_MODEL="completion-test",
                  MINT_CONFIG=str(W / "none.yaml"), LOG_DIR=str(W / "logs"), MINT_LANG="ru")
app = harness.load_mint(W, include_ui=False)
from mint import services
from mint.i18n import use_lang

cfg, _ = app.load_settings()
cfg = replace(cfg, llm_stream=True, llm_retries=1, llm_timeout=10)
check = harness.Checker()


class Reply:
    status_code = 200
    text = ""

    def __init__(self, content="Partial answer", finish="stop", done=True, stream=True, broken=False):
        self.content, self.finish, self.done = content, finish, done
        self.broken, self.closed = broken, False
        self.headers = {"Content-Type": "text/event-stream" if stream else "application/json"}

    def json(self):
        return {"choices": [{"message": {"content": self.content}, "finish_reason": self.finish}]}

    def iter_lines(self):
        yield ("data: " + json.dumps({"choices": [{"delta": {"content": self.content},
                                                   "finish_reason": None}]})).encode()
        if self.broken:
            raise services.requests.exceptions.ChunkedEncodingError("connection lost")
        if self.finish:
            yield ("data: " + json.dumps({"choices": [{"delta": {}, "finish_reason": self.finish}]})).encode()
        if self.done:
            yield b"data: [DONE]"

    def close(self):
        self.closed = True


def ask(reply, lang="ru"):
    with use_lang(lang), patch.object(services.requests, "post", return_value=reply):
        return app.ask_llm("s", "u", cfg, guard=True)


try:
    for lang, marker in [("ru", "⚠️ Ответ обрезан"), ("en", "⚠️ Answer truncated")]:
        for stream in (True, False):
            result = ask(Reply(finish="length", stream=stream), lang)
            check("Partial answer" in result and marker in result,
                  f"{lang}: length with text is marked, stream={stream}")
            check(ask(Reply(content="", finish="length", stream=stream), lang).startswith("❌"),
                  f"{lang}: empty length is an error, stream={stream}")
            check(ask(Reply(content="", stream=stream), lang).startswith("❌"),
                  f"{lang}: empty successful reply is an error, stream={stream}")
        for broken in (False, True):
            result = ask(Reply(finish=None, done=False, broken=broken), lang)
            check("Partial answer" in result and marker in result,
                  f"{lang}: missing terminal event is marked, broken={broken}")
        for cut in ("length", "loop", "time"):
            with patch.object(services, "_read_stream", return_value=("A complete line\nunfinished", False, None, None, cut)):
                result = ask(Reply(), lang)
            check(marker in result or result.startswith("❌"), f"{lang}: client cut {cut} is explicit")
    for finish, done in [("stop", True), ("stop", False), (None, True)]:
        reply = Reply(finish=finish, done=done)
        check(ask(reply) == "Partial answer", f"complete reply preserved: finish={finish}, DONE={done}")
        check(reply.closed, "stream connection closed")
finally:
    shutil.rmtree(W, ignore_errors=True)
check.finish()

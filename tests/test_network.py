"""Что MINT делает вовне — для проверки в песочнице и описания docs/SECURITY.md. Настоящие пакеты (как после
install.sh), модели — имитация шлюза на 127.0.0.1 (tests/mock_server.py). Журнал — audit hooks Python
(tests/net_audit_hook.py): видно и то, что делают библиотеки, а не только код MINT.

1. В процессе: база (.docx настоящим Docling) → чат → консультант → аудит с сохранением → контроль исправлений →
   страница целиком (streamlit.testing).
2. Настоящий сервер Streamlit (`python -m streamlit run app.py`, как run_mint.sh): запуск, страница, сеанс браузера по
   WebSocket — страница выполняется и обращается к шлюзу.

Проверяется: соединения и обращения к DNS — только к адресам из .env (здесь — имитация шлюза на 127.0.0.1); сервер
слушает только localhost; программы не запускаются; файлы пишутся только в KB_DIR, LOG_DIR и временную папку; реестр
Windows не меняется. Итог печатается таблицей — её можно приложить к заявке на проверку.

Запуск — Python из установленной .venv, из корня проекта:
    .venv/bin/python tests/test_network.py          (Windows: .venv\\Scripts\\python tests\\test_network.py)
На GitHub — .github/workflows/install.yml после установки с нуля.
"""
import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TESTS))           # mock_server и журнал; заглушки tests/stubs НЕ подключаются
import mock_server  # noqa: E402
import net_audit_hook as hook  # noqa: E402

FAILS = []
LOCAL = {"127.0.0.1", "::1", "localhost", "0.0.0.0", "::", "", "None"}


def check(cond, msg, extra=""):
    print(("  ✓ " if cond else "  ✗ ") + msg + (f" — {extra}" if extra and not cond else ""))
    if not cond:
        FAILS.append(msg)


work = Path(tempfile.mkdtemp(prefix="mint_net_"))
subprocess.run([sys.executable, str(ROOT / "tools" / "docx_parity.py"), "--make-samples", str(work / "docx")],
               check=True, capture_output=True)
sample = work / "docx" / "mint_sample_requirements.docx"
srv = mock_server.start()
gw_port = srv.server_address[1]
base = f"http://127.0.0.1:{gw_port}/v1"
env = {"LLM_API_URL": base, "EMBED_API_URL": base + "/embeddings", "RERANK_API_URL": base + "/rerank",
       "LLM_MODEL": "test-llm", "EMBED_MODEL": "emb-model", "RERANK_MODEL": "rr-model", "LLM_API_KEY": "k",
       "KB_DIR": str(work / "kb"), "LOG_DIR": str(work / "logs"), "MINT_CONFIG": str(work / "none.yaml"),
       "GLOSSARY_PATH": str(work / "none.json"), "PROMPTS_PATH": str(work / "prompts.yaml"),
       "MINT_CHECKLISTS": str(work / "checklists.yaml"), "MINT_LANG": "ru"}
os.environ.update(env)
ALLOWED_WRITE = {"KB_DIR": work / "kb", "LOG_DIR": work / "logs", "временная папка": Path(tempfile.gettempdir())}


def where(path):
    """Куда пишет: KB_DIR, LOG_DIR, временная папка — или «другое» (тогда это ошибка)."""
    p = os.path.abspath(path)
    if "__pycache__" in Path(p).parts:
        return "кэш байт-кода Python (__pycache__)"
    for name, root in ALLOWED_WRITE.items():
        try:
            if os.path.commonpath([p, os.path.abspath(root)]) == os.path.abspath(root):
                return name
        except ValueError:          # другой диск в Windows
            pass
    return None


def analyze(events, title):
    """Сводка событий одного процесса → строки отчёта; нарушения — в FAILS."""
    conn = sorted({f"{h}:{p}" for e in events if e["kind"] in ("connect", "sendto") for h, p in [e["detail"]]})
    foreign = [c for c in conn if c.rsplit(":", 1)[0] not in LOCAL]
    names = sorted({str(e["detail"][0]) for e in events if e["kind"] in ("resolve", "url")})
    foreign_dns = [n for n in names if n not in LOCAL and not n.startswith(f"http://127.0.0.1:{gw_port}")
                   and not n.startswith("http://localhost:")]
    binds = sorted({f"{h}:{p}" for e in events if e["kind"] == "bind" for h, p in [e["detail"]]})
    open_binds = [b for b in binds if b.rsplit(":", 1)[0] not in {"127.0.0.1", "::1", "localhost"}]
    procs = [e["detail"] for e in events if e["kind"] == "process"]
    writes = {}
    bad_writes = []
    for e in events:
        if e["kind"] in ("write", "fs"):
            path = e["detail"][1] if e["kind"] == "fs" else e["detail"][0]
            if not path:
                continue
            w = where(path)
            if w is None:
                bad_writes.append(f"{e['detail'][0] if e['kind'] == 'fs' else 'open'} {path}")
            else:
                writes[w] = writes.get(w, 0) + 1
    registry = [e["detail"] for e in events if e["kind"] == "registry"]
    check(not foreign, f"{title}: соединения только с имитацией шлюза и localhost ({', '.join(conn) or 'нет'})",
          ", ".join(foreign))
    check(not foreign_dns, f"{title}: обращений к DNS за чужими адресами нет", ", ".join(foreign_dns))
    check(not open_binds, f"{title}: слушает только localhost ({', '.join(binds) or 'не слушает'})", ", ".join(open_binds))
    check(not procs, f"{title}: программы не запускаются", json.dumps(procs, ensure_ascii=False)[:600])
    check(not bad_writes, f"{title}: файлы пишутся только в KB_DIR, LOG_DIR и временную папку "
                          f"({', '.join(f'{k}: {v}' for k, v in sorted(writes.items())) or 'не пишет'})",
          "; ".join(sorted(set(bad_writes))[:15]))
    check(not registry, f"{title}: реестр Windows не меняется", str(registry)[:300])
    return {"connections": conn, "listen": binds, "writes": writes, "processes": len(procs)}


# ---------------------------------------------------------------------------------------------------------------
print("1. В процессе: база → чат → консультант → аудит → контроль исправлений → страница")
hook.install()
from mint.config import load_settings  # noqa: E402
from mint.limits import detect_server_info, resolve_model_limits, resolve_settings  # noqa: E402

base_cfg, _ = load_settings()
cfg, _ = resolve_settings(base_cfg, resolve_model_limits(base_cfg, detect_server_info(base_cfg), None, {}), {})
from mint.kb import process_and_add_to_kb  # noqa: E402
from mint.parsing import document_to_markdown  # noqa: E402

data = sample.read_bytes()
ok, msg = process_and_add_to_kb(sample.name, data, cfg)
md_text = document_to_markdown(sample.name, data)
from mint.chat import answer_question  # noqa: E402
from mint.consult import answer_consult  # noqa: E402
from mint.audit import annotate_docx_with_findings, run_audit  # noqa: E402
from mint.audit_store import save_audit  # noqa: E402
from mint.review import verify_remarks  # noqa: E402

qa = answer_question("Сколько хранятся файлы?", cfg)
co = answer_consult("Разбери проблему: файлы удаляются раньше срока. Предложи решения.", cfg)
au = run_audit(md_text, sample.name, cfg)
aid = save_audit(cfg, au, sample.name, doc_bytes=data)
annotate_docx_with_findings(data, au.get("findings") or [])
rv = verify_remarks(["Указать срок хранения файлов и порядок их удаления"], md_text, cfg)
check(ok and qa["answer"] and co["answer"] and au.get("report") and aid and rv["rows"],
      "сценарии выполнены: база, чат, консультант, аудит (сохранён), контроль исправлений")
try:
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.run()
    check(not at.exception, "страница целиком (streamlit.testing) — без ошибок",
          str(at.exception[0].message)[:300] if at.exception else "")
except ImportError:
    print("  (нет streamlit.testing — страница проверяется только в части 2)")
in_process = analyze([e for e in hook.EVENTS if e["pid"] == os.getpid()], "в процессе")

# ---------------------------------------------------------------------------------------------------------------
print("2. Настоящий сервер Streamlit (как run_mint.sh): запуск, страница, сеанс браузера")
with hook.paused():
    hook_dir = work / "hook"
    hook_dir.mkdir()
    shutil.copy(TESTS / "net_audit_hook.py", hook_dir / "sitecustomize.py")
    log = work / "server_events.jsonl"
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env2 = {**os.environ, "PYTHONPATH": os.pathsep.join([str(hook_dir), os.environ.get("PYTHONPATH", "")]),
            "MINT_NET_LOG": str(log), "PYTHONUTF8": "1"}
    before = len(mock_server.STATE["requests"])
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", str(port)],
                            cwd=ROOT, env=env2, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    url = f"http://localhost:{port}"
    up = False
    for _ in range(120):
        try:
            with urllib.request.urlopen(url + "/_stcore/health", timeout=2) as r:
                up = r.read().decode().strip() == "ok"
            if up:
                break
        except OSError:
            time.sleep(0.5)
    check(up, f"сервер запустился ({url})")
    page_ok = False
    if up:
        with urllib.request.urlopen(url + "/", timeout=10) as r:
            page_ok = r.status == 200 and b"<html" in r.read().lower()
    check(page_ok, "страница отдаётся")

    async def browser_session():
        """Как браузер: WebSocket, запрос на выполнение страницы, ожидание конца выполнения."""
        from streamlit.proto.BackMsg_pb2 import BackMsg
        from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
        from tornado.websocket import websocket_connect
        ws = await websocket_connect(f"ws://localhost:{port}/_stcore/stream", subprotocols=["streamlit"])
        msg = BackMsg()
        msg.rerun_script.query_string = ""
        msg.rerun_script.page_script_hash = ""
        await ws.write_message(msg.SerializeToString(), binary=True)
        deadline = time.time() + 180
        while time.time() < deadline:
            raw = await asyncio.wait_for(ws.read_message(), timeout=max(1.0, deadline - time.time()))
            if raw is None:
                break
            fm = ForwardMsg()
            fm.ParseFromString(raw)
            if fm.WhichOneof("type") == "script_finished":
                ws.close()
                return True
        ws.close()
        return False

    finished = False
    if up:
        try:
            finished = asyncio.run(browser_session())
        except Exception as e:
            print(f"  сеанс браузера: {type(e).__name__}: {str(e)[:300]}")
    gateway_calls = mock_server.STATE["requests"][before:]
    check(finished and gateway_calls, f"страница выполнилась в сеансе браузера и обратилась к шлюзу "
                                      f"(запросов к имитации шлюза: {len(gateway_calls)})")
    proc.terminate()
    try:
        out = proc.communicate(timeout=30)[0].decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        proc.kill()
        out = proc.communicate()[0].decode("utf-8", "replace")
    events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()] \
        if log.exists() else []
check(len(events) > 0, f"журнал сервера получен (событий: {len(events)})", out[-1500:])
server = analyze(events, "сервер Streamlit")

srv.shutdown()

# ---------------------------------------------------------------------------------------------------------------
print("\nИтог для заявки на проверку (адрес шлюза здесь — имитация на 127.0.0.1; в работе — адреса из .env):")
print("| | В процессе (база, чат, консультант, аудит, контроль исправлений, страница) | Сервер Streamlit |")
print("|---|---|---|")
print(f"| Исходящие соединения | {', '.join(in_process['connections']) or 'нет'} | "
      f"{', '.join(server['connections']) or 'нет'} |")
print(f"| Слушает | {', '.join(in_process['listen']) or 'нет'} (имитация шлюза) | {', '.join(server['listen']) or 'нет'} |")
print(f"| Запуск программ | {in_process['processes'] or 'нет'} | {server['processes'] or 'нет'} |")
print(f"| Запись файлов | {', '.join(f'{k}: {v}' for k, v in sorted(in_process['writes'].items()))} | "
      f"{', '.join(f'{k}: {v}' for k, v in sorted(server['writes'].items()))} |")
if os.environ.get("GITHUB_ACTIONS") == "true":
    print(f"::notice title=Обращения вовне::{sys.platform}: соединения — только адреса из .env; слушает "
          f"{', '.join(server['listen'])}; программ не запускает; пишет в KB_DIR, LOG_DIR и временную папку"
          + ("" if not FAILS else f" — НАРУШЕНИЯ: {len(FAILS)}"))
shutil.rmtree(work, ignore_errors=True)
print("\nИТОГ:", "все проверки пройдены" if not FAILS else f"провалено {len(FAILS)}: {FAILS}")
sys.exit(1 if FAILS else 0)

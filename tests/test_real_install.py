"""Проверка настоящей установки — то, что получит пользователь после install.sh / install.bat. Без заглушек: настоящий
Docling, Streamlit, faiss; модели — имитация шлюза (tests/mock_server.py).

Что проверяется:
1. пакеты: Docling — облегчённая сборка точной версии из requirements.lock; PyTorch, transformers, huggingface_hub
   и прочие библиотеки моделей не установлены;
2. разбор .docx настоящим Docling (бэкендом Word) — заголовки, списки, таблица; PyTorch не загружается;
3. база знаний → поиск → ответ чата → аудит документа на настоящих пакетах;
4. самопроверка установки (check_install.py) — без ошибок, включая страницу на настоящем Streamlit.

Запуск — Python из установленной .venv, из корня проекта:
    .venv/bin/python tests/test_real_install.py          (Windows: .venv\\Scripts\\python tests\\test_real_install.py)
На GitHub — .github/workflows/install.yml после install.sh / install.bat на чистой машине.
"""
import importlib.metadata as md
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TESTS))           # только mock_server; заглушки tests/stubs НЕ подключаются
import mock_server  # noqa: E402

FAILS = []


def check(cond, msg, extra=""):
    print(("  ✓ " if cond else "  ✗ ") + msg + (f" — {extra}" if extra and not cond else ""))
    if not cond:
        FAILS.append(msg)


def version(dist):
    try:
        return md.version(dist)
    except md.PackageNotFoundError:
        return None


def locked_versions():
    """{пакет: версия} из requirements.lock для этого Python (строки с маркерами — только подходящие)."""
    out = {}
    for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        m = re.match(r"([A-Za-z0-9_.\-]+)==([^\s;]+)\s*(?:;\s*(.*))?$", line)
        if not m:
            continue
        name, ver, marker = m.groups()
        if marker:
            try:
                from packaging.markers import Marker
                if not Marker(marker).evaluate():
                    continue
            except Exception:
                pass
        out[name.lower().replace("_", "-")] = ver
    return out


print("1. Пакеты: точные версии, без библиотек моделей")
lock = locked_versions()
check(version("docling-slim") == lock.get("docling-slim") == "2.127.0" and version("docling") is None,
      f"Docling — облегчённая сборка из requirements.lock: {version('docling-slim')}")
heavy = [d for d in ("torch", "torchvision", "transformers", "huggingface-hub", "opencv-python-headless",
                     "scipy", "docling-parse", "rapidocr", "easyocr", "accelerate") if version(d)]
check(not heavy, "PyTorch и другие библиотеки моделей не установлены", str(heavy))
installed = {d.metadata["Name"].lower().replace("_", "-"): d.version for d in md.distributions()}
off = {n: (installed.get(n), v) for n, v in lock.items() if installed.get(n) not in (None, v)}
check(not off, f"версии совпадают с requirements.lock ({len(lock)} пакетов)", str(off))

print("2. Разбор .docx настоящим Docling (бэкенд Word)")
work = Path(tempfile.mkdtemp(prefix="mint_real_"))
subprocess.run([sys.executable, str(ROOT / "tools" / "docx_parity.py"), "--make-samples", str(work / "docx")], check=True)
from mint.parsing import docx_parser, document_to_markdown, parse_document  # noqa: E402
sample = work / "docx" / "mint_sample_requirements.docx"
md_text = document_to_markdown(sample.name, sample.read_bytes())
doc = parse_document(sample.name, sample.read_bytes())
paths = {u["path"] for u in doc["units"]}
check(docx_parser() == "backend" and re.search(r"^#+ 1\. Общие положения", md_text, re.M)
      and "| Шаг" in md_text and "Файлы хранятся 30 дней" in md_text, "Markdown: заголовки, список, таблица",
      md_text[:400])
check(doc["info"]["structure"] == "styles" and any("1.1 Хранение" in p for p in paths) and doc["tables"],
      f"структура для базы: разделы по стилям, таблица ({doc['info']})")
check("torch" not in sys.modules, "PyTorch не загружался")

print("3. База знаний → поиск → чат → аудит на настоящих пакетах")
srv = mock_server.start()
base = f"http://127.0.0.1:{srv.server_address[1]}/v1"
env = {"LLM_API_URL": base, "EMBED_API_URL": base + "/embeddings", "RERANK_API_URL": base + "/rerank",
       "LLM_MODEL": "test-llm", "EMBED_MODEL": "emb-model", "RERANK_MODEL": "rr-model", "LLM_API_KEY": "k",
       "KB_DIR": str(work / "kb"), "LOG_DIR": str(work / "logs"), "MINT_CONFIG": str(work / "none.yaml"),
       "GLOSSARY_PATH": str(work / "none.json"), "MINT_LANG": "ru"}
os.environ.update(env)
from mint.config import load_settings  # noqa: E402
from mint.limits import resolve_model_limits, resolve_settings  # noqa: E402
from mint.limits import detect_server_info  # noqa: E402
base_cfg, _ = load_settings()
server = detect_server_info(base_cfg)
cfg, _ = resolve_settings(base_cfg, resolve_model_limits(base_cfg, server, None, {}), {})
from mint.kb import list_kb_documents, process_and_add_to_kb  # noqa: E402
ok, msg = process_and_add_to_kb(sample.name, sample.read_bytes(), cfg)
check(ok and list_kb_documents(cfg)[0] == [sample.name], f"документ проиндексирован: {msg}")
from mint.chat import answer_question  # noqa: E402
qa = answer_question("Сколько хранятся файлы?", cfg)
check(qa["sources"] and not qa["error"] and qa["answer"], f"чат ответил по базе: {qa['answer'][:80]!r}")
from mint.audit import run_audit  # noqa: E402
au = run_audit(md_text, sample.name, cfg)
check(au.get("report") and au.get("sections"), f"аудит: разделов {au.get('sections')}, замечаний {len(au.get('findings', []))}")
check("torch" not in sys.modules, "PyTorch не загружался и при работе MINT")

print("4. Самопроверка установки (check_install.py, страница на настоящем Streamlit)")
r = subprocess.run([sys.executable, str(ROOT / "check_install.py")], cwd=ROOT, env={**os.environ, "PYTHONUTF8": "1"},
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
fails = [ln for ln in r.stdout.splitlines() if "[FAIL]" in ln]
check(r.returncode == 0 and not fails and "[ OK ] тестовый .docx разобран" in r.stdout,
      "самопроверка без ошибок, .docx разобран", "\n".join(fails) or r.stdout[-1500:] + r.stderr[-1500:])
print("\n" + "\n".join(ln for ln in r.stdout.splitlines() if ln.strip().startswith(("[", "Итог")))[-3000:])

srv.shutdown()
shutil.rmtree(work, ignore_errors=True)
size = sum(f.stat().st_size for f in Path(sys.prefix).rglob("*") if f.is_file())
print(f"\nУстановка: {len(installed)} пакетов, {size / 1e6:.0f} МБ ({sys.prefix})")
if os.environ.get("GITHUB_ACTIONS") == "true":
    print(f"::notice title=Установка с нуля::{sys.platform} Python {sys.version.split()[0]}: {len(installed)} пакетов, "
          f"{size / 1e6:.0f} МБ, Docling {version('docling-slim')}, PyTorch — нет")
print("\nИТОГ:", "все проверки пройдены" if not FAILS else f"провалено {len(FAILS)}: {FAILS}")
sys.exit(1 if FAILS else 0)

"""Схемы docs/MINT_*.excalidraw не отстают от кода.

  • docs/ (английские) и docs/ru/ (русские) совпадают с тем, что собирают скрипты tools/diagrams (схемы правятся
    в скриптах, не вручную); в tools/diagrams/en.py нет переводов надписей, которых больше нет;
  • каждое имя функции, параметра и файла на схемах есть в коде;
  • таблица «Что получится при разных моделях» совпадает с расчётом resolve_settings().

Запуск из корня проекта:  python tests/test_diagrams.py
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402

ROOT, TOOLS, DOCS = harness.ROOT, harness.ROOT / "tools" / "diagrams", harness.ROOT / "docs"
SCRIPTS = {"MINT_architecture": "build_architecture.py", "MINT_engineering": "build_engineering.py"}
check = harness.Checker()


def texts(path):
    return [e["text"] for e in json.loads(path.read_text(encoding="utf-8"))["elements"] if e["type"] == "text"]


print("1. Схемы в docs/ и docs/ru/ собраны из tools/diagrams")
tmp = Path(tempfile.mkdtemp(prefix="mint_diagrams_"))
all_texts, collected = [], {}
for lang, folder in (("ru", DOCS / "ru"), ("en", DOCS)):
    for name, script in SCRIPTS.items():
        keys_file = tmp / f"keys_{lang}_{name}.json"
        env = {**os.environ, "PYTHONUTF8": "1", "DIAGRAM_COLLECT": str(keys_file)}
        r = subprocess.run([sys.executable, str(TOOLS / script), str(tmp / f"{name}_{lang}"), "--lang", lang],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=TOOLS, env=env)
        check(r.returncode == 0, f"{script} --lang {lang} собирает схему", r.stderr[-1500:])
        if r.returncode:
            continue
        if lang == "ru":
            collected.update(json.loads(keys_file.read_text(encoding="utf-8")))
        rel = folder.relative_to(ROOT)
        built, current = texts(tmp / f"{name}_{lang}.excalidraw"), texts(folder / f"{name}.excalidraw")
        diff = sorted(set(built) ^ set(current))
        check(built == current, f"{rel}/{name}.excalidraw совпадает со скриптом",
              f"пересоберите: cd tools/diagrams && python {script} ../../{rel}/{name} --lang {lang}; расхождения: "
              + " | ".join(t[:80].replace("\n", " ") for t in diff[:4]))
        md = (folder / f"{name}.excalidraw.md").read_text(encoding="utf-8").replace("\r\n", "\n")
        check(all(t in md for t in current[:5] + current[-5:]), f"{rel}/{name}.excalidraw.md — та же схема")
        if lang == "en":
            cyr = [t for t in current if re.search("[А-Яа-яЁё]", t)]
            check(not cyr, f"{rel}/{name}.excalidraw — без русского текста", " | ".join(t[:60] for t in cyr[:3]))
        all_texts += current
sys.path.insert(0, str(TOOLS))
from en import EN  # noqa: E402
from lang import key  # noqa: E402
stale = sorted(set(EN) - {key(t) for t in collected.values()})
check(not stale, f"в en.py нет устаревших переводов ({len(EN)} надписей)", " | ".join(k[:70] for k in stale[:5]))
shutil.rmtree(tmp, ignore_errors=True)

print("2. Имена на схемах есть в коде")
code = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "mint").rglob("*.py"))
                 + [ROOT / n for n in ("app.py", "eval_search.py", "kb_stats.py", "check_install.py",
                                       "config.example.yaml", ".env.example")])
text = "\n".join(all_texts)
names = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9]*_[A-Za-z0-9_]*\b", text)) | set(re.findall(r"\b([a-z_][a-z0-9_]+)\(", text))
missing = sorted(n for n in names if n not in code)
check(not missing, f"все {len(names)} имён функций и параметров найдены в коде", ", ".join(missing[:20]))
files = set(re.findall(r"\b[\w-]+\.(?:py|json|jsonl|pkl|faiss|yaml|toml|log)\b", text))
missing_files = sorted(f for f in files if f not in code and not list(ROOT.rglob(f)))
check(not missing_files, f"все {len(files)} имён файлов есть в коде или в проекте", ", ".join(missing_files))

print("3. Таблица «Что получится при разных моделях» = расчёт MINT")
tree = ast.parse((TOOLS / "build_engineering.py").read_text(encoding="utf-8"))
consts = {t.id: ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
          for t in node.targets if isinstance(t, ast.Name) and t.id in ("SCENARIO_LIMITS", "SCENARIO_ROWS")}
app = harness.load_mint(ROOT, include_ui=False)
base = replace(app.DEFAULTS, embed_model="Qwen3-Embedding-4B", top_k=5, llm_model="m")
wrong = []
for col, (llm, emb, rr, cpt) in enumerate(consts.get("SCENARIO_LIMITS", [])):
    limits = {"llm_context_tokens": (llm, "x"), "embed_max_tokens": (emb, "x"), "rerank_max_tokens": (rr, "x"),
              "chars_per_token": (cpt, "x")}
    cfg, _ = app.resolve_settings(replace(base, chars_per_token=cpt), limits, {})
    for row in consts["SCENARIO_ROWS"]:
        field, shown = row[0].split()[0], int(re.match(r"\d+", row[col + 1]).group())
        if getattr(cfg, field) != shown:
            wrong.append(f"{field} при {llm}/{emb}/{rr}: на схеме {shown}, в коде {getattr(cfg, field)}")
check(consts.get("SCENARIO_ROWS") and not wrong, f"{len(consts.get('SCENARIO_ROWS', []))} параметров × 4 модели",
      "; ".join(wrong[:6]))

check.finish()

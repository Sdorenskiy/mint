"""Самопроверка установки (check_install.py): рабочая конфигурация и типичные ошибки.

Запуск из корня проекта:  python tests/test_check_install.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402
import mock_server  # noqa: E402

W = harness.make_project(prefix="mint_check_", extra_files=("check_install.py", ".streamlit"))
srv = mock_server.start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/v1"
check = harness.Checker()
for k in ("LLM_API_URL", "EMBED_API_URL", "RERANK_API_URL", "LLM_API_KEY", "LLM_MODEL", "EMBED_MODEL", "KB_DIR",
          "LOG_DIR", "MINT_CONFIG", "GLOSSARY_PATH", "_MINT_DOTENV_KEYS"):
    os.environ.pop(k, None)
env = {**os.environ, "PYTHONPATH": harness.child_pythonpath(W)}


def run(*args, lang="ru"):
    r = subprocess.run([sys.executable, str(W / "check_install.py"), *args], cwd=W, env={**env, "MINT_LANG": lang},
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    return r.returncode, r.stdout + r.stderr


(W / ".env").write_text(
    f"LLM_API_URL={BASE}\nEMBED_API_URL={BASE}/embeddings\nRERANK_API_URL={BASE}/rerank\nLLM_API_KEY=sk-secret-123\n"
    f"LLM_MODEL=test-llm\nEMBED_MODEL=emb-model\nRERANK_MODEL=rr-model\nKB_DIR={W / 'kb'}\nLOG_DIR={W / 'logs'}\n",
    encoding="utf-8")
code, out = run()
print(out[-3000:] if code else "")
check(code == 0, "рабочая конфигурация — без ошибок", out[-1500:])
for frag in ("[ OK ] Python", ".env прочитан", "тестовый .docx разобран", "LLM: сервер отвечает",
             "LLM ответила", "Эмбеддинги: вектор размерности 64", "Реранкер: доступен", "(localhost)"):
    check(frag in out, f"в выводе: {frag}")
check("sk-secret-123" not in out, "ключ не печатается")

code, out = run(lang="en")
check(code == 0 and "=== Python packages ===" in out and "test .docx parsed" in out and "LLM answered" in out
      and "Summary:" in out and not any("а" <= c <= "я" for line in out.splitlines() if not line.startswith("    ")
                                         for c in line.replace("ЗПС", "")),
      "вывод на английском (MINT_LANG=en; строки ответа модели не в счёт)",
      out[-1500:])

code, out = run("--no-llm", "--skip-docling")
check(code == 0 and "LLM ответила" not in out and "разбор .docx" not in out.lower().replace("разбор .docx (docling)", ""),
      "--no-llm и --skip-docling пропускают проверки")

(W / ".env").write_text("LLM_API_URL=http://127.0.0.1:1/v1\nEMBED_API_URL=http://127.0.0.1:1/v1/embeddings\n"
                        f"KB_DIR={W / 'kb'}\nLOG_DIR={W / 'logs'}\n", encoding="utf-8")
code, out = run("--skip-docling")
check(code == 1 and "нет соединения" in out, "недоступный сервер — ошибка с подсказкой", out[-1500:])

(W / ".env").unlink()
(W / "env.txt").write_text("LLM_API_URL=x\n", encoding="utf-8")
code, out = run("--skip-docling")
check(code == 1 and ".env не найден" in out and "LLM_API_URL" in out, "нет .env — подсказка, где искал", out[-1500:])

(W / ".streamlit" / "config.toml").write_text("", encoding="utf-8")
code, out = run("--skip-docling")
check("доступна по сети" in out, "нет address = localhost — предупреждение")

srv.shutdown()
shutil.rmtree(W, ignore_errors=True)
check.finish()

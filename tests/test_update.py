"""Обновление на месте (update.sh): новая версия из архива или папки заменяет код, а свои настройки (.env,
config.yaml, glossary.json, checklists.yaml, prompts.yaml), окружение .venv, база и логи остаются.

Запуск из корня проекта:  python tests/test_update.py      (в Windows пропускается: там update.bat)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402

check = harness.Checker()
if os.name == "nt" or not shutil.which("sh"):
    print("  — нет sh: тест update.sh пропущен")
    print("\nИТОГ: пропущено (Windows)")
    sys.exit(0)

W = Path(tempfile.mkdtemp(prefix="mint_update_"))
OLD, NEW = W / "MINT", W / "build" / "mint-main"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# установленная версия: код, свои настройки, окружение, данные
write(OLD / "mint" / "version.py", '"""Версия MINT."""\n\n\nMINT_VERSION = "1.0"\n')
write(OLD / "mint" / "old_module.py", "# удалён в новой версии\n")
shutil.copy(harness.ROOT / "update.sh", OLD / "update.sh")
write(OLD / "install.sh", "#!/bin/sh\necho old > installed.txt\n")
for name, text in ((".env", "LLM_API_KEY=my-key\n"), ("config.yaml", "audit:\n  audit_passes: 2\n"),
                   ("glossary.json", "{}\n"), ("checklists.yaml", "common: [мой пункт]\n"),
                   ("prompts.yaml", "audit_map_system: мой промпт\n"), ("requirements.lock", "old==1\n"),
                   ("README.md", "старое описание\n"), (".venv/marker", "venv\n"), ("eval/questions.csv", "мои\n"),
                   (".streamlit/secrets.toml", "secret = 1\n"), ("knowledge_base/index.txt", "база\n")):
    write(OLD / name, text)
# новая версия (архив с папкой верхнего уровня, как у GitHub): в ней чужие .env и config.yaml — не должны попасть
write(NEW / "mint" / "version.py", '"""Версия MINT."""\n\n\nMINT_VERSION = "99.0"\n')
write(NEW / "mint" / "new_module.py", "# новый\n")
write(NEW / "install.sh", '#!/bin/sh\necho "args:$*" > installed.txt\n')
# update.sh новой версии другой: старый, который сейчас работает, заменяется им по ходу работы
write(NEW / "update.sh", "#!/bin/sh\n" + "# другая версия\n" * 300 + "echo NEW-SCRIPT-RAN\nexit 7\n")
for name, text in ((".env", "LLM_API_KEY=someone-else\n"), ("config.yaml", "чужой\n"), ("README.md", "новое\n"),
                   ("requirements.txt", "streamlit>=1.36\n"), ("eval/new_tool.py", "# новый\n"),
                   (".streamlit/config.toml", "[theme]\n"), ("wheels/pkg-1.0-py3-none-any.whl", "whl\n")):
    write(NEW / name, text)
archive = W / "mint-99.0.zip"
with zipfile.ZipFile(archive, "w") as z:
    for p in NEW.parent.rglob("*"):
        if p.is_file():
            z.write(p, p.relative_to(NEW.parent))


def update(*args, env=None, cwd=W):
    return subprocess.run(["sh", str(OLD / "update.sh"), *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", env={**os.environ, **(env or {})})


print("1. Из архива, путь относительно папки запуска")
r = update("mint-99.0.zip", env={"SKIP_INSTALL": "1"})
check(r.returncode == 0 and "MINT 1.0 -> 99.0" in r.stdout, "обновление прошло, версии в выводе", r.stdout + r.stderr)
check('MINT_VERSION = "99.0"' in (OLD / "mint" / "version.py").read_text(encoding="utf-8")
      and (OLD / "mint" / "new_module.py").exists() and not (OLD / "mint" / "old_module.py").exists(),
      "папка mint заменена целиком: старого модуля нет, новый есть")
check((OLD / ".env").read_text(encoding="utf-8") == "LLM_API_KEY=my-key\n"
      and (OLD / "config.yaml").read_text(encoding="utf-8") == "audit:\n  audit_passes: 2\n"
      and (OLD / "checklists.yaml").read_text(encoding="utf-8") == "common: [мой пункт]\n"
      and (OLD / "prompts.yaml").exists() and (OLD / "glossary.json").exists(),
      "свои .env, config.yaml, чек-листы, промпты и словарь не тронуты (чужие из архива не попали)")
check((OLD / ".venv" / "marker").exists() and (OLD / "knowledge_base" / "index.txt").exists()
      and (OLD / "eval" / "questions.csv").exists() and (OLD / "eval" / "new_tool.py").exists()
      and (OLD / ".streamlit" / "secrets.toml").exists() and (OLD / ".streamlit" / "config.toml").exists(),
      ".venv, база, свои вопросы eval и secrets.toml остались; новые файлы добавлены")
check((OLD / "README.md").read_text(encoding="utf-8") == "новое\n" and not (OLD / "requirements.lock").exists()
      and (OLD / "requirements.txt").exists() and not (OLD / "installed.txt").exists(),
      "файлы верхнего уровня новые, старой фиксации версий нет; SKIP_INSTALL — пакеты не ставятся")
check(os.access(OLD / "install.sh", os.X_OK), "скрипты остаются исполняемыми")
check("NEW-SCRIPT-RAN" not in r.stdout and "файлы обновлены" in r.stdout and (OLD / "update.sh").read_text(
      encoding="utf-8").count("другая версия") == 300, "update.sh заменён новым по ходу работы — старый доработал до конца")
shutil.copy(harness.ROOT / "update.sh", OLD / "update.sh")

print("2. Из папки: установка пакетов из офлайн-комплекта новой версии")
r = update(str(NEW))
installed = (OLD / "installed.txt").read_text(encoding="utf-8") if (OLD / "installed.txt").exists() else ""
check(r.returncode == 0 and installed.strip() == f"args:{NEW / 'wheels'}" and "MINT 99.0" in r.stdout,
      "из папки; пакеты — из её wheels", installed + r.stdout + r.stderr)

shutil.copy(harness.ROOT / "update.sh", OLD / "update.sh")

print("3. Ошибки")
r = update(str(W / "nothing.zip"))
check(r.returncode != 0 and "не найдено" in r.stdout, "нет архива — понятная ошибка", r.stdout)
write(W / "other" / "readme.txt", "x\n")
r = update(str(W / "other"))
check(r.returncode != 0 and "нет MINT" in r.stdout, "папка без MINT — отказ", r.stdout)
r = update(str(OLD))
check(r.returncode != 0 and "та же папка" in r.stdout, "та же папка — отказ", r.stdout)
r = update()
check(r.returncode != 0 and "Usage" in r.stdout, "без аргумента — подсказка", r.stdout)
check(b"\r\n" in (harness.ROOT / "update.bat").read_bytes(), "update.bat — с переводами строк Windows (CRLF)")

shutil.rmtree(W, ignore_errors=True)
check.finish()

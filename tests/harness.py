"""Общая обвязка тестов MINT.

- Streamlit и Docling — всегда заглушки из tests/stubs: страница прогоняется без браузера, а .docx
  разбирается через python-docx (настоящий Docling тяжёлый; его проверяет check_install.py на машине
  пользователя).
- faiss — настоящий faiss-cpu, если установлен, иначе заглушка на numpy из tests/fallback.
- Пакет mint копируется во временную папку: тесты не видят ваши .env, config.yaml и glossary.json.
"""
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent

REAL_FAISS = importlib.util.find_spec("faiss") is not None   # проверяется до подключения заглушки
os.environ.setdefault("MINT_LANG", "ru")   # существующие проверки написаны для русского интерфейса
sys.path.insert(0, str(TESTS / "stubs"))
if not REAL_FAISS:
    sys.path.append(str(TESTS / "fallback"))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))


def child_pythonpath(project_dir):
    """PYTHONPATH для дочерних процессов (eval_search.py): та же копия пакета и те же заглушки. Заглушка
    faiss — только если настоящего нет: PYTHONPATH важнее site-packages, и иначе дочерний процесс не прочитал
    бы индекс, записанный настоящим faiss."""
    parts = [str(project_dir), str(TESTS / "stubs")] + ([] if REAL_FAISS else [str(TESTS / "fallback")])
    return os.pathsep.join(parts)


def make_project(prefix="mint_test_", extra_files=()):
    """Временная папка проекта: копия mint/ (и файлов из extra_files). Возвращает её путь."""
    work = Path(tempfile.mkdtemp(prefix=prefix))
    shutil.copytree(ROOT / "mint", work / "mint", ignore=shutil.ignore_patterns("__pycache__"))
    for name in extra_files:
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy(src, work / name)
    return work


def load_mint(project_dir, include_ui=True):
    """Импортирует mint из копии проекта и возвращает пространство имён всех его модулей."""
    sys.path.insert(0, str(project_dir))
    for name in [n for n in sys.modules if n == "mint" or n.startswith("mint.")]:
        del sys.modules[name]
    from mint.devtools import load_namespace
    app = load_namespace(include_ui=include_ui)
    assert Path(app.APP_DIR).resolve() == Path(project_dir).resolve(), app.APP_DIR
    return app


class Checker:
    def __init__(self):
        self.fails = []

    def __call__(self, cond, msg, extra=""):
        print(("  ✓ " if cond else "  ✗ ") + msg + (f" — {extra}" if extra and not cond else ""))
        if not cond:
            self.fails.append(msg)

    def finish(self):
        print("\nИТОГ:", "все проверки пройдены" if not self.fails else f"провалено {len(self.fails)}: {self.fails}")
        sys.exit(1 if self.fails else 0)

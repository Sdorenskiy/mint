"""Журнал того, что процесс делает вовне: соединения и обращения к DNS, адреса, на которых он слушает, запуск программ,
запись файлов, изменения реестра Windows. Основан на audit hooks Python (PEP 578): события приходят от самого
интерпретатора, поэтому видно и то, что делают библиотеки (Streamlit, Docling, requests), а не только код MINT.

Для tests/test_network.py. В процессе теста — install(), события в EVENTS. В другом процессе — как sitecustomize.py
(папка с ним в PYTHONPATH): если задан MINT_NET_LOG, события пишутся туда строками JSON.
"""
import json
import os
import sys
import threading
import traceback
from contextlib import contextmanager

EVENTS = []
_LOCK = threading.Lock()
_STATE = {"paused": False, "installed": False}
_BUSY = threading.local()
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
_PROCESS = {"subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.spawn", "os.startfile", "os.fork",
            "os.forkpty"}
_FS = {"os.mkdir", "os.rename", "os.replace", "os.remove", "os.rmdir", "os.symlink", "os.link", "os.truncate",
       "shutil.rmtree", "shutil.move", "shutil.copyfile"}
# позиция аргумента dir_fd: путь относительно открытой папки — это удаление дерева (shutil.rmtree), само оно
# приходит отдельным событием с полным путём
_DIR_FD = {"os.mkdir": 2, "os.remove": 1, "os.rmdir": 1, "os.rename": 2, "os.replace": 2, "os.symlink": 2,
           "os.link": 2}
_REGISTRY_WRITE = {"winreg.CreateKey", "winreg.DeleteKey", "winreg.DeleteValue", "winreg.SetValue",
                   "winreg.SaveKey", "winreg.LoadKey"}


def _path(p):
    try:
        return os.fsdecode(p) if isinstance(p, (str, bytes, os.PathLike)) else str(p)
    except Exception:
        return str(p)


def _addr(a):
    return [a[0], a[1]] if isinstance(a, tuple) and len(a) >= 2 else [_path(a), None]


_STDLIB = os.path.dirname(os.__file__)


def _caller():
    """Кто вызвал: ближайшие кадры стека вне стандартной библиотеки и этого файла — «пакет/файл:строка функция»
    (кадры стандартной библиотеки — platform, subprocess — только показывают, как вызов дошёл до запуска)."""
    frames = [f for f in traceback.extract_stack()[:-3]
              if not f.filename.endswith(("net_audit_hook.py", "sitecustomize.py"))]
    own = [f for f in frames if not os.path.abspath(f.filename).startswith(_STDLIB + os.sep)
           or "site-packages" in f.filename]
    pick = own[-5:] + [f for f in frames[-2:] if f not in own[-5:]]
    return [f"{os.sep.join(f.filename.split(os.sep)[-2:])}:{f.lineno} {f.name}" for f in pick]


def _record(kind, detail):
    if _STATE["paused"] or getattr(_BUSY, "on", False):
        return
    _BUSY.on = True                 # своя запись в журнал — тоже событие «open»: без повторного входа
    try:
        item = {"kind": kind, "detail": detail, "pid": os.getpid(), "thread": threading.current_thread().name}
        with _LOCK:
            EVENTS.append(item)
            log = os.environ.get("MINT_NET_LOG")
            if log:
                with open(log, "a", encoding="utf-8") as f:
                    f.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
    finally:
        _BUSY.on = False


def _hook(event, args):
    try:
        if event == "socket.connect":
            _record("connect", _addr(args[1]))
        elif event == "socket.bind":
            _record("bind", _addr(args[1]))
        elif event == "socket.sendto":
            _record("sendto", _addr(args[1]))
        elif event == "socket.getaddrinfo":
            _record("resolve", [args[0] if not isinstance(args[0], bytes) else args[0].decode(), args[1]])
        elif event in ("socket.gethostbyname", "socket.gethostbyname_ex", "socket.gethostbyaddr"):
            _record("resolve", [str(args[0]), None])
        elif event == "urllib.Request":
            _record("url", [str(args[0]), None])
        elif event in _PROCESS:
            _record("process", [event, _path(args[0])[:300] if args else "", str(args[1])[:300] if len(args) > 1 else "",
                                _caller()])
        elif event == "open":
            path, _mode, flags = args
            if not isinstance(path, int) and isinstance(flags, int) and flags & _WRITE_FLAGS:
                _record("write", [_path(path), None])
        elif event in _FS:
            pos = _DIR_FD.get(event)
            if pos is not None and len(args) > pos and isinstance(args[pos], int) and args[pos] >= 0:
                return
            _record("fs", [event, _path(args[0]) if args else ""])
        elif event in _REGISTRY_WRITE:
            _record("registry", [event, str(args[:2])[:300]])
    except Exception:              # журнал не должен ломать проверяемый процесс
        pass


def install():
    if not _STATE["installed"]:
        sys.addaudithook(_hook)
        _STATE["installed"] = True


@contextmanager
def paused():
    """Действия самого теста (запуск сервера, обращения к нему) — не в журнал."""
    _STATE["paused"] = True
    try:
        yield
    finally:
        _STATE["paused"] = False


if os.environ.get("MINT_NET_LOG") and __name__ == "sitecustomize":
    install()

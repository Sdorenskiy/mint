#!/bin/sh
# Start MINT on Linux or macOS:  ./run_mint.sh   → http://localhost:8501, stop with Ctrl+C.
# Запуск MINT в Linux (Astra Linux, Ubuntu и др.) и macOS. Остановить — Ctrl+C в этом окне.
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=${PYTHON:-python3}; fi
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    echo "MINT: Python 3.10+ is required, found: $("$PY" --version 2>&1). See docs/INSTALL.md"
    echo "MINT: нужен Python 3.10 или новее. См. docs/ru/INSTALL.md"
    exit 1
fi
if ! "$PY" -c 'import streamlit' 2>/dev/null; then
    echo "MINT: packages are not installed — run ./install.sh first (docs/INSTALL.md)"
    echo "MINT: не установлены пакеты — запустите ./install.sh (docs/ru/INSTALL.md)"
    exit 1
fi
URL="http://localhost:8501"
echo "MINT: $URL   (Ctrl+C — stop / остановить)"
( sleep 4; { xdg-open "$URL" || open "$URL"; } >/dev/null 2>&1 || true ) &   # Linux: xdg-open, macOS: open
exec "$PY" -m streamlit run app.py "$@"

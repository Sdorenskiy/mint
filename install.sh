#!/bin/sh
# Install MINT into a .venv folder next to the program. No administrator rights needed.
# Установка MINT в папку .venv рядом с программой. Права администратора не нужны.
#   ./install.sh            — packages from the internet or a PyPI mirror (pip settings)
#                             пакеты из интернета или внутреннего зеркала PyPI
#   ./install.sh wheels     — offline, from a bundle in the "wheels" folder (docs/INSTALL.md)
#                             без интернета, из офлайн-комплекта (docs/ru/INSTALL.md)
# Another Python / другой Python:  PYTHON=/opt/python3.11/bin/python3 ./install.sh
cd "$(dirname "$0")" || exit 1
PY=${PYTHON:-python3}
WHEELS=$1
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    echo "Python 3.10+ is required, found: $("$PY" --version 2>&1). See docs/INSTALL.md"
    echo "Нужен Python 3.10 или новее. Astra Linux 1.7 поставляется с Python 3.7 — см. docs/ru/INSTALL.md"
    exit 1
fi
REQ=requirements.txt
[ -f requirements.lock ] && REQ=requirements.lock
echo "Python: $("$PY" --version 2>&1); requirements: $REQ${WHEELS:+; offline bundle: $WHEELS}"

if [ ! -x .venv/bin/python ]; then
    if ! "$PY" -m venv .venv >/dev/null 2>&1; then
        # Debian/Astra without python3-venv have no ensurepip: create the environment without pip
        # and take pip from the offline bundle.
        rm -rf .venv
        "$PY" -m venv --without-pip .venv || { echo "Cannot create .venv / не удалось создать .venv"; exit 1; }
        PIPWHL=$(ls "${WHEELS:-wheels}"/pip-*.whl 2>/dev/null | head -n 1)
        if [ -z "$PIPWHL" ]; then
            echo "No ensurepip (package python3-venv) and no pip-*.whl in ${WHEELS:-wheels}."
            echo "Ask an administrator to install python3-venv, or use an offline bundle (docs/INSTALL.md)."
            echo "Нет модуля ensurepip (пакет python3-venv) и нет pip-*.whl в папке ${WHEELS:-wheels}:"
            echo "попросите администратора установить python3-venv или возьмите офлайн-комплект (docs/ru/INSTALL.md)."
            exit 1
        fi
        .venv/bin/python "$PIPWHL/pip" install --no-index "$PIPWHL" || exit 1
    fi
fi

if [ -n "$WHEELS" ]; then
    .venv/bin/python -m pip install --no-index --find-links "$WHEELS" -r "$REQ" || exit 1
else
    .venv/bin/python -m pip install -r "$REQ" || exit 1
fi
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from the template — fill in the API addresses and key (docs/INSTALL.md)."
    echo "Создан .env из образца — впишите адреса и ключ (docs/ru/INSTALL.md)."
fi
echo
.venv/bin/python check_install.py --no-llm
echo
echo "Done. Start MINT: ./run_mint.sh   /   Готово. Запуск: ./run_mint.sh"

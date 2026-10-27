#!/bin/sh
# Install MINT into a .venv folder next to the program. No administrator rights needed.
# Установка MINT в папку .venv рядом с программой. Права администратора не нужны.
#   ./install.sh            — packages from the internet or a PyPI mirror (your pip settings)
#                             пакеты из интернета или внутреннего зеркала PyPI (ваши настройки pip)
#   ./install.sh wheels     — offline, from a bundle in the "wheels" folder (docs/INSTALL.md)
#                             без интернета, из офлайн-комплекта (docs/ru/INSTALL.md)
#   ./install.sh --clean    — recreate .venv from scratch / пересоздать .venv с нуля
# Another Python / другой Python:  PYTHON=/opt/python3.11/bin/python3 ./install.sh
#
# Versions: requirements.lock — the exact versions tested on GitHub (Ubuntu, Debian without python3-venv, Windows;
# Python 3.10–3.12). Версии: requirements.lock — точные версии, проверенные на GitHub.
cd "$(dirname "$0")" || exit 1
PY=${PYTHON:-python3}
WHEELS=""
CLEAN=""
for arg in "$@"; do
    case "$arg" in
        --clean) CLEAN=1 ;;
        *) WHEELS=$arg ;;
    esac
done
TMPW=""
cleanup() { [ -n "$TMPW" ] && rm -rf "$TMPW"; }
fail() {
    echo
    echo "MINT: $1"
    [ -n "$2" ] && echo "      $2"
    [ -n "$3" ] && echo "      $3"
    cleanup
    exit 1
}

# 1. Python 3.10+
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    fail "Python 3.10+ is required, found: $("$PY" --version 2>&1). See docs/INSTALL.md" \
         "Нужен Python 3.10 или новее, найден: $("$PY" --version 2>&1). Astra Linux 1.7 — см. docs/ru/INSTALL.md"
fi
REQ=requirements.txt
[ -f requirements.lock ] && REQ=requirements.lock
if [ -n "$WHEELS" ] && [ ! -d "$WHEELS" ]; then
    fail "Folder not found: $WHEELS / папка не найдена: $WHEELS"
fi
echo "Python: $("$PY" --version 2>&1); packages: $REQ${WHEELS:+; offline bundle: $WHEELS}"

# 2. .venv: recreate if asked, or if it is incomplete (no pip — e.g. after an interrupted first attempt)
#    .venv: пересоздаётся по --clean или если она неполная (без pip — например, после прерванной первой попытки)
[ -n "$CLEAN" ] && rm -rf .venv
if [ -d .venv ] && ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
    echo "Incomplete .venv (no pip) — recreating / неполная .venv (без pip) — создаю заново"
    rm -rf .venv
fi
if [ ! -x .venv/bin/python ]; then
    if ! "$PY" -m venv .venv >/dev/null 2>&1; then
        # Debian / Astra Linux without the python3-venv package: no ensurepip. The environment is created without
        # pip, and pip comes from the offline bundle or is downloaded by the system pip (your mirror settings).
        # Debian / Astra без пакета python3-venv: окружение создаётся без pip, pip — из офлайн-комплекта или его
        # скачивает системный pip (по вашим настройкам зеркала). Администратор не нужен.
        rm -rf .venv
        "$PY" -m venv --without-pip .venv || fail "Cannot create .venv / не удалось создать .venv"
        PIPWHL=$(ls "${WHEELS:-wheels}"/pip-*.whl 2>/dev/null | head -n 1)
        if [ -z "$PIPWHL" ] && [ -z "$WHEELS" ] && "$PY" -m pip --version >/dev/null 2>&1; then
            echo "No python3-venv: downloading pip with the system pip / нет python3-venv: скачиваю pip системным pip"
            TMPW=$(mktemp -d 2>/dev/null || mktemp -d -t mint_pip)
            "$PY" -m pip download -q pip -d "$TMPW" && PIPWHL=$(ls "$TMPW"/pip-*.whl 2>/dev/null | head -n 1)
        fi
        if [ -z "$PIPWHL" ]; then
            rm -rf .venv
            fail "No pip for the environment: no python3-venv, no system pip, no pip-*.whl in ${WHEELS:-wheels}." \
                 "Нет pip для окружения: нет пакета python3-venv, нет системного pip и нет pip-*.whl в ${WHEELS:-wheels}." \
                 "Что сделать: положите pip-*.whl в папку wheels (офлайн-комплект, docs/ru/INSTALL.md) или попросите администратора поставить python3-venv."
        fi
        .venv/bin/python "$PIPWHL/pip" install -q --no-index "$PIPWHL" \
            || { rm -rf .venv; fail "Cannot install pip into .venv / не удалось поставить pip в .venv"; }
    fi
fi

# 3. Packages: exact tested versions (requirements.lock); if the mirror lacks one of them — requirements.txt
#    Пакеты: точные проверенные версии (requirements.lock); если какой-то нет на зеркале — requirements.txt
if [ -n "$WHEELS" ]; then
    .venv/bin/python -m pip install --no-index --find-links "$WHEELS" -r "$REQ" \
        || fail "Packages were not installed from $WHEELS — see the pip messages above." \
                "Пакеты из $WHEELS не установлены — см. сообщения pip выше. Комплект собирают на той же ОС и том же Python."
elif ! .venv/bin/python -m pip install -r "$REQ"; then
    if [ "$REQ" = requirements.lock ]; then
        echo
        echo "Some exact versions are not available (mirror?) — trying requirements.txt"
        echo "Каких-то точных версий нет (зеркало?) — ставлю по requirements.txt"
        .venv/bin/python -m pip install -r requirements.txt \
            || fail "Packages were not installed — see the pip messages above." \
                    "Пакеты не установлены — см. сообщения pip выше. Проверьте доступ к пакетам: python3 -m pip download pip -d /tmp/x"
    else
        fail "Packages were not installed — see the pip messages above / пакеты не установлены — см. сообщения pip выше."
    fi
fi
cleanup
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from the template — fill in the API addresses and key (docs/INSTALL.md)."
    echo "Создан .env из образца — впишите адреса и ключ (docs/ru/INSTALL.md)."
fi
echo
echo "Installed / установлено: $(.venv/bin/python -m pip list 2>/dev/null | tail -n +3 | wc -l | tr -d ' ') packages, .venv $(du -sh .venv 2>/dev/null | cut -f1)"
echo
.venv/bin/python check_install.py --no-llm
echo
echo "Done. Start MINT: ./run_mint.sh   /   Готово. Запуск: ./run_mint.sh"

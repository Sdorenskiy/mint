#!/bin/sh
# Update MINT in place from a new version: a .zip archive or an unpacked folder. Your settings stay:
# .env, config.yaml, glossary.json, checklists.yaml, prompts.yaml, the .venv environment, the knowledge base and logs.
# Обновление MINT на месте из новой версии — архива .zip или распакованной папки. Ваши настройки остаются:
# .env, config.yaml, glossary.json, checklists.yaml, prompts.yaml, окружение .venv, база знаний и логи.
#   ./update.sh ~/Downloads/mint-21.1.zip      — from an archive / из архива
#   ./update.sh ~/Downloads/mint-21.1          — from a folder / из папки
#   ./update.sh mint-21.1.zip wheels_folder    — packages offline / пакеты без интернета (как install.sh wheels)
#   SKIP_INSTALL=1 ./update.sh mint-21.1.zip   — files only, no package install / только файлы, без установки пакетов
# Stop MINT first (Ctrl+C in its window). / Сначала остановите MINT (Ctrl+C в его окне).

# Весь скрипт — в фигурных скобках: оболочка читает его целиком до запуска, а сам update.sh заменяется новой
# версией по ходу работы (без скобок она дочитала бы уже новый файл с середины).
{
abs() { case "$1" in /*|"") echo "$1" ;; *) echo "$PWD/$1" ;; esac; }   # пути — от папки, где запущен скрипт
SRC=$(abs "$1")
WHEELS=$(abs "$2")
cd "$(dirname "$0")" || exit 1
HERE=$(pwd)
if [ -z "$SRC" ]; then
    echo "Usage / запуск:  ./update.sh path/to/mint-new.zip   (or a folder / или папка)"
    exit 1
fi
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=${PYTHON:-python3}; fi
TMP=""
cleanup() { [ -n "$TMP" ] && rm -rf "$TMP"; }
fail() { echo "$1"; cleanup; exit 1; }

if [ -f "$SRC" ]; then
    case "$SRC" in
        *.zip|*.ZIP) ;;
        *) fail "Not a .zip archive or folder: $SRC / это не архив .zip и не папка" ;;
    esac
    TMP=$(mktemp -d 2>/dev/null || mktemp -d -t mint_update) || fail "Cannot create a temporary folder"
    "$PY" -m zipfile -e "$SRC" "$TMP" 2>/dev/null || unzip -q "$SRC" -d "$TMP" \
        || fail "Cannot unpack / не удалось распаковать: $SRC"
    SRC=$TMP
fi
[ -d "$SRC" ] || fail "Not found / не найдено: $SRC"
if [ ! -f "$SRC/mint/version.py" ]; then           # архив с папкой верхнего уровня (mint-main/ …)
    for d in "$SRC"/*/; do
        if [ -f "${d}mint/version.py" ]; then SRC=${d%/}; break; fi
    done
fi
[ -f "$SRC/mint/version.py" ] || fail "No MINT in $1 (mint/version.py not found) / в $1 нет MINT"
SRC=$(cd "$SRC" && pwd)
[ "$SRC" = "$HERE" ] && fail "This is the same folder / это та же папка"

ver() { sed -n 's/^MINT_VERSION = "\(.*\)"/\1/p' "$1" 2>/dev/null; }
OLD=$(ver mint/version.py)
NEW=$(ver "$SRC/mint/version.py")
echo "MINT ${OLD:-?} -> $NEW"

# Папки с кодом заменяются целиком (удалённые в новой версии файлы не остаются), остальное копируется поверх
for d in mint tests tools docs static; do
    if [ -d "$SRC/$d" ]; then
        rm -rf "./$d" && cp -R "$SRC/$d" "./$d" || fail "Cannot copy / не удалось скопировать: $d"
    fi
done
for d in .streamlit eval; do                       # .streamlit/secrets.toml и свои вопросы eval/ — остаются
    if [ -d "$SRC/$d" ]; then
        mkdir -p "./$d" && cp -R "$SRC/$d/." "./$d/" || fail "Cannot copy / не удалось скопировать: $d"
    fi
done
for f in requirements.lock requirements-windows.lock; do     # старая фиксация версий не должна остаться
    [ -f "$SRC/$f" ] || rm -f "./$f"
done
for f in "$SRC"/* "$SRC"/.[!.]*; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    case "$name" in
        .env|config.yaml|glossary.json|checklists.yaml|prompts.yaml) continue ;;   # свои настройки не трогаем
    esac
    cp "$f" "./$name" || fail "Cannot copy / не удалось скопировать: $name"
done
chmod +x ./*.sh 2>/dev/null
echo "Files updated, your settings kept / файлы обновлены, ваши настройки сохранены."

if [ -n "$SKIP_INSTALL" ]; then
    cleanup
    echo "Packages not installed (SKIP_INSTALL). / Пакеты не устанавливались (SKIP_INSTALL)."
    exit 0
fi
if [ -z "$WHEELS" ] && [ -d "$SRC/wheels" ]; then
    WHEELS="$SRC/wheels"                           # новая версия с офлайн-комплектом — пакеты из него
fi
if [ -n "$WHEELS" ]; then ./install.sh "$WHEELS"; else ./install.sh; fi
code=$?
cleanup
[ $code -eq 0 ] && echo "MINT $NEW. Start / запуск: ./run_mint.sh"
exit $code
}

"""Для скриптов оценки и тестов: все имена пакета mint в одном пространстве имён.

    from mint.devtools import load_namespace
    app = load_namespace()
    app.search_parent_child(...)            # функция из любого модуля пакета
    app.get_query_embedding = cached_embed  # подмена во всех модулях, которые её импортировали

Обычному коду это не нужно — он импортирует функции из своих модулей напрямую.
"""
import importlib
import pkgutil


def _modules(include_ui):
    import mint
    mods = [mint]
    for info in pkgutil.walk_packages(mint.__path__, "mint."):
        if not include_ui and info.name.startswith("mint.ui"):
            continue
        mods.append(importlib.import_module(info.name))
    return mods


class Namespace:
    """Чтение — из первого модуля, где имя есть (импортированные имена — те же объекты). Присваивание
    меняет имя во всех модулях пакета, где оно есть: так подмена функции действует и там, где она была
    импортирована через `from .services import ...`."""

    def __init__(self, modules):
        object.__setattr__(self, "_modules", modules)

    def __getattr__(self, name):
        for mod in self._modules:
            values = vars(mod)
            if name in values:
                return values[name]
        raise AttributeError(f"в пакете mint нет имени {name!r}")

    def __setattr__(self, name, value):
        found = False
        for mod in self._modules:
            if name in vars(mod):
                setattr(mod, name, value)
                found = True
        if not found:
            raise AttributeError(f"в пакете mint нет имени {name!r}")

    def __dir__(self):
        names = set()
        for mod in self._modules:
            names.update(n for n in vars(mod) if not n.startswith("__"))
        return sorted(names)


def load_namespace(include_ui=False):
    """include_ui=True подключает и интерфейс (нужен Streamlit): app.main() рисует страницу."""
    return Namespace(_modules(include_ui))

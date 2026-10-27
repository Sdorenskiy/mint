"""Заглушка: входной документ Docling создаёт экземпляр бэкенда (как InputDocument._init_doc)."""


class InputDocument:
    def __init__(self, path_or_stream, format, backend, **_kw):
        self.valid = True
        self._backend = backend(self, path_or_stream=path_or_stream)

"""Заглушка бэкенда Word из Docling: тот же разбор, что у заглушки DocumentConverter (mint/parsing.py по умолчанию
разбирает .docx бэкендом напрямую)."""
from ..document_converter import _Doc


class MsWordDocumentBackend:
    def __init__(self, in_doc, path_or_stream):
        self.path = path_or_stream

    def is_valid(self):
        return True

    def convert(self):
        return _Doc(str(self.path))

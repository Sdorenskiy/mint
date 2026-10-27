"""Заглушка: форматы входных документов Docling."""
from enum import Enum


class InputFormat(str, Enum):
    DOCX = "docx"

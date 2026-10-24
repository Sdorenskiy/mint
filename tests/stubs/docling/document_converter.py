"""Заглушка Docling: читает .docx через python-docx и отдаёт объект с API, похожим на DoclingDocument."""
import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

class _Item:
    def __init__(self, label, text="", level=1, table=None):
        self.label = label
        self.text = text
        self.level = level
        self.prov = None
        self._table = table
    def export_to_markdown(self, doc=None):
        rows = [[c.text.strip() for c in r.cells] for r in self._table.rows]
        if not rows:
            return ""
        out = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * len(rows[0])]
        out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return "\n".join(out)
    def caption_text(self, doc):
        return ""

class _Doc:
    def __init__(self, path):
        d = docx.Document(path)
        self.items = []
        for child in d.element.body.iterchildren():
            tag = child.tag.split("}")[-1]
            if tag == "p":
                p = Paragraph(child, d)
                style = (p.style.name if p.style is not None else "") or ""
                text = p.text.strip()
                if not text:
                    continue
                if style.startswith("Heading"):
                    try:
                        lvl = int(style.split()[-1])
                    except ValueError:
                        lvl = 1
                    self.items.append(_Item("section_header", text, lvl))
                elif style == "Title":
                    self.items.append(_Item("title", text, 1))
                else:
                    self.items.append(_Item("text", text, 0))
            elif tag == "tbl":
                self.items.append(_Item("table", table=Table(child, d)))
        self.texts = [i for i in self.items if i.label != "table"]
        self.tables = [i for i in self.items if i.label == "table"]
    def iterate_items(self):
        for it in self.items:
            yield it, 0
    def export_to_markdown(self):
        out = []
        for it in self.items:
            if it.label == "table":
                out.append(it.export_to_markdown())
            elif it.label in ("section_header", "title"):
                out.append("#" * max(1, it.level) + " " + it.text)
            else:
                out.append(it.text)
        return "\n\n".join(out)

class _Result:
    def __init__(self, document):
        self.document = document

class DocumentConverter:
    created = 0
    def __init__(self):
        DocumentConverter.created += 1
    def convert(self, path):
        return _Result(_Doc(path))

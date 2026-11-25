"""Offline structural reference and progress regression tests."""
import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint.draft_progress import StageProgress, tracked
from mint.draft_references import ReferenceMap
from mint.draft_target_analysis import _map_sources
from mint.draft_word_references import word_reference_metadata
from mint.draft_pilot_report import target_registry_export


def test_progress():
    events = []
    for item in tracked(lambda *args: events.append(args), "phase", [1, 2, 3]):
        assert events[-1] == (("phase_total", 3) if item == 1 else ("phase_done", item - 1))
    assert events == [("phase_total", 3), ("phase_done", 1), ("phase_done", 2), ("phase_done", 3)]
    now = [0]
    p = StageProgress(lambda: now[0])
    assert p.update("extract_total", 10)
    assert not p.update("extract", 1)  # started is not completed
    assert not p.update("extract_done", 1)
    now[0] = 2
    assert p.update("extract_done", 3)
    assert p.snapshot()[0]["eta"] == 14 / 3
    p.update("extract_cached", 1)
    assert p.snapshot()[0]["eta"] is None
    p.update("extract_failed", 1)
    assert p.failed == 1
    now[0] = 3
    assert p.update("extract_done", 10)
    now[0] = 5
    assert p.snapshot()[0]["elapsed"] == 3
    p.update("empty_total", 0)
    now[0] = 20
    assert p.snapshot()[1]["elapsed"] == 0
    try:
        for item in tracked(lambda *args: events.append(args), "error", [1]):
            raise RuntimeError("interrupted")
    except RuntimeError:
        pass
    assert events[-1] == ("error_total", 1)


def make_map(docs, metadata=None):
    spans, _ = _map_sources(docs, {})
    return ReferenceMap(docs, spans, word_metadata=metadata), spans


def test_references():
    docs = [
        ("need.md", "# 5 Duties\nSee clause 3.1.1.\nСм. п. 3.1.2–3.1.3.\n"
         "См. раздел 2 документа «design.md».\nСм. п. 9.\nСм. п. 2 документа «not-selected.md».\n"
         "# 3 Functions\n## 3.1 Flow\n### 3.1.1 Format\nСм. таблицу 5.\n"
         "### 3.1.2 Errors\nError details.\n### 3.1.3 Conditions\nСм. п. 5.\n"
         "# 4 Data\nТаблица 5 — fields\n\n| Field | Unit |\n| --- | --- |\n| fictional | count |\n"
         "# Приложение А\nExtra material.\n"),
        ("design.md", "# 2 Current\nCurrent details.\n# 3.1.1 Other\nNot same source."),
    ]
    refs, spans = make_map(docs)
    root = next(sid for sid, span in spans.items() if span["section"] == "5 Duties")
    rows, gaps = refs.related([root], quote="See clause 3.1.1.", budget=10000)
    assert len(rows) == 2, rows
    assert rows[0]["section"].endswith("3.1.1 Format")
    assert "fictional" in rows[1]["quote"]
    assert rows[1]["path"] == [root, rows[0]["id"], rows[1]["id"]]
    assert not gaps, gaps
    rows, gaps = refs.related([root], quote="См. п. 3.1.2–3.1.3.", budget=10000)
    assert len(rows) == 2 and gaps.get("cycle"), (rows, gaps)
    rows, gaps = refs.related([root], quote="См. раздел 2 документа «design.md».")
    assert len(rows) == 1 and rows[0]["source"] == "design.md" and not gaps
    assert refs.related([root], quote="См. п. 9.")[1] == {"missing": 1}
    assert refs.related([root], quote="См. п. 2 документа «not-selected.md».")[1] == {"outside_scope": 1}
    assert refs.related([root], quote="См. п. 3.1.1 ФТ.")[1] == {"unidentified_document": 1}
    assert refs.related([root], quote="См. п. 3.1.1.", budget=0)[1] == {"budget_limit": 1}
    assert refs.related([root], quote="См. п. 3.1.1.", depth=0)[1] == {"depth_limit": 1}
    assert refs.related([root], quote="См. приложение А.")[0][0]["quote"] == "Extra material."
    assert refs.related([root], quote="См. п. 3.1.1–3.2.1.")[1] == {"unsupported_range": 1}
    dup, spans = make_map([("dup.md", "# 5 Ref\nСм. п. 1.\n# 1 First\nFirst\n# 1 Other\nOther")])
    root = next(iter(spans))
    assert dup.related([root])[1] == {"ambiguous": 1}


def test_word_numbering_and_bookmark():
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    doc = f'<w:document xmlns:w="{ns}"><w:body>' + """
      <w:p><w:pPr><w:pStyle w:val="Heading1"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>
      <w:r><w:t>Functions</w:t></w:r></w:p>
      <w:p><w:pPr><w:pStyle w:val="Heading2"/><w:numPr><w:ilvl w:val="1"/><w:numId w:val="1"/></w:numPr></w:pPr>
      <w:bookmarkStart w:id="1" w:name="ref_format"/><w:r><w:t>Format</w:t></w:r><w:bookmarkEnd w:id="1"/></w:p>
      <w:p><w:r><w:t>See format</w:t></w:r><w:fldSimple w:instr="REF ref_format"><w:r><w:t> now</w:t></w:r></w:fldSimple></w:p>
      </w:body></w:document>"""
    styles = f'<w:styles xmlns:w="{ns}"><w:style w:styleId="Heading1"><w:name w:val="heading 1"/></w:style><w:style w:styleId="Heading2"><w:name w:val="heading 2"/></w:style></w:styles>'
    numbering = f'<w:numbering xmlns:w="{ns}">' + """
      <w:abstractNum w:abstractNumId="0">
      <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl>
      <w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1.%2"/></w:lvl>
      </w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>"""
    buf = BytesIO()
    with ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/numbering.xml", numbering)
    meta = word_reference_metadata(buf.getvalue())
    assert meta["numbers"] == {"Functions": "1", "Format": "1.1"}, meta
    assert meta["bookmarks"] == {"ref_format": "Format"}
    assert meta["fields"] == [{"text": "See format now", "bookmark": "ref_format"}]
    refs, spans = make_map([("a.docx", "# Duties\nСм. п. 1.1.\nSee format now\n# Functions\n## Format\nOriginal data.")],
                           {"a.docx": meta})
    root = next(iter(spans))
    assert refs.related([root], quote="См. п. 1.1.")[0][0]["quote"] == "Original data."
    assert refs.related([root], quote="See format now")[0][0]["quote"] == "Original data."


def test_sanitized_export():
    result = {"diagnostics": {"references": {"resolved": 3, "secret filename": 20},
                              "reference_gaps": {"missing": 2, "secret text": 1}}}
    safe = target_registry_export({}, result)
    assert safe["diagnostics"]["references"]["resolved"] == 3
    assert safe["diagnostics"]["reference_gaps"]["missing"] == 2
    assert "secret" not in repr(safe)


if __name__ == "__main__":
    test_progress()
    test_references()
    test_word_numbering_and_bookmark()
    test_sanitized_export()
    print("OK: progress counters, scoped references, nested traversal, Word addresses, safe export")

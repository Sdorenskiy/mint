"""Conservative OOXML address metadata for original Word sources.

Only standard decimal heading numbering is reconstructed. Unsupported list
formats/restarts are not guessed; literal Markdown addresses still work.
"""
from collections import Counter, defaultdict
from io import BytesIO
from zipfile import ZipFile, BadZipFile
import re
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _child(node, path):
    if node is None:
        return None
    return node.find("/".join(W + p for p in path.split("/")))


def _val(node, path):
    child = _child(node, path)
    return child.get(W + "val") if child is not None else None


def _text(node):
    return " ".join("".join(t.text or "" for t in node.iter(W + "t")).split())


def word_reference_metadata(data):
    """Extract addresses and field references without changing document text."""
    empty = {"numbers": {}, "bookmarks": {}, "fields": []}
    try:
        with ZipFile(BytesIO(data)) as z:
            doc = ET.fromstring(z.read("word/document.xml"))
            styles = ET.fromstring(z.read("word/styles.xml")) if "word/styles.xml" in z.namelist() else ET.Element("styles")
            nums = ET.fromstring(z.read("word/numbering.xml")) if "word/numbering.xml" in z.namelist() else ET.Element("numbering")
    except (BadZipFile, KeyError, ET.ParseError, OSError):
        return empty
    style_map = {s.get(W + "styleId"): s for s in styles.findall(W + "style")}
    abstracts = {a.get(W + "abstractNumId"): a for a in nums.findall(W + "abstractNum")}
    instances = {n.get(W + "numId"): n for n in nums.findall(W + "num")}
    counters, numbers, bookmarks, fields = defaultdict(dict), defaultdict(list), defaultdict(list), []
    title_counts = Counter()
    unsupported = set()
    for p in doc.iter(W + "p"):
        props = _child(p, "pPr")
        style = _val(props, "pStyle")
        chain = [props]
        visited = set()
        heading = False
        while style in style_map and style not in visited:
            visited.add(style)
            s = style_map[style]
            chain.append(_child(s, "pPr"))
            name = (_val(s, "name") or style).casefold()
            heading |= bool(re.match(r"^(heading|заголовок)\s*\d+$", name))
            style = _val(s, "basedOn")

        def inherited(path):
            for pr in chain:
                v = _val(pr, path)
                if v is not None:
                    return v
            return None

        outline = inherited("outlineLvl")
        heading |= outline is not None and outline.isdecimal() and int(outline) < 9
        title = _text(p)
        if heading and title:
            title_counts[title] += 1
            for bookmark in p.iter(W + "bookmarkStart"):
                name = bookmark.get(W + "name")
                if name:
                    bookmarks[name].append(title)
        instructions = [n.text or "" for n in p.iter(W + "instrText")]
        instructions += [n.get(W + "instr", "") for n in p.iter(W + "fldSimple")]
        for match in re.finditer(r'\b(?:REF|PAGEREF)\s+("?)([\w.-]+)\1', "".join(instructions), re.I):
            if title and not match[0].upper().startswith("PAGEREF"):
                fields.append({"text": title, "bookmark": match[2]})
        for link in p.iter(W + "hyperlink"):
            anchor = link.get(W + "anchor")
            if anchor and title:
                fields.append({"text": title, "bookmark": anchor})
        num_id = inherited("numPr/numId")
        level = inherited("numPr/ilvl")
        if num_id not in instances or num_id in unsupported:
            continue
        instance = instances[num_id]
        abstract = abstracts.get(_val(instance, "abstractNumId"))
        if abstract is None or instance.findall(W + "lvlOverride"):
            unsupported.add(num_id)
            continue
        levels = {n.get(W + "ilvl"): n for n in abstract.findall(W + "lvl")}
        if level is None:
            # Use a unique style-linked level if defined, otherwise the
            # explicitly inherited outline level. No positional guesses.
            linked = [k for k, n in levels.items() if _val(n, "pStyle") in visited]
            level = linked[0] if len(linked) == 1 else outline
        if level not in levels or not level.isdecimal():
            unsupported.add(num_id)
            continue
        i = int(level)
        lvl = levels[level]
        pattern = _val(lvl, "lvlText") or ""
        start = _val(lvl, "start") or "1"
        if (_val(lvl, "numFmt") != "decimal" or _child(lvl, "lvlRestart") is not None
                or not start.isdecimal() or not re.fullmatch(r"%[1-9](?:\.%[1-9])*[.)]?", pattern)):
            unsupported.add(num_id)
            continue
        refs = [int(n) - 1 for n in re.findall(r"%([1-9])", pattern)]
        if refs != list(range(i + 1)):
            unsupported.add(num_id)
            continue
        counts = counters[num_id]
        counts[i] = counts.get(i, int(start) - 1) + 1
        for k in list(counts):
            if k > i:
                del counts[k]
        if heading and title and all(k in counts for k in refs):
            numbers[title].append((num_id, ".".join(str(counts[k]) for k in refs)))
    return {"numbers": {title: values[0][1] for title, values in numbers.items()
                        if len(values) == title_counts[title] == 1 and values[0][0] not in unsupported},
            "bookmarks": {k: v[0] for k, v in bookmarks.items() if len(v) == 1 and title_counts[v[0]] == 1},
            "fields": fields}

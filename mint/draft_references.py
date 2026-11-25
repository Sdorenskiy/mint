"""Deterministic cross-references over selected original Markdown spans.

No LLM, external document lookup or additional search index. A numbered address
is accepted only if it maps to one original structural occurrence.
"""
from collections import Counter, defaultdict, deque
from pathlib import PurePosixPath
import re

from .draft_progress import tracked

_NUMBER = r"\d+(?:\.\d+)*"
_LIST = rf"{_NUMBER}(?:\s*(?:[,;]|и\b|and\b|[–—-])\s*{_NUMBER})*"
_SECTION = re.compile(rf"(?<!\w)(?:пп?\.|пункт(?:а|е|у|ом|ы|ов|ам)?\b|подпункт(?:а|е|у|ом|ы|ов)?\b|раздел(?:а|е|у|ом|ы|ов)?\b|sections?\b|clauses?\b|paragraphs?\b|secs?\.)\s*№?\s*(?P<address>{_LIST})(?![\d.])", re.I)
_TABLE = re.compile(r"(?<!\w)(?:таблиц(?:а|е|ы|у|ей|ам|ах)?\b|табл\.|tables?\b)\s*№?\s*(?P<address>\d+(?:\.\d+)*)(?![\d.])", re.I)
_APPENDIX = re.compile(r"(?<!\w)(?:приложени(?:е|я|ю|и|ем|ях)\b|appendix\b|annex\b)\s*№?\s*(?P<address>[А-ЯA-Z]|\d+)(?!\w)", re.I)
_HEADING = re.compile(rf"^\s*({_NUMBER})[.)]?(?:\s+|$)")
_APPENDIX_TITLE = re.compile(r"^\s*(?:приложение|appendix|annex)\s+([А-ЯA-Z]|\d+)(?!\w)", re.I)
_TABLE_TITLE = re.compile(rf"^\s*(?:таблица|table)\s*№?\s*({_NUMBER})(?![\d.])", re.I)
_MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_TOC = re.compile(r"^(?:содержание|оглавление|contents|table of contents)$", re.I)
_DOC = re.compile(r'^\s*(?:настоящего\s+документа|данного\s+документа|this\s+document)\b', re.I)
_NAMED_DOC = re.compile(r'^\s*(?:(?:документа|документе|файла|of|in)\s+)?[«“"]([^»”"]+)[»”"]', re.I)
_OTHER_DOC = re.compile(r"^\s*(?:документа\b|документе\b|файла\b|файле\b|ФТ\b|ТЗ\b|ВАР\b|of\b|in\s+(?:the\s+)?document\b)", re.I)
_MAX_RANGE = 25


def _norm(value):
    return " ".join(str(value).split())


def _address(value):
    return value.strip().upper()


def _file_key(value):
    return value.replace("\\", "/").casefold().strip()


def _expand(value):
    """Bounded sibling ranges, never guess a cross-level interval."""
    tokens = re.findall(rf"{_NUMBER}|[–—-]", value)
    result = []
    i = 0
    while i < len(tokens):
        a = tokens[i]
        if i + 2 < len(tokens) and tokens[i + 1] in {"–", "—", "-"}:
            b = tokens[i + 2]
            left, right = a.split("."), b.split(".")
            if left[:-1] != right[:-1] or not 0 <= int(right[-1]) - int(left[-1]) < _MAX_RANGE:
                return [], "unsupported_range"
            prefix = ".".join(left[:-1])
            result.extend((prefix + "." if prefix else "") + str(n)
                          for n in range(int(left[-1]), int(right[-1]) + 1))
            i += 3
        else:
            result.append(a)
            i += 1
    return list(dict.fromkeys(result)), ""


class ReferenceMap:
    def __init__(self, documents, spans, emit=None, word_metadata=None):
        self.spans = spans
        self.counts = Counter()
        self.edges = {}
        self.targets = defaultdict(list)
        self.positions = {(s["source"], s["fragment"]): sid for sid, s in spans.items()}
        self.by_source = defaultdict(list)
        self.names = defaultdict(set)
        for name, _ in documents:
            base = PurePosixPath(name.replace("\\", "/"))
            for alias in (name, base.name, base.stem):
                self.names[_file_key(alias)].add(name)
        for sid, span in spans.items():
            self.by_source[span["source"]].append(sid)
        for name, markdown in documents:
            self._index(name, markdown, (word_metadata or {}).get(name, {}))
        for sid in tracked(emit or (lambda *_: None), "reference_map", spans):
            span = spans[sid]
            self.edges[sid] = self._resolve(span["source"], span["text"])
            metadata = (word_metadata or {}).get(span["source"], {})
            for field in metadata.get("fields", []):
                if field["text"] and _norm(field["text"]) in _norm(span["text"]):
                    self.edges[sid].append(self._lookup(span["source"], "bookmark", field["bookmark"],
                                                        "REF " + field["bookmark"]))
            self.counts.update(edge["status"] for edge in self.edges[sid])

    def _add(self, source, kind, address, ids):
        # Distinct occurrences stay distinct even if malformed duplicate titles
        # happen to have the same path in the current span representation.
        self.targets[(source, kind, _address(address))].append(tuple(dict.fromkeys(ids)))

    def _index(self, source, markdown, metadata):
        ids = self.by_source[source]
        stack = []
        occurrences = []
        titles = defaultdict(list)
        for line in markdown.splitlines():
            match = _MARKDOWN_HEADING.match(line)
            if not match:
                continue
            level, title = len(match[1]), match[2].strip()
            stack = [(n, t) for n, t in stack if n < level]
            stack.append((level, title))
            path = " › ".join(t for _, t in stack)
            if any(_TOC.fullmatch(t) for _, t in stack):
                continue
            occurrences.append((title, path))
            titles[_norm(title)].append(path)
        for title, path in occurrences:
            children = [sid for sid in ids if self.spans[sid]["section"] == path
                        or self.spans[sid]["section"].startswith(path + " › ")]
            number = _HEADING.match(title)
            appendix = _APPENDIX_TITLE.match(title)
            if number:
                self._add(source, "section", number[1], children)
            elif len(titles[_norm(title)]) == 1:
                # Only a uniquely matched original Word heading may contribute
                # a numbering alias. No guess based on heading order.
                alias = metadata.get("numbers", {}).get(_norm(title))
                if alias:
                    self._add(source, "section", alias, children)
            if appendix:
                self._add(source, "appendix", appendix[1], children)
        for bookmark, title in metadata.get("bookmarks", {}).items():
            paths = titles.get(_norm(title), [])
            if len(paths) == 1:
                path = paths[0]
                self._add(source, "bookmark", bookmark,
                          [sid for sid in ids if self.spans[sid]["section"] == path
                           or self.spans[sid]["section"].startswith(path + " › ")])
        # Require an actual caption immediately before a Markdown table. Match
        # complete rows in original spans, never an unrelated table number.
        lines = markdown.splitlines()
        for i, line in enumerate(lines):
            caption = _TABLE_TITLE.match(line.strip("* "))
            if not caption:
                continue
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            rows = []
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append(_norm(lines[j]))
                j += 1
            if not rows:
                continue
            # At least header + separator. Require every substantive row to
            # map to exactly one span or an overlap of adjacent spans.
            if len(rows) < 2 or not re.fullmatch(r"[\s|:\-]+", rows[1]):
                continue
            selected = set()
            valid = True
            for row in rows[:1] + rows[2:]:
                matched = [sid for sid in ids if row in {_norm(s) for s in self.spans[sid]["text"].splitlines()}]
                if not matched or len({self.spans[sid]["section_id"] for sid in matched}) != 1:
                    valid = False
                    break
                fragments = sorted(self.spans[sid]["fragment"] for sid in matched)
                if fragments[-1] - fragments[0] > 1:
                    valid = False
                    break
                selected.update(matched)
            self._add(source, "table", caption[1], [sid for sid in ids if sid in selected] if valid else [])

    def _lookup(self, source, kind, address, raw):
        candidates = self.targets.get((source, kind, _address(address)), [])
        status = "ambiguous" if len(candidates) > 1 else "resolved" if candidates and candidates[0] else "missing"
        return {"status": status, "kind": kind, "address": address, "reference": raw,
                "targets": list(candidates[0]) if status == "resolved" else []}

    def _resolve(self, source, text):
        edges = []
        for kind, pattern in (("section", _SECTION), ("table", _TABLE), ("appendix", _APPENDIX)):
            for match in pattern.finditer(text):
                # Caption and list-entry lines are targets, not references.
                before = text[text.rfind("\n", 0, match.start()) + 1:match.start()].strip("* ")
                tail = text[match.end():]
                if kind in {"table", "appendix"} and not before and not _OTHER_DOC.match(tail):
                    if re.match(r"\s*(?:[.:–—-]|$|\n)", tail):
                        continue
                name, destination = _NAMED_DOC.match(tail), source
                if _DOC.match(tail):
                    pass
                elif name:
                    matches = self.names.get(_file_key(name[1]), set())
                    if len(matches) != 1:
                        edges.append({"status": "ambiguous" if matches else "outside_scope",
                                      "kind": kind, "address": match["address"], "reference": match[0] + name[0],
                                      "targets": []})
                        continue
                    destination = next(iter(matches))
                elif _OTHER_DOC.match(tail):
                    edges.append({"status": "unidentified_document", "kind": kind,
                                  "address": match["address"], "reference": match[0], "targets": []})
                    continue
                values, error = _expand(match["address"]) if kind == "section" else ([match["address"]], "")
                if error:
                    edges.append({"status": error, "kind": kind, "address": match["address"],
                                  "reference": match[0], "targets": []})
                else:
                    edges.extend(self._lookup(destination, kind, address, match[0]) for address in values)
        return edges

    def related(self, roots, *, quote=None, budget=6000, depth=4, max_spans=24):
        """BFS over original spans with paths, bounded context and explicit gaps.
        Root edges can be limited to an exact extracted quote, not all duties in
        the same fragment. Descendant edges may provide further context only.
        """
        queue = deque((sid, (sid,), 0, None) for sid in dict.fromkeys(roots) if sid in self.spans)
        seen = set(roots)
        result, gaps, spent = [], Counter(), 0
        while queue:
            sid, path, level, edge_ref = queue.popleft()
            if level:
                span = self.spans[sid]
                cost = len(span["text"]) + len(span["section"]) + len(span["source"]) + 200
                if len(result) >= max_spans or spent + cost > budget:
                    gaps["budget_limit"] += 1
                    continue
                result.append({"id": sid, "source": span["source"], "section": span["section"],
                               "quote": span["text"], "path": list(path), "reference": edge_ref})
                spent += cost
            edges = self.edges.get(sid, [])
            if level == 0 and quote is not None:
                # Resolve literal references from this obligation, not neighbouring
                # text. Word REF metadata is usable when its rendered field is present.
                edges = self._resolve(self.spans[sid]["source"], quote)
            for edge in edges:
                if edge["status"] != "resolved":
                    gaps[edge["status"]] += 1
                    continue
                for target in edge["targets"]:
                    if target in path:
                        gaps["cycle"] += 1
                        continue
                    if target in seen:
                        continue
                    if level >= depth:
                        gaps["depth_limit"] += 1
                        continue
                    seen.add(target)
                    queue.append((target, path + (target,), level + 1, edge["reference"]))
        return result, dict(gaps)

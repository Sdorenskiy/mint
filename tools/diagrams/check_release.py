"""Block a GitHub release if its architecture/engineering diagrams or previews are stale.

Runs without external libraries. Regenerate docs with tools/diagrams before a new release.
It verifies bilingual sources and PNG previews against the exact scene and release tag.
"""
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIAGRAMS = ROOT / "tools" / "diagrams"
MANIFEST = ROOT / "release" / "manifest.json"
NAMES = ("MINT_architecture", "MINT_engineering")
GENERATORS = ("build_architecture.py", "build_engineering.py")
PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def generator_tag(filename):
    path = Path(filename) if Path(filename).is_absolute() else DIAGRAMS / filename
    code = ast.parse(path.read_text(encoding="utf-8"))
    for node in code.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(n, ast.Name) and n.id in {"DIAGRAM_RELEASE", "MINT_VERSION"} for n in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(f"Missing DIAGRAM_RELEASE in {filename}")


def scene_signature(scene):
    # Element timestamps change on every build even if the content is identical.
    elements = [{key: value for key, value in item.items() if key != "updated"}
                for item in scene["elements"]]
    body = json.dumps(elements, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def validate():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tag = data["tag"]
    errors = []
    if generator_tag(ROOT / "mint" / "version.py") != tag.removeprefix("v"):
        errors.append("mint/version.py: application version differs from release tag")
    for filename in GENERATORS:
        current = generator_tag(filename)
        if current != tag:
            errors.append(f"{filename}: version {current!r} differs from release {tag!r}")
    for lang, folder in (("en", ROOT / "docs"), ("ru", ROOT / "docs" / "ru")):
        for name in NAMES:
            stem = folder / name
            scene_file = stem.with_suffix(".excalidraw")
            md_file = folder / (name + ".excalidraw.md")
            png_file = folder / (name + "_preview.png")
            try:
                scene = json.loads(scene_file.read_text(encoding="utf-8"))
                labels = [element["text"] for element in scene["elements"]
                          if element["type"] == "text" and not element.get("isDeleted")]
                if not any(f"Mint {tag}" in line for line in labels):
                    errors.append(f"{scene_file}: release marker Mint {tag} missing")
                word = "Word drafting" if lang == "en" else "Формирование Word"
                evidence = "evidence" if lang == "en" else "основани"
                if not any(word in line for line in labels):
                    errors.append(f"{scene_file}: Word draft stage missing")
                if not any(evidence.casefold() in line.casefold() for line in labels):
                    errors.append(f"{scene_file}: source traceability stage missing")
                md = md_file.read_text(encoding="utf-8")
                if "## Drawing" not in md or f"Mint {tag}" not in md:
                    errors.append(f"{md_file}: editable Obsidian diagram is stale")
                png = png_file.read_bytes()
                expected = (f"Mint {tag} scene sha256=" + scene_signature(scene)).encode("utf-8")
                if not png.startswith(PNG_HEADER) or b"tEXtDescription\x00" + expected not in png:
                    errors.append(f"{png_file}: preview does not match scene/tag; rerender")
            except (ValueError, OSError, KeyError, TypeError) as exc:
                errors.append(f"{stem}: {exc}")
    if errors:
        print("Diagram release guard FAILED:")
        for error in errors:
            print(" - " + error)
        return False
    print(f"Release diagrams verified: {tag}, two diagrams, RU/EN sources and previews.")
    return True


if __name__ == "__main__":
    sys.exit(0 if validate() else 1)

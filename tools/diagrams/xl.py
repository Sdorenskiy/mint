"""Общие функции для генерации сцен Excalidraw."""
import json
import random
import time

from lang import T

RND = random.Random(20261010)
B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
NOW = int(time.time() * 1000)
FONT = 5            # Excalifont, как в образце
CHAR_W = 0.6        # оценка ширины символа (доля размера шрифта) для переноса строк
LINE_H = 1.25
PAD = 12

elements = []
_ids = set()


def new_id():
    while True:
        i = "".join(RND.choice(B62) for _ in range(8))
        if i not in _ids:
            _ids.add(i)
            return i


def frac_index(n):
    return "a" + B62[n] if n < 62 else "b" + B62[n // 62] + B62[n % 62]


def base(kind, x, y, w, h, stroke, bg="transparent", dashed=False, rounded=True, fill="solid", width=2):
    return {
        "id": new_id(), "type": kind, "x": round(x, 2), "y": round(y, 2), "width": round(w, 2), "height": round(h, 2),
        "angle": 0, "strokeColor": stroke, "backgroundColor": bg, "fillStyle": fill, "strokeWidth": width,
        "strokeStyle": "dashed" if dashed else "solid", "roughness": 1, "opacity": 100, "groupIds": [],
        "frameId": None, "roundness": {"type": 3} if rounded else None, "seed": RND.randint(1, 2 ** 31 - 1),
        "version": 1, "versionNonce": RND.randint(1, 2 ** 31 - 1), "isDeleted": False, "boundElements": [],
        "updated": NOW, "link": None, "locked": False,
    }


def wrap(text, max_chars):
    text = T(text)
    out = []
    for para in text.split("\n"):
        if not para.strip():
            out.append("")
            continue
        indent = len(para) - len(para.lstrip())
        words, line = para.split(" "), ""
        for wd in words:
            cand = (line + " " + wd) if line else wd
            if len(cand) <= max_chars or not line:
                line = cand
            else:
                out.append(line)
                line = " " * (indent + 3 if para.lstrip()[:2] in ("• ", "- ") or para.lstrip()[:1].isdigit() else indent) + wd
        out.append(line)
    return "\n".join(out)


def text_size(text, size):
    text = T(text)
    lines = text.split("\n")
    return max(len(l) for l in lines) * size * CHAR_W, len(lines) * size * LINE_H


def text_el(x, y, text, size=20, color="#1e1e1e", align="left", valign="top", container=None, w=None, h=None):
    text = T(text)
    tw, th = text_size(text, size)
    el = base("text", x, y, w if w is not None else tw, h if h is not None else th, color, rounded=False)
    el.update({"text": text, "fontSize": size, "fontFamily": FONT, "textAlign": align, "verticalAlign": valign,
               "containerId": container["id"] if container else None, "originalText": text, "autoResize": True,
               "lineHeight": LINE_H})
    elements.append(el)
    if container is not None:
        container["boundElements"].append({"type": "text", "id": el["id"]})
    return el


def box(x, y, w, h, text="", stroke="#1e1e1e", bg="transparent", size=18, align="center", valign="middle",
        dashed=False, text_color=None, kind="rectangle"):
    el = base(kind, x, y, w, h, stroke, bg, dashed=dashed)
    elements.append(el)
    if text:
        wrapped = wrap(text, max(8, int((w - 2 * PAD) / (size * CHAR_W))))
        tw, th = text_size(wrapped, size)
        tw = min(tw, w - 2 * PAD)
        tx = x + (w - tw) / 2 if align == "center" else x + PAD
        ty = y + (h - th) / 2 if valign == "middle" else y + PAD
        text_el(tx, ty, wrapped, size, text_color or stroke, align, valign, container=el, w=tw, h=th)
    return el


def needed_height(text, w, size, extra=2 * PAD):
    wrapped = wrap(text, max(8, int((w - 2 * PAD) / (size * CHAR_W))))
    return text_size(wrapped, size)[1] + extra


def anchor(el, side, t=0.5):
    """Точка на стороне элемента: side ∈ top/bottom/left/right, t — доля вдоль стороны."""
    x, y, w, h = el["x"], el["y"], el["width"], el["height"]
    return {"top": (x + w * t, y), "bottom": (x + w * t, y + h), "left": (x, y + h * t),
            "right": (x + w, y + h * t)}[side]


def _binding(el, px, py):
    fx = (px - el["x"]) / el["width"] if el["width"] else 0.5
    fy = (py - el["y"]) / el["height"] if el["height"] else 0.5
    return {"elementId": el["id"], "focus": 0, "gap": 8, "mode": "orbit",
            "fixedPoint": [round(min(1, max(0, fx)), 4), round(min(1, max(0, fy)), 4)]}


def arrow(a, b, color, label=None, both=False, dashed=False, a_side="bottom", b_side="top", a_t=0.5, b_t=0.5,
          via=None, label_size=16):
    sx, sy = anchor(a, a_side, a_t)
    ex, ey = anchor(b, b_side, b_t)
    gap = 6
    dirs = {"top": (0, -1), "bottom": (0, 1), "left": (-1, 0), "right": (1, 0)}
    sx += dirs[a_side][0] * gap; sy += dirs[a_side][1] * gap
    ex += dirs[b_side][0] * gap; ey += dirs[b_side][1] * gap
    pts = [(sx, sy)] + list(via or []) + [(ex, ey)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    el = base("arrow", sx, sy, max(xs) - min(xs), max(ys) - min(ys), color, dashed=dashed, rounded=False)
    el["roundness"] = {"type": 2}
    el.update({"points": [[round(px - sx, 2), round(py - sy, 2)] for px, py in pts], "lastCommittedPoint": None,
               "startBinding": _binding(a, *anchor(a, a_side, a_t)), "endBinding": _binding(b, *anchor(b, b_side, b_t)),
               "startArrowhead": "arrow" if both else None, "endArrowhead": "arrow", "elbowed": False})
    elements.append(el)
    a["boundElements"].append({"type": "arrow", "id": el["id"]})
    b["boundElements"].append({"type": "arrow", "id": el["id"]})
    if label:
        mid = len(pts) // 2
        (x1, y1), (x2, y2) = pts[mid - 1], pts[mid]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        tw, th = text_size(label, label_size)
        text_el(mx - tw / 2, my - th / 2, label, label_size, color, "center", "middle", container=el, w=tw, h=th)
    return el




def save(scene_elements, out, app_state=None):
    for n, el in enumerate(scene_elements):
        el["index"] = frac_index(n)
    scene = {"type": "excalidraw", "version": 2, "source": "https://excalidraw.com", "elements": scene_elements,
             "appState": app_state or {"gridSize": 20, "viewBackgroundColor": "#ffffff", "currentItemFontFamily": FONT,
                                       "currentItemRoughness": 1},
             "files": {}}
    with open(out + ".excalidraw", "w", encoding="utf-8") as f:
        json.dump(scene, f, ensure_ascii=False, indent=2)
    texts = [e for e in scene_elements if e["type"] == "text"]
    md = ["---", "", "excalidraw-plugin: parsed", "tags: [excalidraw]", "", "---",
          "==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠== You can decompress Drawing "
          "data with the command palette: 'Decompress current Excalidraw file'. For more info check in plugin settings "
          "under 'Saving'", "", "", "# Excalidraw Data", "", "## Text Elements"]
    for t in texts:
        md += [f"{t['text']} ^{t['id']}", ""]
    md += ["%%", "## Drawing", "```json", json.dumps(scene, ensure_ascii=False, indent=2), "```", "%%"]
    with open(out + ".excalidraw.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    return scene

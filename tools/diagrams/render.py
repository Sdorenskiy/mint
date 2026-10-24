"""Предпросмотр сцены Excalidraw в PNG (docs/*_preview.png и проверка раскладки: наложения, переполнение текста).

Запуск:  python render.py <схема.excalidraw> <картинка.png> [масштаб]
"""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Ellipse, Polygon

FONT_W = 0.55   # средняя ширина символа Excalifont относительно размера шрифта (оценка)


def render(scene, out, scale=0.5):
    els = [e for e in scene["elements"] if not e.get("isDeleted")]
    xs, ys = [], []
    for e in els:
        if e["type"] in ("arrow", "line"):   # у стрелок x, y — первая точка, остальные точки могут быть левее
            xs += [e["x"] + p[0] for p in e["points"]]
            ys += [e["y"] + p[1] for p in e["points"]]
        else:
            xs += [e["x"], e["x"] + e.get("width", 0)]
            ys += [e["y"], e["y"] + e.get("height", 0)]
    x0, x1, y0, y1 = min(xs) - 40, max(xs) + 40, min(ys) - 40, max(ys) + 40
    fig = plt.figure(figsize=((x1 - x0) * scale / 100, (y1 - y0) * scale / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(x0, x1)
    ax.set_ylim(y1, y0)
    ax.axis("off")
    for e in els:
        sc = e.get("strokeColor", "#000")
        bg = e.get("backgroundColor", "transparent")
        bg = "none" if bg == "transparent" else bg
        ls = "--" if e.get("strokeStyle") == "dashed" else (":" if e.get("strokeStyle") == "dotted" else "-")
        if e["type"] == "rectangle":
            ax.add_patch(FancyBboxPatch((e["x"], e["y"]), e["width"], e["height"],
                                        boxstyle="round,pad=0,rounding_size=12" if e.get("roundness") else "square,pad=0",
                                        fc=bg, ec=sc, lw=e.get("strokeWidth", 2) * scale, ls=ls, alpha=e.get("opacity", 100) / 100))
        elif e["type"] == "diamond":
            cx, cy, w, h = e["x"], e["y"], e["width"], e["height"]
            ax.add_patch(Polygon([(cx + w / 2, cy), (cx + w, cy + h / 2), (cx + w / 2, cy + h), (cx, cy + h / 2)],
                                 fc=bg, ec=sc, lw=e.get("strokeWidth", 2) * scale))
        elif e["type"] == "ellipse":
            ax.add_patch(Ellipse((e["x"] + e["width"] / 2, e["y"] + e["height"] / 2), e["width"], e["height"],
                                 fc=bg, ec=sc, lw=e.get("strokeWidth", 2) * scale))
        elif e["type"] in ("arrow", "line"):
            pts = [(e["x"] + p[0], e["y"] + p[1]) for p in e["points"]]
            px, py = zip(*pts)
            ax.plot(px, py, color=sc, lw=e.get("strokeWidth", 2) * scale, ls=ls)
            if e["type"] == "arrow" and e.get("endArrowhead"):
                (ax_, ay_), (bx, by) = pts[-2], pts[-1]
                ax.annotate("", xy=(bx, by), xytext=(ax_ + (bx - ax_) * 0.8, ay_ + (by - ay_) * 0.8),
                            arrowprops=dict(arrowstyle="-|>", color=sc, lw=e.get("strokeWidth", 2) * scale))
            if e["type"] == "arrow" and e.get("startArrowhead"):
                (ax_, ay_), (bx, by) = pts[1], pts[0]
                ax.annotate("", xy=(bx, by), xytext=(ax_ + (bx - ax_) * 0.8, ay_ + (by - ay_) * 0.8),
                            arrowprops=dict(arrowstyle="-|>", color=sc, lw=e.get("strokeWidth", 2) * scale))
    for e in els:
        if e["type"] != "text":
            continue
        ha = {"left": "left", "center": "center", "right": "right"}[e.get("textAlign", "left")]
        tx = e["x"] + (e["width"] / 2 if ha == "center" else (e["width"] if ha == "right" else 0))
        ax.text(tx, e["y"], e["text"], fontsize=e["fontSize"] * scale * 0.72, color=e.get("strokeColor", "#000"),
                ha=ha, va="top", family="DejaVu Sans", linespacing=1.25)
    fig.savefig(out)
    plt.close(fig)


if __name__ == "__main__":
    render(json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 0.5)

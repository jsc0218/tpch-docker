#!/usr/bin/env python3
"""Draws the two README charts (TPC-DS SF100, all 99 queries, cold and warm, light theme) from results.csv.

Standard library only:  python3 tpcds100/make_chart.py
Writes sf100_cold.svg and sf100_warm.svg. One colour per engine in a fixed order, thin bars from a single
baseline, hairline grid, values at the bar tips. The times run from 0.1 s to several hundred seconds, so
the time axis is logarithmic (bar lengths compare as ratios, not as differences). A query that failed or
timed out has no bar, only the word. The README tables hold the same numbers.
"""
import csv
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

ENGINES = ["ClickHouse", "StarRocks"]                        # bar order, and colour slot 1..2
T = dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
         grid="#e1e0d9", base="#c3c2b7",
         series=["#eb6834", "#8a63c9"])
CHARTS = [
    ("cold", "sf100_cold.svg", "TPC-DS SF100, cold start, lower is better",
     "One host, one engine at a time; mean of two runs, each the first after an engine restart and an empty page cache; logarithmic axis"),
    ("warm", "sf100_warm.svg", "TPC-DS SF100, warm, lower is better",
     "One host, one engine at a time; median of the six later runs (three after each of the two cold starts); logarithmic axis"),
]
AXIS_MIN, AXIS_MAX = 0.1, 1000.0                             # seconds
TICKS = [0.1, 1, 10, 100, 1000]

FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"
W, M = 900, 24
LW, VLW = 40, 58
BAR, GAP, PAD = 6, 2, 3
GROUP = len(ENGINES) * BAR + (len(ENGINES) - 1) * GAP + 2 * PAD
TOP, AXIS = 100, 30
LEGEND_SLOT = 132


def bar_path(x, y, w, h, r=3):
    """Square at the baseline (left), rounded data end (right)."""
    r = min(r, w / 2, h / 2)
    return (f"M{x:.1f},{y:.1f} h{w - r:.1f} a{r:.1f},{r:.1f} 0 0 1 {r:.1f},{r:.1f} "
            f"v{h - 2 * r:.1f} a{r:.1f},{r:.1f} 0 0 1 {-r:.1f},{r:.1f} h{-(w - r):.1f} z")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load_rows():
    data, order = {}, {}
    with open(os.path.join(HERE, "results.csv"), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            val = float(r["value"]) / 1000 if r["value"] else None
            data.setdefault(r["mode"], {}).setdefault(r["panel"], {})[r["engine"]] = (val, r["label"])
            order.setdefault(r["mode"], [])
            if r["panel"] not in order[r["mode"]]:
                order[r["mode"]].append(r["panel"])
    return order, data


def render(fname, title, subtitle, order, data):
    t = T
    x0 = M + LW + 6
    plotw = W - x0 - M - VLW
    span = math.log10(AXIS_MAX / AXIS_MIN)
    xs = lambda v: x0 + math.log10(max(v, AXIS_MIN) / AXIS_MIN) / span * plotw
    ytop, ybot = TOP, TOP + len(order) * GROUP
    height = ybot + AXIS + 16
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" '
           f'height="{height}" role="img" aria-labelledby="t d" font-family="{FONT}">']
    summary = "; ".join(f"{p}: " + ", ".join(f"{e} {data[p][e][1]}" for e in ENGINES) for p in order)
    out.append(f"<title id=\"t\">{esc(title)}</title>")
    out.append(f"<desc id=\"d\">{esc(subtitle)}. {esc(summary)}.</desc>")
    out.append(f'<rect width="{W}" height="{height}" fill="{t["surface"]}"/>')
    out.append(f'<text x="{M}" y="34" font-size="17" font-weight="700" fill="{t["ink"]}">{esc(title)}</text>')
    out.append(f'<text x="{M}" y="55" font-size="12" fill="{t["ink2"]}">{esc(subtitle)}</text>')
    for i, e in enumerate(ENGINES):
        x = M + i * LEGEND_SLOT
        out.append(f'<rect x="{x}" y="70" width="10" height="10" rx="2" fill="{t["series"][i]}"/>')
        out.append(f'<text x="{x + 16}" y="79" font-size="12" fill="{t["ink2"]}">{e}</text>')
    for v in TICKS:
        gx = xs(v)
        if v != AXIS_MIN:
            out.append(f'<line x1="{gx:.1f}" y1="{ytop}" x2="{gx:.1f}" y2="{ybot}" stroke="{t["grid"]}" stroke-width="1"/>')
        out.append(f'<text x="{gx:.1f}" y="{ybot + 18}" font-size="11" text-anchor="middle" fill="{t["muted"]}">{v:g} s</text>')
    for k in range(1, len(order)):
        y = ytop + k * GROUP
        out.append(f'<line x1="{M}" y1="{y}" x2="{W - M}" y2="{y}" stroke="{t["grid"]}" stroke-width="0.5" opacity="0.6"/>')
    out.append(f'<line x1="{x0:.1f}" y1="{ytop}" x2="{x0:.1f}" y2="{ybot}" stroke="{t["base"]}" stroke-width="1"/>')
    for qi, p in enumerate(order):
        gy = ytop + qi * GROUP
        out.append(f'<text x="{M + LW}" y="{gy + GROUP / 2 + 4:.1f}" font-size="12" text-anchor="end" fill="{t["ink2"]}">{esc(p)}</text>')
        for i, e in enumerate(ENGINES):
            val, label = data[p][e]
            y = gy + PAD + i * (BAR + GAP)
            if val is None:                                  # failed or timed out: no bar
                out.append(f'<text x="{x0 + 5:.1f}" y="{y + BAR - 0.5:.1f}" font-size="8" font-style="italic" '
                           f'fill="{t["muted"]}">{esc(label)}</text>')
                continue
            w = max(xs(val) - x0, 2.0)
            out.append(f'<path d="{bar_path(x0, y, w, BAR)}" fill="{t["series"][i]}"/>')
            out.append(f'<text x="{x0 + w + 5:.1f}" y="{y + BAR - 0.5:.1f}" font-size="8" font-weight="600" '
                       f'fill="{t["ink"]}" stroke="{t["surface"]}" stroke-width="3" '
                       f'stroke-linejoin="round" paint-order="stroke">{esc(label)}</text>')
    out.append("</svg>")
    path = os.path.join(HERE, fname)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return path


if __name__ == "__main__":
    order, data = load_rows()
    for mode, fname, title, subtitle in CHARTS:
        print(render(fname, title, subtitle, order[mode], data[mode]))

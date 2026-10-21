#!/usr/bin/env python3
"""Draws the README chart (SF10, light theme) from results.csv as one SVG.

Standard library only:  python3 charts/make_charts.py

Design: one colour per engine in a fixed order, thin bars that grow from a single baseline, hairline
grid, values at the bar tips, one linear axis per panel (so bar lengths compare within a panel, not
between panels). The README tables hold the same numbers, plus SF1.
"""
import csv
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

SCALE = "SF10"
ENGINES = ["MonetDB", "ClickHouse", "WarehousePG", "PostgreSQL"]     # bar order, and colour slot 1..4

T = dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
         grid="#e1e0d9", base="#c3c2b7",
         series=["#2a78d6", "#eb6834", "#1baf7a", "#eda100"])      # validated palette, light surface

TITLE = "TPC-H SF10, lower is better"
SUBTITLE = "One host, one engine at a time; query times are the median of 5 warm runs"
# (panel heading, csv chart, csv panel)
PANELS = [
    ("Q6 query time (scan)", "latency", f"Q6 · {SCALE}"),
    ("Q12 query time (join)", "latency", f"Q12 · {SCALE}"),
    ("Load time", "load", SCALE),
    ("Database size", "size", SCALE),
]
COLS = 2

FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"
W, M, GAP = 900, 24, 36             # width, side margin, gap between panel columns
LW, VLW = 94, 66                    # engine-label column, room for the value label after the bars
BAR, ROW = 18, 28                   # bar thickness (<= 24) and row pitch (leaves air between bars)
PTITLE, AXIS, PGAP = 26, 24, 22     # panel title band, axis band, gap between panel rows
TOP = 100                           # title + subtitle + legend
LEGEND_SLOT = 132                   # width of one legend entry


def nice_axis(vmax):
    """Smallest round axis maximum >= vmax with 3 to 5 intervals; returns (max, step)."""
    for exp in range(-3, 7):
        for mult in (1, 2, 2.5, 5):
            step = mult * 10 ** exp
            top = math.ceil(vmax / step - 1e-9) * step
            if 3 <= round(top / step) <= 5:
                return top, step
    return vmax, vmax / 4


def bar_path(x, y, w, h, r=4):
    """Square at the baseline (left), rounded data end (right)."""
    r = min(r, w / 2, h / 2)
    return (f"M{x:.1f},{y:.1f} h{w - r:.1f} a{r:.1f},{r:.1f} 0 0 1 {r:.1f},{r:.1f} "
            f"v{h - 2 * r:.1f} a{r:.1f},{r:.1f} 0 0 1 {-r:.1f},{r:.1f} h{-(w - r):.1f} z")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load_rows():
    data = {}
    with open(os.path.join(HERE, "results.csv"), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            data.setdefault((r["chart"], r["panel"]), {})[r["engine"]] = (float(r["value"]), r["label"])
    return data


def render(rows):
    t = T
    nrows = math.ceil(len(PANELS) / COLS)
    pw = (W - 2 * M - GAP * (COLS - 1)) / COLS
    height = TOP + nrows * (PTITLE + len(ENGINES) * ROW + AXIS + PGAP) - PGAP + 16
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" '
           f'height="{height}" role="img" aria-labelledby="t d" font-family="{FONT}">']

    summary = "; ".join(
        f"{head}: " + ", ".join(f"{e} {rows[(c, p)][e][1]}" for e in ENGINES)
        for head, c, p in PANELS)
    out.append(f"<title id=\"t\">{esc(TITLE)}</title>")
    out.append(f"<desc id=\"d\">{esc(SUBTITLE)}. {esc(summary)}.</desc>")
    out.append(f'<rect width="{W}" height="{height}" fill="{t["surface"]}"/>')
    out.append(f'<text x="{M}" y="34" font-size="17" font-weight="700" fill="{t["ink"]}">{esc(TITLE)}</text>')
    out.append(f'<text x="{M}" y="55" font-size="12" fill="{t["ink2"]}">{esc(SUBTITLE)}</text>')

    for i, e in enumerate(ENGINES):                      # legend: a swatch per engine, text in ink
        x = M + i * LEGEND_SLOT
        out.append(f'<rect x="{x}" y="70" width="10" height="10" rx="2" fill="{t["series"][i]}"/>')
        out.append(f'<text x="{x + 16}" y="79" font-size="12" fill="{t["ink2"]}">{e}</text>')

    for pi, (head, chart, panel) in enumerate(PANELS):
        px = M + (pi % COLS) * (pw + GAP)
        py = TOP + (pi // COLS) * (PTITLE + len(ENGINES) * ROW + AXIS + PGAP)
        data = rows[(chart, panel)]
        x0, plotw = px + LW + 6, pw - LW - 6 - VLW
        ref = data.get("raw")
        axis_max, step = nice_axis(max(max(data[e][0] for e in ENGINES), ref[0] if ref else 0))
        scale = plotw / axis_max
        ytop, ybot = py + PTITLE, py + PTITLE + len(ENGINES) * ROW

        out.append(f'<text x="{px}" y="{py + 14}" font-size="13" font-weight="600" '
                   f'fill="{t["ink"]}">{esc(head)}</text>')
        for k in range(round(axis_max / step) + 1):      # hairline grid + tick labels
            gx = x0 + k * step * scale
            if k:
                out.append(f'<line x1="{gx:.1f}" y1="{ytop}" x2="{gx:.1f}" y2="{ybot}" '
                           f'stroke="{t["grid"]}" stroke-width="1"/>')
            out.append(f'<text x="{gx:.1f}" y="{ybot + 16}" font-size="11" text-anchor="middle" '
                       f'fill="{t["muted"]}">{k * step:g}</text>')
        out.append(f'<line x1="{x0:.1f}" y1="{ytop}" x2="{x0:.1f}" y2="{ybot}" '
                   f'stroke="{t["base"]}" stroke-width="1"/>')

        for i, e in enumerate(ENGINES):
            val, label = data[e]
            cy = ytop + i * ROW + ROW / 2
            w = max(val * scale, 2.0)
            out.append(f'<path d="{bar_path(x0, cy - BAR / 2, w, BAR)}" fill="{t["series"][i]}"/>')
            out.append(f'<text x="{px + LW}" y="{cy + 4:.1f}" font-size="12" text-anchor="end" '
                       f'fill="{t["ink2"]}">{e}</text>')
            # the surface-coloured halo lets grid lines and the reference line break around the number
            out.append(f'<text x="{x0 + w + 7:.1f}" y="{cy + 4:.1f}" font-size="12" font-weight="600" '
                       f'fill="{t["ink"]}" stroke="{t["surface"]}" stroke-width="4" '
                       f'stroke-linejoin="round" paint-order="stroke">{esc(label)}</text>')

        if ref:                                          # reference line: the raw .tbl files
            rx = x0 + ref[0] * scale
            out.append(f'<line x1="{rx:.1f}" y1="{ytop - 4}" x2="{rx:.1f}" y2="{ybot}" '
                       f'stroke="{t["ink2"]}" stroke-width="1.5"/>')
            out.append(f'<text x="{rx + 5:.1f}" y="{py + 14}" font-size="11" fill="{t["ink2"]}">'
                       f'raw .tbl files {esc(ref[1])}</text>')

    out.append("</svg>")
    path = os.path.join(HERE, f"{SCALE.lower()}.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return path


if __name__ == "__main__":
    print(render(load_rows()))

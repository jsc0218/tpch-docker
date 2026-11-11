#!/usr/bin/env python3
"""Draws the README chart (SF10, light theme) from results.csv as one SVG.

Standard library only:  python3 pgaa/make_chart.py

Same style as ../charts/make_charts.py: thin bars from one baseline, hairline grid, values at the
bar tips, one linear axis per panel (bar lengths compare within a panel, not between panels).
The README table holds the same numbers.
"""
import csv
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

MODES = ["pgaa, cache off", "pgaa, cache 1 GiB (default)", "pgaa, cache 10 GiB",
         "ClickHouse, no cache, 1 MiB seek", "ClickHouse, 10 GiB cache, 1 MiB seek"]
T = dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
         grid="#e1e0d9", base="#c3c2b7",
         series=["#eb6834", "#eda100", "#2a78d6", "#8a5cc2", "#2f9e6e"])
TITLE = "pgaa 1.12 and ClickHouse on TPC-H SF10 Parquet in S3, lower is better"
SUBTITLE = "Same host and data; one connection, median of runs 2 to 6 (run 1 is the cold one)"
PANELS = [("Q6 query time (scan)", "Q6"), ("Q12 query time (join)", "Q12")]

FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"
W, M = 900, 24
LW, VLW = 265, 80
BAR, ROW = 18, 28
PTITLE, AXIS, PGAP = 26, 24, 22
TOP = 76


def nice_axis(vmax):
    for exp in range(-3, 7):
        for mult in (1, 2, 2.5, 5):
            step = mult * 10 ** exp
            top = math.ceil(vmax / step - 1e-9) * step
            if 3 <= round(top / step) <= 6:
                return top, step
    return vmax, vmax / 4


def bar_path(x, y, w, h, r=4):
    r = min(r, w / 2, h / 2)
    return (f"M{x:.1f},{y:.1f} h{w - r:.1f} a{r:.1f},{r:.1f} 0 0 1 {r:.1f},{r:.1f} "
            f"v{h - 2 * r:.1f} a{r:.1f},{r:.1f} 0 0 1 {-r:.1f},{r:.1f} h{-(w - r):.1f} z")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load_rows():
    data = {}
    with open(os.path.join(HERE, "results.csv"), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            data.setdefault(r["panel"], {})[r["mode"]] = (float(r["value"]), r["label"])
    return data


def render(rows):
    t = T
    ph = PTITLE + len(MODES) * ROW + AXIS
    height = TOP + len(PANELS) * (ph + PGAP) - PGAP + 16
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" '
           f'height="{height}" role="img" aria-labelledby="t d" font-family="{FONT}">']
    summary = "; ".join(f"{head}: " + ", ".join(f"{m} {rows[p][m][1]}" for m in MODES)
                        for head, p in PANELS)
    out.append(f'<title id="t">{esc(TITLE)}</title>')
    out.append(f'<desc id="d">{esc(SUBTITLE)}. {esc(summary)}.</desc>')
    out.append(f'<rect width="{W}" height="{height}" fill="{t["surface"]}"/>')
    out.append(f'<text x="{M}" y="34" font-size="17" font-weight="700" fill="{t["ink"]}">{esc(TITLE)}</text>')
    out.append(f'<text x="{M}" y="55" font-size="12" fill="{t["ink2"]}">{esc(SUBTITLE)}</text>')

    for pi, (head, panel) in enumerate(PANELS):
        px, py = M, TOP + pi * (ph + PGAP)
        data = rows[panel]
        x0, plotw = px + LW + 6, W - 2 * M - LW - 6 - VLW
        axis_max, step = nice_axis(max(data[m][0] for m in MODES))
        scale = plotw / axis_max
        ytop, ybot = py + PTITLE, py + PTITLE + len(MODES) * ROW
        out.append(f'<text x="{px}" y="{py + 14}" font-size="13" font-weight="600" fill="{t["ink"]}">{esc(head)}</text>')
        for k in range(round(axis_max / step) + 1):
            gx = x0 + k * step * scale
            if k:
                out.append(f'<line x1="{gx:.1f}" y1="{ytop}" x2="{gx:.1f}" y2="{ybot}" stroke="{t["grid"]}" stroke-width="1"/>')
            out.append(f'<text x="{gx:.1f}" y="{ybot + 16}" font-size="11" text-anchor="middle" fill="{t["muted"]}">{k * step:g} ms</text>')
        out.append(f'<line x1="{x0:.1f}" y1="{ytop}" x2="{x0:.1f}" y2="{ybot}" stroke="{t["base"]}" stroke-width="1"/>')
        for i, m in enumerate(MODES):
            val, label = data[m]
            cy = ytop + i * ROW + ROW / 2
            w = max(val * scale, 2.0)
            out.append(f'<path d="{bar_path(x0, cy - BAR / 2, w, BAR)}" fill="{t["series"][i]}"/>')
            out.append(f'<text x="{px + LW}" y="{cy + 4:.1f}" font-size="12" text-anchor="end" fill="{t["ink2"]}">{esc(m)}</text>')
            out.append(f'<text x="{x0 + w + 7:.1f}" y="{cy + 4:.1f}" font-size="12" font-weight="600" fill="{t["ink"]}" '
                       f'stroke="{t["surface"]}" stroke-width="4" stroke-linejoin="round" paint-order="stroke">{esc(label)}</text>')
    out.append("</svg>")
    path = os.path.join(HERE, "sf10.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return path


if __name__ == "__main__":
    print(render(load_rows()))

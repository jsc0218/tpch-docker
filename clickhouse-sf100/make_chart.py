#!/usr/bin/env python3
"""Draws the SF100 query-time chart from results-sf100-26.10.7.24.csv as one SVG (light theme).

Standard library only:  python3 clickhouse-sf100/make_chart.py

Same style as ../charts/make_charts.py: thin bars from one baseline, hairline grid, values at the
bar tips, one linear axis. One series, so no legend. The README table holds the same numbers.
"""
import csv
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "results-sf100-26.10.7.24.csv")

T = dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
         grid="#e1e0d9", base="#c3c2b7", bar="#1baf7a")
TITLE = "ClickHouse 26.10.7.24 on TPC-H SF100, lower is better"
SUBTITLE = "c6id.8xlarge (32 vCPU, 64 GB); best of 2 runs; all 22 queries match the official answers at SF1"

FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"
W, M = 900, 24
LW, VLW = 36, 70
BAR, ROW = 14, 22
AXIS, TOP = 28, 76


def nice_axis(vmax):
    for exp in range(-3, 7):
        for mult in (1, 2, 2.5, 5):
            step = mult * 10 ** exp
            top = math.ceil(vmax / step - 1e-9) * step
            if 3 <= round(top / step) <= 7:
                return top, step
    return vmax, vmax / 4


def bar_path(x, y, w, h, r=4):
    r = min(r, w / 2, h / 2)
    return (f"M{x:.1f},{y:.1f} h{w - r:.1f} a{r:.1f},{r:.1f} 0 0 1 {r:.1f},{r:.1f} "
            f"v{h - 2 * r:.1f} a{r:.1f},{r:.1f} 0 0 1 {-r:.1f},{r:.1f} h{-(w - r):.1f} z")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load():
    best = {}
    with open(CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["status"] == "OK":
                n = int(r["query"])
                best[n] = min(best.get(n, 1e9), float(r["seconds"]))
    return best


def render(best):
    t = T
    qs = sorted(best)
    height = TOP + len(qs) * ROW + AXIS + 12
    x0 = M + LW + 6
    plotw = W - 2 * M - LW - 6 - VLW
    axis_max, step = nice_axis(max(best.values()))
    scale = plotw / axis_max
    ytop, ybot = TOP, TOP + len(qs) * ROW
    summary = ", ".join(f"Q{n} {best[n]:.2f} s" for n in qs)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" '
           f'height="{height}" role="img" aria-labelledby="t d" font-family="{FONT}">',
           f'<title id="t">{esc(TITLE)}</title>',
           f'<desc id="d">{esc(SUBTITLE)}. {esc(summary)}.</desc>',
           f'<rect width="{W}" height="{height}" fill="{t["surface"]}"/>',
           f'<text x="{M}" y="34" font-size="17" font-weight="700" fill="{t["ink"]}">{esc(TITLE)}</text>',
           f'<text x="{M}" y="55" font-size="12" fill="{t["ink2"]}">{esc(SUBTITLE)}</text>']
    for k in range(round(axis_max / step) + 1):
        gx = x0 + k * step * scale
        if k:
            out.append(f'<line x1="{gx:.1f}" y1="{ytop}" x2="{gx:.1f}" y2="{ybot}" stroke="{t["grid"]}" stroke-width="1"/>')
        out.append(f'<text x="{gx:.1f}" y="{ybot + 18}" font-size="11" text-anchor="middle" fill="{t["muted"]}">{k * step:g} s</text>')
    out.append(f'<line x1="{x0:.1f}" y1="{ytop}" x2="{x0:.1f}" y2="{ybot}" stroke="{t["base"]}" stroke-width="1"/>')
    for i, n in enumerate(qs):
        cy = ytop + i * ROW + ROW / 2
        w = max(best[n] * scale, 2.0)
        out.append(f'<path d="{bar_path(x0, cy - BAR / 2, w, BAR)}" fill="{t["bar"]}"><title>Q{n}: {best[n]:.2f} s</title></path>')
        out.append(f'<text x="{M + LW}" y="{cy + 4:.1f}" font-size="12" text-anchor="end" fill="{t["ink2"]}">Q{n}</text>')
        out.append(f'<text x="{x0 + w + 7:.1f}" y="{cy + 4:.1f}" font-size="12" font-weight="600" fill="{t["ink"]}" '
                   f'stroke="{t["surface"]}" stroke-width="4" stroke-linejoin="round" paint-order="stroke">{best[n]:.2f} s</text>')
    out.append("</svg>")
    path = os.path.join(HERE, "sf100.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return path


if __name__ == "__main__":
    print(render(load()))

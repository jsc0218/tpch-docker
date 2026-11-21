#!/usr/bin/env python3
"""Turn harness output files into results.csv (the warm time per query) and runs.csv (every run).

usage: summarize.py <out_dir> "<label>=<pass1.json>,<pass2.json>" ...
  e.g. summarize.py tpcds10 "ClickHouse=out/ch_a.json,out/ch_b.json" "StarRocks=out/sr_a.json,out/sr_b.json"

Warm time of a query = median of runs 2 to 6 of every pass (the first run of each pass is a warm-up that is
discarded): ten runs for two passes.
"""
import csv, json, statistics as st, sys

out = sys.argv[1]
engines = [(a.split("=", 1)[0], a.split("=", 1)[1].split(",")) for a in sys.argv[2:]]

def lab(ms):
    s = ms / 1000
    return f"{s:.2f} s" if s < 10 else f"{s:.1f} s"

results, runs = [], []
for label, files in engines:
    passes = [json.load(open(f)) for f in files]
    for q in range(1, 100):
        for i, data in enumerate(passes, 1):
            rec = data[str(q)]
            runs.append([label, i, f"Q{q}"] + rec["runs_ms"] + ([] if not rec["error"] else ["ERROR " + rec["error"][:80]]))
        warm = [x for data in passes for x in data[str(q)]["runs_ms"][1:]]
        if any(d[str(q)]["error"] for d in passes) or not warm:
            results.append([f"Q{q}", label, "", "failed"])
        else:
            v = round(st.median(warm), 2); results.append([f"Q{q}", label, v, lab(v)])
with open(f"{out}/results.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["panel", "engine", "value", "label"]); w.writerows(results)
with open(f"{out}/runs.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["engine", "pass", "query"] + [f"run{i}_ms" for i in range(1, 7)]); w.writerows(runs)
print("wrote", len(results), "results,", len(runs), "run rows")

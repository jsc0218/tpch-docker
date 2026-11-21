#!/usr/bin/env python3
"""Turn the output directories of run_cold.sh into results.csv, runs.csv and disk_mib.csv.

usage: summarize.py <out_dir> "<label>=<dir_pass1>,<dir_pass2>" ...
  e.g. summarize.py tpch100 "ClickHouse 26.8=out/ch268,out/ch268_2" "StarRocks=out/sr,out/sr_2"

Each pass directory holds <engine>.json (written by merge.py) and disk_mib.csv. Per query:
  cold = mean of the first runs of the passes (restart, empty page cache);
  warm = median of all the later runs of all passes (five per pass).
"""
import csv, glob, json, os, statistics as st, sys

out = sys.argv[1]
engines = []
for arg in sys.argv[2:]:
    label, dirs = arg.split("=", 1)
    engines.append((label, dirs.split(",")))

def lab(ms):                                   # seconds with 3 significant figures
    s = ms / 1000
    return f"{s:.2f} s" if s < 10 else f"{s:.1f} s"

results, runs, disk = [], [], []
for label, dirs in engines:
    passes = []
    for i, d in enumerate(dirs, 1):
        f = [p for p in (f"{d}/clickhouse.json", f"{d}/starrocks.json") if os.path.exists(p)][0]
        data = json.load(open(f))
        dk = {r["query"]: r for r in csv.DictReader(open(f"{d}/disk_mib.csv"))}
        passes.append((i, data, dk))
    for q in range(1, 23):
        cold = [data[str(q)]["runs_ms"][0] for _, data, _ in passes]
        warm = [x for _, data, _ in passes for x in data[str(q)]["runs_ms"][1:]]
        for mode, val in (("cold", st.mean(cold)), ("warm", st.median(warm))):
            results.append([mode, f"Q{q}", label, round(val, 2), lab(round(val, 2))])
        for i, data, dk in passes:
            runs.append([label, i, f"Q{q}"] + data[str(q)]["runs_ms"])
            disk.append([label, i, f"Q{q}", dk[f"Q{q}"]["cold_mib_read"], dk[f"Q{q}"]["warm_mib_read"]])

with open(f"{out}/results.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["mode", "panel", "engine", "value", "label"]); w.writerows(results)
with open(f"{out}/runs.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["engine", "pass", "query"] + [f"run{i}_ms" for i in range(1, 7)]); w.writerows(runs)
with open(f"{out}/disk_mib.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["engine", "pass", "query", "cold_mib_read", "warm_mib_read"]); w.writerows(disk)
print("wrote", len(results), "results,", len(runs), "run rows,", len(disk), "disk rows")

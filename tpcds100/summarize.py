#!/usr/bin/env python3
"""Turn the output directories of run_cold.sh into results.csv, runs.csv and disk_mib.csv.

usage: summarize.py <out_dir> "<label>=<dir_pass1>,<dir_pass2>" ...
  e.g. summarize.py tpcds100 "ClickHouse=out/ch,out/ch_2" "StarRocks=out/sr,out/sr_2"

Each pass directory holds <engine>.json (written by merge.py) and disk_mib.csv. Per query:
  cold = mean of the first runs of the passes (restart, empty page cache);
  warm = median of all the later runs of all passes.
A query that failed or timed out in any pass is "failed" or "timeout" and has no value.
"""
import csv, json, os, statistics as st, sys

out = sys.argv[1]
engines = [(a.split("=", 1)[0], a.split("=", 1)[1].split(",")) for a in sys.argv[2:]]

def lab(ms):
    s = ms / 1000
    return f"{s:.2f} s" if s < 10 else f"{s:.1f} s" if s < 100 else f"{s:.0f} s"

results, runs, disk = [], [], []
for label, dirs in engines:
    passes = []
    for i, d in enumerate(dirs, 1):
        f = [p for p in (f"{d}/clickhouse.json", f"{d}/starrocks.json") if os.path.exists(p)][0]
        dk = {r["query"]: r for r in csv.DictReader(open(f"{d}/disk_mib.csv"))}
        passes.append((i, json.load(open(f)), dk))
    for q in range(1, 100):
        recs = [data[str(q)] for _, data, _ in passes]
        for i, data, dk in passes:
            rec = data[str(q)]
            runs.append([label, i, f"Q{q}"] + rec["runs_ms"] + ([] if not rec["error"] else ["ERROR " + rec["error"][:80]]))
            disk.append([label, i, f"Q{q}", dk[f"Q{q}"]["cold_mib_read"], dk[f"Q{q}"]["warm_mib_read"]])
        errs = [r["error"] for r in recs if r["error"]]
        if errs:
            word = "timeout" if any("timeout" in e for e in errs) else "failed"
            results += [["cold", f"Q{q}", label, "", word], ["warm", f"Q{q}", label, "", word]]
            continue
        cold = st.mean(r["runs_ms"][0] for r in recs); warm = st.median(x for r in recs for x in r["runs_ms"][1:])
        results += [["cold", f"Q{q}", label, round(cold, 2), lab(cold)], ["warm", f"Q{q}", label, round(warm, 2), lab(warm)]]
with open(f"{out}/results.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["mode", "panel", "engine", "value", "label"]); w.writerows(results)
width = max(len(r) for r in runs) - 3
with open(f"{out}/runs.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["engine", "pass", "query"] + [f"run{i}_ms" for i in range(1, width + 1)]); w.writerows(runs)
with open(f"{out}/disk_mib.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["engine", "pass", "query", "cold_mib_read", "warm_mib_read"]); w.writerows(disk)
print("wrote", len(results), "results,", len(runs), "run rows,", len(disk), "disk rows")

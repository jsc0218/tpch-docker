#!/usr/bin/env python3
"""TPC-H on ClickHouse: load, validate against official answers, time.

  tpch_bench.py load     <db> <data_dir>
  tpch_bench.py validate <db>                     # SF1 only: compares with answers/qN.sf1.tsv
  tpch_bench.py run      <db> [--runs 2] [--timeout 600] [--out results.csv] [--sf 100] [--only N ...]

Env: CLICKHOUSE_CLIENT  client command (default: clickhouse-client)
"""
import argparse, csv, math, os, re, shlex, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLIENT = shlex.split(os.environ.get("CLICKHOUSE_CLIENT", "clickhouse-client"))
TABLES = ["nation", "region", "part", "supplier", "partsupp", "customer", "orders", "lineitem"]


def ch(args, sql=None, stdin=None):
    return subprocess.run(CLIENT + args, input=stdin if stdin is not None else (sql.encode() if sql else None),
                          capture_output=True)


def load(db, data_dir):
    ch(["-q", f"DROP DATABASE IF EXISTS {db}"])
    ch(["-q", f"CREATE DATABASE {db}"])
    p = ch(["--database", db, "-mn"], stdin=(HERE / "schema.sql").read_bytes())
    if p.returncode:
        sys.exit(p.stderr.decode())

    def one(t):
        t0 = time.monotonic()
        with open(Path(data_dir) / f"{t}.tbl", "rb") as f:
            p = subprocess.run(CLIENT + ["--database", db, "--format_csv_delimiter=|",
                                         "-q", f"INSERT INTO {t} FORMAT CSV"], stdin=f, capture_output=True)
        if p.returncode:
            sys.exit(f"{t}: {p.stderr.decode()}")
        return t, time.monotonic() - t0

    t0 = time.monotonic()
    # lineitem and orders dominate, so start them first
    with ThreadPoolExecutor(4) as ex:
        for t, s in ex.map(one, ["lineitem", "orders", "partsupp", "customer", "part", "supplier", "nation", "region"]):
            print(f"loaded {t} in {s:.1f}s", flush=True)
    print(f"load total {time.monotonic() - t0:.1f}s")


SF = 1.0


def run_query(db, n, timeout, fmt="TSVWithNames"):
    sql = (HERE / "queries" / f"q{n}.sql").read_bytes()
    if n == 11:  # Q11 threshold is FRACTION = 0.0001 / SF (spec 2.4.11.3); the file holds the SF1 value
        sql = sql.replace(b"0.0001000000", f"{0.0001 / SF:.10f}".encode())
    t0 = time.monotonic()
    p = ch(["--database", db, "-mn", f"--max_execution_time={timeout}", f"--format={fmt}"], stdin=sql)
    return p, time.monotonic() - t0


def close(a, b):
    try:
        x, y = float(a), float(b)
    except ValueError:
        return a.strip() == b.strip()
    return math.isclose(x, y, rel_tol=1e-6, abs_tol=0.011)


def validate(db):
    bad = 0
    for n in range(1, 23):
        p, s = run_query(db, n, 600)
        if p.returncode:
            print(f"Q{n}: ERROR {p.stderr.decode().strip()[:200]}"); bad += 1; continue
        got = [l.split("\t") for l in p.stdout.decode().splitlines()][1:]
        exp = [l.split("|") for l in (HERE / "answers" / f"q{n}.sf1.tsv").read_text().splitlines()][1:]
        ok = len(got) == len(exp) and all(len(g) == len(e) and all(close(x, y) for x, y in zip(g, e))
                                          for g, e in zip(got, exp))
        if not ok:
            bad += 1
            first = next((i for i, (g, e) in enumerate(zip(got, exp)) if not all(close(x, y) for x, y in zip(g, e))), None)
            print(f"Q{n}: MISMATCH rows got={len(got)} exp={len(exp)} first_diff_row={first}"
                  + (f"\n   got {got[first]}\n   exp {exp[first]}" if first is not None else ""))
        else:
            print(f"Q{n}: ok ({s:.2f}s)")
    print("all 22 match" if not bad else f"{bad} query(ies) wrong")
    return bad


def run(db, runs, timeout, out, only):
    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["query", "run", "status", "seconds", "rows", "error"])
        for n in only:
            for r in range(1, runs + 1):
                p, s = run_query(db, n, timeout, "TSV")
                ok = p.returncode == 0
                err = ""
                if not ok:
                    m = re.search(r"Code: \d+\.[^(]*(\([A-Z_]+\))?", p.stderr.decode(errors="replace"))
                    err = " ".join((m.group(0) if m else p.stderr.decode(errors="replace")).split())[:200]
                row = [n, r, "OK" if ok else "FAIL", f"{s:.3f}", p.stdout.count(b"\n"), err]
                w.writerow(row); f.flush(); print(",".join(map(str, row)), flush=True)
                if not ok:
                    break


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("load"); a.add_argument("db"); a.add_argument("data_dir")
    a = sub.add_parser("validate"); a.add_argument("db")  # SF1 only
    a = sub.add_parser("run"); a.add_argument("db"); a.add_argument("--runs", type=int, default=2)
    a.add_argument("--timeout", type=int, default=600); a.add_argument("--out", default="results.csv")
    a.add_argument("--sf", type=float, default=1.0); a.add_argument("--only", type=int, nargs="*", default=list(range(1, 23)))
    args = ap.parse_args()
    SF = getattr(args, "sf", 1.0)
    if args.cmd == "load": load(args.db, args.data_dir)
    elif args.cmd == "validate": sys.exit(1 if validate(args.db) else 0)
    else: run(args.db, args.runs, args.timeout, args.out, args.only)

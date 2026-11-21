#!/usr/bin/env python3
"""Reference answers for the 22 queries, computed by DuckDB from the same .tbl files the engines load.

usage: reference.py <tbl_dir> <query_dir> <out.json>
Run it where the files are, e.g.:
  docker run --rm -v /data/tpch:/data/tpch:ro -v $PWD/tpch22:/w -w /w python:3.12-slim sh -c \
    "pip install -q duckdb && python3 reference.py /data/tpch queries /w/reference.json"
"""
import datetime, decimal, json, sys, time
import duckdb

tbl, qdir, out = sys.argv[1:4]
c = duckdb.connect()
c.execute("INSTALL tpch; LOAD tpch;")
c.execute("CALL dbgen(sf=0)")                       # empty tables with the standard TPC-H schema
for t in ['region', 'nation', 'supplier', 'customer', 'part', 'partsupp', 'orders', 'lineitem']:
    cols = c.execute(f"select name, type from pragma_table_info('{t}')").fetchall()
    spec = ', '.join(f"'{n}': '{ty}'" for n, ty in cols) + ", 'dummy': 'VARCHAR'"   # rows end with '|'
    s = time.time()
    c.execute(f"insert into {t} select * exclude(dummy) from read_csv('{tbl}/{t}.tbl', delim='|', header=false, columns={{{spec}}})")
    print(t, c.execute(f"select count(*) from {t}").fetchone()[0], f"{time.time() - s:.1f}s", flush=True)

def norm(v):
    if isinstance(v, decimal.Decimal): return str(v)
    if isinstance(v, (datetime.date, datetime.datetime)): return v.isoformat()
    return v

res = {}
for n in range(1, 23):
    rows = c.execute(open(f'{qdir}/q{n}.sql').read()).fetchall()
    res[n] = [[norm(x) for x in r] for r in rows]
    print(f"q{n}: {len(rows)} rows", flush=True)
json.dump(res, open(out, 'w'))

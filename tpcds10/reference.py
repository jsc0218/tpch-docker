#!/usr/bin/env python3
"""Reference answers for the 99 queries, computed by DuckDB from the same .dat files the engines load.

usage: reference.py <dat_dir> <query_dir> <out.json>
  docker run --rm -v /data/tpcds:/data/tpcds:ro -v $PWD/tpcds10:/w -v $PWD/q:/q:ro -v $PWD/out:/out -w /w python:3.12-slim \
    sh -c "pip install -q duckdb && python3 reference.py /data/tpcds /q /out/reference.json"
Optional env for out-of-core runs (SF100): DUCKDB_DB (database file), DUCKDB_MEMORY (e.g. 40GB), DUCKDB_TEMP (directory),
ONLY (comma list of query numbers).
"""
import datetime, decimal, glob, json, os, re, sys, time
import duckdb

dat, qdir, out = sys.argv[1:4]
c = duckdb.connect(os.environ.get("DUCKDB_DB", ":memory:"))
if os.environ.get("DUCKDB_MEMORY"): c.execute(f"SET memory_limit='{os.environ['DUCKDB_MEMORY']}'")
if os.environ.get("DUCKDB_TEMP"): c.execute(f"SET temp_directory='{os.environ['DUCKDB_TEMP']}'")
c.execute("INSTALL tpcds; LOAD tpcds;")
c.execute("CALL dsdgen(sf=0)")                      # empty tables with the standard TPC-DS schema
tables = [r[0] for r in c.execute("select table_name from duckdb_tables() where table_name <> 'dbgen_version' order by 1").fetchall()]
for t in tables:
    files = sorted(f for f in glob.glob(f'{dat}/{t}_*.dat') if re.fullmatch(rf'{t}_\d+_\d+\.dat', os.path.basename(f)))
    cols = c.execute(f"select name, type from pragma_table_info('{t}')").fetchall()
    spec = ', '.join(f"'{n}': '{ty}'" for n, ty in cols) + ", 'dummy': 'VARCHAR'"   # rows end with '|'
    s = time.time()
    flist = ', '.join(f"'{f}'" for f in files)
    c.execute(f"insert into {t} select * exclude(dummy) from read_csv([{flist}], delim='|', header=false, columns={{{spec}}})")
    print(t, c.execute(f"select count(*) from {t}").fetchone()[0], f"{time.time() - s:.1f}s", flush=True)

def norm(v):
    if isinstance(v, decimal.Decimal): return str(v)
    if isinstance(v, (datetime.date, datetime.datetime)): return v.isoformat()
    return v

only = [int(x) for x in os.environ.get('ONLY', '').split(',') if x] or range(1, 100)
res = {}
for n in only:
    s = time.time()
    rows = c.execute(open(f'{qdir}/q{n}.sql').read()).fetchall()
    res[n] = [[norm(x) for x in r] for r in rows]
    print(f"q{n}: {len(rows)} rows {time.time() - s:.1f}s", flush=True)
    json.dump(res, open(out, 'w'))

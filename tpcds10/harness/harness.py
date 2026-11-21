#!/usr/bin/env python3
"""Run TPC-DS queries against one engine and time each one end to end.
usage: harness.py <clickhouse|starrocks> <query_dir> <out.json>
env: RUNS (default 6), TIMEOUT seconds (default 900), ONLY (comma list of query numbers), CH_SETTINGS (json)"""
import datetime, decimal, json, os, signal, sys, time

engine, qdir, out = sys.argv[1:4]
RUNS = int(os.environ.get('RUNS', 6)); TIMEOUT = int(os.environ.get('TIMEOUT', 900))
ONLY = [int(x) for x in os.environ.get('ONLY', '').split(',') if x] or list(range(1, 100))

def norm(v):
    if isinstance(v, decimal.Decimal): return str(v)
    if isinstance(v, (datetime.date, datetime.datetime)): return v.isoformat()
    if isinstance(v, bytes): return v.decode()
    return v

if engine == 'clickhouse':
    import clickhouse_connect
    settings = json.loads(os.environ.get('CH_SETTINGS', '{}')); settings['max_execution_time'] = TIMEOUT
    def connect(): return clickhouse_connect.get_client(host='127.0.0.1', port=8123, username='default', password='', database='tpcds', settings=settings)
    def run(cli, sql): return cli.query(sql).result_rows
elif engine == 'starrocks':
    import pymysql
    def connect(): return pymysql.connect(host='127.0.0.1', port=9030, user='root', password='', database='tpcds', autocommit=True, read_timeout=TIMEOUT)
    def run(cli, sql):
        cur = cli.cursor(); cur.execute(sql); rows = cur.fetchall(); cur.close(); return rows
else:
    sys.exit('unknown engine')

class Timeout(Exception): pass
def on_alarm(*_): raise Timeout()
signal.signal(signal.SIGALRM, on_alarm)

cli = connect(); result = {}
for n in ONLY:
    sql = open(f'{qdir}/q{n}.sql').read().strip().rstrip(';')
    rec = {'runs_ms': [], 'rows': None, 'error': None}
    for i in range(RUNS):
        signal.alarm(TIMEOUT + 30)
        try:
            t = time.perf_counter(); rows = run(cli, sql); ms = (time.perf_counter() - t) * 1000
            signal.alarm(0)
        except Timeout:
            rec['error'] = f'timeout after {TIMEOUT}s'; cli = connect(); break
        except Exception as e:
            signal.alarm(0); rec['error'] = f'{type(e).__name__}: {str(e)[:300]}'; break
        rec['runs_ms'].append(round(ms, 2))
        if rec['rows'] is None: rec['rows'] = [[norm(x) for x in r] for r in rows]
    result[n] = rec
    warm = sorted(rec['runs_ms'][1:]) if len(rec['runs_ms']) > 1 else []
    med = warm[len(warm) // 2] if len(warm) % 2 else (warm[len(warm)//2-1] + warm[len(warm)//2]) / 2 if warm else None
    print(f"q{n:<2} rows={len(rec['rows']) if rec['rows'] is not None else '-':<6} first={rec['runs_ms'][0] if rec['runs_ms'] else '-'} median(2-{RUNS})={round(med,1) if med else '-'} ms {('ERROR: ' + rec['error']) if rec['error'] else ''}", flush=True)
    json.dump(result, open(out, 'w'), default=str)
print('HARNESS_DONE', flush=True)

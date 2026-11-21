#!/usr/bin/env python3
"""Merge the per-query cold and warm harness files written by run_cold.sh into <engine>.json
(the format harness.py writes and compare.py reads): runs_ms = [cold run, warm runs]. A query whose cold run
failed has no warm file and keeps the error of the cold run."""
import json, os, sys
out, engine = sys.argv[1:3]
res = {}
for q in range(1, 100):
    if not os.path.exists(f'{out}/cold_q{q}.json'): continue          # ONLY was used
    cold = json.load(open(f'{out}/cold_q{q}.json'))[str(q)]
    wf = f'{out}/warm_q{q}.json'
    warm = json.load(open(wf))[str(q)] if os.path.exists(wf) else {'runs_ms': [], 'error': None}
    res[str(q)] = {'runs_ms': cold['runs_ms'] + warm['runs_ms'], 'rows': cold['rows'], 'error': cold['error'] or warm['error']}
json.dump(res, open(f'{out}/{engine}.json', 'w'))
print('wrote', f'{out}/{engine}.json')

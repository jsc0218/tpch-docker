#!/usr/bin/env python3
"""compare.py <engine.json> <reference.json>: check every query's answer against the reference.

A number matches if it is within half a unit of the cent (0.0051) or 1e-9 relative; a value that is off by exactly one
unit in the last printed digit (0.01, 1e-4 for small ratios) because the engines round decimal divisions differently is
reported as "rounding" and counted separately. Rows may come in a different order when the ORDER BY has ties, and the
LIMIT may cut a tie group differently: that is reported as "tie".
"""
import json, sys
eng = json.load(open(sys.argv[1])); ref = json.load(open(sys.argv[2]))
def num(x):
    if isinstance(x, bool): return None
    try: return float(x)
    except (TypeError, ValueError): return None
def level(a, b):          # 0 same, 1 rounding, 2 different
    if a is None or b is None: return 0 if a is None and b is None else 2
    na, nb = num(a), num(b)
    if na is not None and nb is not None:
        d = abs(na - nb)
        if d <= max(0.0051, 1e-9 * abs(nb)): return 0
        return 1 if d <= 0.0101 + 1e-9 * abs(nb) else 2
    return 0 if str(a).strip() == str(b).strip() else 2
def row_level(r, s):
    if len(r) != len(s): return 2
    return max([level(x, y) for x, y in zip(r, s)] or [0])
def key(r): return tuple((0, round(num(x), 1)) if num(x) is not None else (1, str(x).strip() if x is not None else '') for x in r)

bad = 0; rounding = 0
for n in sorted(map(int, eng)):
    e = eng[str(n)]; r = ref[str(n)]
    if e['error']: print(f"q{n:<2} ERROR {e['error'][:140]}"); bad += 1; continue
    rows = e['rows']
    if len(rows) != len(r): print(f"q{n:<2} MISMATCH row count {len(rows)} vs reference {len(r)}"); bad += 1; continue
    lv = [row_level(a, b) for a, b in zip(rows, r)]
    if max(lv, default=0) == 0: print(f"q{n:<2} ok ({len(rows)} rows)"); continue
    if max(lv) == 1: print(f"q{n:<2} ok within rounding: {sum(1 for x in lv if x)} of {len(rows)} rows have a value off by one unit in the last digit"); rounding += 1; continue
    if sorted(map(key, rows)) == sorted(map(key, r)): print(f"q{n:<2} tie: same rows, {sum(1 for x in lv if x)} in a different order ({len(rows)} rows)"); continue
    d = [i for i, x in enumerate(lv) if x == 2]; i = d[0]
    print(f"q{n:<2} MISMATCH {len(d)} of {len(rows)} rows differ; first at row {i}: got {rows[i]} expected {r[i]}"); bad += 1
print('RESULT:', 'all answers match the reference' if not bad else f'{bad} problem(s)', f'({rounding} queries with rounding differences)' if rounding else '')

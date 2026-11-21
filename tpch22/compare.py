#!/usr/bin/env python3
"""compare.py <engine.json> <reference.json>: check every query's answer against the reference.

engine.json comes from harness/harness.py, reference.json from reference.py."""
import json, math, sys
eng = json.load(open(sys.argv[1])); ref = json.load(open(sys.argv[2]))
def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None
def same(a, b):
    if a is None or b is None: return a is None and b is None
    na, nb = num(a), num(b)
    if na is not None and nb is not None:
        # exact money sums should match to the cent; small values (ratios, rounded to 4 decimals by some engines) to 1e-4
        return abs(na - nb) <= (0.0051 if abs(nb) >= 10 else 1e-4)
    return str(a).strip() == str(b).strip()
def row_same(r, s): return len(r) == len(s) and all(same(x, y) for x, y in zip(r, s))
def key(r): return tuple(round(num(x), 2) if num(x) is not None else str(x).strip() for x in r)

bad = 0
for n in sorted(map(int, eng)):
    e = eng[str(n)]; r = ref[str(n)]
    if e['error']: print(f"q{n:<2} ERROR {e['error'][:120]}"); bad += 1; continue
    rows = e['rows']
    if len(rows) != len(r): print(f"q{n:<2} MISMATCH row count {len(rows)} vs reference {len(r)}"); bad += 1; continue
    diffs = [i for i, (a, b) in enumerate(zip(rows, r)) if not row_same(a, b)]
    if not diffs: print(f"q{n:<2} ok ({len(rows)} rows)"); continue
    # same rows in a different order (ties in the ORDER BY)?
    if sorted(map(key, rows)) == sorted(map(key, r)): print(f"q{n:<2} ok as a set; {len(diffs)} rows in a different order (ties) ({len(rows)} rows)"); continue
    i = diffs[0]; print(f"q{n:<2} MISMATCH {len(diffs)} of {len(rows)} rows differ; first at row {i}: got {rows[i]} expected {r[i]}"); bad += 1
print('RESULT:', 'all answers match the reference' if not bad else f'{bad} problem(s)')

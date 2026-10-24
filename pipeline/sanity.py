"""Stop a bad week from going live. Exits non-zero (so nothing is committed) if the new numbers look wrong."""
import json, os, sys, statistics as stt

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, '..', 'docs', 'data', 'lgas.json')))
prevp = os.path.join(HERE, 'out', 'prev_lgas.json')
P = json.load(open(prevp)) if os.path.exists(prevp) else None
bad = []
L = D['lgas']
if len(L) != 774: bad.append(f'{len(L)} LGAs, expected 774')
if len(D['states']) != 37: bad.append(f'{len(D["states"])} states, expected 37')
for g in L:
    v = g['v']
    if not (100 <= (v.get("res") or 0) <= 3e7): bad.append(f'{g["n"]} ({g["s"]}) residential {v.get("res")}')
    for k in ('rent3', 'sale4', 'com', 'ind'):
        if not v.get(k) or v[k] <= 0: bad.append(f'{g["n"]} ({g["s"]}) missing {k}')
by = {(g['s'], g['n']): g['v']['res'] for g in L}
checks = [(('LA', 'Eti Osa'), 200000, 6e6), (('FC', 'Municipal Area Council'), 35000, 2e6), (('LA', 'Ikeja'), 80000, 3e6),
          (('KN', 'Kano Municipal'), 4000, 120000), (('EN', 'Enugu North'), 15000, 150000), (('OY', 'Iseyin'), 300, 8000)]
# rural LGAs: typical village land stays in a realistic band (benchmarks put village plots at N0.3-1.5m)
rur = sorted(g['v']['res'] for g in L if g.get('cls') == 'Rural')
if rur and not (300 <= rur[len(rur)//2] <= 3000): bad.append(f'median rural LGA land {rur[len(rur)//2]:.0f}/m2 outside 300-3,000')
rr = sorted(g['v']['rent3'] for g in L if g.get('cls') == 'Rural')
if rr and not (80000 <= rr[len(rr)//2] <= 600000): bad.append(f'median rural 3-bed rent {rr[len(rr)//2]:.0f} outside 80k-600k')
for key, lo, hi in checks:
    v = by.get(key)
    if v is not None and not (lo <= v <= hi): bad.append(f'{key} residential {v} outside {lo}-{hi}')
if P:
    old = {(g['s'], g['n']): g['v']['res'] for g in P['lgas']}
    ratios = [by[k] / old[k] for k in by if k in old and old[k]]
    med = stt.median(ratios)
    if not (0.75 <= med <= 1.33): bad.append(f'national median moved x{med:.2f} in one week')
    wild = sum(1 for r in ratios if r > 2.5 or r < 0.4)
    if wild > 40: bad.append(f'{wild} LGAs moved more than x2.5 in one week')
    print(f'week-on-week: median x{med:.3f}, {wild} LGAs beyond x2.5')
if bad:
    print('SANITY CHECK FAILED:'); [print(' -', b) for b in bad[:40]]
    sys.exit(1)
print('sanity ok:', len(L), 'LGAs')

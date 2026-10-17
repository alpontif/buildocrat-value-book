"""Score the model against independent benchmarks (static/benchmarks.json). Prints per-row ratios and log error."""
import json, pickle, sys, collections, numpy as np
from build_common import norm, SC
P = json.load(open('out/places_raw.json')); M = pickle.load(open('out/model.pkl','rb')); LG = json.load(open('static/lgas_full.json'))
pv = np.array(M['pv']); tier = np.array(M['tier'])
B = json.load(open('static/benchmarks.json'))['rows']
TY = {'city':0,'town':1,'suburb':2,'quarter':3,'neighbourhood':4,'estate':5,'gated':6,'village':7,'hamlet':8,'locality':9}
lat = np.array([p['lat'] for p in P]); lng = np.array([p['lng'] for p in P]); st = np.array([p['st'] for p in P])
URB = np.isin([p['type'] for p in P], ['city','town','suburb','quarter','neighbourhood'])
name_ix = collections.defaultdict(list)
for j,p in enumerate(P): name_ix[(p['st'], norm(p['name']))].append(j)
def km(j, la, lo): return np.hypot((lat[j]-la)*110.6, (lng[j]-lo)*109.5)
rows = []
for s_, nm, kind, val, src in B:
    sts = s_.split('|')
    if kind == 'farm':
        if nm == '*': lv = [g['v']['farm'] for g in M['lg_out'] if g['s'] in sts]
        else: lv = [g['v']['farm'] for g in M['lg_out'] if g['s'] in sts and norm(g['n']) in {norm(x) for x in nm.split('|')}]
        got = float(np.median(lv)); rows.append((s_, nm, kind, val, got, np.log(got/val))); continue
    if kind == 'rural':
        if nm == '*': m = np.isin(st, sts)
        else:
            lg = {i for i,l in enumerate(LG) if l['state'] in sts and norm(l['name']) in {norm(x) for x in nm.split('|')}}
            m = np.isin([p['lga'] for p in P], list(lg))
        m = m & (tier >= 4)
        if not m.any(): print('no match', nm); continue
        got = float(np.median(pv[m]))
    else:
        c = name_ix.get((sts[0], norm(nm)), [])
        if not c: print('no match', s_, nm); continue
        j = min(c, key=lambda j: TY.get(P[j]['type'], 9))
        if kind == 'city':
            m = URB & (np.hypot((lat-lat[j])*110.6, (lng-lng[j])*109.5) <= 8)
            got = float(np.median(pv[m])) if m.any() else float(pv[j])
        else: got = float(pv[j])
    rows.append((s_, nm, kind, val, got, np.log(got/val)))
e = np.array([r[5] for r in rows])
if '-q' not in sys.argv:
    for r in rows: print(f"{r[0]:9} {r[1][:26]:26} {r[2]:5} bench {r[3]:>9,.0f}  model {r[4]:>11,.0f}  x{np.exp(r[5]):5.2f}")
def grp(k): x = np.array([r[5] for r in rows if r[2]==k]); return f"{k} n={len(x)} median x{np.exp(np.median(x)):.2f} mean|log| {np.mean(np.abs(x)):.2f}"
nonLA = np.array([r[5] for r in rows if r[0] not in ('LA','FC') and r[2]!='farm'])
e = np.array([r[5] for r in rows if r[2]!='farm'])
print(f"ALL n={len(e)} median ratio x{np.exp(np.median(e)):.2f}  mean|log err| {np.mean(np.abs(e)):.2f}  within x2 {np.mean(np.abs(e)<np.log(2)):.0%} | outside LA/FC median x{np.exp(np.median(nonLA)):.2f} mean|log| {np.mean(np.abs(nonLA)):.2f}")
print(' | '.join(grp(k) for k in ('place','city','rural','farm')))
print('holdout (listing nodes):', M['holdout'])

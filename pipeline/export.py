import json, pickle, math, collections, os, datetime
os.chdir(os.path.dirname(os.path.abspath(__file__)))
OUT = '../docs/data/'; os.makedirs(OUT, exist_ok=True)
CFG = json.load(open('../site-config.json'))
RUN = json.load(open('raw/run.json')) if os.path.exists('raw/run.json') else {}
import numpy as np
from geo import dp, rings_of
from build_common import *

M = pickle.load(open('out/model.pkl','rb'))
P = json.load(open('out/places_raw.json'))
E = json.load(open('out/evidence_raw.json'))
lg_out, pv, pconf = M['lg_out'], M['pv'], M['pconf']
TYPEI = {'city':0,'town':1,'suburb':2,'quarter':3,'neighbourhood':4,'village':5,'hamlet':6,'locality':7,'estate':8,'gated':9}
ZONE, TIER = M['zone'], M['tier']

def enc(r, tol):
    s = dp(r, tol); s = [(round(x*1000), round(y*1000)) for x,y,*_ in s]
    out=[]; px=py=0
    for x,y in s:
        if out and x==px and y==py: continue
        out.append(f"{x-px},{y-py}"); px,py=x,y
    return ' '.join(out) if len(out) >= 4 else None

def rv(v, d=3):
    if v is None or not math.isfinite(v): return None
    if v == 0: return 0
    p = 10**max(0, int(math.floor(math.log10(abs(v)))) - d + 1)
    return int(round(v/p)*p)

lgas=[]
for g in lg_out:
    if g['cls']=='Metro core': g['v']['farm']=None
    rs=[e for e in (enc(r,0.004) for r in g['rings']) if e]
    lgas.append({'n':g['n'],'s':g['s'],'cls':g['cls'],'lat':round(g['lat'],4),'lng':round(g['lng'],4),'km2':g['km2'],'plot':g['plot'],
                 'v':{k:rv(v) for k,v in g['v'].items()},'ev':g['ev'],'conf':g['conf'],'np':g['np'],'r':rs,
                 'zs':[[z,n,rv(a),rv(b),rv(c),rv(d)] for z,n,a,b,c,d in g.get('zs',[])]})

# borders (states)
s1 = json.load(open('static/ADM1.geojson'))['features']
borders=[]
for f in s1:
    c = {'Abuja Federal Capital Territory':'FC'}.get(f['properties']['shapeName'])
    c = c or [k for k,v in SC.items() if v==f['properties']['shapeName']][0]
    borders.append({'c':c,'r':[e for e in (enc(r,0.006) for r in rings_of(f['geometry'])) if e]})

# states summary
counts = collections.Counter(o['st'] for o in E['obs'])
states=[]
for c in sorted(SC):
    gi=[i for i,g in enumerate(lg_out) if g['s']==c]
    # capital: LGA containing capital coordinate -> use places near the capital (within 8 km), urban types
    la,lo = CAP_LL[c]
    near=[j for j,p in enumerate(P) if p['st']==c and hav(la,lo,p['lat'],p['lng'])<=8 and p['type'] in ('city','town','suburb','quarter','neighbourhood')]
    capv = float(np.median([pv[j] for j in near])) if near else max(lg_out[i]['v']['res'] for i in gi)
    rur=[pv[j] for j,p in enumerate(P) if p['st']==c and p['type'] in ('village','hamlet','locality')]
    # derived values at the capital: scale nearest LGA's ratio values
    capL = min(gi, key=lambda i: hav(la,lo,lg_out[i]['lat'],lg_out[i]['lng']))
    base = lg_out[capL]['v']; r = capv/base['res']
    B = M['RM_beta']
    v = {'res':capv,'resR':float(np.median(rur)) if rur else None}
    for k,m in [('com','land_com'),('ind','land_ind'),('farm','land_farm'),('rent1','rent1'),('rent2','rent2'),('rent3','rent3'),('rent4','rent4'),
                ('sale2','sale2'),('sale3','sale3'),('sale4','sale4'),('sale5','sale5'),('crent','com_rent_m2')]:
        b = B.get(m) or 1.0
        v[k] = base[k]*r**b if base.get(k) else None
    # farmland: state median of rural LGAs rather than capital
    fv=[lg_out[i]['v']['farm'] for i in gi if lg_out[i]['v'].get('farm')]
    v['farm'] = float(np.median(fv)) if fv else None
    ev = sum(1 for o in E['obs'] if o['st']==c and o['m']=='land_res' and hav(la,lo,o['lat'],o['lng'])<=15)
    conf = 0 if ev>=30 else 1 if ev>=8 else 2 if ev>=2 else 3
    xs=[p[0] for i in gi for rr in lg_out[i]['rings'] for p in rr]; ys=[p[1] for i in gi for rr in lg_out[i]['rings'] for p in rr]
    # economic zones across the state: listing-count-weighted medians of the LGA zone rows
    zs=[]
    for z in range(7):
        rows=[r for i in gi for r in lg_out[i].get('zs',[]) if r[0]==z]
        if not rows: continue
        n=sum(r[1] for r in rows)
        def wmed(k):
            vals=sorted((r[k],r[1]) for r in rows if r[k] is not None)
            if not vals: return None
            acc=0
            for v_,w_ in vals:
                acc+=w_
                if acc>=sum(w for _,w in vals)/2: return rv(v_)
        zs.append([z,n,wmed(2),wmed(3),wmed(4),wmed(5)])
    states.append({'c':c,'zs':zs,'cap':CAPITAL[c],'lat':la,'lng':lo,'v':{k:rv(x) for k,x in v.items()},'nl':counts.get(c,0),'np':sum(1 for p in P if p['st']==c),'conf':conf,'bb':[round(min(xs),3),round(min(ys),3),round(max(xs),3),round(max(ys),3)]})

nobs=len(E['obs'])
cnt=collections.Counter(o['m'] for o in E['obs'])
meta={'zones':['Prime','High-income','Middle-income','Lower-income','Small town','Village','Remote / farmland'],'date':RUN.get('date') or datetime.date.today().isoformat(),'fx':RUN.get('fx') or CFG['fx_fallback'],'fxNote':RUN.get('fxNote',''),'build':RUN.get('build') or CFG['build_rate_fallback'],'avgMonth':RUN.get('avgMonth',''),'edition':RUN.get('edition',''),
      'beta':{'com':1.0,'ind':0.7,'farm':0.4,'rent2':(M['RM_beta'].get('rent2') or 0.4),'rent3':(M['RM_beta'].get('rent3') or 0.4),'sale3':(M['RM_beta'].get('sale3') or 0.5),'sale4':(M['RM_beta'].get('sale4') or 0.5)},
      'nListings': nobs,
      'counts':{'land_res':cnt['land_res'],'land_com':cnt['land_com'],'land_ind':cnt['land_ind'],'land_farm':cnt['land_farm']+cnt['land_tract'],'rent':sum(cnt[k] for k in ('rent1','rent2','rent3','rent4')),'sale':sum(cnt[k] for k in ('sale2','sale3','sale4','sale5'))},
      'fit':{'within2':M['holdout'][0],'n':M['holdout'][1]}}
for k in ('rent1','rent4','sale2','sale5'): meta['beta'][k]=M['RM_beta'].get(k) or 0.4
for k in ('rent1','rent2','rent3','rent4','sale2','sale3','sale4','sale5'): meta['beta'][k]=max(0.15,min(0.9,meta['beta'][k]))
json.dump({'states':states,'lgas':lgas,'borders':borders,'meta':meta}, open(OUT+'lgas.json','w'), separators=(',',':'))

# places columnar, sorted by LGA then latitude; coordinates delta-encoded. split_data publishes the chunks.
order = sorted(range(len(P)), key=lambda j:(P[j]['lga'], round(P[j]['lat']*1e4), round(P[j]['lng']*1e4)))
wards = {}; W=[]
pl={'n':[],'t':[],'la':[],'lo':[],'g':[],'v':[],'c':[],'w':[],'z':[]}
pla=plo=0
for j in order:
    p=P[j]
    la=round(p['lat']*1e4); lo=round(p['lng']*1e4)
    pl['la'].append(la-pla); pl['lo'].append(lo-plo); pla,plo=la,lo
    pl['n'].append(p['name']); pl['t'].append(TYPEI[p['type']]); pl['g'].append(p['lga'])
    pl['v'].append(rv(pv[j],2)); pl['c'].append(pconf[j]); pl['z'].append(ZONE[j])
    wk=(p['lga'], p.get('ward') or '')
    if wk not in wards: wards[wk]=len(W); W.append(wk[1])
    pl['w'].append(wards[wk])
pl['W']=W
pl['ap']=[k for k,j in enumerate(order) if P[j].get('ap')]   # estates placed from listing addresses (approximate)
# hierarchy: City > District/Area > Neighbourhood > Gated estate/area (parent = nearest higher level within reach)
from scipy.spatial import cKDTree
pos = {j:k for k,j in enumerate(order)}
CXk = math.cos(math.radians(9))*111.32
XYp = np.array([[P[j]['lng']*CXk, P[j]['lat']*110.57] for j in order])
tk = [TYPEI[P[j]['type']] for j in order]; stk = [P[j]['st'] for j in order]
def tree_of(types):
    ids = np.array([k for k,t in enumerate(tk) if t in types]); return (cKDTree(XYp[ids]), ids) if len(ids) else (None, ids)
TR = {name: tree_of(ts) for name, ts in [('nb',{4}),('dist',{2,3}),('city',{0}),('town',{1}),('vil',{5})]}
# candidate parent levels with their reach (km); the nearest relative to its reach wins
# groups are tried in order (finest first); within a group the nearest relative to its reach wins
RULES = {8:[[('nb',1.0),('dist',1.5)],[('town',4)],[('city',12)]], 9:[[('nb',1.0),('dist',1.5)],[('town',4)],[('city',12)]],
         4:[[('dist',2.0)],[('town',4)],[('city',12)]], 2:[[('town',5)],[('city',20)]], 3:[[('town',5)],[('city',20)]], 6:[[('vil',2.5)]], 7:[[('vil',2.5)],[('town',5)]]}
pk, pp = [], []
for k,t in enumerate(tk):
    best = None
    for group in RULES.get(t, []):
        for name, rad in group:
            tr, ids = TR[name]
            if tr is None: continue
            d, i = tr.query(XYp[k], k=3, distance_upper_bound=rad)
            for dd, ii in zip(np.atleast_1d(d), np.atleast_1d(i)):
                if np.isfinite(dd) and ids[ii] != k and stk[ids[ii]] == stk[k]:
                    sc = dd/rad
                    if best is None or sc < best[0]: best = (sc, int(ids[ii]))
                    break
        if best: break
    if best: pk.append(k); pp.append(best[1])
pl['pk'] = [pk[0]] + [pk[i]-pk[i-1] for i in range(1, len(pk))] if pk else []
pl['pp'] = pp
print('parents', len(pk))
print('places', len(pl['n']), 'wards', len(W))

# evidence nodes (all metrics, n>=3)
ev=[]
from model import nodes_for
for m in ['land_res','land_com','land_ind','land_farm','rent1','rent2','rent3','rent4','sale2','sale3','sale4','sale5']:
    for nd in nodes_for(m):
        if nd['n']<3: continue
        f = 10000 if m=='land_farm' else 1
        ev.append({'m':m,'st':nd['st'],'label':nd['label'],'lat':round(nd['lat'],4),'lng':round(nd['lng'],4),'n':nd['n'],'med':rv(nd['med']*f),'p25':rv(nd['p25']*f),'p75':rv(nd['p75']*f)})
from split_data import publish
publish({'states':states,'lgas':lgas,'borders':borders,'meta':meta}, pl, ev, os.path.abspath(OUT))
import os
for f in os.listdir(OUT): print(f, os.path.getsize(OUT+f))

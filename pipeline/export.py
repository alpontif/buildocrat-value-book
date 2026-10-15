import json, pickle, math, collections, os, base64, datetime
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
TYPEI = {'city':0,'town':1,'suburb':2,'quarter':3,'neighbourhood':4,'village':5,'hamlet':6,'locality':7}

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
                 'v':{k:rv(v) for k,v in g['v'].items()},'ev':g['ev'],'conf':g['conf'],'np':g['np'],'r':rs})

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
    for k,m in [('com','land_com'),('ind','land_ind'),('farm','land_farm'),('rent2','rent2'),('rent3','rent3'),('sale3','sale3'),('sale4','sale4'),('crent','com_rent_m2')]:
        b = B.get(m) or 1.0
        v[k] = base[k]*r**b if base.get(k) else None
    # farmland: state median of rural LGAs rather than capital
    fv=[lg_out[i]['v']['farm'] for i in gi if lg_out[i]['v'].get('farm')]
    v['farm'] = float(np.median(fv)) if fv else None
    ev = sum(1 for o in E['obs'] if o['st']==c and o['m']=='land_res' and hav(la,lo,o['lat'],o['lng'])<=15)
    conf = 0 if ev>=30 else 1 if ev>=8 else 2 if ev>=2 else 3
    xs=[p[0] for i in gi for rr in lg_out[i]['rings'] for p in rr]; ys=[p[1] for i in gi for rr in lg_out[i]['rings'] for p in rr]
    states.append({'c':c,'cap':CAPITAL[c],'lat':la,'lng':lo,'v':{k:rv(x) for k,x in v.items()},'nl':counts.get(c,0),'np':sum(1 for p in P if p['st']==c),'conf':conf,'bb':[round(min(xs),3),round(min(ys),3),round(max(xs),3),round(max(ys),3)]})

nobs=len(E['obs'])
cnt=collections.Counter(o['m'] for o in E['obs'])
meta={'date':RUN.get('date') or datetime.date.today().isoformat(),'fx':RUN.get('fx') or CFG['fx_fallback'],'fxNote':RUN.get('fxNote',''),'build':RUN.get('build') or CFG['build_rate_fallback'],'avgMonth':RUN.get('avgMonth',''),'edition':RUN.get('edition',''),
      'beta':{'com':1.0,'ind':0.7,'farm':0.4,'rent2':(M['RM_beta'].get('rent2') or 0.4),'rent3':(M['RM_beta'].get('rent3') or 0.4),'sale3':(M['RM_beta'].get('sale3') or 0.5),'sale4':(M['RM_beta'].get('sale4') or 0.5)},
      'nListings': nobs,
      'counts':{'land_res':cnt['land_res'],'land_com':cnt['land_com'],'land_ind':cnt['land_ind'],'land_farm':cnt['land_farm']+cnt['land_tract'],'rent':sum(cnt[k] for k in ('rent1','rent2','rent3','rent4')),'sale':sum(cnt[k] for k in ('sale2','sale3','sale4','sale5'))},
      'fit':{'within2':M['holdout'][0],'n':M['holdout'][1]}}
for k in ('rent2','rent3','sale3','sale4'): meta['beta'][k]=max(0.15,min(0.9,meta['beta'][k]))
json.dump({'states':states,'lgas':lgas,'borders':borders,'meta':meta}, open(OUT+'lgas.json','w'), separators=(',',':'))

# places columnar, sorted by LGA then latitude; coordinates delta-encoded; gzip
import gzip
order = sorted(range(len(P)), key=lambda j:(P[j]['lga'], round(P[j]['lat']*1e4), round(P[j]['lng']*1e4)))
wards = {}; W=[]
pl={'n':[],'t':[],'la':[],'lo':[],'g':[],'v':[],'c':[],'w':[]}
pla=plo=0
for j in order:
    p=P[j]
    la=round(p['lat']*1e4); lo=round(p['lng']*1e4)
    pl['la'].append(la-pla); pl['lo'].append(lo-plo); pla,plo=la,lo
    pl['n'].append(p['name']); pl['t'].append(TYPEI[p['type']]); pl['g'].append(p['lga'])
    pl['v'].append(rv(pv[j],2)); pl['c'].append(pconf[j])
    wk=(p['lga'], p.get('ward') or '')
    if wk not in wards: wards[wk]=len(W); W.append(wk[1])
    pl['w'].append(wards[wk])
pl['W']=W
raw=json.dumps(pl, separators=(',',':'), ensure_ascii=False).encode('utf-8')
gzb=gzip.compress(raw, 9, mtime=0)
open(OUT+'places.b64.txt','w').write(base64.b64encode(gzb).decode())
print('places raw', len(raw), 'gz', len(gzb), 'wards', len(W))

# evidence nodes (all metrics, n>=3)
ev=[]
from model import nodes_for
for m in ['land_res','land_com','land_ind','land_farm','rent2','rent3','sale3','sale4']:
    for nd in nodes_for(m):
        if nd['n']<3: continue
        f = 10000 if m=='land_farm' else 1
        ev.append({'m':m,'st':nd['st'],'label':nd['label'],'lat':round(nd['lat'],4),'lng':round(nd['lng'],4),'n':nd['n'],'med':rv(nd['med']*f),'p25':rv(nd['p25']*f),'p75':rv(nd['p75']*f)})
json.dump(ev, open(OUT+'evidence.json','w'), separators=(',',':'), ensure_ascii=False)
import os
for f in os.listdir(OUT): print(f, os.path.getsize(OUT+f))

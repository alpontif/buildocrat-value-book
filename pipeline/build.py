"""Build the Nigeria Land Value Book dataset.
Inputs: static/ (GRID3 settlements, OSM places, LGA polygons) and raw/ (weekly crawls: lb_npc_land.json, lb_jiji.json, lb_npc_avg.json).
Outputs: out/*.json for the page, plus diagnostics.
"""
import json, math, re, collections, sys, os
import numpy as np
from scipy.spatial import cKDTree
from geo import pip, dp

HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
def F(fn):
    """Crawled files live in raw/, fixed reference data in static/."""
    return 'raw/'+fn if os.path.exists('raw/'+fn) else 'static/'+fn
os.makedirs('out', exist_ok=True)

from build_common import *

# ---------------- LGAs ----------------
LG = json.load(open('static/lgas_full.json'))
for i, l in enumerate(LG):
    l['i'] = i
    xs=[p[0] for r in l['rings'] for p in r]; ys=[p[1] for r in l['rings'] for p in r]
    l['bb'] = (min(xs), min(ys), max(xs), max(ys))
cell = collections.defaultdict(list)
for l in LG:
    x0,y0,x1,y1 = l['bb']
    for gx in range(int(x0*4), int(x1*4)+1):
        for gy in range(int(y0*4), int(y1*4)+1):
            cell[(gx,gy)].append(l['i'])
def lga_at(lat, lng):
    for i in cell.get((int(lng*4), int(lat*4)), []):
        l = LG[i]; x0,y0,x1,y1 = l['bb']
        if x0<=lng<=x1 and y0<=lat<=y1 and any(pip(lng, lat, r) for r in l['rings']): return i
    return None

# ---------------- Places: GRID3 settlement register + OSM urban places ----------------
TYPES = {'city':0,'town':1,'suburb':2,'quarter':3,'neighbourhood':4,'village':5,'hamlet':6,'locality':7}
osm = []; seen=set()
for fn in ('lb_osm.txt','lb_osm_urban.txt'):
    if not os.path.exists(F(fn)): continue
    for line in open(F(fn), encoding='utf-8'):
        p = line.rstrip('\n').split('|')
        if len(p) < 4 or not p[2] or p[3] not in TYPES: continue
        try: la, lo = float(p[0]), float(p[1])
        except: continue
        k = (round(la,3), round(lo,3), norm(p[2]))
        if k in seen: continue
        seen.add(k); osm.append({'lat':la,'lng':lo,'name':p[2].strip(),'type':p[3],'src':'osm'})
print('osm places', len(osm))
grid = []
if os.path.exists(F('lb_grid3.txt')):
    for line in open(F('lb_grid3.txt'), encoding='utf-8'):
        p = line.rstrip('\n').split('|')
        if len(p) < 6 or not p[0].strip(): continue
        try: la, lo = float(p[4]), float(p[5])
        except: continue
        grid.append({'lat':la,'lng':lo,'name':p[0].strip(),'ward':p[1].strip(),'lganame':p[2].strip(),'stc':p[3].strip(),'type':'village','src':'grid3'})
print('grid3 settlements', len(grid))
# OSM urban types override GRID3 points of the same name within 2 km; OSM places with no GRID3 twin are added
from scipy.spatial import cKDTree as _T
places = grid[:]
if grid:
    GX = np.array([[g['lng'],g['lat']] for g in grid]); gt=_T(GX)
    for o in osm:
        hit=None
        for j in gt.query_ball_point([o['lng'],o['lat']], 0.02):
            if norm(grid[j]['name'])==norm(o['name']): hit=j; break
        if hit is not None:
            if TYPES[o['type']] < TYPES[grid[hit]['type']]: grid[hit]['type']=o['type']
        elif o['type'] in ('city','town','suburb','quarter','neighbourhood') or not grid:
            places.append(o)
else:
    places = osm
for p in places:
    p['lga'] = lga_at(p['lat'], p['lng'])
places = [p for p in places if p['lga'] is not None]
for p in places: p['st'] = LG[p['lga']]['state']
# urban / rural for GRID3 points without an OSM urban type: dense clusters near a city or town are urban neighbourhoods
PX=np.array([[p['lng']*math.cos(math.radians(9))*111.32, p['lat']*110.57] for p in places]); ptree=_T(PX)
U=np.array([PX[j] for j,p in enumerate(places) if p['type'] in ('city','town')]); utree=_T(U)
dens = np.array([len(x) for x in ptree.query_ball_point(PX, 1.5)])
du,_ = utree.query(PX)
for j,p in enumerate(places):
    p['d15']=int(dens[j]); p['du']=float(du[j])
    if p['src']=='grid3' and p['type']=='village':
        if dens[j]>=14 or (dens[j]>=8 and du[j]<=8): p['type']='neighbourhood'
        elif dens[j]<=2 and du[j]>15: p['type']='hamlet'
print('in Nigeria', len(places), collections.Counter(p['type'] for p in places))

# name index per state
idx = collections.defaultdict(list)
for j,p in enumerate(places):
    idx[(p['st'], norm(p['name']))].append(j)
ward_pts = collections.defaultdict(list)
for p in places:
    if p.get('ward'): ward_pts[(p['st'], norm(p['ward']))].append((p['lat'],p['lng']))
ward_idx = {k:(float(np.mean([a for a,b in v])), float(np.mean([b for a,b in v]))) for k,v in ward_pts.items()}
lga_idx = collections.defaultdict(list)
for l in LG: lga_idx[(l['state'], norm(l['name']))].append(l['i'])

def geocode(state, names, near=None, maxkm=40):
    """names: candidate strings, most specific first. Returns (lat,lng,label,level) or None."""
    ex=[]
    for nm in names:
        ex.append(nm)
        for part in re.split(r"[/,]| - ", nm or ''):
            if part.strip() and part.strip()!=nm: ex.append(part)
        ex.append(re.sub(r"\b(gra|road|rd|expressway|express|junction|new|old|main)\b", " ", nm or '', flags=re.I))
    for nm in ex:
        k = norm(nm)
        if not k or len(k) < 3: continue
        cands = idx.get((state, k), [])
        if cands:
            # prefer bigger place types, and closeness to `near`
            def score(j):
                p=places[j]; s=TYPES[p['type']]
                if near: s += hav(near[0],near[1],p['lat'],p['lng'])/10
                return s
            j = min(cands, key=score); p = places[j]
            if near and hav(near[0],near[1],p['lat'],p['lng']) > maxkm: continue
            return (p['lat'], p['lng'], p['name'], 'place')
        w = ward_idx.get((state, k))
        if w and (not near or hav(near[0],near[1],w[0],w[1]) <= maxkm):
            return (w[0], w[1], nm.strip()+' ward', 'ward')
        li = lga_idx.get((state, k), [])
        if li:
            l = LG[li[0]]
            if near and hav(near[0],near[1],l['lat'],l['lng']) > maxkm+30: continue
            return (l['lat'], l['lng'], l['name']+' LGA', 'lga')
    return None

# ---------------- Listings ----------------
def plot_size(title, desc, chip):
    if chip and chip >= 50: return chip
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(?:sqm|sq\.?\s?m(?:tr|t)?s?|square\s*met(?:er|re)s?|m2|m²)\b", title or '', re.I)
    if m: return float(m.group(1).replace(',',''))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:hectares?|ha)\b", title or '', re.I)
    if m: return float(m.group(1))*10000
    m = re.search(r"(\d+(?:\.\d+)?)\s*acres?\b", title or '', re.I)
    if m: return float(m.group(1))*4046.86
    al = [float(z.replace(',','')) for z in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*(?:sqm|sq\.?\s?m(?:tr|t)?s?|square\s*met(?:er|re)s?|m2|m²)\b", desc or '', re.I)]
    al = [v for v in al if v >= 100]
    if len(set(al)) == 1: return al[0]
    return None

def land_class(kind, title):
    k = (kind or '').lower(); t = (title or '').lower()
    if 'farm' in k or re.search(r"\bfarm", t): return 'farm'
    if 'industrial' in k or re.search(r"industrial|warehouse|factory|tank farm", t): return 'ind'
    if 'commercial' in k or 'mixed' in k or re.search(r"commercial|filling station|petrol station|plaza|hotel site", t): return 'com'
    return 'res'

obs = []   # evidence observations: dict(st, lat,lng, label, level, metric, value, src)
def add(st, g, metric, value, src):
    obs.append({'st':st,'lat':g[0],'lng':g[1],'label':g[2],'level':g[3],'m':metric,'v':value,'src':src})

# NPC land
R = json.load(open(F('lb_npc_land.json'), encoding='utf-8'))
seenh=set(); stats=collections.Counter()
locgeo = {}
for x in R:
    if x['href'] in seenh: stats['dup']+=1; continue
    seenh.add(x['href'])
    st = SLUG2C.get(x['state']);  b = (x.get('basis') or '').lower()
    if not st: continue
    cls = land_class(x.get('kind'), x.get('title'))
    size = plot_size(x.get('title'), x.get('desc'), x.get('chip'))
    price = x['price']
    if 'per sq.m' in b: ppm = price
    elif 'per acre' in b: ppm = price/4046.86; size = size or 4046.86
    elif 'per hectare' in b: ppm = price/10000; size = size or 10000
    elif 'per sq.ft' in b: ppm = price*10.764
    elif size: ppm = price/size
    else: stats['nosize']+=1; continue
    if 'per plot' in b and not (150 <= size <= 1200): stats['badplot']+=1; continue
    if not (100 <= (size or 600) <= 5e6) or not (50 <= ppm <= 2.5e7): stats['range']+=1; continue
    if cls != 'farm' and size and size > 40000: cls = 'tract'
    # geocode: address parts (most specific first), then NPC locality slug
    loc = x['loc'].replace('-', ' ')
    if (st, loc) not in locgeo: locgeo[(st,loc)] = geocode(st, [loc], near=CAP_LL[st], maxkm=400)
    base = locgeo[(st,loc)]
    parts = [s.strip() for s in (x.get('addr') or '').split(',') if s.strip()]
    parts = [s for s in parts if norm(s) not in (norm(SC[st]), 'abuja', 'lagos')]
    g = geocode(st, parts[:-1] if len(parts) > 1 else [], near=base[:2] if base else CAP_LL[st], maxkm=25) or base
    if not g: stats['nogeo']+=1; continue
    metric = {'res':'land_res','com':'land_com','ind':'land_ind','farm':'land_farm','tract':'land_tract'}[cls]
    add(st, g, metric, ppm, 'npc'); stats['ok']+=1
print('npc land', dict(stats))

# Jiji
J = json.load(open(F('lb_jiji.json'), encoding='utf-8'))
stats=collections.Counter(); rgeo={}
for x in J:
    st = SLUG2C.get(x['st'])
    if not st or not x.get('p'): continue
    key=(st, x.get('r'), x.get('rp'))
    if key not in rgeo:
        rp = x.get('rp') or ''
        base = geocode(st, [rp], near=CAP_LL[st], maxkm=400) if 'State' not in rp and 'FCT' not in rp else None
        rgeo[key] = geocode(st, [x.get('r') or ''], near=base[:2] if base else CAP_LL[st], maxkm=60 if base else 400) or base
    g = rgeo[key]
    if not g: stats['nogeo']+=1; continue
    c = x['c']; p = x['p']; per = (x.get('per') or '').lower(); t = x.get('t') or ''
    if c == 'ls':
        sqm = x.get('sqm')
        cls = land_class('', t)
        if 'per sqm' in per: ppm = p
        elif 'per sqf' in per: ppm = p*10.764
        elif sqm and sqm >= 100: ppm = p/sqm
        else: stats['ls_nosize']+=1; continue
        if not (50 <= ppm <= 2.5e7): stats['range']+=1; continue
        if cls != 'farm' and sqm and sqm > 40000: cls='tract'
        add(st, g, {'res':'land_res','com':'land_com','ind':'land_ind','farm':'land_farm','tract':'land_tract'}[cls], ppm, 'jiji'); stats['ls']+=1
    elif c == 'hr':
        b = x.get('b')
        mult = {'per annum':1,'':1,'per month':12,'per half-year':2,'per quarter':4}.get(per)
        if not mult or not b: continue
        rent = p*mult
        if not (1.0e5 <= rent <= 3e8): continue
        if b in (1,2,3,4): add(st, g, f'rent{b}', rent, 'jiji'); stats['hr']+=1
    elif c == 'hs':
        b = x.get('b')
        if b in (2,3,4,5) and 2e6 <= p <= 1e10: add(st, g, f'sale{b}', p, 'jiji'); stats['hs']+=1
    elif c in ('crc','csc'):
        sqm = x.get('sqm')
        if sqm and 10 <= sqm <= 20000 and re.search(r"rent|let|lease", t, re.I) and not re.search(r"sale", t, re.I):
            v = p/sqm
            if 500 <= v <= 5e5: add(st, g, 'com_rent_m2', v, 'jiji'); stats['crent']+=1
print('jiji', dict(stats))

# NPC average-price tables (locality medians, each weighted by its listing count)
AVG = json.load(open(F('lb_npc_avg.json'), encoding='utf-8'))
MAP = {'for-sale|houses|4':'sale4','for-sale|flats-apartments|3':'sale3','for-rent|houses|4':'rent4','for-rent|flats-apartments|3':'rent3','for-rent|flats-apartments|2':'rent2'}
agg_rows = []
for k, v in AVG.items():
    m, t, b, s = k.split('|'); st = SLUG2C.get(s); metric = MAP[f'{m}|{t}|{b}']
    for name, val, rng, n in v['rows']:
        if not val or n < 3: continue
        g = geocode(st, [name.replace('(VI)','').replace('Berger, Arepo','Arepo')], near=CAP_LL[st], maxkm=400)
        if g: agg_rows.append({'st':st,'lat':g[0],'lng':g[1],'label':g[2],'level':g[3],'m':metric,'v':val,'n':n,'src':'npcavg'})
print('npc avg rows', len(agg_rows))

json.dump({'obs':obs,'agg':agg_rows}, open('out/evidence_raw.json','w'))
json.dump(places, open('out/places_raw.json','w'))
print('obs', len(obs), collections.Counter(o['m'] for o in obs))

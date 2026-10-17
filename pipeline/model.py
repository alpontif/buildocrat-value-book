"""Valuation model (vectorised): evidence nodes -> hedonic-spatial model -> values anywhere."""
import json, math, collections, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy.spatial import cKDTree
from build_common import *

E = json.load(open('out/evidence_raw.json')); P = json.load(open('out/places_raw.json'))
LG = json.load(open('static/lgas_full.json'))
obs, agg = E['obs'], E['agg']
CXK = math.cos(math.radians(9))*111.32; CYK = 110.57
def XY(lat, lng): return np.column_stack([np.asarray(lng,float)*CXK, np.asarray(lat,float)*CYK])
PX = XY([p['lat'] for p in P], [p['lng'] for p in P])
tree = cKDTree(PX[[i for i,p in enumerate(P) if p['type'] not in ('estate','gated')]])  # estates are not extra settlements
URBT = ('city','town','suburb','quarter','neighbourhood')
utree = cKDTree(PX[[i for i,p in enumerate(P) if p['type'] in URBT]])
STATES = sorted(CAP_LL); SI = {s:i for i,s in enumerate(STATES)}
CAPXY = {s: XY([CAP_LL[s][0]],[CAP_LL[s][1]])[0] for s in STATES}
METXY = XY([m[1] for m in METRO],[m[2] for m in METRO])

# Geopolitical zones: a state with few listings leans on its own region's level, not on a national pattern that
# Lagos and Abuja dominate. Lagos and the FCT have so much data that they stand on their own state terms.
REGIONS = {'NW':'KN KD KT KE SK ZA JI','NE':'AD BA BR GM TA YB','NC':'BE KG KW NA NI PL','SW':'EK OG ON OS OY','SE':'AB AN EB EN IM','SS':'AK BY CR DE ED RI'}
REG = {s: i for i,(r,ss) in enumerate(REGIONS.items()) for s in ss.split()}
NREG = len(REGIONS)
def feats(lat, lng, st):
    Q = XY(lat, lng); st = list(st)
    capd = np.array([np.linalg.norm(Q[i]-CAPXY[s]) for i,s in enumerate(st)])
    dm = np.min(np.linalg.norm(Q[:,None,:]-METXY[None,:2,:],axis=2),axis=1)
    dm3 = np.min(np.linalg.norm(Q[:,None,:]-METXY[None,:4,:],axis=2),axis=1)   # Kano has too few listings to carry a metro premium learned elsewhere
    n3 = tree.query_ball_point(Q, 3.0, return_length=True)
    u3 = utree.query_ball_point(Q, 3.0, return_length=True)
    du,_ = utree.query(Q)
    F = np.column_stack([np.log1p(capd), np.log1p(dm), np.log1p(dm3), np.log1p(n3), np.log1p(u3), np.log1p(du)])
    R = np.zeros((len(st), len(REGIONS))); 
    for i,s in enumerate(st):
        if REG.get(s) is not None: R[i, REG[s]] = 1
    S = np.zeros((len(st), len(STATES))); S[np.arange(len(st)), [SI[s] for s in st]] = 1
    return np.column_stack([np.ones(len(st)), F, R, S])

def robust(vals):
    v = np.log(np.array(vals))
    if len(v) >= 6:
        q1,q3 = np.percentile(v,[25,75]); iqr=q3-q1; v = v[(v>=q1-1.5*iqr)&(v<=q3+1.5*iqr)]
    return float(np.exp(np.median(v))), float(np.exp(np.percentile(v,25))), float(np.exp(np.percentile(v,75))), len(v)

# Calibration (checked against independent market benchmarks with calib.py):
# CWQ  - listings located only to a whole city/town/LGA are a mix of that place's markets, skewed to premium
#        listings; they stand for the place at this percentile of their prices, not the median.
# CWW  - and count for this share of their listings.
# NCAP - no single evidence point counts for more than this many listings when spreading to its neighbours.
CWQ = float(os.environ.get('LVB_CWQ', 35)); CWW = float(os.environ.get('LVB_CWW', 0.4)); NCAP = float(os.environ.get('LVB_NCAP', 12))
def nodes_for(metric):
    g = collections.defaultdict(list); meta = {}
    for o in obs:
        if o['m'] != metric: continue
        k = (o['st'], round(o['lat'],3), round(o['lng'],3), o.get('cw',0)); g[k].append(o['v']); meta[k]=o
    for a in agg:
        if a['m'] != metric: continue
        k = (a['st'], round(a['lat'],3), round(a['lng'],3), 0)
        g[k].extend([a['v']]*min(a['n'],40)); meta.setdefault(k, a)
    out=[]
    for k, vals in g.items():
        med,p25,p75,n = robust(vals); o=meta[k]
        if k[3]:
            med = float(np.exp(np.percentile(np.log(vals), CWQ))); n = max(1, int(round(n*CWW)))
        out.append({'st':k[0],'lat':o['lat'],'lng':o['lng'],'label':o['label'],'level':o['level'],'med':med,'p25':p25,'p75':p75,'n':n,'cw':k[3]})
    return out

class Surface:
    """ridge hedonic model + two-scale smoothing of residuals (coarse h, fine h2), with outlier pruning"""
    def __init__(self, metric, lam=6.0, h=3.0, w0=8.0, h2=0.8, w2=3.0, nodes=None, prune=math.log(6)):
        nodes = nodes if nodes is not None else nodes_for(metric)
        for it in range(3):
            self._fit(nodes, lam)
            keep=[i for i,n in enumerate(nodes) if not (abs(self.res[i])>prune and n['n']<=3)]
            if len(keep)==len(nodes): break
            nodes=[nodes[i] for i in keep]
        self._fit(nodes, lam)
        self.nodes=nodes; nd=nodes
        self.NX = XY([n['lat'] for n in nd],[n['lng'] for n in nd]); self.nt = cKDTree(self.NX)
        self.n = np.minimum(np.array([n['n'] for n in nd], float), NCAP); self.st = np.array([n['st'] for n in nd])
        self.h=h; self.w0=w0; self.h2=h2; self.w2=w2
        # fine-scale residual after coarse smoothing (leave-one-out so a node does not explain itself)
        c,_ = self._smooth(self.NX, list(self.st), self.res, h, w0, exclude=np.arange(len(nd)))
        self.res2 = self.res - c
    def _fit(self, nd, lam):
        X = feats([n['lat'] for n in nd],[n['lng'] for n in nd],[n['st'] for n in nd])
        y = np.log([n['med'] for n in nd]); w = np.sqrt([n['n'] for n in nd])
        k = X.shape[1]; nf = k-len(STATES); pen=np.zeros(k); pen[nf:]=lam; pen[nf-NREG:nf]=1.0
        self.beta = np.linalg.solve((X*w[:,None]).T@X + np.diag(pen), (X*w[:,None]).T@y)
        self.res = y - X@self.beta
    def _smooth(self, Q, st, vals, h, w0, exclude=None):
        ws=np.zeros(len(Q)); rs=np.zeros(len(Q))
        for i,ids in enumerate(self.nt.query_ball_point(Q, h*4)):
            if not ids: continue
            ids=np.array(ids)
            if exclude is not None: ids=ids[ids!=exclude[i]]
            if not len(ids): continue
            d=np.linalg.norm(self.NX[ids]-Q[i],axis=1); wst=np.where(self.st[ids]==st[i],1.0,0.5)
            w=self.n[ids]*np.exp(-(d/h)**2)*wst; ws[i]=w.sum(); rs[i]=(w*vals[ids]).sum()
        return rs/(ws+w0), ws
    def at(self, lat, lng, st, exclude=None):
        lat=np.atleast_1d(lat); lng=np.atleast_1d(lng); st=list(np.atleast_1d(st))
        base = feats(lat,lng,st)@self.beta
        Q = XY(lat,lng)
        c, ws = self._smooth(Q, st, self.res, self.h, self.w0, exclude)
        f, _ = self._smooth(Q, st, self.res2, self.h2, self.w2, exclude)
        return np.exp(base + c + f), ws

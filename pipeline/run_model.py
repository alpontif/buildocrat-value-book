import json, math, collections, pickle, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy.spatial import cKDTree
from model import *

# ---------- residential land surface ----------
RES = Surface('land_res', lam=8.0, h=3.0, w0=8.0, h2=0.6, w2=2.0)
print('res nodes', len(RES.nodes), 'listings', int(RES.n.sum()))
# held-out check on market locations with 5+ listings (own node excluded from smoothing)
big = [i for i,n in enumerate(RES.nodes) if n['n']>=5]
pred,_ = RES.at([RES.nodes[i]['lat'] for i in big],[RES.nodes[i]['lng'] for i in big],[RES.nodes[i]['st'] for i in big], exclude=np.array(big))
err = np.abs(np.log(pred) - np.log([RES.nodes[i]['med'] for i in big]))
HOLD = (int(round(100*np.mean(err<math.log(2)))), len(big), float(np.median(err)))
print('holdout within x2 %d%% of %d locations; median abs log err %.2f' % HOLD)

class Ratio:
    """log(metric) = a + b*log(res) + state offset (ridge) + smoothed residual"""
    def __init__(self, metric, h=6.0, w0=6.0, lam=8.0):
        self.nodes = nodes_for(metric); nd=self.nodes
        lat=[n['lat'] for n in nd]; lng=[n['lng'] for n in nd]; st=[n['st'] for n in nd]
        r,_ = RES.at(lat,lng,st)
        S=np.zeros((len(nd),len(STATES))); S[np.arange(len(nd)),[SI[s] for s in st]]=1
        X=np.column_stack([np.ones(len(nd)), np.log(r), S]); y=np.log([n['med'] for n in nd]); w=np.sqrt([n['n'] for n in nd])
        pen=np.zeros(X.shape[1]); pen[2:]=lam
        self.beta=np.linalg.solve((X*w[:,None]).T@X+np.diag(pen),(X*w[:,None]).T@y)
        self.res=y-X@self.beta; self.NX=XY(lat,lng); self.nt=cKDTree(self.NX); self.n=np.array([n['n'] for n in nd],float); self.h=h; self.w0=w0
        print(metric,'nodes',len(nd),'listings',int(self.n.sum()),'elasticity %.2f'%self.beta[1])
    def at(self, lat, lng, st, resv):
        lat=np.atleast_1d(lat); lng=np.atleast_1d(lng); st=list(st)
        S=np.zeros((len(st),len(STATES))); S[np.arange(len(st)),[SI[s] for s in st]]=1
        base=np.column_stack([np.ones(len(st)), np.log(resv), S])@self.beta
        Q=XY(lat,lng); ws=np.zeros(len(Q)); rs=np.zeros(len(Q))
        for i,ids in enumerate(self.nt.query_ball_point(Q,self.h*4)):
            if not ids: continue
            ids=np.array(ids); d=np.linalg.norm(self.NX[ids]-Q[i],axis=1); w=self.n[ids]*np.exp(-(d/self.h)**2)
            ws[i]=w.sum(); rs[i]=(w*self.res[ids]).sum()
        return np.exp(base+rs/(ws+self.w0))

RM = {m: Ratio(m) for m in ['land_com','land_ind','land_farm','rent1','rent2','rent3','rent4','sale2','sale3','sale4','sale5','com_rent_m2']}

def values_at(lat, lng, st, resv):
    out={'res':resv}
    for m,k in [('land_com','com'),('land_ind','ind'),('land_farm','farm'),('rent1','rent1'),('rent2','rent2'),('rent3','rent3'),('rent4','rent4'),
                ('sale2','sale2'),('sale3','sale3'),('sale4','sale4'),('sale5','sale5'),('com_rent_m2','crent')]:
        out[k]=RM[m].at(lat,lng,st,resv)
    out['farm']=np.minimum(out['farm'], resv*0.5)*10000      # per hectare; farmland never above half the residential rate
    out['com']=np.maximum(out['com'], resv*1.0)
    out['ind']=np.clip(out['ind'], resv*0.35, resv*2.0)
    out['rent3']=np.maximum(out['rent3'], out['rent2']*1.2)
    out['sale4']=np.maximum(out['sale4'], out['sale3']*1.25)
    out['rent2']=np.maximum(out['rent2'], out['rent1']*1.15)
    out['rent4']=np.maximum(out['rent4'], out['rent3']*1.15)
    out['sale3']=np.maximum(out['sale3'], out['sale2']*1.15)
    out['sale5']=np.maximum(out['sale5'], out['sale4']*1.15)
    return out

# ---------- every place ----------
lat=np.array([p['lat'] for p in P]); lng=np.array([p['lng'] for p in P]); st=[p['st'] for p in P]
pv, pev = RES.at(lat,lng,st)
TADJ = {'city':1.0,'town':0.95,'suburb':1.0,'quarter':1.0,'neighbourhood':1.0,'village':0.6,'hamlet':0.45,'locality':0.5,'estate':1.2,'gated':1.12}
tadj = np.array([TADJ[p['type']] for p in P]) ** (1/(1+pev/10))
pv = pv*tadj

# ---------- settlement tier and small-town re-estimate ----------
# Tier: 0 metro (Lagos, Abuja, Port Harcourt, Ibadan, Kano), 1 state capital, 2 other city, 3 town, 4 village, 5 remote
QX = XY(lat, lng)
METR = np.array([35, 30, 20, 15, 15.0])
dmet = np.linalg.norm(QX[:,None,:]-METXY[None,:,:], axis=2); inmet = (dmet <= METR[None,:]).any(1); metid = np.argmin(dmet/METR[None,:], axis=1)
dcap = np.linalg.norm(QX - np.array([CAPXY[s] for s in st]), axis=1)
cityI = [i for i,p in enumerate(P) if p['type']=='city']; townI = [i for i,p in enumerate(P) if p['type']=='town']
dc, ci = cKDTree(QX[cityI]).query(QX); dt, ti = cKDTree(QX[townI]).query(QX)
isurb = np.array([p['type'] in ('city','town','suburb','quarter','neighbourhood','estate','gated') for p in P])
tier = np.where(inmet, 0, np.where(dcap <= 10, 1, np.where(dc <= 6, 2, np.where(dt <= 3, 3, np.where((dt <= 12) | (dc <= 15), 4, 5)))))
tier = np.where((tier==3) & ~isurb & (dt > 1.5), 4, tier)   # villages beside a town stay villages
# Held-out test: with no listings nearby the model over-reads towns (x1.25) and state capitals (x1.47).
# Undo that where the place has little evidence of its own, then remove the listing premium that
# estate schemes add to small-town and village asking prices.
w = 1/(1+pev/10)
BIAS = np.array([1.0, 1.47, 1.0, 1.25, 1.0, 1.0]); HAIR = np.array([1.0, 1.0, 1.0, 0.85, 0.8, 0.7])
pv = pv / BIAS[tier]**w * HAIR[tier]
# A state's premium is learnt mostly from its capital's listings (Enugu, Asaba, Benin...). Outside the metros and
# capitals, only half of a positive premium carries over, unless the place has listings of its own.
nfR = len(RES.beta) - len(STATES); sprem = {s_: max(0.0, float(RES.beta[nfR + SI[s_]])) for s_ in STATES}
pv = pv * np.where(tier >= 2, np.exp(-0.5 * np.array([sprem[s_] for s_ in st])), 1.0) ** w
# small towns and villages can't sit above a share of their state capital's typical urban value (unless listings say so)
capmed = {}
for s_ in STATES:
    m = (np.array(st)==s_) & (dcap <= 8) & isurb
    capmed[s_] = float(np.median(pv[m])) if m.any() else float(np.median(pv[np.array(st)==s_]))
cm = np.array([capmed[s_] for s_ in st])
cap = cm * np.select([tier==3, tier>=4], [0.25, 0.15], 10.0) * np.minimum(1.0, 20000/cm)**0.5   # pricier capitals pull their towns up less than in proportion
pv = np.where(pv > cap, cap**w * pv**(1-w), pv)
print('tiers', np.bincount(tier, minlength=6))

# ---------- economic-status zones ----------
# 0 Prime, 1 High-income, 2 Middle-income, 3 Lower-income (metros, capitals, cities, by value within that urban area)
# 4 Small town, 5 Village, 6 Remote / farmland
zone = np.full(len(P), 5)
grp = np.where(tier==0, metid, np.where(tier==1, 100+np.array([SI[s_] for s_ in st]), np.where(tier==2, 1000+ci, -1)))
for g_ in np.unique(grp[grp>=0]):
    m = (grp==g_) & isurb
    if m.sum() < 3: zone[(grp==g_)] = 2; continue
    v = pv[m]; q = np.percentile(v, [35, 70, 92]); med = np.median(v); big = m.sum() >= 15
    z = np.where(v >= q[2], 0 if big else 1, np.where(v >= q[1], 1, np.where(v >= q[0], 2, 3)))
    z = np.where((z==0) & (v < 2.5*med), 1, z)
    z = np.where((z==0) & (v < 60000), 1, z)     # 'prime' and 'high-income' also need national-scale values
    z = np.where((z==1) & (v < 20000), 2, z)
    zone[np.where(m)[0]] = z
    nm = (grp==g_) & ~isurb; zone[nm] = 3
zone[(tier==3) & isurb] = 4
zone[(tier==3) & ~isurb] = 5
zone[tier==4] = 5
zone[tier==5] = 6
print('zones', np.bincount(zone, minlength=7))
pconf = np.where(pev>=30,0,np.where(pev>=8,1,np.where(pev>=1.5,2,3)))
print('places valued', len(pv), np.bincount(pconf))

# ---------- LGAs ----------
URB=set(URBT)
by=collections.defaultdict(list)
for j,p in enumerate(P): by[p['lga']].append(j)
lgv=[]; meta=[]
for i,l in enumerate(LG):
    js=[j for j in by.get(i,[]) if P[j]['type'] not in ('estate','gated')]   # LGA medians from settlements, not estates
    if js:
        v=pv[js]; isu=np.array([P[j]['type'] in URB for j in js]); w=np.where(isu,3.0,1.0)
        o=np.argsort(v); cw=np.cumsum(w[o]); med=float(v[o][np.searchsorted(cw,cw[-1]/2)])
        lo,hi=float(np.percentile(v,5)),float(np.percentile(v,95))
        resU=float(np.median(v[isu])) if isu.any() else None; resR=float(np.median(v[~isu])) if (~isu).any() else None
        ev=float(pev[js].max()); nU=int(isu.sum())
    else:
        c,cw_=RES.at([l['lat']],[l['lng']],[l['state']]); med=float(c[0]); lo,hi=med*0.6,med*1.3; resU=None; resR=med*0.7; ev=float(cw_[0]); nU=0
    lgv.append(med); meta.append((js,lo,hi,resU,resR,ev,nU))
lgv=np.array(lgv)
LV = values_at([l['lat'] for l in LG],[l['lng'] for l in LG],[l['state'] for l in LG], lgv)
# economic-zone summary per LGA: places, residential, commercial, farmland, 3-bed rent
PZ = values_at(lat, lng, st, pv)
zsum = []
for i in range(len(LG)):
    js = np.array(by.get(i, []), int); rows = []
    for z_ in range(7):
        jz = js[zone[js]==z_] if len(js) else js
        if len(jz) < 3: continue
        farm = float(np.median(PZ['farm'][jz])) if z_ >= 4 else None
        rows.append([z_, int(len(jz)), float(np.median(pv[jz])), float(np.median(PZ['com'][jz])), farm, float(np.median(PZ['rent3'][jz]))])
    zsum.append(rows)
# farmland follows the LGA's rural land, not its urban core
resR_arr=np.array([ (meta[i][4] if meta[i][4] else lgv[i]*0.6) for i in range(len(LG))])
LV['farm']=np.minimum(RM['land_farm'].at([l['lat'] for l in LG],[l['lng'] for l in LG],[l['state'] for l in LG], resR_arr), resR_arr*0.5)*10000
lg_out=[]
for i,l in enumerate(LG):
    js,lo,hi,resU,resR,ev,nU = meta[i]; med=lgv[i]
    shareU = nU/max(1,len(js)); dens=len(js)/max(1,l['km2'])
    if med>=150000 or (shareU>=0.5 and dens>=1.5): cl='Metro core'
    elif shareU>=0.2 or med>=40000: cl='Urban'
    elif shareU>=0.05 or med>=12000: cl='Peri-urban'
    else: cl='Rural'
    v={k:float(LV[k][i]) for k in LV}; v.update({'lo':lo,'hi':hi,'resU':resU if resU else med,'resR':resR if resR else min(med,lo*1.2)})
    conf=0 if ev>=30 else 1 if ev>=8 else 2 if ev>=1.5 else 3
    lg_out.append({'n':l['name'],'s':l['state'],'cls':cl,'lat':l['lat'],'lng':l['lng'],'km2':round(l['km2']),'v':v,'ev':int(round(ev)),'conf':conf,'np':len(js),'rings':l['rings']})
PLOT={'LA':600,'RI':465}
NORTH={'KN','KD','SK','KT','KE','ZA','JI','YB','BR','BA','GM','AD','NI','TA','PL','NA','KW','KG','BE'}
for g in lg_out: g['plot']=PLOT.get(g['s'], 900 if g['s'] in NORTH else 600)

for i,g in enumerate(lg_out): g['zs'] = zsum[i]
pickle.dump({'lg_out':lg_out,'pv':pv.tolist(),'pconf':pconf.tolist(),'pev':pev.tolist(),'tier':tier.tolist(),'zone':zone.tolist(),'RM_beta':{m:float(RM[m].beta[1]) for m in RM},'holdout':HOLD}, open('out/model.pkl','wb'))
print('done', collections.Counter(g['cls'] for g in lg_out))

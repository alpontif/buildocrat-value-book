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

RM = {m: Ratio(m) for m in ['land_com','land_ind','land_farm','rent2','rent3','sale3','sale4','com_rent_m2']}

def values_at(lat, lng, st, resv):
    out={'res':resv}
    for m,k in [('land_com','com'),('land_ind','ind'),('land_farm','farm'),('rent2','rent2'),('rent3','rent3'),('sale3','sale3'),('sale4','sale4'),('com_rent_m2','crent')]:
        out[k]=RM[m].at(lat,lng,st,resv)
    out['farm']=np.minimum(out['farm'], resv*0.5)*10000      # per hectare; farmland never above half the residential rate
    out['com']=np.maximum(out['com'], resv*1.0)
    out['ind']=np.clip(out['ind'], resv*0.35, resv*2.0)
    out['rent3']=np.maximum(out['rent3'], out['rent2']*1.2)
    out['sale4']=np.maximum(out['sale4'], out['sale3']*1.25)
    return out

# ---------- every place ----------
lat=np.array([p['lat'] for p in P]); lng=np.array([p['lng'] for p in P]); st=[p['st'] for p in P]
pv, pev = RES.at(lat,lng,st)
TADJ = {'city':1.0,'town':0.95,'suburb':1.0,'quarter':1.0,'neighbourhood':1.0,'village':0.6,'hamlet':0.45,'locality':0.5}
tadj = np.array([TADJ[p['type']] for p in P]) ** (1/(1+pev/10))
pv = pv*tadj
pconf = np.where(pev>=30,0,np.where(pev>=8,1,np.where(pev>=1.5,2,3)))
print('places valued', len(pv), np.bincount(pconf))

# ---------- LGAs ----------
URB=set(URBT)
by=collections.defaultdict(list)
for j,p in enumerate(P): by[p['lga']].append(j)
lgv=[]; meta=[]
for i,l in enumerate(LG):
    js=by.get(i,[])
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

pickle.dump({'lg_out':lg_out,'pv':pv.tolist(),'pconf':pconf.tolist(),'pev':pev.tolist(),'RM_beta':{m:float(RM[m].beta[1]) for m in RM},'holdout':HOLD}, open('out/model.pkl','wb'))
print('done', collections.Counter(g['cls'] for g in lg_out))

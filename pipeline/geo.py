import json, math
U='/mnt/user-data/uploads/Claude/landbook-data/'
def rings_of(geom):
    polys=[geom['coordinates']] if geom['type']=='Polygon' else geom['coordinates']
    return [p[0] for p in polys]  # outer rings
def area_centroid(r):
    a=cx=cy=0
    for i in range(len(r)-1):
        x1,y1=r[i][:2]; x2,y2=r[i+1][:2]; f=x1*y2-x2*y1; a+=f; cx+=(x1+x2)*f; cy+=(y1+y2)*f
    if abs(a)<1e-12: return abs(a)/2, r[0][0], r[0][1]
    return abs(a)/2, cx/(3*a), cy/(3*a)
def pip(x,y,r):
    c=False; n=len(r); j=n-1
    for i in range(n):
        xi,yi=r[i][:2]; xj,yj=r[j][:2]
        if (yi>y)!=(yj>y) and x < (xj-xi)*(y-yi)/(yj-yi)+xi: c=not c
        j=i
    return c
def interior(rings):
    big=max(rings,key=lambda r:area_centroid(r)[0]); _,cx,cy=area_centroid(big)
    if pip(cx,cy,big): return cx,cy
    # scanline through cy
    xs=[]; n=len(big)
    for i in range(n-1):
        x1,y1=big[i][:2]; x2,y2=big[i+1][:2]
        if (y1>cy)!=(y2>cy): xs.append(x1+(cy-y1)*(x2-x1)/(y2-y1))
    xs.sort(); best=None
    for k in range(0,len(xs)-1,2):
        w=xs[k+1]-xs[k]
        if best is None or w>best[0]: best=(w,(xs[k]+xs[k+1])/2)
    return (best[1],cy) if best else (big[0][0],big[0][1])
def dp(pts,tol):
    if len(pts)<4: return pts
    keep=[False]*len(pts); keep[0]=keep[-1]=True; st=[(0,len(pts)-1)]
    while st:
        a,b=st.pop(); x1,y1=pts[a][:2]; x2,y2=pts[b][:2]; dx,dy=x2-x1,y2-y1; L=math.hypot(dx,dy); md=-1; mi=-1
        for i in range(a+1,b):
            px,py=pts[i][:2]
            d=math.hypot(px-x1,py-y1) if L<1e-12 else abs(dy*px-dx*py+x2*y1-y2*x1)/L
            if d>md: md,mi=d,i
        if md>tol: keep[mi]=True; st+= [(a,mi),(mi,b)]
    return [p for p,k in zip(pts,keep) if k]
if __name__=='__main__':
    s1=json.load(open(U+'ADM1.geojson'))['features']; s2=json.load(open(U+'ADM2.geojson'))['features']
    NAME2CODE={'Abia':'AB','Adamawa':'AD','Akwa Ibom':'AK','Anambra':'AN','Bauchi':'BA','Bayelsa':'BY','Benue':'BE','Borno':'BR','Cross River':'CR','Delta':'DE','Ebonyi':'EB','Edo':'ED','Ekiti':'EK','Enugu':'EN','Abuja Federal Capital Territory':'FC','Gombe':'GM','Imo':'IM','Jigawa':'JI','Kaduna':'KD','Kano':'KN','Katsina':'KT','Kebbi':'KE','Kogi':'KG','Kwara':'KW','Lagos':'LA','Nasarawa':'NA','Niger':'NI','Ogun':'OG','Ondo':'ON','Osun':'OS','Oyo':'OY','Plateau':'PL','Rivers':'RI','Sokoto':'SK','Taraba':'TA','Yobe':'YB','Zamfara':'ZA'}
    states=[(NAME2CODE[f['properties']['shapeName']], rings_of(f['geometry'])) for f in s1]
    lgas=[]
    for f in s2:
        rs=rings_of(f['geometry']); x,y=interior(rs)
        code=None
        for c,srs in states:
            if any(pip(x,y,r) for r in srs): code=c; break
        if code is None:
            code=min(states,key=lambda s: min(math.hypot(x-p[0],y-p[1]) for r in s[1] for p in r[::20]))[0]
        area=sum(area_centroid(r)[0] for r in rs)*(111.32**2)*math.cos(math.radians(y))
        lgas.append({'name':f['properties']['shapeName'],'state':code,'lng':round(x,4),'lat':round(y,4),'km2':round(area,1),'rings':rs})
    json.dump(lgas,open('lgas_full.json','w'))
    import collections; c=collections.Counter(l['state'] for l in lgas); print(len(lgas)); print(sorted(c.items()))

'use strict';
/* Buildocrat Land Value Book \u2014 app */
const SC={AB:'Abia',AD:'Adamawa',AK:'Akwa Ibom',AN:'Anambra',BA:'Bauchi',BY:'Bayelsa',BE:'Benue',BR:'Borno',CR:'Cross River',DE:'Delta',EB:'Ebonyi',ED:'Edo',EK:'Ekiti',EN:'Enugu',FC:'FCT, Abuja',GM:'Gombe',IM:'Imo',JI:'Jigawa',KD:'Kaduna',KN:'Kano',KT:'Katsina',KE:'Kebbi',KG:'Kogi',KW:'Kwara',LA:'Lagos',NA:'Nasarawa',NI:'Niger',OG:'Ogun',ON:'Ondo',OS:'Osun',OY:'Oyo',PL:'Plateau',RI:'Rivers',SK:'Sokoto',TA:'Taraba',YB:'Yobe',ZA:'Zamfara'};
const TYPEN=['City','Town','District','Area','Neighbourhood','Village','Hamlet','Locality','Gated estate','Gated area'];
const URBAN_T=new Set([0,1,2,3,4,8,9]);
const DRANK=[0,1,2,3,4,5,6,7,4,4]; // map display order: estates appear with neighbourhoods
const RURAL_T=t=>t===5||t===6||t===7;
const ZONEC=['#1D2675','#3C49A1','#7D87CA','#B7BCE6','#E8725B','#F2A28E','#CDB9A6'];
const CONF=[['H','High','Market data: 30+ listings close by'],['M','Medium','Market data: 8\u201329 listings close by'],['L','Low','A few listings close by, mostly modelled'],['X','Modelled','No listings within reach; modelled from the LGA, state and settlement pattern']];
let FX=1333, BUILD=367748;
const TABS={
  land:{name:'Land value',head:'res',layers:[['res','Residential','\u20a6/m\u00b2'],['com','Commercial','\u20a6/m\u00b2'],['ind','Industrial','\u20a6/m\u00b2'],['farm','Farmland','\u20a6/ha'],['zone','Economic zones','']]},
  bld:{name:'Building value',head:'sale4',layers:[['sale3','3-bed flat','\u20a6'],['sale4','4-bed house','\u20a6'],['bpm','Per m\u00b2 of floor','\u20a6/m\u00b2'],['bcost','Cost to build new','\u20a6/m\u00b2']]},
  rent:{name:'Rental value',head:'rent3',layers:[['rent1','1-bed flat','\u20a6/yr'],['rent2','2-bed flat','\u20a6/yr'],['rent3','3-bed flat','\u20a6/yr'],['rent4','4-bed house','\u20a6/yr'],['crent','Shop / office','\u20a6/m\u00b2/yr'],['yld','Gross yield','% a year']]}
};
const LAYERS=[].concat(...Object.values(TABS).map(t=>t.layers));
let TAB='land';
const GFA4=250; // typical 4-bed house floor area, m2

/* ---------- formatting ---------- */
const fmt=n=>n==null||!isFinite(n)?'\u2013':'\u20a6'+Math.round(n).toLocaleString('en-NG');
function trim0(s){return s.includes('.')?s.replace(/0+$/,'').replace(/\.$/,''):s;}
function short(n){ if(n==null||!isFinite(n)) return '\u2013';
  if(n>=1e9){return '\u20a6'+trim0((n/1e9).toFixed(2))+'bn';}
  if(n>=1e6){const v=n/1e6; return '\u20a6'+trim0(v.toFixed(v>=100?0:(v>=10?1:2)))+'m';}
  if(n>=1e3){const v=n/1e3; return '\u20a6'+trim0(v.toFixed(v>=100?0:1))+'k';}
  return '\u20a6'+Math.round(n); }
const sig=(n,d=2)=>{ if(!n) return n; const p=Math.pow(10,Math.max(0,Math.floor(Math.log10(n))-d+1)); return Math.round(n/p)*p; };
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const norm=s=>String(s||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9 ]+/g,' ').replace(/\s+/g,' ').trim();
const $=id=>document.getElementById(id);

/* ---------- data ---------- */
let ST=[], LG=[], PL=null, EV=[], META={}, BORDERS=[];
const STI={};
async function load(){
  const gz=async u=>{ const txt=(await (await fetch(u)).text()).trim(); const bin=atob(txt); const buf=new Uint8Array(bin.length); for(let i=0;i<bin.length;i++) buf[i]=bin.charCodeAt(i);
    if(buf[0]===0x1f&&buf[1]===0x8b){ const ds=new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip')); return JSON.parse(await new Response(ds).text()); }
    return JSON.parse(new TextDecoder().decode(buf)); };
  const [a,b,c]=await Promise.all([fetch('data/lgas.json').then(r=>r.json()), gz('data/places.b64.txt'), fetch('data/evidence.json').then(r=>r.json())]);
  ST=a.states; LG=a.lgas; META=a.meta; BORDERS=a.borders; PL=b; EV=c; FX=META.fx||FX; BUILD=META.build||BUILD;
  for(let j=1;j<PL.la.length;j++){ PL.la[j]+=PL.la[j-1]; PL.lo[j]+=PL.lo[j-1]; }
  ST.forEach((s,i)=>STI[s.c]=i);
  // hierarchy: parent pointers (City > District/Area > Neighbourhood > Gated estate)
  PL.pa=new Int32Array(PL.n.length).fill(-1); PL.ch=new Map();
  if(PL.pk){ let k=0; PL.pk.forEach((d,i)=>{ k+=d; const p=PL.pp[i]; PL.pa[k]=p; let a=PL.ch.get(p); if(!a){a=[];PL.ch.set(p,a);} a.push(k); }); }
  if(!PL.z) PL.z=new Array(PL.n.length).fill(5);
  for(const g of LG) derive(g.v,g.s);
  for(const s of ST) derive(s.v,s.c);
  for(const g of LG){ const zs=g.zs||[]; let best=null; for(const r of zs){ if(!best||Math.abs(Math.log(r[2]/g.v.res))<Math.abs(Math.log(best[2]/g.v.res))) best=r; } g.v.zone=best?best[0]:null; }
}
function derive(v,st){ // building and rental measures derived from the modelled values
  v.bpm=v.sale4?v.sale4/GFA4:null; v.bcost=BUILD*(STF[st]??0.93); v.yld=(v.rent3&&v.sale3)?100*v.rent3/v.sale3:null;
  return v;
}

/* ---------- derived values ---------- */
function decode(enc){ const out=[]; let x=0,y=0; for(const p of enc.split(' ')){ const k=p.indexOf(','); x+=+p.slice(0,k); y+=+p.slice(k+1); out.push([x/1000,y/1000]); } return out; }
function placeVals(j){
  const g=LG[PL.g[j]], v=PL.v[j], r=v/g.v.res, B=META.beta;
  const o={res:v};
  o.com=g.v.com*Math.pow(r,B.com); o.ind=g.v.ind*Math.pow(r,B.ind); o.farm=(g.v.farm&&RURAL_T(PL.t[j]))?Math.min(g.v.farm*Math.pow(r/((g.v.resR||g.v.res)/g.v.res),B.farm), v*5000):null;
  for(const k of ['rent1','rent2','rent3','rent4','sale2','sale3','sale4','sale5']) o[k]=g.v[k]?g.v[k]*Math.pow(r,B[k]??0.4):null;
  o.crent=g.v.crent?g.v.crent*Math.pow(r,B.com):null; o.zone=PL.z[j];
  // keep sizes in order after scaling (bigger homes never cheaper)
  if(o.rent1&&o.rent2) o.rent2=Math.max(o.rent2,o.rent1*1.15); if(o.rent2&&o.rent3) o.rent3=Math.max(o.rent3,o.rent2*1.2); if(o.rent3&&o.rent4) o.rent4=Math.max(o.rent4,o.rent3*1.15);
  if(o.sale2&&o.sale3) o.sale3=Math.max(o.sale3,o.sale2*1.15); if(o.sale3&&o.sale4) o.sale4=Math.max(o.sale4,o.sale3*1.25); if(o.sale4&&o.sale5) o.sale5=Math.max(o.sale5,o.sale4*1.15);
  return derive(o,g.s);
}

/* ---------- map ---------- */
const CX=Math.cos(9*Math.PI/180);
const W2=(lng,lat)=>[lng*CX,-lat];
const canvas=$('map'), ctx=canvas.getContext('2d');
let dpr=1, view={s:1,tx:0,ty:0}, layer='res', breaks={}, lgaPaths=[], statePaths=[], hoverL=-1, selL=-1, selState=null, selPt=null, PIDX=null;
function css(v){return getComputedStyle(document.documentElement).getPropertyValue(v).trim();}
let COL={};
function readColors(){ COL={sea:css('--sea'),land:css('--land'),edge:css('--edge'),sedge:css('--sedge'),sel:css('--sel'),nd:css('--nd'),ink:css('--ink'),muted:css('--muted'),pin:css('--pin'),surface:css('--surface'),accent:css('--accent'),s:[0,1,2,3,4,5,6].map(i=>css('--s'+i))}; }
function buildPaths(){
  lgaPaths=LG.map(g=>{ const p=new Path2D(); for(const enc of g.r){ const pts=decode(enc); pts.forEach(([lng,lat],i)=>{const [X,Y]=W2(lng,lat); i?p.lineTo(X,Y):p.moveTo(X,Y);}); p.closePath(); } return p; });
  statePaths=BORDERS.map(b=>{ const p=new Path2D(); for(const enc of b.r){ const pts=decode(enc); pts.forEach(([lng,lat],i)=>{const [X,Y]=W2(lng,lat); i?p.lineTo(X,Y):p.moveTo(X,Y);}); p.closePath(); } return {c:b.c,p}; });
  // grid index for places
  PIDX=new Map(); const n=PL.n.length;
  for(let j=0;j<n;j++){ const k=(Math.floor(PL.lo[j]/2000))+':'+(Math.floor(PL.la[j]/2000)); let a=PIDX.get(k); if(!a){a=[];PIDX.set(k,a);} a.push(j); }
}
function computeBreaks(){
  for(const [k] of LAYERS){ const vals=LG.map(g=>g.v[k]).filter(v=>v>0).sort((a,b)=>a-b); const q=[0.2,0.42,0.62,0.78,0.9,0.97].map(f=>vals[Math.floor(vals.length*f)]); breaks[k]=q.map(v=>sig(v,2)).filter((v,i,a)=>!i||v>a[i-1]); }
  breaks.res=[3000,8000,20000,50000,120000,300000];
}
const cls=(k,v)=>{ if(k==='zone') return v==null?-1:v; if(!(v>0)) return -1; const b=breaks[k]; let i=0; while(i<b.length&&v>=b[i]) i++; return i; };
const colOf=(k,c)=>c<0?COL.nd:(k==='zone'?ZONEC[c]:COL.s[Math.min(6,c)]);
function pval(j,k){ return k==='res'?PL.v[j]:k==='zone'?PL.z[j]:placeVals(j)[k]; }
function resize(){ const r=canvas.getBoundingClientRect(); dpr=window.devicePixelRatio||1; canvas.width=Math.round(r.width*dpr); canvas.height=Math.round(r.height*dpr); draw(); }
function fitBox(x0,y0,x1,y1,pad=0.06){ const r=canvas.getBoundingClientRect(); const w=(x1-x0)*(1+2*pad), h=(y1-y0)*(1+2*pad); const s=Math.min(r.width/w, r.height/h); view.s=s; view.tx=r.width/2-s*(x0+x1)/2; view.ty=r.height/2-s*(y0+y1)/2; draw(); }
function fitLL(lat0,lng0,lat1,lng1){ const a=W2(lng0,lat0), b=W2(lng1,lat1); fitBox(Math.min(a[0],b[0]),Math.min(a[1],b[1]),Math.max(a[0],b[0]),Math.max(a[1],b[1])); }
const fitAll=()=>fitLL(4.2,2.65,13.9,14.7);
function toWorld(px,py){ return [(px-view.tx)/view.s,(py-view.ty)/view.s]; }
function toLL(px,py){ const [X,Y]=toWorld(px,py); return [-Y, X/CX]; }
function toScreen(lat,lng){ const [X,Y]=W2(lng,lat); return [X*view.s+view.tx, Y*view.s+view.ty]; }
let raf=0; function draw(){ cancelAnimationFrame(raf); raf=requestAnimationFrame(render); }
function render(){
  if(!lgaPaths.length) return;
  const W=canvas.width, H=canvas.height;
  ctx.setTransform(1,0,0,1,0,0); ctx.fillStyle=COL.sea; ctx.fillRect(0,0,W,H);
  ctx.setTransform(dpr*view.s,0,0,dpr*view.s,dpr*view.tx,dpr*view.ty);
  const lw=1/view.s;
  for(let i=0;i<LG.length;i++){ ctx.fillStyle=colOf(layer,cls(layer,LG[i].v[layer])); ctx.fill(lgaPaths[i]); }
  ctx.strokeStyle=COL.edge; ctx.lineWidth=lw*0.6; for(const p of lgaPaths) ctx.stroke(p);
  ctx.strokeStyle=COL.sedge; ctx.lineWidth=lw*1.4; for(const b of statePaths) ctx.stroke(b.p);
  if(selState){ const b=statePaths.find(x=>x.c===selState); if(b){ ctx.strokeStyle=COL.sel; ctx.lineWidth=lw*2.6; ctx.stroke(b.p);} }
  if(hoverL>=0){ ctx.strokeStyle=COL.sel; ctx.lineWidth=lw*1.6; ctx.stroke(lgaPaths[hoverL]); }
  if(selL>=0){ ctx.strokeStyle=COL.sel; ctx.lineWidth=lw*3; ctx.stroke(lgaPaths[selL]); }
  ctx.setTransform(dpr,0,0,dpr,0,0);
  drawPlaces();
  if(selPt){ const [x,y]=toScreen(selPt[0],selPt[1]); ctx.fillStyle=COL.pin; ctx.strokeStyle=COL.surface; ctx.lineWidth=2.5; ctx.beginPath(); ctx.arc(x,y,7,0,Math.PI*2); ctx.fill(); ctx.stroke(); }
}
function visiblePlaces(minType){
  const r=canvas.getBoundingClientRect(); const [la1,lo0]=toLL(0,0), [la0,lo1]=toLL(r.width,r.height);
  const out=[]; const gx0=Math.floor(lo0*10000/2000), gx1=Math.floor(lo1*10000/2000), gy0=Math.floor(la0*10000/2000), gy1=Math.floor(la1*10000/2000);
  if((gx1-gx0)*(gy1-gy0)>6000) return null;
  for(let gx=gx0;gx<=gx1;gx++) for(let gy=gy0;gy<=gy1;gy++){ const a=PIDX.get(gx+':'+gy); if(a) for(const j of a) if(DRANK[PL.t[j]]<=minType) out.push(j); }
  return out;
}
let labelsDrawn=[];
function drawPlaces(){
  const s=view.s; labelsDrawn=[];
  let maxT = s<120?1: s<300?2: s<700?4: s<1500?5: 7;
  let list;
  if(s<90){ list=[]; for(let j=0;j<PL.t.length;j++) if(PL.t[j]===0) list.push(j); }
  else list=visiblePlaces(maxT)||[];
  const r=canvas.getBoundingClientRect();
  const occ=new Set(); const cell=8; let nlab=0;
  list.sort((a,b)=>DRANK[PL.t[a]]-DRANK[PL.t[b]]||PL.v[b]-PL.v[a]);
  ctx.font='600 11px '+getComputedStyle(document.body).fontFamily;
  ctx.textBaseline='middle';
  let drawn=0;
  for(const j of list){
    if(drawn>5000) break;
    const [x,y]=toScreen(PL.la[j]/1e4,PL.lo[j]/1e4); if(x<-20||y<-20||x>r.width+20||y>r.height+20) continue;
    const t=PL.t[j], dt=DRANK[t], rad=dt===0?4.5:dt===1?3.5:dt<=3?2.8:dt===4?2.2:2.0;
    ctx.fillStyle=colOf(layer,cls(layer,pval(j,layer))); ctx.strokeStyle=t>=8?COL.pin:COL.ink; ctx.lineWidth=t<=1?1.2:0.8;
    ctx.beginPath(); ctx.arc(x,y,rad,0,Math.PI*2); ctx.fill(); ctx.stroke(); drawn++;
    labelsDrawn.push([j,x,y,rad]);
    const showLab = dt===0 || (dt===1&&s>=60) || (dt<=3&&s>=300) || (dt<=4&&s>=900) || s>=1800;
    if(showLab && nlab<260){ const name=PL.n[j]; const w=ctx.measureText(name).width; const k1=Math.floor((x+4)/cell), k2=Math.floor((x+8+w)/cell), y1=Math.floor((y-9)/cell), y2=Math.floor((y+9)/cell);
      let free=true; for(let k=k1;k<=k2&&free;k++) for(let yy=y1;yy<=y2;yy++) if(occ.has(k+':'+yy)){free=false;break;}
      if(free){ nlab++; for(let k=k1;k<=k2;k++) for(let yy=y1;yy<=y2;yy++) occ.add(k+':'+yy); ctx.lineWidth=3; ctx.strokeStyle=COL.surface; ctx.strokeText(name,x+6,y); ctx.fillStyle=COL.ink; ctx.fillText(name,x+6,y); } }
  }
}
function lgaAt(px,py){
  ctx.setTransform(dpr*view.s,0,0,dpr*view.s,dpr*view.tx,dpr*view.ty);
  for(let i=0;i<LG.length;i++){ if(ctx.isPointInPath(lgaPaths[i],px*dpr,py*dpr)){ ctx.setTransform(dpr,0,0,dpr,0,0); return i; } }
  ctx.setTransform(dpr,0,0,dpr,0,0); return -1;
}
function placeAt(px,py){ let best=-1,bd=81; for(const [j,x,y] of labelsDrawn){ const d=(x-px)**2+(y-py)**2; if(d<bd){bd=d;best=j;} } return best; }
function nearestPlaces(lat,lng,k=6,maxKm=8){
  const out=[]; const gx=Math.floor(lng*10000/2000), gy=Math.floor(lat*10000/2000);
  for(let dx=-1;dx<=1;dx++) for(let dy=-1;dy<=1;dy++){ const a=PIDX.get((gx+dx)+':'+(gy+dy)); if(a) for(const j of a){ const d=km(lat,lng,PL.la[j]/1e4,PL.lo[j]/1e4); if(d<=maxKm) out.push([j,d]); } }
  out.sort((a,b)=>a[1]-b[1]); return out.slice(0,k);
}
function km(a,b,c,d){ const R=6371,t=Math.PI/180; const h=Math.sin((c-a)*t/2)**2+Math.cos(a*t)*Math.cos(c*t)*Math.sin((d-b)*t/2)**2; return 2*R*Math.asin(Math.sqrt(h)); }

/* interaction */
const tip=$('tip'), card=$('mapcard');
let drag=null, moved=false; const ptrs=new Map(); let pinch=null;
canvas.addEventListener('pointerdown',e=>{ canvas.setPointerCapture(e.pointerId); ptrs.set(e.pointerId,{x:e.clientX,y:e.clientY}); drag={x:e.clientX,y:e.clientY}; moved=false; canvas.classList.add('drag'); });
canvas.addEventListener('pointermove',e=>{
  const r=canvas.getBoundingClientRect();
  if(ptrs.has(e.pointerId)){
    const prev=ptrs.get(e.pointerId); ptrs.set(e.pointerId,{x:e.clientX,y:e.clientY});
    if(ptrs.size===2){ const [a,b]=[...ptrs.values()]; const d=Math.hypot(a.x-b.x,a.y-b.y); if(pinch){ zoomAt(d/pinch,(a.x+b.x)/2-r.left,(a.y+b.y)/2-r.top);} pinch=d; moved=true; return; }
    const dx=e.clientX-prev.x, dy=e.clientY-prev.y; if(Math.abs(e.clientX-drag.x)+Math.abs(e.clientY-drag.y)>4) moved=true;
    if(moved){ view.tx+=dx; view.ty+=dy; tip.hidden=true; draw(); }
    return;
  }
  const px=e.clientX-r.left, py=e.clientY-r.top; const i=lgaAt(px,py);
  const j=placeAt(px,py);
  if(i!==hoverL){ hoverL=i; draw(); }
  if(j>=0) tip.innerHTML=tipPlace(j); else if(i>=0) tip.innerHTML=tipLGA(i);
  if(i>=0||j>=0){ tip.hidden=false; let x=px+14, y=py+12; if(x>r.width-250) x=px-250; if(y>r.height-90) y=py-80; tip.style.left=x+'px'; tip.style.top=y+'px'; } else tip.hidden=true;
});
const endPtr=e=>{ ptrs.delete(e.pointerId); if(ptrs.size<2) pinch=null; if(!ptrs.size){ canvas.classList.remove('drag'); } };
canvas.addEventListener('pointerup',e=>{ const wasMoved=moved; endPtr(e); if(wasMoved||e.button>0) return; const r=canvas.getBoundingClientRect(); const px=e.clientX-r.left, py=e.clientY-r.top;
  const j=placeAt(px,py); if(j>=0){ selectPlace(j,false); return; }
  const [lat,lng]=toLL(px,py); const i=lgaAt(px,py); if(i<0) return; selectPoint(lat,lng,i); });
canvas.addEventListener('pointercancel',endPtr);
canvas.addEventListener('pointerleave',()=>{ tip.hidden=true; if(hoverL>=0){hoverL=-1; draw();} });
canvas.addEventListener('wheel',e=>{ e.preventDefault(); const r=canvas.getBoundingClientRect(); zoomAt(e.deltaY<0?1.25:0.8,e.clientX-r.left,e.clientY-r.top); },{passive:false});
canvas.addEventListener('dblclick',e=>{ const r=canvas.getBoundingClientRect(); zoomAt(2,e.clientX-r.left,e.clientY-r.top); });
function zoomAt(f,px,py){ const ns=Math.max(25,Math.min(9000,view.s*f)); f=ns/view.s; view.tx=px-(px-view.tx)*f; view.ty=py-(py-view.ty)*f; view.s=ns; draw(); }
$('zin').onclick=()=>MAPI.zoom(1.6);
$('zout').onclick=()=>MAPI.zoom(1/1.6);
$('zall').onclick=()=>MAPI.fitAll();
/* canvas map behind the common map interface (used when no Mapbox token is configured) */
function lgaBox(i){ let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9; for(const enc of LG[i].r) for(const [lng,lat] of decode(enc)){ x0=Math.min(x0,lng);x1=Math.max(x1,lng);y0=Math.min(y0,lat);y1=Math.max(y1,lat);} return [y0,x0,y1,x1]; }
const CANVAS_MAP={ kind:'canvas', refresh:()=>draw(), fitAll:()=>fitAll(), fitLL:(a,b,c,d)=>fitLL(a,b,c,d),
  fitLGA(i){ const [a,b,c,d]=lgaBox(i); const p=0.15*Math.max(c-a,d-b); fitLL(a-p,b-p,c+p,d+p); },
  flyPlace(la,lo,t){ const [X,Y]=W2(lo,la); const r=canvas.getBoundingClientRect(); view.s=Math.max(view.s, t<=1?420:900); view.tx=r.width/2-X*view.s; view.ty=r.height/2-Y*view.s; draw(); },
  zoom(f){ const r=canvas.getBoundingClientRect(); zoomAt(f,r.width/2,r.height/2); },
  sat(la,lo){ this.flyPlace(la,lo,7); } };
let MAPI=CANVAS_MAP;
function unitOf(k){ return (LAYERS.find(l=>l[0]===k)||['','',''])[2]; }
function fmtL(k,v){ return v==null||!isFinite(v)?'\u2013':k==='yld'?v.toFixed(1)+'%':k==='zone'?(META.zones||[])[v]||'\u2013':short(v); }
function buildLayers(){
  $('layers').innerHTML=TABS[TAB].layers.map(([k,n])=>`<button type="button" data-k="${k}" aria-pressed="${k===layer}">${n}</button>`).join('');
}
$('layers').addEventListener('click',e=>{ const b=e.target.closest('button'); if(!b) return; layer=b.dataset.k; [...$('layers').children].forEach(x=>x.setAttribute('aria-pressed',x.dataset.k===layer)); legend(); MAPI.refresh(); });
function setTab(t){
  if(!TABS[t]||(t===TAB&&$('tabs').dataset.ready)) return; TAB=t; $('tabs').dataset.ready=1;
  [...$('tabs').querySelectorAll('[role=tab]')].forEach(b=>{ b.setAttribute('aria-selected',b.dataset.t===TAB); b.tabIndex=b.dataset.t===TAB?0:-1; });
  layer=TABS[TAB].layers.find(l=>l[0]===TABS[TAB].head)?TABS[TAB].head:TABS[TAB].layers[0][0];
  buildLayers(); legend(); MAPI.refresh(); if(RER) RER(); if(TBL) TBL();
}
$('tabs').addEventListener('click',e=>{ const b=e.target.closest('[role=tab]'); if(b) setTab(b.dataset.t); });
document.querySelectorAll('.tlead[data-tab]').forEach(b=>b.addEventListener('click',()=>{ setTab(b.dataset.tab); $('mapsec').scrollIntoView(); }));
$('tabs').addEventListener('keydown',e=>{ if(e.key!=='ArrowRight'&&e.key!=='ArrowLeft') return; const k=Object.keys(TABS); const n=k[(k.indexOf(TAB)+(e.key==='ArrowRight'?1:k.length-1))%k.length]; setTab(n); $('tabs').querySelector(`[data-t="${n}"]`).focus(); });
function legend(){ const L=LAYERS.find(l=>l[0]===layer);
  if(layer==='zone'){ $('legend').innerHTML=`<div>Economic zones (dots); LGAs by their typical zone</div><div class="zleg">${(META.zones||[]).map((z,i)=>`<span><i style="background:${ZONEC[i]}"></i>${esc(z)}</span>`).join('')}</div>`; return; }
  const b=breaks[layer];
  $('legend').innerHTML=`<div>${TABS[TAB].name}: ${L[1]}, ${L[2]}${layer==='res'?' (LGA median)':''}</div><div class="row">${[0,1,2,3,4,5,6].map(i=>`<i style="background:var(--s${i})"></i>`).join('')}</div><div class="lab">${b.map(v=>`<span>${layer==='yld'?v.toFixed(1):short(v).replace('\u20a6','')}</span>`).join('')}<span></span></div>`; }
function tipPlace(j){ const v=placeVals(j); return `<b>${esc(PL.n[j])}</b> <span class="muted">${TYPEN[PL.t[j]]}</span><br>${esc(LG[PL.g[j]].n)} LGA, ${esc(SC[LG[PL.g[j]].s])}<br><span class="num">${fmtL(layer,layer==='zone'?PL.z[j]:v[layer])}</span> ${layer==='zone'?'zone':unitOf(layer)}`; }
function tipLGA(i){ const g=LG[i]; return `<b>${esc(g.n)}</b> <span class="muted">LGA \u00b7 ${g.s}</span><br>${esc(SC[g.s])} \u00b7 ${g.cls}<br><span class="num">${fmtL(layer,g.v[layer])}</span> ${layer==='zone'?'typical zone':unitOf(layer)} ${layer==='res'?'median':''}<br><span class="muted small">Click to value this exact spot</span>`; }

/* ---------- panel ---------- */
const osm=(la,lo,z=18)=>`https://www.openstreetmap.org/?mlat=${la.toFixed(6)}&mlon=${lo.toFixed(6)}#map=${z}/${la.toFixed(6)}/${lo.toFixed(6)}`;
function confPill(c,ev){ const C=CONF[c]; return `<span class="pill c-${C[0]==='X'?'L':C[0]}" title="${esc(C[2])}">${C[1]}</span>`; }
const cell=(label,val,unit)=>`<div><span>${label}</span><b>${val}</b><small>${unit}</small></div>`;
// headline + grid for the open tab: Land value | Building value | Rental value
function valueBlock(v,plot,where,note){
  const zn=v.zone!=null&&META.zones?`<span class="ztag" style="--zc:${ZONEC[v.zone]}">${esc(META.zones[v.zone])} zone</span>`:'';
  if(TAB==='land') return `<div><p class="eyebrow">Residential land${where}</p><div class="headline"><span class="big num">${short(v.res)}</span><span class="muted">per m\u00b2</span>${zn}</div><p class="note">${note}</p></div>
   <div class="vals">${cell('Commercial land',short(v.com),'per m\u00b2')}${cell('Industrial land',short(v.ind),'per m\u00b2')}${cell('Farmland',short(v.farm),v.farm?'per hectare':'built-up, n/a')}${cell(`Typical ${plot} m\u00b2 plot`,short(v.res*plot),'residential')}${cell('Half plot (300 m\u00b2)',short(v.res*300),'residential')}${cell('One acre',short(v.res*4047),'residential rate')}</div>`;
  if(TAB==='bld') return `<div><p class="eyebrow">4-bedroom house${where}</p><div class="headline"><span class="big num">${short(v.sale4)}</span><span class="muted">asking price</span>${zn}</div><p class="note">${note}</p></div>
   <div class="vals">${cell('2-bed flat',short(v.sale2),'asking')}${cell('3-bed flat',short(v.sale3),'asking')}${cell('5-bed house',short(v.sale5),'asking')}${cell('Value per m\u00b2 of floor',short(v.bpm),`4-bed house, ${GFA4} m\u00b2`)}${cell('Cost to build new',short(v.bcost),'per m\u00b2, standard finish')}${cell('Land share of a 4-bed',v.sale4?Math.round(100*Math.min(0.95,v.res*plot/v.sale4))+'%':'\u2013',`on a ${plot} m\u00b2 plot`)}</div>`;
  return `<div><p class="eyebrow">Rent, 3-bed flat${where}</p><div class="headline"><span class="big num">${short(v.rent3)}</span><span class="muted">per year</span>${zn}</div><p class="note">${note}</p></div>
   <div class="vals">${cell('1-bed / mini flat',short(v.rent1),'per year')}${cell('2-bed flat',short(v.rent2),'per year')}${cell('4-bed house',short(v.rent4),'per year')}${cell('Shop / office',short(v.crent),v.crent?'per m\u00b2 a year':'few listings')}${cell('Gross yield, 3-bed flat',fmtL('yld',v.yld),'rent \u00f7 asking price')}${cell('Gross yield, 4-bed house',v.rent4&&v.sale4?(100*v.rent4/v.sale4).toFixed(1)+'%':'\u2013','rent \u00f7 asking price')}</div>`;
}
function zoneTable(zs,title){
  if(!zs||!zs.length) return '';
  return `<div><p class="eyebrow" style="margin-bottom:4px">${title}</p><table class="mini zt"><tr><td class="muted small">Zone</td><td class="r muted small">Residential</td><td class="r muted small">Commercial</td><td class="r muted small">Farmland /ha</td><td class="r muted small">Rent 3-bed</td></tr>${zs.map(([z,n,res,com,farm,r3])=>`<tr><td><span class="zdot" style="background:${ZONEC[z]}"></span>${esc(META.zones[z])} <span class="muted small">${n.toLocaleString('en-NG')}</span></td><td class="r">${short(res)}</td><td class="r">${short(com)}</td><td class="r">${short(farm)}</td><td class="r">${short(r3)}</td></tr>`).join('')}</table><p class="note">Economic-status zones: metros, state capitals and cities split into prime, high-, middle- and lower-income areas by value; then small towns, villages and remote farmland.</p></div>`;
}
function actions(la,lo,st,exact){
  const satBtn=MAPI.kind==='mapbox'?`<button class="btn" type="button" data-sat="${la.toFixed(6)},${lo.toFixed(6)}">Satellite close-up</button>`:`<a class="btn" href="${osm(la,lo)}" target="_blank" rel="noopener">Open in OpenStreetMap \u2197</a>`;
  return `<div class="actions">${satBtn}<a class="btn wab" href="${waHref({name:'this spot in '+SC[st],lat:la,lng:lo})}" target="_blank" rel="noopener">WhatsApp us about it</a><a class="btn ghost" href="https://www.postcode.gov.ng" target="_blank" rel="noopener">postcode.gov.ng \u2197</a></div>
  <div class="pc" data-pc="${la.toFixed(6)},${lo.toFixed(6)}" data-st="${st}" data-exact="${exact?1:0}">${postcodeIdle(st)}</div>
  <p class="note">Coordinates <span class="mono">${la.toFixed(5)}, ${lo.toFixed(5)}</span> <button class="linkbtn" type="button" data-copy="${la.toFixed(6)}, ${lo.toFixed(6)}">Copy</button> \u00b7 <button class="linkbtn" type="button" data-copy="https://value.buildocrat.store/#at=${la.toFixed(5)},${lo.toFixed(5)}">Copy link</button></p>`; }
const EVM={land:['land_res','residential land','/m\u00b2'],bld:['sale4','4-bed house sales',''],rent:['rent3','3-bed flat rents','/yr']};
function nearbyEvidence(la,lo){ const [m,lab,u]=EVM[TAB]; const rows=EV.filter(e=>e.m===m&&km(la,lo,e.lat,e.lng)<=12).map(e=>({...e,d:km(la,lo,e.lat,e.lng)})).sort((a,b)=>a.d-b.d).slice(0,6);
  if(!rows.length) return `<p class="note">No ${lab} listings within 12 km. Values here are modelled.</p>`;
  return `<div><p class="eyebrow" style="margin-bottom:4px">${lab[0].toUpperCase()+lab.slice(1)} listings within 12 km</p><table class="mini">${rows.map(e=>`<tr><td>${esc(e.label)} <span class="muted small">${e.d.toFixed(1)} km</span></td><td class="r">${short(e.med)}${u}</td><td class="r muted">${e.n} listings</td></tr>`).join('')}</table></div>`; }
function crumbs(parts){ return `<div class="crumbs">${parts.map(([t,a],i)=>(a?`<button type="button" data-go="${a}">${esc(t)}</button>`:`<span>${esc(t)}</span>`)+(i<parts.length-1?'<span>\u203a</span>':'')).join('')}</div>`; }
function ancestors(j){ const out=[]; let p=PL.pa[j], n=0; while(p>=0&&n<5){ out.unshift(p); p=PL.pa[p]; n++; } return out; }
let SEL=null, RER=null; // current selection and how to redraw it (for tab switches)
const WA_NO='2347018024292';
function waText(s){ return s?`Hello Buildocrat, I'm interested in ${s.name.replace(/^Pinned spot/,'a spot')} on the Land Value Book: https://value.buildocrat.store/#at=${s.lat.toFixed(5)},${s.lng.toFixed(5)} . `:"Hello Buildocrat, I'm on the Land Value Book (value.buildocrat.store). "; }
const waHref=s=>`https://wa.me/${WA_NO}?text=${encodeURIComponent(waText(s))}`;
function setSel(s){ SEL=s; estimate(); const a=$('wa'); if(a) a.href=waHref(s); }
function selectPlace(j,fly=true){
  RER=()=>selectPlace(j,false);
  const g=LG[PL.g[j]], la=PL.la[j]/1e4, lo=PL.lo[j]/1e4, v=placeVals(j), t=PL.t[j], plot=g.plot||600;
  selL=PL.g[j]; selState=null; selPt=[la,lo];
  if(fly) MAPI.flyPlace(la,lo,DRANK[t]);
  MAPI.refresh();
  const anc=ancestors(j), kids=(PL.ch.get(j)||[]).slice().sort((a,b)=>PL.t[b]-PL.t[a]||PL.v[b]-PL.v[a]);
  const base=TAB==='land'?`LGA median ${short(g.v.res)}/m\u00b2.`:TAB==='bld'?`LGA typical ${short(g.v.sale4)}.`:`LGA typical ${short(g.v.rent3)} a year.`;
  $('panel').innerHTML=`${crumbs([['Nigeria','ng'],[SC[g.s],'s:'+g.s],[g.n+' LGA','l:'+PL.g[j]]].concat(anc.map(a=>[PL.n[a],'p:'+a])).concat([[PL.n[j],null]]))}
   <div class="ptitle"><div><h3>${esc(PL.n[j])}</h3><div class="tags"><span class="tag ${URBAN_T.has(t)?'u':''}">${URBAN_T.has(t)?'Urban':'Rural'} \u00b7 ${TYPEN[t]}</span>${anc.length?`<span class="tag">in ${esc(PL.n[anc[anc.length-1]])}</span>`:''}${PL.W[PL.w[j]]?`<span class="tag">${esc(PL.W[PL.w[j]])} ward</span>`:''}<span class="tag">${g.cls} LGA</span></div></div>${confPill(PL.c[j])}</div>
   ${valueBlock(v,plot,'',`${CONF[PL.c[j]][2]}. ${base}`)}${actions(la,lo,g.s,false)}
   ${kids.length?`<div><p class="eyebrow" style="margin-bottom:4px">Inside ${esc(PL.n[j])} (${kids.length})</p><table class="mini">${kids.slice(0,40).map(k=>`<tr><td><button type="button" data-place="${k}">${esc(PL.n[k])}</button> <span class="muted small">${TYPEN[PL.t[k]]}</span></td><td class="r">${fmtL(TABS[TAB].head,pval(k,TABS[TAB].head))}</td></tr>`).join('')}</table></div>`:''}
   ${nearbyEvidence(la,lo)}`;
  postcodeFill();
  setSel({kind:'place',name:PL.n[j]+', '+g.n+' LGA, '+SC[g.s],lat:la,lng:lo,st:g.s,v,plot,conf:PL.c[j]});
}
const BKEYS=['res','com','ind','farm','rent1','rent2','rent3','rent4','sale2','sale3','sale4','sale5'];
function spotValues(la,lo,i){ // value at any point: blend of the nearest mapped places, else the LGA
  const g=LG[i]; const nb=nearestPlaces(la,lo,6,8);
  let v, note, conf=3;
  if(nb.length){ const acc={}, wk={}; BKEYS.forEach(k=>{acc[k]=0; wk[k]=0;});
    for(const [j,d] of nb){ const w=1/Math.max(0.3,d)**2; const pv=placeVals(j); BKEYS.forEach(k=>{ if(pv[k]>0){ acc[k]+=w*Math.log(pv[k]); wk[k]+=w; } }); }
    v={}; BKEYS.forEach(k=>v[k]=wk[k]>0?Math.exp(acc[k]/wk[k]):null);
    if(v.farm!=null && wk.farm<0.5*wk.res) v.farm=null; /* mostly built-up surroundings: no farmland figure */
    v.crent=g.v.crent; v.zone=PL.z[nb[0][0]]; conf=Math.max(...nb.slice(0,2).map(([j])=>PL.c[j]));
    note=`Blended from the ${nb.length} nearest mapped places; closest is ${esc(PL.n[nb[0][0]])}, ${nb[0][1].toFixed(1)} km away.`; }
  else { v={...g.v}; note='No mapped settlement within 8 km, so this uses the LGA values. Likely rural or undeveloped land.'; v.res=g.v.resR||g.v.res; v.zone=6; }
  return {v:derive(v,g.s),note,conf,nb};
}
function selectPoint(la,lo,i){
  RER=()=>selectPoint(la,lo,i);
  const g=LG[i]; const {v,note,conf,nb}=spotValues(la,lo,i);
  selL=i; selState=null; selPt=[la,lo]; MAPI.refresh();
  const plot=g.plot||600;
  $('panel').innerHTML=`${crumbs([['Nigeria','ng'],[SC[g.s],'s:'+g.s],[g.n+' LGA','l:'+i]].concat(nb.length&&nb[0][1]<1.5?ancestors(nb[0][0]).concat([nb[0][0]]).map(a=>[PL.n[a],'p:'+a]):[]).concat([['Pinned spot',null]]))}
   <div class="ptitle"><div><h3>Pinned spot</h3><div class="tags"><span class="tag">${g.n} LGA</span><span class="tag">${g.cls}</span></div></div>${confPill(conf)}</div>
   ${valueBlock(v,plot,' here',note)}${actions(la,lo,g.s,true)}
   ${nb.length?`<div><p class="eyebrow" style="margin-bottom:4px">Nearest places</p><table class="mini">${nb.map(([j,d])=>`<tr><td><button type="button" data-place="${j}">${esc(PL.n[j])}</button> <span class="muted small">${TYPEN[PL.t[j]]}, ${d.toFixed(1)} km</span></td><td class="r">${fmtL(TABS[TAB].head,pval(j,TABS[TAB].head))}</td></tr>`).join('')}</table></div>`:''}
   ${nearbyEvidence(la,lo)}`;
  postcodeFill();
  setSel({kind:'point',name:'Pinned spot in '+g.n+' LGA, '+SC[g.s],lat:la,lng:lo,st:g.s,v,plot,conf});
}
const LTYPES=[['','All places'],['0','Cities'],['1','Towns'],['5','Villages'],['3','Areas'],['2','Districts'],['4','Neighbourhoods'],['8','Gated estates'],['9','Gated areas'],['6','Hamlets']];
function selectLGA(i,fly=true){
  RER=()=>selectLGA(i,false);
  const g=LG[i]; selL=i; selState=null; selPt=null;
  if(fly) MAPI.fitLGA(i); MAPI.refresh();
  const hk=TABS[TAB].head;
  const pl=[]; for(let j=0;j<PL.g.length;j++) if(PL.g[j]===i) pl.push(j);
  const pv=new Map(pl.map(j=>[j,pval(j,hk)||0])); pl.sort((a,b)=>pv.get(b)-pv.get(a));
  const note=TAB==='land'?`Urban areas ${short(g.v.resU)}/m\u00b2, villages and rural land ${short(g.v.resR)}/m\u00b2. Range across the LGA ${short(g.v.lo)} to ${short(g.v.hi)}. ${g.ev?`Backed by ${g.ev} listings in or near the LGA.`:'No listings in the LGA; modelled.'}`:`Typical for ${esc(g.n)} as a whole; pick a place or a house for its own figure.`;
  $('panel').innerHTML=`${crumbs([['Nigeria','ng'],[SC[g.s],'s:'+g.s],[g.n+' LGA',null]])}
   <div class="ptitle"><div><h3>${esc(g.n)} LGA</h3><div class="tags"><span class="tag ${g.cls==='Rural'?'':'u'}">${g.cls}</span><span class="tag">${esc(SC[g.s])}</span><span class="tag">${g.km2.toLocaleString('en-NG')} km\u00b2</span><span class="tag">${pl.length} places</span></div></div>${confPill(g.conf)}</div>
   ${valueBlock(g.v,g.plot||600,TAB==='land'?', LGA median':', LGA typical',note)}
   ${zoneTable(g.zs,'Economic zones in '+esc(g.n))}
   <p class="note">NIPOST postcodes in ${esc(SC[g.s])} start <b class="mono">${g.s}</b>. Click a street or house on the map for its own postcode and values.</p>
   <div><p class="eyebrow" style="margin-bottom:4px">Places in ${esc(g.n)} (${pl.length})</p>
   <div class="lgafilt"><input type="search" id="lgaPlaceQ" placeholder="Find a place in this LGA"><select id="lgaPlaceT" aria-label="Level">${LTYPES.map(([v,n])=>`<option value="${v}">${n}</option>`).join('')}</select></div>
   <table class="mini" id="lgaPlaces"></table></div>`;
  const draw2=()=>{ const q=norm($('lgaPlaceQ').value), ty=$('lgaPlaceT').value; const rows=pl.filter(j=>(!q||norm(PL.n[j]).includes(q))&&(ty===''||PL.t[j]===+ty||(ty==='5'&&PL.t[j]===7))).slice(0,80);
    $('lgaPlaces').innerHTML=rows.map(j=>`<tr><td><button type="button" data-place="${j}">${esc(PL.n[j])}</button> <span class="muted small">${TYPEN[PL.t[j]]}</span></td><td class="r">${fmtL(hk,pv.get(j))}${TAB==='land'?'/m\u00b2':''}</td></tr>`).join('')||'<tr><td class="muted">No match.</td></tr>'; };
  $('lgaPlaceQ').addEventListener('input',draw2); $('lgaPlaceT').addEventListener('input',draw2); draw2();
  setSel({kind:'lga',name:g.n+' LGA, '+SC[g.s],lat:g.lat,lng:g.lng,st:g.s,v:g.v,plot:g.plot||600,conf:g.conf});
}
function selectState(c,fly=true){
  RER=()=>selectState(c,false);
  const s=ST[STI[c]]; selState=c; selL=-1; selPt=null;
  if(fly){ const b=s.bb; MAPI.fitLL(b[1],b[0],b[3],b[2]); } MAPI.refresh();
  const hk=TABS[TAB].head;
  const lg=LG.map((g,i)=>[g,i]).filter(([g])=>g.s===c).sort((a,b)=>(b[0].v[hk]||0)-(a[0].v[hk]||0));
  $('panel').innerHTML=`${crumbs([['Nigeria','ng'],[SC[c],null]])}
   <div class="ptitle"><div><h3>${esc(SC[c])}</h3><div class="tags"><span class="tag u">Capital: ${esc(s.cap)}</span><span class="tag">${lg.length} LGAs</span><span class="tag">${s.np.toLocaleString('en-NG')} places</span><span class="tag">Postcodes start ${c}</span></div></div>${confPill(s.conf)}</div>
   ${valueBlock(s.v,600,' in '+esc(s.cap),`Rural land across ${esc(SC[c])}: ${short(s.v.resR)}/m\u00b2. Listings analysed in the state: ${s.nl.toLocaleString('en-NG')}.`)}
   ${zoneTable(s.zs,'Economic zones across '+esc(SC[c]))}
   <div><p class="eyebrow" style="margin-bottom:4px">LGAs by ${TABS[TAB].layers.find(l=>l[0]===hk)[1].toLowerCase()}</p><table class="mini">${lg.map(([g,i])=>`<tr><td><button type="button" data-lga="${i}">${esc(g.n)}</button> <span class="muted small">${g.cls}</span></td><td class="r">${fmtL(hk,g.v[hk])}</td></tr>`).join('')}</table></div>`;
  setSel({kind:'state',name:s.cap+', '+SC[c],lat:s.lat,lng:s.lng,st:c,v:s.v,plot:600,conf:s.conf});
}
function nationalPanel(){
  RER=()=>nationalPanel();
  selState=null; selL=-1; selPt=null; MAPI.refresh();
  const hk=TABS[TAB].head, hn=TABS[TAB].layers.find(l=>l[0]===hk)[1].toLowerCase();
  const top=[...LG.keys()].sort((a,b)=>(LG[b].v[hk]||0)-(LG[a].v[hk]||0)).slice(0,8);
  $('panel').innerHTML=`<div class="ptitle"><div><h3>Nigeria</h3><div class="tags"><span class="tag">37 states</span><span class="tag">774 LGAs</span><span class="tag">${PL.n.length.toLocaleString('en-NG')} places</span></div></div></div>
   <p class="note">Click a state, an LGA, a dot or any house on the map, or enter coordinates above. Switch between land, building and rental values with the tabs. Each result gives the NIPOST postcode for the exact spot.</p>
   <div><p class="eyebrow" style="margin-bottom:4px">Highest LGAs, ${hn}</p><table class="mini">${top.map(i=>`<tr><td><button type="button" data-lga="${i}">${esc(LG[i].n)}</button> <span class="muted small">${LG[i].s}</span></td><td class="r">${fmtL(hk,LG[i].v[hk])}</td></tr>`).join('')}</table></div>
   <div><p class="eyebrow" style="margin-bottom:4px">States, capital city</p><table class="mini">${[...ST].sort((a,b)=>(b.v[hk]||0)-(a.v[hk]||0)).map(s=>`<tr><td><button type="button" data-go="s:${s.c}">${esc(SC[s.c])}</button> <span class="muted small">${esc(s.cap)}</span></td><td class="r">${fmtL(hk,s.v[hk])}</td></tr>`).join('')}</table></div>`;
}
$('panel').addEventListener('click',e=>{
  const b=e.target.closest('[data-go],[data-place],[data-lga],[data-copy],[data-sat],[data-pcgo]'); if(!b) return;
  if(b.dataset.sat){ const [a,c]=b.dataset.sat.split(',').map(Number); MAPI.sat(a,c); return; }
  if(b.dataset.pcgo){ const el=b.closest('.pc'); el.dataset.go='1'; postcodeFill(); return; }
  if(b.dataset.copy){ const t=b.dataset.copy; const done=()=>{b.textContent='Copied';}; try{ navigator.clipboard.writeText(t).then(done,()=>{}); }catch(err){} return; }
  if(b.dataset.place) return selectPlace(+b.dataset.place);
  if(b.dataset.lga) return selectLGA(+b.dataset.lga);
  const g=b.dataset.go; if(g==='ng'){ MAPI.fitAll(); nationalPanel(); } else if(g.startsWith('s:')) selectState(g.slice(2)); else if(g.startsWith('l:')) selectLGA(+g.slice(2)); else if(g.startsWith('p:')) selectPlace(+g.slice(2));
});

/* ---------- enter a pin: coordinates, map links, DMS ---------- */
function parseSpot(q){
  q=String(q||'').trim(); if(!q) return null; let m;
  const ok=(a,b)=>isFinite(a)&&isFinite(b)&&a>=3.5&&a<=14.5&&b>=2&&b<=15.5?[a,b]:(isFinite(a)&&isFinite(b)&&b>=3.5&&b<=14.5&&a>=2&&a<=15.5?[b,a]:null);
  if((m=q.match(/!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)/))) return ok(+m[1],+m[2]);
  if((m=q.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/))) return ok(+m[1],+m[2]);
  if((m=q.match(/[?&](?:q|query|ll|sll|daddr|destination|center)=(-?\d+\.\d+)(?:,|%2C)\s*(-?\d+\.\d+)/i))) return ok(+m[1],+m[2]);
  if((m=q.match(/mlat=(-?\d+\.\d+).*mlon=(-?\d+\.\d+)/))) return ok(+m[1],+m[2]);
  if((m=q.match(/#map=\d+\/(-?\d+\.\d+)\/(-?\d+\.\d+)/))) return ok(+m[1],+m[2]);
  if((m=q.match(/#at=(-?\d+\.\d+),(-?\d+\.\d+)/))) return ok(+m[1],+m[2]);
  const dms=[...q.matchAll(/(\d{1,3})\s*[\u00b0d:\s]\s*(\d{1,2})?\s*['\u2032m:\s]?\s*(\d{1,2}(?:\.\d+)?)?\s*["\u2033s]?\s*([NSEW])/gi)];
  if(dms.length>=2){ const dec=x=>(+x[1]+(+x[2]||0)/60+(+x[3]||0)/3600)*(/[SW]/i.test(x[4])?-1:1); const a=dms.find(x=>/[NS]/i.test(x[4])), b=dms.find(x=>/[EW]/i.test(x[4])); if(a&&b) return ok(dec(a),dec(b)); }
  if((m=q.match(/^\s*(-?\d{1,2}(?:\.\d+)?)\s*[,;\s]\s*(-?\d{1,2}(?:\.\d+)?)\s*$/))) return ok(+m[1],+m[2]);
  return null;
}
function goSpot(){ const p=parseSpot($('pinq').value); const msg=$('pinmsg');
  if(!p){ msg.textContent='Enter latitude and longitude (e.g. 9.0765, 7.3986), degrees-minutes-seconds, or paste a Google Maps, Apple Maps or OpenStreetMap link.'; return; }
  if(!pickSpot(p[0],p[1],true)){ msg.textContent='That point is outside Nigeria.'; return; }
  msg.textContent=`Valued ${p[0].toFixed(5)}, ${p[1].toFixed(5)}.`; history.replaceState(null,'','#at='+p[0].toFixed(5)+','+p[1].toFixed(5)); }
$('pinform').addEventListener('submit',e=>{ e.preventDefault(); goSpot(); });
$('pinme').addEventListener('click',()=>{ const msg=$('pinmsg'); if(!navigator.geolocation){ msg.textContent='This browser cannot share its location.'; return; }
  msg.textContent='Finding you\u2026'; navigator.geolocation.getCurrentPosition(p=>{ $('pinq').value=p.coords.latitude.toFixed(6)+', '+p.coords.longitude.toFixed(6); goSpot(); }, err=>{ msg.textContent='Location not available ('+err.message+').'; },{enableHighAccuracy:true,timeout:15000}); });

/* ---------- search ---------- */
let SIDX=null;
function buildSearch(){ SIDX=PL.n.map(norm); }
function search(q){
  const pc=parsePostcode(q); if(pc) return [{k:'pc',id:pc,label:'Postcode '+pc.display,sub:SC[pc.st]+' \u00b7 LGA '+pc.lga,score:0}];
  const ll=parseSpot(q); if(ll) return [{k:'at',id:ll,label:'Coordinates '+ll[0].toFixed(5)+', '+ll[1].toFixed(5),sub:'Value this spot',score:0}];
  q=norm(q); if(q.length<2) return [];
  const out=[];
  for(const s of ST) if(norm(SC[s.c]).startsWith(q)||s.c.toLowerCase()===q) out.push({k:'s',id:s.c,label:SC[s.c],sub:'State \u00b7 capital '+s.cap,score:0});
  LG.forEach((g,i)=>{ const n=norm(g.n); if(n.startsWith(q)) out.push({k:'l',id:i,label:g.n+' LGA',sub:SC[g.s],score:1}); else if(n.includes(q)) out.push({k:'l',id:i,label:g.n+' LGA',sub:SC[g.s],score:3}); });
  const sub=j=>TYPEN[PL.t[j]]+' \u00b7 '+(PL.pa[j]>=0?PL.n[PL.pa[j]]+', ':PL.W[PL.w[j]]?PL.W[PL.w[j]]+', ':'')+LG[PL.g[j]].n+', '+SC[LG[PL.g[j]].s];
  for(let j=0;j<SIDX.length&&out.length<400;j++){ const n=SIDX[j]; if(n.startsWith(q)) out.push({k:'p',id:j,label:PL.n[j],sub:sub(j),score:2+DRANK[PL.t[j]]*0.1-Math.log10(PL.v[j]+1)*0.01}); else if(q.length>=4&&n.includes(' '+q)) out.push({k:'p',id:j,label:PL.n[j],sub:sub(j),score:4+DRANK[PL.t[j]]*0.1}); }
  return out.sort((a,b)=>a.score-b.score).slice(0,14);
}
const qi=$('q'), sg=$('sugg'); let sres=[], sact=-1;
function showSugg(){ sres=search(qi.value); sact=-1; if(!sres.length){ sg.hidden=true; return; } sg.innerHTML=sres.map((r,i)=>`<li><button type="button" role="option" data-i="${i}"><span>${esc(r.label)}</span><span class="k">${esc(r.sub)}</span></button></li>`).join(''); sg.hidden=false; }
function pick(r){ sg.hidden=true; qi.value=r.label; document.getElementById('mapsec').scrollIntoView(); if(r.k==='s') selectState(r.id); else if(r.k==='l') selectLGA(r.id); else if(r.k==='pc') showPostcode(r.id); else if(r.k==='at') pickSpot(r.id[0],r.id[1],true); else selectPlace(r.id); }
qi.addEventListener('input',showSugg);
qi.addEventListener('keydown',e=>{ if(sg.hidden) return; if(e.key==='ArrowDown'||e.key==='ArrowUp'){ e.preventDefault(); sact=(sact+(e.key==='ArrowDown'?1:-1)+sres.length)%sres.length; [...sg.querySelectorAll('button')].forEach((b,i)=>b.setAttribute('aria-selected',i===sact)); } else if(e.key==='Enter'){ e.preventDefault(); pick(sres[Math.max(0,sact)]); } else if(e.key==='Escape') sg.hidden=true; });
sg.addEventListener('click',e=>{ const b=e.target.closest('button'); if(b) pick(sres[+b.dataset.i]); });
document.addEventListener('click',e=>{ if(!e.target.closest('.searchbox')) sg.hidden=true; });

/* ---------- tables ---------- */
function sortable(tbl, cols, getRows, render, pager, pageSize=50){
  // fresh header/pager nodes so a rebuild (tab switch) does not stack listeners
  const oldH=tbl.querySelector('thead'); const thead=oldH.cloneNode(false); oldH.replaceWith(thead);
  if(pager){ const np=pager.cloneNode(false); pager.replaceWith(np); pager=np; }
  let key=cols.find(c=>c.def)?.k||cols[0].k, dir=-1, page=0;
  const tbody=tbl.querySelector('tbody');
  thead.innerHTML='<tr>'+cols.map(c=>`<th data-k="${c.sort===false?'':c.k}" class="${c.r?'r':''}">${c.h}${c.k===key?(dir<0?' \u2193':' \u2191'):''}</th>`).join('')+'</tr>';
  function go(){ const rows=getRows(); const c=cols.find(x=>x.k===key); const f=c.val||(r=>r[key]);
    rows.sort((a,b)=>{ const x=f(a), y=f(b); return (typeof x==='string'? x.localeCompare(y): (x||0)-(y||0))*dir; });
    const pages=Math.max(1,Math.ceil(rows.length/pageSize)); page=Math.min(page,pages-1);
    tbody.innerHTML=rows.slice(page*pageSize,(page+1)*pageSize).map(render).join('')||`<tr><td colspan="${cols.length}" class="muted">No matches. Clear a filter.</td></tr>`;
    if(pager) pager.innerHTML=`<button class="btn ghost sm" type="button" data-p="-1" ${page?'':'disabled'}>Previous</button><span>Page ${page+1} of ${pages} \u00b7 ${rows.length.toLocaleString('en-NG')} rows</span><button class="btn ghost sm" type="button" data-p="1" ${page<pages-1?'':'disabled'}>Next</button>`;
    thead.querySelectorAll('th').forEach(th=>{ const cc=cols.find(x=>x.k===th.dataset.k); if(cc) th.innerHTML=cc.h+(cc.k===key?(dir<0?' \u2193':' \u2191'):''); }); }
  thead.addEventListener('click',e=>{ const th=e.target.closest('th'); if(!th||!th.dataset.k) return; if(key===th.dataset.k) dir=-dir; else {key=th.dataset.k; dir=cols.find(c=>c.k===key).asc?1:-1;} page=0; go(); });
  if(pager) pager.addEventListener('click',e=>{ const b=e.target.closest('[data-p]'); if(b){ page+=+b.dataset.p; go(); tbl.scrollIntoView({block:'nearest'}); } });
  return {go, reset:()=>{page=0; go();}};
}
const confCell=c=>{ const C=CONF[c]; return `<span class="pill c-${C[0]==='X'?'L':C[0]}">${C[1]}</span>`; };
// value columns per tab: [key, header]
const TCOLS={
  land:[['res','Residential \u20a6/m\u00b2'],['com','Commercial'],['ind','Industrial'],['farm','Farmland \u20a6/ha']],
  bld:[['sale2','2-bed flat'],['sale3','3-bed flat'],['sale4','4-bed house'],['sale5','5-bed house'],['bpm','\u20a6/m\u00b2 floor'],['bcost','Build new \u20a6/m\u00b2']],
  rent:[['rent1','1-bed'],['rent2','2-bed'],['rent3','3-bed flat'],['rent4','4-bed house'],['crent','Shop \u20a6/m\u00b2'],['yld','Yield']]
};
let TBL=null, lT=null, stT=null, prenderRef=null;
function tables(){
  for(const s of [...ST].sort((a,b)=>SC[a.c].localeCompare(SC[b.c]))){ $('lst').insertAdjacentHTML('beforeend',`<option value="${s.c}">${esc(SC[s.c])}</option>`); $('pst').insertAdjacentHTML('beforeend',`<option value="${s.c}">${esc(SC[s.c])}</option>`); }
  $('stable').addEventListener('click',e=>{ const tr=e.target.closest('tr[data-go]'); if(tr){ selectState(tr.dataset.go.slice(2)); $('mapsec').scrollIntoView(); } });
  const lrows=()=>{ const q=norm($('lq').value), s=$('lst').value, c=$('lcl').value; return LG.map((g,i)=>({...g,i})).filter(g=>(!s||g.s===s)&&(!c||g.cls===c)&&(!q||norm(g.n+' '+SC[g.s]).includes(q))); };
  ['lq','lst','lcl'].forEach(id=>$(id).addEventListener('input',()=>lT&&lT.reset()));
  $('ltable').addEventListener('click',e=>{ const b=e.target.closest('[data-lga]'); if(b){ selectLGA(+b.dataset.lga); $('mapsec').scrollIntoView(); } });
  TBL=()=>{
    const tc=TCOLS[TAB], vc=tc.map(([k,h],n)=>({k,h,r:1,def:n===(TAB==='land'?0:TAB==='bld'?2:2)?1:0,val:r=>r.v[k]}));
    const cellsV=v=>tc.map(([k],n)=>`<td class="r num">${n===(TAB==='land'?0:2)?'<b>':''}${fmtL(k,v[k])}${n===(TAB==='land'?0:2)?'</b>':''}</td>`).join('');
    $('stabT').textContent=`${TABS[TAB].name} in each state capital, beside rural land.`;
    stT=sortable($('stable'),[{k:'c',h:'Code',asc:true},{k:'name',h:'State',asc:true,val:r=>SC[r.c]},{k:'cap',h:'Capital',asc:true}].concat(vc).concat(TAB==='land'?[{k:'resR',h:'Rural land \u20a6/m\u00b2',r:1,val:r=>r.v.resR}]:[]).concat([{k:'nl',h:'Listings',r:1},{k:'conf',h:'Conf.',val:r=>-r.conf}]),
      ()=>[...ST],r=>`<tr data-go="s:${r.c}" style="cursor:pointer"><td class="code mono">${r.c}</td><td class="nm">${esc(SC[r.c])}</td><td>${esc(r.cap)}</td>${cellsV(r.v)}${TAB==='land'?`<td class="r num">${short(r.v.resR)}</td>`:''}<td class="r num">${r.nl.toLocaleString('en-NG')}</td><td>${confCell(r.conf)}</td></tr>`,null,40);
    stT.go();
    lT=sortable($('ltable'),[{k:'n',h:'LGA',asc:true},{k:'s',h:'State',asc:true},{k:'cls',h:'Setting',asc:true}].concat(vc).concat(TAB==='land'?[{k:'range',h:'Village \u2192 core',r:1,val:r=>r.v.hi}]:[]).concat([{k:'np',h:'Places',r:1},{k:'ev',h:'Listings',r:1},{k:'conf',h:'Conf.',val:r=>-r.conf},{k:'x',h:'',sort:false}]),
      lrows,g=>`<tr><td class="nm">${esc(g.n)}<small>${g.km2.toLocaleString('en-NG')} km\u00b2</small></td><td class="mono">${g.s}</td><td class="small">${g.cls}</td>${cellsV(g.v)}${TAB==='land'?`<td class="r num">${short(g.v.lo)} \u2013 ${short(g.v.hi)}</td>`:''}<td class="r num">${g.np}</td><td class="r num">${g.ev||'\u2013'}</td><td>${confCell(g.conf)}</td><td><button class="linkbtn" type="button" data-lga="${g.i}">Map</button></td></tr>`,$('lpager'));
    lT.go();
    pT.page=0; prender();
  };
  // places
  const pT={page:0};
  function prender(){
    const q=norm($('pq').value), s=$('pst').value, ty=$('pty').value, so=$('psort').value, hk=TABS[TAB].head;
    const out=[]; const n=PL.n.length;
    for(let j=0;j<n;j++){ if(s&&LG[PL.g[j]].s!==s) continue; if(ty!==''){ const t=PL.t[j]; if(ty==='6'? !(t===6||t===7) : t!==+ty) continue; } if(q&&!SIDX[j].includes(q)) continue; out.push(j); }
    const sv=hk==='res'?(j=>PL.v[j]):(j=>pval(j,hk)||0);
    if(so==='v') out.sort((a,b)=>sv(b)-sv(a)); else if(so==='l') out.sort((a,b)=>sv(a)-sv(b)); else out.sort((a,b)=>PL.n[a].localeCompare(PL.n[b]));
    const ps=50, pages=Math.max(1,Math.ceil(out.length/ps)); pT.page=Math.min(pT.page,pages-1);
    const PC={land:[['res','Land \u20a6/m\u00b2'],['plot','Typical plot']],bld:[['sale3','3-bed flat'],['sale4','4-bed house']],rent:[['rent2','Rent 2-bed'],['rent3','Rent 3-bed']]}[TAB];
    $('ptable').querySelector('thead').innerHTML=`<tr><th data-k="">Place</th><th data-k="">Level</th><th data-k="">Within \u00b7 LGA</th><th data-k="">State</th>${PC.map(([,h])=>`<th data-k="" class="r">${h}</th>`).join('')}<th data-k="">Zone</th><th data-k="">Conf.</th><th data-k=""></th></tr>`;
    $('ptable').querySelector('tbody').innerHTML=out.slice(pT.page*ps,(pT.page+1)*ps).map(j=>{ const g=LG[PL.g[j]], v=placeVals(j); const within=PL.pa[j]>=0?PL.n[PL.pa[j]]:PL.W[PL.w[j]];
      return `<tr><td class="nm"><button class="linkbtn" style="font-size:inherit;font-weight:600;text-decoration:none;color:var(--ink)" type="button" data-place="${j}">${esc(PL.n[j])}</button></td><td class="small"><span class="tag ${URBAN_T.has(PL.t[j])?'u':''}">${TYPEN[PL.t[j]]}</span></td><td class="small">${within?esc(within)+' \u00b7 ':''}${esc(g.n)}</td><td class="mono">${g.s}</td>${PC.map(([k],n)=>`<td class="r num">${n===1?'':'<b>'}${k==='plot'?short(v.res*(g.plot||600)):fmtL(k,v[k])}${n===1?'':'</b>'}</td>`).join('')}<td class="small"><span class="zdot" style="background:${ZONEC[PL.z[j]]}"></span>${esc((META.zones||[])[PL.z[j]]||'')}</td><td>${confCell(PL.c[j])}</td><td><button class="linkbtn" type="button" data-place="${j}">Map</button></td></tr>`; }).join('')||'<tr><td colspan="10" class="muted">No places match.</td></tr>';
    $('ppager').innerHTML=`<button class="btn ghost sm" type="button" data-p="-1" ${pT.page?'':'disabled'}>Previous</button><span>Page ${pT.page+1} of ${pages.toLocaleString('en-NG')} \u00b7 ${out.length.toLocaleString('en-NG')} places</span><button class="btn ghost sm" type="button" data-p="1" ${pT.page<pages-1?'':'disabled'}>Next</button>`;
  }
  let pt=0; ['pq','pst','pty','psort'].forEach(id=>$(id).addEventListener('input',()=>{ clearTimeout(pt); pt=setTimeout(()=>{pT.page=0; prender();},120); }));
  $('ppager').addEventListener('click',e=>{ const b=e.target.closest('[data-p]'); if(b){ pT.page+=+b.dataset.p; prender(); } });
  $('ptable').addEventListener('click',e=>{ const b=e.target.closest('[data-place]'); if(b){ selectPlace(+b.dataset.place); $('mapsec').scrollIntoView(); } });
  TBL();
  // evidence
  const eT=sortable($('etable'),[
    {k:'label',h:'Location',asc:true},{k:'st',h:'State',asc:true},{k:'med',h:'Median',r:1},{k:'p25',h:'Middle half of listings',r:1},{k:'n',h:'Listings',r:1,def:1},{k:'x',h:'',sort:false}
  ],()=>{ const m=$('em').value, q=norm($('eq').value); return EV.filter(e=>e.m===m&&e.n>=5&&(!q||norm(e.label+' '+SC[e.st]).includes(q))); },
  e=>`<tr><td class="nm">${esc(e.label)}</td><td class="mono">${e.st}</td><td class="r num"><b>${short(e.med)}</b></td><td class="r num">${short(e.p25)} \u2013 ${short(e.p75)}</td><td class="r num">${e.n}</td><td><button class="linkbtn" type="button" data-at="${e.lat},${e.lng}">Map</button></td></tr>`,$('epager'));
  ['em','eq'].forEach(id=>$(id).addEventListener('input',eT.reset)); eT.go();
  $('etable').addEventListener('click',e=>{ const b=e.target.closest('[data-at]'); if(b){ const [a,c]=b.dataset.at.split(',').map(Number); pickSpot(a,c,true); $('mapsec').scrollIntoView(); } });
}

/* ---------- estimator: land + building + rent ---------- */
const STF={LA:1.05,FC:1,RI:1.08,NA:0.97,OG:0.97};
const nv=id=>parseFloat($(id).value)||0;
function estimate(){
  if(!SEL){ return; }
  $('e_loc').innerHTML=`<b>${esc(SEL.name)}</b> <span class="muted">(${CONF[SEL.conf][1].toLowerCase()} confidence)</span>`;
  const use=$('e_use').value; const rate=SEL.v[use]; const size=Math.max(0,nv('e_size'));
  const adj=nv('e_title')*nv('e_road')*nv('e_shape'); const r1k=v=>Math.round(v/1000)*1000;
  const land=r1k(rate*size*adj); const bf=nv('e_bld'); const gfa=bf?Math.max(0,nv('e_gfa')):0;
  const newc=r1k(BUILD*gfa*bf*nv('e_fin')*(STF[SEL.st]??0.93)); const dep=Math.min(0.7,0.02*Math.max(0,nv('e_age'))); const depAmt=r1k(newc*dep); const bld=newc-depAmt, total=land+bld;
  const band=[0.1,0.18,0.28,0.4][SEL.conf];
  // likely rent: by building type, scaled by finish
  const bt=$('e_bld').selectedIndex, v=SEL.v, fin=nv('e_fin');
  const rent=!bf?null:r1k((bt===1?(v.rent3||0)*Math.max(0.8,gfa/140): bt===2?(v.rent4||0)*Math.max(0.8,gfa/250): Math.max(1,Math.round(gfa/110))*(v.rent2||0))*Math.pow(fin,0.6)*(1-dep*0.5));
  const S=(id,x)=>$(id).textContent=x;
  S('o_total',fmt(total)); S('o_range',`Likely range ${short(total*(1-band))} to ${short(total*(1+band))}`);
  S('o_rate',fmt(sig(rate,3))); S('o_adj','\u00d7 '+adj.toFixed(3)); S('o_land',fmt(land)); S('o_new',fmt(newc)); S('o_dep',depAmt?'\u2212 '+fmt(depAmt)+` (${Math.round(dep*100)}%)`:'\u2013'); S('o_bld',fmt(bld)); S('o_usd','$'+Math.round(total/FX).toLocaleString('en-US'));
  S('o_rent',rent?fmt(rent)+' a year':'\u2013'); S('o_yield',rent&&total?(100*rent/total).toFixed(1)+'% gross':'\u2013');
  ['e_gfa','e_fin','e_age'].forEach(id=>$(id).disabled=!bf);
}
$('ef').addEventListener('input',estimate);

/* ---------- method ---------- */
function method(){
  const m=META;
  $('methodcols').innerHTML=`
  <div><h3>The evidence</h3><p>In the week of ${dlong(m.date)} we read ${m.nListings.toLocaleString('en-NG')} land, house and rental listings from Nigeria Property Centre and Jiji across all 37 states, plus Nigeria Property Centre's ${esc(m.avgMonth||'latest')} locality medians. The book is rebuilt every week. Each listing was placed on the map from its address. A land listing counts when its price and plot size are both stated; prices per m\u00b2, per plot, per acre and per hectare are converted to \u20a6 per m\u00b2.</p>
  <ul><li>${m.counts.land_res.toLocaleString('en-NG')} residential land listings</li><li>${m.counts.land_com.toLocaleString('en-NG')} commercial and mixed-use</li><li>${m.counts.land_ind.toLocaleString('en-NG')} industrial</li><li>${m.counts.land_farm.toLocaleString('en-NG')} farmland</li><li>${m.counts.rent.toLocaleString('en-NG')} rentals and ${m.counts.sale.toLocaleString('en-NG')} house sales</li></ul></div>
  <div><h3>The model</h3><p>Residential land is modelled from state, distance to the state capital and the big metros, distance to the nearest town and how built-up the surroundings are, then pulled toward the actual listings within a few kilometres. Every settlement in the GRID3 national register and every named area, district, neighbourhood, gated estate and gated area in OpenStreetMap (${PL.n.length.toLocaleString('en-NG')} places across ${PL.W.filter(Boolean).length.toLocaleString('en-NG')} wards) is valued this way, and placed in its city or town.</p>
  <p style="margin-top:8px"><b>Small towns.</b> Tested against held-out listings, the model read towns about 25% too high and state capitals about 45% too high wherever it had no listings close by, so those places are corrected. Small-town and village asking prices also carry an estate-scheme premium, so they are cut a further 15\u201330%, and capped at a share of the state capital\u2019s typical urban value unless local listings say otherwise.</p>
  <p style="margin-top:8px"><b>Economic zones.</b> Each metro, state capital and city is split into prime, high-, middle- and lower-income zones by value within that urban area; the rest are small towns, villages and remote farmland. Building and rental values use the same method on house sales and rents. Fit on held-out market locations: residential land within a factor of 2 for ${m.fit.within2}% of locations.</p></div>
  <div><h3>Reading the values</h3><ul>
   <li><span class="pill c-H">High</span> 30+ listings within a few km.</li><li><span class="pill c-M">Medium</span> 8\u201329 listings.</li><li><span class="pill c-L">Low</span> a few listings; mostly modelled.</li><li><span class="pill c-L">Modelled</span> no listings within reach.</li></ul>
   <p style="margin-top:8px">All values are asking prices. Deals usually close 5\u201315% lower. Building value per m\u00b2 is the 4-bed asking price over ${GFA4} m\u00b2 of floor; the cost to build new is the Rate Book bungalow rate with a state factor. Gross yield is a year\u2019s rent over the asking price. Satellite imagery and the street map are from Mapbox (\u00a9 Mapbox, \u00a9 OpenStreetMap, \u00a9 Maxar). Postcodes are looked up live from NIPOST\u2019s Nigeria Postcode API (postcode.gov.ng) for the exact spot you pick.</p>
   <p style="margin-top:8px">Sources: <a href="https://nigeriapropertycentre.com/market-trends/average-prices" target="_blank" rel="noopener">Nigeria Property Centre</a>, <a href="https://jiji.ng/land-and-plots-for-sale" target="_blank" rel="noopener">Jiji</a>, <a href="https://www.openstreetmap.org" target="_blank" rel="noopener">OpenStreetMap</a>, <a href="https://www.geoboundaries.org" target="_blank" rel="noopener">geoBoundaries / GRID3</a>, <a href="https://www.postcode.gov.ng" target="_blank" rel="noopener">NIPOST</a>, <a href="https://www.mapbox.com" target="_blank" rel="noopener">Mapbox</a>, <a href="https://rates.buildocrat.store/" target="_blank" rel="noopener">Buildocrat Rate Book</a>.</p></div>`;
}

/* ---------- helpers ---------- */
const MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December'];
function dlong(iso){ const d=new Date((iso||'')+'T12:00:00'); return isNaN(d)?String(iso||''):d.getDate()+' '+MONTHS[d.getMonth()]+' '+d.getFullYear(); }
const slug=s=>norm(s).replace(/ /g,'-');
let LGR=null; // decoded rings + boxes for point-in-LGA
function ringsOf(i){ if(!LGR) LGR=LG.map(g=>{ const rs=g.r.map(decode); let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9; for(const r of rs) for(const [x,y] of r){ if(x<x0)x0=x; if(x>x1)x1=x; if(y<y0)y0=y; if(y>y1)y1=y; } return {rs,bb:[x0,y0,x1,y1]}; }); return LGR[i]; }
function pipRing(x,y,r){ let c=false; for(let a=0,b=r.length-1;a<r.length;b=a++){ const [xi,yi]=r[a],[xj,yj]=r[b]; if(((yi>y)!==(yj>y))&&(x<(xj-xi)*(y-yi)/(yj-yi)+xi)) c=!c; } return c; }
function lgaContaining(lat,lng){
  let best=-1;
  for(let i=0;i<LG.length;i++){ const o=ringsOf(i), b=o.bb; if(lng<b[0]||lng>b[2]||lat<b[1]||lat>b[3]) continue; let n=0; for(const r of o.rs) if(pipRing(lng,lat,r)) n++; if(n%2===1) return i; if(n) best=i; }
  if(best>=0) return best;
  // just outside a simplified edge (coast, border): nearest LGA centre within 15 km
  let d0=15; for(let i=0;i<LG.length;i++){ const d=km(lat,lng,LG[i].lat,LG[i].lng); if(d<d0){d0=d;best=i;} } return best;
}
function pickSpot(lat,lng,fly){ const i=lgaContaining(lat,lng); if(i<0) return false; if(fly) MAPI.flyPlace(lat,lng,4); selectPoint(lat,lng,i); return true; }

/* ---------- NIPOST postcodes (postcode.gov.ng) ---------- */
const PC_RE=/^([A-Z]{2})[\s-]?(\d{2})[\s-]?([A-Z0-9]{3})[\s-]?([A-Z]{2})[\s-]?(\d{2})$/;
function parsePostcode(q){ const m=String(q||'').toUpperCase().trim().match(PC_RE); if(!m||!SC[m[1]]) return null; return {st:m[1],lga:m[2],district:m[3],area:m[4],unit:m[5],canon:m.slice(1).join('-'),display:m.slice(1).join(' ')}; }
const NP=()=>window.LB_CONFIG||{};
const pcCache=new Map();
function postcodeIdle(st){ return `<p class="eyebrow">NIPOST postcode</p><p class="note">Postcodes in ${esc(SC[st])} start <b class="mono">${st}</b>.${NP().nipostKey?' Looking up this spot\u2026':' Use postcode.gov.ng to find the building\u2019s full code.'}</p>`; }
async function nipost(path){
  const c=NP(); const r=await fetch((c.nipostBase||'https://api.postcode.gov.ng')+path,{headers:{'X-API-Key':c.nipostKey,'Accept':'application/json'}});
  let j=null; try{ j=await r.json(); }catch(e){}
  if(!r.ok) throw new Error((j&&(j.message||j.error||(j.error&&j.error.code)))||('HTTP '+r.status));
  return j;
}
async function postcodeFill(){
  const el=document.querySelector('#panel .pc'); if(!el) return; const c=NP(); if(!c.nipostKey) return;
  const [la,lo]=el.dataset.pc.split(',').map(Number); const exact=el.dataset.exact==='1';
  const rad=exact?Math.min(250,c.nipostRadius||120):250; const key=la.toFixed(5)+','+lo.toFixed(5)+','+rad;
  try{
    let j=pcCache.get(key); if(!j){ j=await nipost(`/v1/search/reverse?lat=${la.toFixed(6)}&lng=${lo.toFixed(6)}&max_distance_m=${rad}`); pcCache.set(key,j); }
    if(!el.isConnected) return;
    if(j&&j.found&&j.unit){ const u=j.unit, conf=u.confidence?` \u00b7 ${esc(u.confidence)} confidence`:'';
      const addr=[u.address,u.locality_name,u.lga_name,u.state_name].filter(Boolean).map(esc).join(', ');
      el.innerHTML=`<p class="eyebrow">NIPOST postcode${exact?'':' near the centre of this place'}</p><div class="pcode"><span class="mono">${esc(u.display||u.postcode)}</span><button class="linkbtn" type="button" data-copy="${esc(u.display||u.postcode)}">Copy</button></div>
        <p class="note">Nearest addressed building, ${Math.round(u.distance_m||0)} m from the ${exact?'pin':'place centre'}${conf}.${addr?' '+addr+'.':''} Source: NIPOST, postcode.gov.ng.</p>`;
    } else {
      const area=j&&(j.area||j.district); el.innerHTML=`<p class="eyebrow">NIPOST postcode</p><p class="note">No addressed building within ${j&&j.radius_m||rad} m of this spot${area?`; NIPOST area <b class="mono">${esc(area)}</b>`:''}. Click closer to a building, or zoom to the satellite close-up and pick the roof.</p>`;
    }
  }catch(err){ if(el.isConnected) el.innerHTML=`<p class="eyebrow">NIPOST postcode</p><p class="note">The postcode service did not answer (${esc(err.message)}). Postcodes in ${esc(SC[el.dataset.st])} start <b class="mono">${esc(el.dataset.st)}</b>; postcode.gov.ng has the full code.</p>`; }
}
async function showPostcode(p){
  selectState(p.st);
  const box=document.createElement('div'); box.className='pc';
  box.innerHTML=`<p class="eyebrow">Postcode ${esc(p.display)}</p><p class="note">State <b>${esc(SC[p.st])}</b> \u00b7 LGA ${p.lga} \u00b7 district ${p.district} \u00b7 area ${p.area} \u00b7 unit ${p.unit}.${NP().nipostKey?' Checking with NIPOST\u2026':''}</p>`;
  $('panel').querySelector('.ptitle').after(box);
  if(!NP().nipostKey) return;
  try{ const j=await nipost(`/v1/lookup?code=${encodeURIComponent(p.canon)}&level=1`); const ok=j&&(j.valid??j.is_valid??j.exists??(j.status==='valid'));
    box.querySelector('.note').insertAdjacentHTML('beforeend',` <b>${ok===false?'NIPOST does not recognise this postcode.':ok?'Valid NIPOST postcode.':''}</b>`); }
  catch(err){ box.querySelector('.note').insertAdjacentHTML('beforeend',' NIPOST check unavailable.'); }
}

/* ---------- Mapbox GL satellite map ---------- */
function loadMapbox(){ return new Promise((ok,no)=>{ if(window.mapboxgl) return ok();
  const v='3.10.0', l=document.createElement('link'); l.rel='stylesheet'; l.href=`https://api.mapbox.com/mapbox-gl-js/v${v}/mapbox-gl.css`; document.head.appendChild(l);
  const s=document.createElement('script'); s.src=`https://api.mapbox.com/mapbox-gl-js/v${v}/mapbox-gl.js`; s.onload=()=>ok(); s.onerror=no; document.head.appendChild(s); }); }
function MapboxMap(){
  const c=NP(); mapboxgl.accessToken=c.mapboxToken;
  const el=$('mbmap'); el.hidden=false; canvas.hidden=true; $('mapcard').classList.add('mb'); $('basemap').hidden=false;
  const NG=[[2.65,4.2],[14.7,13.9]];
  let sat=true, curLayer=null, selShown=-1, hoverShown=-1, marker=null, plTimer=0;
  const map=new mapboxgl.Map({container:el, style:c.styleSatellite||'mapbox://styles/mapbox/satellite-streets-v12', bounds:NG, fitBoundsOptions:{padding:16}, maxBounds:[[-4,0],[22,18]], projection:'mercator', attributionControl:true});
  map.addControl(new mapboxgl.NavigationControl({showCompass:false}),'bottom-right');
  const geo=new mapboxgl.GeolocateControl({positionOptions:{enableHighAccuracy:true},fitBoundsOptions:{maxZoom:17},showUserLocation:true});
  map.addControl(geo,'bottom-right'); geo.on('geolocate',p=>pickSpot(p.coords.latitude,p.coords.longitude,false));
  map.addControl(new mapboxgl.ScaleControl({unit:'metric'}),'bottom-right');
  const LKEYS=LAYERS.map(l=>l[0]);
  const lgaFC={type:'FeatureCollection',features:LG.map((g,i)=>{ const p={i}; for(const k of LKEYS) p['k_'+k]=cls(k,g.v[k]); return {type:'Feature',id:i,properties:p,geometry:{type:'MultiPolygon',coordinates:ringsOf(i).rs.map(r=>[r])}}; })};
  const stFC={type:'FeatureCollection',features:BORDERS.map(b=>({type:'Feature',properties:{c:b.c},geometry:{type:'MultiLineString',coordinates:b.r.map(decode)}}))};
  const colr=()=>{ const e=['match',['get','k_'+layer]]; for(let i=0;i<7;i++) e.push(i,layer==='zone'?ZONEC[i]:COL.s[i]); e.push(COL.nd); return e; };
  function placesFC(){
    const z=map.getZoom(), b=map.getBounds(); const maxT=z<6.2?0: z<7.6?1: z<9?2: z<10.3?4: z<11.3?5: 7;
    let js=[];
    if(z<6.2){ for(let j=0;j<PL.t.length;j++) if(PL.t[j]===0) js.push(j); }
    else { const gx0=Math.floor(b.getWest()*5), gx1=Math.floor(b.getEast()*5), gy0=Math.floor(b.getSouth()*5), gy1=Math.floor(b.getNorth()*5);
      for(let gx=gx0;gx<=gx1;gx++) for(let gy=gy0;gy<=gy1;gy++){ const a=PIDX.get(gx+':'+gy); if(a) for(const j of a) if(DRANK[PL.t[j]]<=maxT) js.push(j); } }
    if(js.length>7000){ js.sort((a,b)=>DRANK[PL.t[a]]-DRANK[PL.t[b]]||PL.v[b]-PL.v[a]); js=js.slice(0,7000); }
    return {type:'FeatureCollection',features:js.map(j=>({type:'Feature',properties:{j,n:PL.n[j],t:DRANK[PL.t[j]],e:PL.t[j]>=8?1:0,col:colOf(layer,cls(layer,pval(j,layer)))},geometry:{type:'Point',coordinates:[PL.lo[j]/1e4,PL.la[j]/1e4]}}))};
  }
  function addLayers(){
    const halo=sat?'rgba(10,16,13,.85)':'#ffffff', ink=sat?'#ffffff':'#16201B', edge=sat?'rgba(255,255,255,.55)':'rgba(22,32,27,.35)';
    map.addSource('lga',{type:'geojson',data:lgaFC}); map.addSource('st',{type:'geojson',data:stFC}); const pfc=placesFC(); map.addSource('pl',{type:'geojson',data:pfc}); map.addSource('plL',{type:'geojson',data:pfc}); // labels in their own source: a missing font never hides the dots
    const op=sat?['interpolate',['linear'],['zoom'],5,0.6,9,0.42,12,0.16,14.5,0]:['interpolate',['linear'],['zoom'],5,0.78,10,0.5,13,0.22,15,0.08];
    map.addLayer({id:'lga-fill',type:'fill',source:'lga',paint:{'fill-color':colr(),'fill-opacity':op}});
    map.addLayer({id:'lga-edge',type:'line',source:'lga',paint:{'line-color':edge,'line-width':['interpolate',['linear'],['zoom'],5,0.4,10,1]}});
    map.addLayer({id:'lga-hi',type:'line',source:'lga',paint:{'line-color':COL.pin,'line-width':['case',['boolean',['feature-state','sel'],false],3.2,['boolean',['feature-state','hover'],false],1.8,0],'line-opacity':['case',['boolean',['feature-state','sel'],false],1,['boolean',['feature-state','hover'],false],0.9,0]}});
    map.addLayer({id:'st-line',type:'line',source:'st',paint:{'line-color':sat?'#ffffff':'#3f4b44','line-width':['interpolate',['linear'],['zoom'],5,1.1,10,2.2],'line-opacity':0.85}});
    map.addLayer({id:'st-sel',type:'line',source:'st',filter:['==',['get','c'],selState||''],paint:{'line-color':COL.pin,'line-width':3.4}});
    map.addLayer({id:'pl-dot',type:'circle',source:'pl',paint:{'circle-color':['get','col'],
      'circle-radius':['interpolate',['linear'],['zoom'],5,['match',['get','t'],0,4.5,1,3,2],12,['match',['get','t'],0,8,1,7,2,6,3,5.5,4,5,4.5],16,['match',['get','t'],0,10,1,9,2,8,6.5]],
      'circle-stroke-color':['case',['==',['get','e'],1],COL.pin,sat?'#ffffff':'#16201B'],'circle-stroke-width':['match',['get','t'],0,1.6,1,1.4,1],'circle-opacity':['interpolate',['linear'],['zoom'],14,1,17,0.55]}});
    map.addLayer({id:'pl-lab',type:'symbol',source:'plL',layout:{'text-field':['get','n'],'text-font':['DIN Pro Medium','Arial Unicode MS Regular'],'text-size':['match',['get','t'],0,14,1,13,2,12.5,11.5],
      'text-variable-anchor':['left','right','top','bottom'],'text-radial-offset':0.7,'text-justify':'auto','symbol-sort-key':['+',['*',['get','t'],10],['*',['get','e'],-5]],'text-optional':true,'text-max-width':10},
      paint:{'text-color':ink,'text-halo-color':halo,'text-halo-width':1.6}});
    curLayer=layer; selShown=-1; hoverShown=-1; api.refresh();
  }
  map.on('style.load',addLayers);
  map.on('moveend',()=>{ clearTimeout(plTimer); plTimer=setTimeout(()=>{ const s=map.getSource('pl'), sL=map.getSource('plL'); if(s){ const d=placesFC(); s.setData(d); if(sL) sL.setData(d); } },60); });
  const setHover=i=>{ if(i===hoverShown) return; if(hoverShown>=0) map.setFeatureState({source:'lga',id:hoverShown},{hover:false}); hoverShown=i; if(i>=0) map.setFeatureState({source:'lga',id:i},{hover:true}); };
  const box=p=>[[p.x-6,p.y-6],[p.x+6,p.y+6]];
  map.on('mousemove',e=>{
    const f=map.getLayer('pl-dot')?map.queryRenderedFeatures(box(e.point),{layers:['pl-dot']})[0]:null;
    const r=el.getBoundingClientRect(); const i=f?PL.g[f.properties.j]:lgaContainingFast(e.lngLat.lat,e.lngLat.lng);
    setHover(i);
    if(f){ tip.innerHTML=tipPlace(f.properties.j); el.style.cursor='pointer'; }
    else if(i>=0){ tip.innerHTML=tipLGA(i); el.style.cursor='crosshair'; }
    if(i>=0||f){ tip.hidden=false; let x=e.point.x+14, y=e.point.y+12; if(x>r.width-250) x=e.point.x-250; if(y>r.height-100) y=e.point.y-90; tip.style.left=x+'px'; tip.style.top=y+'px'; } else tip.hidden=true;
  });
  map.on('mouseout',()=>{ tip.hidden=true; setHover(-1); });
  map.on('movestart',()=>{ tip.hidden=true; });
  map.on('click',e=>{ const f=map.queryRenderedFeatures(box(e.point),{layers:['pl-dot']})[0];
    if(f&&map.getZoom()<15.5){ selectPlace(f.properties.j,false); return; }
    pickSpot(e.lngLat.lat,e.lngLat.lng,false); });
  // quick LGA lookup for hover (bbox prefilter, cached)
  let lastH=null; function lgaContainingFast(la,lo){ const k=la.toFixed(3)+','+lo.toFixed(3); if(lastH&&lastH[0]===k) return lastH[1]; const i=lgaContaining(la,lo); lastH=[k,i]; return i; }
  function setBase(s){ if(s===sat) return; sat=s; [...$('basemap').children].forEach(b=>b.setAttribute('aria-pressed',(b.dataset.b==='sat')===sat)); map.setStyle(sat?(c.styleSatellite||'mapbox://styles/mapbox/satellite-streets-v12'):(c.styleStreets||'mapbox://styles/mapbox/light-v11'),{diff:false}); }
  $('basemap').addEventListener('click',e=>{ const b=e.target.closest('button'); if(b) setBase(b.dataset.b==='sat'); });
  const whenReady=f=>{ if(map.loaded()) f(); else { f(); map.once('load',f); } };  // move now, and again once loaded
  const api={ kind:'mapbox', map,
    refresh(){ if(!map.isStyleLoaded()||!map.getLayer('lga-fill')) return;
      if(curLayer!==layer){ map.setPaintProperty('lga-fill','fill-color',colr()); curLayer=layer; const d=placesFC(); map.getSource('pl').setData(d); map.getSource('plL').setData(d); }
      if(selShown!==selL){ if(selShown>=0) map.setFeatureState({source:'lga',id:selShown},{sel:false}); if(selL>=0) map.setFeatureState({source:'lga',id:selL},{sel:true}); selShown=selL; }
      map.setFilter('st-sel',['==',['get','c'],selState||'']);
      if(selPt){ if(!marker) marker=new mapboxgl.Marker({color:COL.pin}); marker.setLngLat([selPt[1],selPt[0]]).addTo(map); } else if(marker) marker.remove(); },
    // moves asked for before the map has loaded (deep links) wait for it, so the initial fit doesn't undo them
    fitAll(){ whenReady(()=>map.fitBounds(NG,{padding:16})); },
    fitLL(a,b,c2,d){ whenReady(()=>map.fitBounds([[b,a],[d,c2]],{padding:30,maxZoom:13})); },
    fitLGA(i){ const [a,b,c2,d]=lgaBox(i); whenReady(()=>map.fitBounds([[b,a],[d,c2]],{padding:30,maxZoom:13})); },
    flyPlace(la,lo,t){ const o={center:[lo,la],zoom:Math.max(map.getZoom(),t<=1?11.5:14.5)}; if(map.loaded()) map.flyTo({...o,essential:true}); else map.jumpTo(o); },
    zoom(f){ f>1?map.zoomIn():map.zoomOut(); },
    sat(la,lo){ setBase(true); map.flyTo({center:[lo,la],zoom:18,essential:true}); $('mapsec').scrollIntoView({block:'start'}); } };
  return api;
}

/* ---------- deep links: #state=LA  #lga=LA/ikeja  #at=6.45,3.42  #postcode=EK-01-A03-FK-01 ---------- */
function route(){
  const h=decodeURIComponent(location.hash.slice(1)); if(!h) return false; const [k,v]=h.split('=');
  if(k==='state'&&SC[v]&&STI[v]!=null){ selectState(v); return true; }
  if(k==='lga'&&v){ const [s,l]=v.split('/'); const i=LG.findIndex(g=>g.s===s&&slug(g.n)===l); if(i>=0){ selectLGA(i); return true; } }
  if(k==='at'&&v){ const [a,b]=v.split(',').map(Number); if(isFinite(a)&&isFinite(b)) return pickSpot(a,b,true); }
  if(k==='postcode'&&v){ const p=parsePostcode(v); if(p){ showPostcode(p); return true; } }
  return false;
}

/* ---------- boot ---------- */
(async()=>{
  readColors();
  try{ await load(); }catch(err){ $('panel').innerHTML='<p class="note">The data files did not load. Reload the page to try again.</p>'; return; }
  FX=META.fx||FX; BUILD=META.build||BUILD;
  $('edDate').textContent=dlong(META.date); $('edFx').textContent=FX.toLocaleString('en-NG'); $('sDate').textContent=dlong(META.date);
  $('buildRate').textContent=fmt(BUILD); document.querySelectorAll('.evDate').forEach(e=>e.textContent=dlong(META.date));
  $('sPlaces').textContent=PL.n.length.toLocaleString('en-NG'); $('hPlaces').textContent=PL.n.length.toLocaleString('en-NG'); $('sWards').textContent=PL.W.filter(Boolean).length.toLocaleString('en-NG'); $('sEv').textContent=EV.filter(e=>e.m==='land_res').length.toLocaleString('en-NG');
  $('sListings').textContent=META.nListings.toLocaleString('en-NG'); $('hListings').textContent=META.nListings.toLocaleString('en-NG');
  buildPaths(); computeBreaks(); buildLayers(); legend(); buildSearch();
  if(NP().mapboxToken){ try{ await loadMapbox(); if(mapboxgl.supported&&!mapboxgl.supported()) throw new Error('WebGL unavailable'); MAPI=MapboxMap(); }catch(err){ console.warn('Mapbox unavailable, using the plain map', err); MAPI=CANVAS_MAP; $('mbmap').hidden=true; canvas.hidden=false; } }
  if(MAPI===CANVAS_MAP){ resize(); fitAll(); new ResizeObserver(()=>resize()).observe(canvas); }
  if(!route()) nationalPanel();
  window.addEventListener('hashchange',route);
  tables(); method();
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{readColors(); MAPI.refresh();});
  new MutationObserver(()=>{readColors(); MAPI.refresh();}).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
})();

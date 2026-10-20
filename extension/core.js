/* Buildocrat Value Lens: valuation core (same formulas as value.buildocrat.store/app.js).
   Loaded by the service worker. Plain script, no modules. */
'use strict';
var VL = (function () {
  const SC = {AB:'Abia',AD:'Adamawa',AK:'Akwa Ibom',AN:'Anambra',BA:'Bauchi',BY:'Bayelsa',BE:'Benue',BR:'Borno',CR:'Cross River',DE:'Delta',EB:'Ebonyi',ED:'Edo',EK:'Ekiti',EN:'Enugu',FC:'FCT, Abuja',GM:'Gombe',IM:'Imo',JI:'Jigawa',KD:'Kaduna',KN:'Kano',KT:'Katsina',KE:'Kebbi',KG:'Kogi',KW:'Kwara',LA:'Lagos',NA:'Nasarawa',NI:'Niger',OG:'Ogun',ON:'Ondo',OS:'Osun',OY:'Oyo',PL:'Plateau',RI:'Rivers',SK:'Sokoto',TA:'Taraba',YB:'Yobe',ZA:'Zamfara'};
  const TYPEN = ['City','Town','District','Area','Neighbourhood','Village','Hamlet','Locality','Gated estate','Gated area'];
  const STF = {LA:1.05,FC:1,RI:1.08,NA:0.97,OG:0.97};
  const GFA4 = 250;
  const KEYS = ['res','com','ind','farm','rent1','rent2','rent3','rent4','sale2','sale3','sale4','sale5'];
  let LG = null, PL = null, META = null, PIDX = null, RINGS = null, BUILD = 367748, loaded = false;

  function decode(enc) { const out = []; let x = 0, y = 0; for (const p of enc.split(' ')) { const k = p.indexOf(','); x += +p.slice(0, k); y += +p.slice(k + 1); out.push([x / 1000, y / 1000]); } return out; }
  function km(a, b, c, d) { const R = 6371, t = Math.PI / 180; const h = Math.sin((c - a) * t / 2) ** 2 + Math.cos(a * t) * Math.cos(c * t) * Math.sin((d - b) * t / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); }
  function derive(v, st) { v.bpm = v.sale4 ? v.sale4 / GFA4 : null; v.bcost = BUILD * (STF[st] ?? 0.93); v.yld = (v.rent3 && v.sale3) ? 100 * v.rent3 / v.sale3 : null; return v; }
  const RURAL = t => t === 5 || t === 6 || t === 7;

  async function gunzipJson(url) {
    const res = await fetch(url); if (!res.ok) throw new Error(url + ' ' + res.status);
    const buf = new Uint8Array(await res.arrayBuffer());
    let text;
    if (buf.length >= 2 && buf[0] === 0x1f && buf[1] === 0x8b) {
      const ds = new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'));
      text = await new Response(ds).text();
    } else text = new TextDecoder().decode(buf);
    return JSON.parse(text);
  }
  async function load(base) {
    if (base.slice(-1) !== '/') base += '/';
    const man = await fetch(base + 'data/manifest.json').then(r => { if (!r.ok) throw new Error('manifest ' + r.status); return r.json(); });
    const summary = await gunzipJson(base + man.summary);
    LG = summary.lgas; META = summary.meta; BUILD = META.build || BUILD;
    const n = META.nPlaces;
    const [W, geos, chunks] = await Promise.all([
      gunzipJson(base + man.wards),
      Promise.all(Object.values(man.geo).map(u => gunzipJson(base + u))),
      Promise.all(Object.values(man.places).map(u => gunzipJson(base + u)))
    ]);
    PL = { n: Array(n), t: Array(n), la: Array(n), lo: Array(n), g: Array(n), v: Array(n), c: Array(n), w: Array(n), z: Array(n), W: W, pa: new Int32Array(n).fill(-1) };
    for (const ch of chunks) {
      let id = 0, la = 0, lo = 0;
      for (let k = 0; k < ch.n.length; k++) {
        id = k ? id + ch.id[k] : ch.id[0];
        la += ch.la[k]; lo += ch.lo[k];
        PL.n[id] = ch.n[k]; PL.t[id] = ch.t[k]; PL.la[id] = la; PL.lo[id] = lo;
        PL.g[id] = ch.g[k]; PL.v[id] = ch.v[k]; PL.c[id] = ch.c[k]; PL.w[id] = ch.w[k]; PL.z[id] = ch.z[k];
        if (ch.pa[k] >= 0) PL.pa[id] = ch.pa[k];
      }
    }
    for (const g of LG) derive(g.v, g.s);
    for (const geo of geos) for (const row of geo.r) LG[row.i].r = row.r;
    PIDX = new Map();
    for (let j = 0; j < n; j++) { const k = Math.floor(PL.lo[j] / 2000) + ':' + Math.floor(PL.la[j] / 2000); let arr = PIDX.get(k); if (!arr) { arr = []; PIDX.set(k, arr); } arr.push(j); }
    RINGS = LG.map(g => { const rs = (g.r || []).map(decode); let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (const r of rs) for (const [x, y] of r) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; } return { rs, bb: [x0, y0, x1, y1] }; });
    loaded = true;
    return { date: META.date, places: n };
  }
  function pip(x, y, r) { let c = false; for (let a = 0, b = r.length - 1; a < r.length; b = a++) { const [xi, yi] = r[a], [xj, yj] = r[b]; if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) c = !c; } return c; }
  function lgaAt(lat, lng) {
    let best = -1;
    for (let i = 0; i < LG.length; i++) { const o = RINGS[i], b = o.bb; if (lng < b[0] || lng > b[2] || lat < b[1] || lat > b[3]) continue; let n = 0; for (const r of o.rs) if (pip(lng, lat, r)) n++; if (n % 2 === 1) return i; if (n) best = i; }
    if (best >= 0) return best;
    let d0 = 15; for (let i = 0; i < LG.length; i++) { const d = km(lat, lng, LG[i].lat, LG[i].lng); if (d < d0) { d0 = d; best = i; } } return best;
  }
  function placeVals(j) {
    const g = LG[PL.g[j]], v = PL.v[j], r = v / g.v.res, B = META.beta;
    const o = { res: v };
    o.com = g.v.com * Math.pow(r, B.com); o.ind = g.v.ind * Math.pow(r, B.ind);
    o.farm = (g.v.farm && RURAL(PL.t[j])) ? Math.min(g.v.farm * Math.pow(r / ((g.v.resR || g.v.res) / g.v.res), B.farm), v * 5000) : null;
    for (const k of ['rent1','rent2','rent3','rent4','sale2','sale3','sale4','sale5']) o[k] = g.v[k] ? g.v[k] * Math.pow(r, B[k] ?? 0.4) : null;
    o.crent = g.v.crent ? g.v.crent * Math.pow(r, B.com) : null; o.zone = PL.z[j];
    if (o.rent1 && o.rent2) o.rent2 = Math.max(o.rent2, o.rent1 * 1.15); if (o.rent2 && o.rent3) o.rent3 = Math.max(o.rent3, o.rent2 * 1.2); if (o.rent3 && o.rent4) o.rent4 = Math.max(o.rent4, o.rent3 * 1.15);
    if (o.sale2 && o.sale3) o.sale3 = Math.max(o.sale3, o.sale2 * 1.15); if (o.sale3 && o.sale4) o.sale4 = Math.max(o.sale4, o.sale3 * 1.25); if (o.sale4 && o.sale5) o.sale5 = Math.max(o.sale5, o.sale4 * 1.15);
    return derive(o, g.s);
  }
  function nearest(lat, lng, k, maxKm) {
    const out = []; const gx = Math.floor(lng * 10000 / 2000), gy = Math.floor(lat * 10000 / 2000);
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) { const a = PIDX.get((gx + dx) + ':' + (gy + dy)); if (a) for (const j of a) { const d = km(lat, lng, PL.la[j] / 1e4, PL.lo[j] / 1e4); if (d <= maxKm) out.push([j, d]); } }
    out.sort((a, b) => a[1] - b[1]); return out.slice(0, k);
  }
  function ancestors(j) { const out = []; let p = PL.pa[j], n = 0; while (p >= 0 && n < 5) { out.unshift(PL.n[p]); p = PL.pa[p]; n++; } return out; }
  // value at any point: blend of the nearest mapped places (inverse-distance, in logs), else the LGA
  function valueAt(lat, lng) {
    if (!loaded) return { error: 'loading' };
    if (lat < 3.8 || lat > 14.2 || lng < 2.5 || lng > 15) return { outside: true };
    const i = lgaAt(lat, lng); if (i < 0) return { outside: true };
    const g = LG[i]; const nb = nearest(lat, lng, 6, 8);
    let v, conf = 3, near = null;
    if (nb.length) {
      const acc = {}, wk = {}; KEYS.forEach(k => { acc[k] = 0; wk[k] = 0; });
      for (const [j, d] of nb) { const w = 1 / Math.max(0.3, d) ** 2; const pv = placeVals(j); KEYS.forEach(k => { if (pv[k] > 0) { acc[k] += w * Math.log(pv[k]); wk[k] += w; } }); }
      v = {}; KEYS.forEach(k => v[k] = wk[k] > 0 ? Math.exp(acc[k] / wk[k]) : null);
      if (v.farm != null && wk.farm < 0.5 * wk.res) v.farm = null;
      v.crent = g.v.crent; v.zone = PL.z[nb[0][0]]; conf = Math.max(...nb.slice(0, 2).map(([j]) => PL.c[j]));
      const j0 = nb[0][0]; near = { name: PL.n[j0], type: TYPEN[PL.t[j0]], km: nb[0][1], within: ancestors(j0) };
    } else { v = Object.assign({}, g.v); v.res = g.v.resR || g.v.res; v.zone = 6; }
    derive(v, g.s);
    const plot = g.plot || 600;
    return { lat, lng, lga: g.n, state: SC[g.s], st: g.s, cls: g.cls, plot, conf, near, zone: (META.zones || [])[v.zone] || '', v, date: META.date };
  }
  return { load, valueAt, isLoaded: () => loaded };
})();

'use strict';
const $ = id => document.getElementById(id);
const short = n => { if (n == null || !isFinite(n)) return '–'; const t = s => s.includes('.') ? s.replace(/0+$/, '').replace(/\.$/, '') : s;
  if (n >= 1e9) return '₦' + t((n / 1e9).toFixed(2)) + 'bn'; if (n >= 1e6) { const v = n / 1e6; return '₦' + t(v.toFixed(v >= 100 ? 0 : v >= 10 ? 1 : 2)) + 'm'; }
  if (n >= 1e3) { const v = n / 1e3; return '₦' + t(v.toFixed(v >= 100 ? 0 : 1)) + 'k'; } return '₦' + Math.round(n); };
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function parseSpot(q) {
  q = String(q || '').trim(); let m;
  const ok = (a, b) => isFinite(a) && isFinite(b) ? [a, b] : null;
  if ((m = q.match(/!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)/))) return ok(+m[1], +m[2]);
  if ((m = q.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/))) return ok(+m[1], +m[2]);
  if ((m = q.match(/[?&](?:q|query|ll|center)=(-?\d+\.\d+)(?:,|%2C)\s*(-?\d+\.\d+)/i))) return ok(+m[1], +m[2]);
  if ((m = q.match(/#map=\d+\/(-?\d+\.\d+)\/(-?\d+\.\d+)/))) return ok(+m[1], +m[2]);
  if ((m = q.match(/^\s*(-?\d{1,2}(?:\.\d+)?)\s*[,;\s]\s*(-?\d{1,2}(?:\.\d+)?)\s*$/))) return ok(+m[1], +m[2]);
  return null;
}
let tab = 'land';
function setTab(t) { tab = t; [...$('tabs').children].forEach(b => b.setAttribute('aria-pressed', b.dataset.t === t)); chrome.storage.local.set({ tab: t }); }
chrome.storage.local.get(['enabled', 'tab']).then(s => { $('on').checked = s.enabled !== false; setTab(s.tab || 'land'); });
$('on').addEventListener('change', () => chrome.storage.local.set({ enabled: $('on').checked }));
$('tabs').addEventListener('click', e => { const b = e.target.closest('button'); if (b) { setTab(b.dataset.t); if (last) show(last); } });
let last = null;
function show(r) {
  last = r; const v = r.v;
  const rows = tab === 'bld' ? [['4-bed house', short(v.sale4)], ['3-bed flat', short(v.sale3)], ['Per m² of floor', short(v.bpm)], ['Build new per m²', short(v.bcost)]]
    : tab === 'rent' ? [['3-bed flat a year', short(v.rent3)], ['1-bed a year', short(v.rent1)], ['4-bed house a year', short(v.rent4)], ['Gross yield', v.yld ? v.yld.toFixed(1) + '%' : '–']]
    : [['Residential land', short(v.res) + '/m²'], ['Commercial land', short(v.com) + '/m²'], [`${r.plot} m² plot`, short(v.res * r.plot)], ['Farmland', v.farm ? short(v.farm) + '/ha' : 'built-up']];
  $('out').innerHTML = `<p>${r.near ? esc(r.near.name) + ', ' : ''}${esc(r.lga)} LGA, ${esc(r.state)}${r.zone ? ' · ' + esc(r.zone) : ''}</p>` +
    rows.map(([a, b]) => `<div>${a}: <b>${b}</b></div>`).join('') +
    `<p><a href="https://value.buildocrat.store/#at=${r.lat.toFixed(5)},${r.lng.toFixed(5)}" target="_blank" rel="noopener">Full report and postcode ↗</a></p>`;
}
async function go() {
  const p = parseSpot($('q').value); if (!p) { $('out').textContent = 'Enter latitude, longitude (e.g. 9.0765, 7.3986) or paste a map link.'; return; }
  $('out').textContent = 'Working…';
  const r = await chrome.runtime.sendMessage({ t: 'value', lat: p[0], lng: p[1] });
  if (!r || r.outside) { $('out').textContent = 'That point is outside Nigeria.'; return; }
  if (r.error) { $('out').textContent = 'Values unavailable right now (' + r.error + ').'; return; }
  show(r); $('meta').textContent = 'Land Value Book data of ' + r.date + '.';
}
$('go').addEventListener('click', go); $('q').addEventListener('keydown', e => { if (e.key === 'Enter') go(); });

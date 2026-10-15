"""Static, indexable pages for every state and LGA, plus sitemap.xml and robots.txt.

Reads docs/data/lgas.json (written by export.py) and writes into docs/.
Each page carries the headline numbers as plain HTML (so search engines and
AI assistants can read them) and links into the interactive map.
"""
import json, os, re, html, datetime, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, '..', 'docs')
CFG = json.load(open(os.path.join(HERE, '..', 'site-config.json')))
HOST = CFG.get('domain') or 'land.buildocrat.store'
D = json.load(open(os.path.join(DOCS, 'data', 'lgas.json')))
META = D['meta']
SC = {'AB':'Abia','AD':'Adamawa','AK':'Akwa Ibom','AN':'Anambra','BA':'Bauchi','BY':'Bayelsa','BE':'Benue','BR':'Borno','CR':'Cross River','DE':'Delta','EB':'Ebonyi','ED':'Edo','EK':'Ekiti','EN':'Enugu','FC':'FCT, Abuja','GM':'Gombe','IM':'Imo','JI':'Jigawa','KD':'Kaduna','KN':'Kano','KT':'Katsina','KE':'Kebbi','KG':'Kogi','KW':'Kwara','LA':'Lagos','NA':'Nasarawa','NI':'Niger','OG':'Ogun','ON':'Ondo','OS':'Osun','OY':'Oyo','PL':'Plateau','RI':'Rivers','SK':'Sokoto','TA':'Taraba','YB':'Yobe','ZA':'Zamfara'}
e = html.escape

def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower().replace('&', 'and')).strip('-')
def naira(v):
    if v is None: return '–'
    if v >= 1e9: return '₦%sbn' % ('%.2f' % (v / 1e9)).rstrip('0').rstrip('.')
    if v >= 1e6: return '₦%sm' % ('%.1f' % (v / 1e6)).rstrip('0').rstrip('.')
    return '₦{:,.0f}'.format(v)
DATE = datetime.date.fromisoformat(META['date'])
DLONG = DATE.strftime('%-d %B %Y'); MON = DATE.strftime('%B %Y')

CSS = """:root{--bg:#ECEDE9;--surface:#F7F7F3;--ink:#16201B;--muted:#56615A;--line:#CDD1C7;--accent:#0E5A4B}
@media (prefers-color-scheme:dark){:root{--bg:#101513;--surface:#171E1B;--ink:#E6EBE6;--muted:#9BA69F;--line:#2A3430;--accent:#5CC3A4;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 "Source Sans 3","Segoe UI",Roboto,Arial,sans-serif;padding:0 16px 48px}
.w{max-width:920px;margin:0 auto}a{color:var(--accent)}header{padding:14px 0;border-bottom:1px solid var(--line);display:flex;gap:16px;flex-wrap:wrap;align-items:baseline}
header b{font:700 1.1rem "Familjen Grotesk",Arial,sans-serif}h1{font:700 clamp(1.7rem,4vw,2.4rem)/1.1 "Familjen Grotesk",Arial,sans-serif;margin:24px 0 8px}
h2{font:700 1.25rem "Familjen Grotesk",Arial,sans-serif;margin:28px 0 8px}.lede{color:var(--muted);max-width:68ch}
.cta{display:inline-block;margin:14px 0;padding:10px 16px;border-radius:8px;background:var(--accent);color:#fff;text-decoration:none;font-weight:600}
table{width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:.95rem}
td,th{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left}td.r,th.r{text-align:right;font-variant-numeric:tabular-nums}
th{font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}.wrapt{overflow-x:auto}
footer{margin-top:32px;font-size:.85rem;color:var(--muted)}"""

def page(path, title, desc, body, crumbs):
    canon = f'https://{HOST}/{path}'
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": f'https://{HOST}/{u}'} for i, (n, u) in enumerate(crumbs)]}
    out = f"""<!doctype html><html lang="en-NG"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}"><link rel="canonical" href="{canon}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{canon}">
<script type="application/ld+json">{json.dumps(ld)}</script><style>{CSS}</style></head><body><div class="w">
<header><a href="/" style="text-decoration:none;color:inherit"><b>Buildocrat Land Value Book</b></a><nav>{' › '.join(f'<a href="/{u}">{e(n)}</a>' for n, u in crumbs[:-1])}</nav></header>
{body}
<footer><p>Indicative asking-price values from listings read on {DLONG}, updated weekly. Not a valuation report; for lending, sale or court use, commission an ESVARBON-registered valuer.
Published by Buildocrat alongside the <a href="https://rates.buildocrat.store/">Nigeria Construction Rate Book</a>.</p></footer></div></body></html>"""
    full = os.path.join(DOCS, path); os.makedirs(full, exist_ok=True)
    open(os.path.join(full, 'index.html'), 'w', encoding='utf-8').write(out)
    return canon

ROWS = [('res', 'Residential land', 'per m²'), ('com', 'Commercial land', 'per m²'), ('ind', 'Industrial land', 'per m²'),
        ('farm', 'Farmland', 'per hectare'), ('rent2', 'Rent, 2-bed flat', 'per year'), ('rent3', 'Rent, 3-bed flat', 'per year'),
        ('sale3', '3-bed flat, asking price', ''), ('sale4', '4-bed house, asking price', ''), ('crent', 'Shop or office rent', 'per m² per year')]
def vtable(v, extra=()):
    rows = list(extra) + [(n, naira(v.get(k)), u) for k, n, u in ROWS if v.get(k)]
    return '<table><tbody>' + ''.join(f'<tr><td>{e(n)}</td><td class="r"><b>{x}</b></td><td>{e(u)}</td></tr>' for n, x, u in rows) + '</tbody></table>'

# clear previously generated folders (named by state slug) before writing
STSLUG = {c: slug(SC[c].replace('FCT, ', '')) for c in SC}
for s in STSLUG.values():
    p = os.path.join(DOCS, s)
    if os.path.isdir(p): shutil.rmtree(p)

urls = [f'https://{HOST}/']
by = {}
for i, g in enumerate(D['lgas']): by.setdefault(g['s'], []).append((i, g))
for st in D['states']:
    c = st['c']; sn = SC[c]; ss = STSLUG[c]; lg = sorted(by.get(c, []), key=lambda x: -x[1]['v']['res'])
    lrows = ''.join(f'<tr><td><a href="/{ss}/{slug(g["n"])}/">{e(g["n"])}</a></td><td>{g["cls"]}</td><td class="r">{naira(g["v"]["res"])}</td>'
                    f'<td class="r">{naira(g["v"].get("farm"))}</td><td class="r">{naira(g["v"].get("rent3"))}</td></tr>' for i, g in lg)
    body = f"""<h1>Land prices in {e(sn)} State, {MON}</h1>
<p class="lede">Residential land in {e(st['cap'])} is about <b>{naira(st['v']['res'])} per m²</b>; rural land across {e(sn)} about {naira(st['v'].get('resR'))} per m².
Values for all {len(lg)} local government areas below, from {st['nl']:,} listings in the state and a spatial model. Postcodes in {e(sn)} start <b>{c}</b>.</p>
<a class="cta" href="/#state={c}">Open {e(sn)} on the satellite map</a>
<h2>{e(st['cap'])}, typical values</h2>{vtable(st['v'])}
<h2>Every LGA in {e(sn)}</h2><div class="wrapt"><table><thead><tr><th>LGA</th><th>Setting</th><th class="r">Land ₦/m²</th><th class="r">Farmland ₦/ha</th><th class="r">Rent 3-bed</th></tr></thead><tbody>{lrows}</tbody></table></div>"""
    urls.append(page(f'{ss}/', f'Land prices in {sn} State ({MON}) | Land Value Book',
                     f'Land value per m² in {st["cap"]} and all {len(lg)} LGAs of {sn}: residential, commercial, industrial and farmland, rents and house prices. Updated {DLONG}.',
                     body, [('Nigeria', ''), (sn, f'{ss}/')]))
    for i, g in lg:
        v = g['v']; ls = slug(g['n']); plot = g.get('plot') or 600
        body = f"""<h1>Land prices in {e(g['n'])} LGA, {e(sn)}</h1>
<p class="lede">{e(g['n'])} is a <b>{g['cls'].lower()}</b> local government area of {e(sn)} ({g['km2']:,} km², {g['np']:,} mapped places). Residential land has a median of
<b>{naira(v['res'])} per m²</b>, from about {naira(v.get('lo'))} in its villages to {naira(v.get('hi'))} in its most valuable neighbourhoods.
{f"Backed by {g['ev']} listings in or near the LGA." if g.get('ev') else 'There are no listings in the LGA, so these values are modelled from its surroundings.'}</p>
<a class="cta" href="/#lga={c}/{ls}">See {e(g['n'])} on the satellite map, with postcodes</a>
<h2>Typical values</h2>{vtable(v, [(f'Typical {plot} m² plot', naira(v['res'] * plot), 'residential')])}
<p class="lede" style="margin-top:12px">Urban parts of the LGA average {naira(v.get('resU'))} per m²; villages and rural land {naira(v.get('resR'))} per m².</p>"""
        urls.append(page(f'{ss}/{ls}/', f'Land prices in {g["n"]}, {sn} ({MON}) | Land Value Book',
                         f'{g["n"]} LGA, {sn}: residential land about {naira(v["res"])} per m², farmland, commercial and industrial land, rents and house prices. Updated {DLONG}.',
                         body, [('Nigeria', ''), (sn, f'{ss}/'), (g['n'], f'{ss}/{ls}/')]))

sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + \
     ''.join(f'<url><loc>{u}</loc><lastmod>{META["date"]}</lastmod></url>\n' for u in urls) + '</urlset>\n'
open(os.path.join(DOCS, 'sitemap.xml'), 'w').write(sm)
open(os.path.join(DOCS, 'robots.txt'), 'w').write(f'User-agent: *\nAllow: /\nSitemap: https://{HOST}/sitemap.xml\n')
open(os.path.join(DOCS, 'CNAME'), 'w').write(HOST + '\n')
if CFG.get('indexnow_key'):
    open(os.path.join(DOCS, CFG['indexnow_key'] + '.txt'), 'w').write(CFG['indexnow_key'])
open(os.path.join(DOCS, '.nojekyll'), 'w').write('')
print('pages', len(urls))

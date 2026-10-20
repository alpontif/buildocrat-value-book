"""Split the published book into a small first-view summary and per-state chunks.

The homepage loads the summary first (gzip, under 100 KB). LGA outlines and places
are fetched per state when the map, a search or a directory page needs them.
Values, coordinates and parent links are copied unchanged from lgas.json and
places.b64.txt (or from the objects export.py just built).

Filenames are content-hashed so a repeat visit can keep them. manifest.json is
the only stable name.
"""
import gzip, hashlib, html, json, math, os, re, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, '..', 'docs')
DATA = os.path.join(DOCS, 'data')
SC = {'AB':'Abia','AD':'Adamawa','AK':'Akwa Ibom','AN':'Anambra','BA':'Bauchi','BY':'Bayelsa','BE':'Benue','BR':'Borno','CR':'Cross River','DE':'Delta','EB':'Ebonyi','ED':'Edo','EK':'Ekiti','EN':'Enugu','FC':'FCT, Abuja','GM':'Gombe','IM':'Imo','JI':'Jigawa','KD':'Kaduna','KN':'Kano','KT':'Katsina','KE':'Kebbi','KG':'Kogi','KW':'Kwara','LA':'Lagos','NA':'Nasarawa','NI':'Niger','OG':'Ogun','ON':'Ondo','OS':'Osun','OY':'Oyo','PL':'Plateau','RI':'Rivers','SK':'Sokoto','TA':'Taraba','YB':'Yobe','ZA':'Zamfara'}
ZONEC = ['#1D2675', '#3C49A1', '#7D87CA', '#B7BCE6', '#E8725B', '#F2A28E', '#CDB9A6']
CONF = [('H', 'High'), ('M', 'Medium'), ('L', 'Low'), ('X', 'Modelled')]
VKEYS = ['res', 'com', 'ind', 'farm', 'rent1', 'rent2', 'rent3', 'rent4', 'sale2', 'sale3', 'sale4', 'sale5', 'crent', 'lo', 'hi', 'resU', 'resR']

# gtag and the X pixel (site rhmpt, Page View tw-rhmpt-14r33g) run after window load
# so they don't compete with the first view. gtag() still queues clicks that happen earlier.
TAGS = """<!-- Google tag (gtag.js) and X pixel rhmpt, after load -->
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
function lbLoadTags(){
  if (window.__lbTags) return; window.__lbTags = 1;
  var g = document.createElement('script');
  g.async = true;
  g.src = 'https://www.googletagmanager.com/gtag/js?id=G-BLGWN0LVSG';
  document.head.appendChild(g);
  gtag('js', new Date());
  gtag('config', 'G-BLGWN0LVSG');
  !function(e,t,n,s,u,a){e.twq||(s=e.twq=function(){s.exe?s.exe.apply(s,arguments):s.queue.push(arguments);
  },s.version='1.1',s.queue=[],u=t.createElement(n),u.async=!0,u.src='https://static.ads-twitter.com/uwt.js',
  a=t.getElementsByTagName(n)[0],a.parentNode.insertBefore(u,a))}(window,document,'script');
  twq('config','rhmpt');
  twq('event','tw-rhmpt-14r33g');
}
if (document.readyState === 'complete') setTimeout(lbLoadTags, 1);
else window.addEventListener('load', function () { setTimeout(lbLoadTags, 1); });
</script>
<script>
document.addEventListener('click', function (e) {
  var a = e.target && e.target.closest && e.target.closest('a');
  if (!a || !a.href) return;
  var u = a.href;
  if (u.indexOf('wa.me') !== -1 || u.indexOf('api.whatsapp.com') !== -1) gtag('event', 'whatsapp_click', {link_url: u});
  else if (u.indexOf('mailto:') === 0) gtag('event', 'email_click', {link_url: u});
});
</script>
"""

OLD_GA = """<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-BLGWN0LVSG"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-BLGWN0LVSG');
</script>
<script>
document.addEventListener('click', function (e) {
  var a = e.target && e.target.closest && e.target.closest('a');
  if (!a || !a.href) return;
  var u = a.href;
  if (u.indexOf('wa.me') !== -1 || u.indexOf('api.whatsapp.com') !== -1) gtag('event', 'whatsapp_click', {link_url: u});
  else if (u.indexOf('mailto:') === 0) gtag('event', 'email_click', {link_url: u});
});
</script>
"""
OLD_X = """<!-- X pixel rhmpt -->
<script>
!function(e,t,n,s,u,a){e.twq||(s=e.twq=function(){s.exe?s.exe.apply(s,arguments):s.queue.push(arguments);
},s.version='1.1',s.queue=[],u=t.createElement(n),u.async=!0,u.src='https://static.ads-twitter.com/uwt.js',
a=t.getElementsByTagName(n)[0],a.parentNode.insertBefore(u,a))}(window,document,'script');
twq('config','rhmpt');
twq('event','tw-rhmpt-14r33g');
</script>
"""
def gz_bytes(obj):
    raw = json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return gzip.compress(raw, 9, mtime=0)


def digest(blob):
    return hashlib.sha256(blob).hexdigest()[:8]


def gunzip_json(path):
    return json.loads(gzip.decompress(open(path, 'rb').read()))


def decode_places(pl):
    """Delta-coded export object -> absolute coordinates, parent index per place."""
    la = list(pl['la']); lo = list(pl['lo'])
    for i in range(1, len(la)):
        la[i] += la[i - 1]; lo[i] += lo[i - 1]
    n = len(pl['n']); pa = [-1] * n
    if pl.get('pk'):
        k = 0
        for d, p in zip(pl['pk'], pl['pp']):
            k += d; pa[k] = p
    return la, lo, pa


def abs_places_from_chunks(data_dir=DATA):
    """Rebuild absolute place columns from the published chunks. Same order and values."""
    man = json.load(open(os.path.join(data_dir, 'manifest.json')))
    W = gunzip_json(os.path.join(DOCS, man['wards']))
    n = None
    # size from summary
    summary = gunzip_json(os.path.join(DOCS, man['summary']))
    n = summary['meta']['nPlaces']
    names = [None] * n; t = [0] * n; la = [0] * n; lo = [0] * n
    g = [0] * n; v = [0] * n; c = [0] * n; w = [0] * n; z = [0] * n; pa = [-1] * n
    ap = []
    seen = 0
    for url in man['places'].values():
        ch = gunzip_json(os.path.join(DOCS, url))
        pid = pla = plo = 0
        for k in range(len(ch['n'])):
            pid = ch['id'][0] if k == 0 else pid + ch['id'][k]
            pla += ch['la'][k]; plo += ch['lo'][k]
            names[pid] = ch['n'][k]; t[pid] = ch['t'][k]; la[pid] = pla; lo[pid] = plo
            g[pid] = ch['g'][k]; v[pid] = ch['v'][k]; c[pid] = ch['c'][k]; w[pid] = ch['w'][k]
            z[pid] = ch['z'][k]; pa[pid] = ch['pa'][k]; seen += 1
        ap.extend(ch.get('ap') or [])
    if seen != n or any(x is None for x in names):
        raise SystemExit('place chunks do not cover every place (%s of %s)' % (seen, n))
    return {'n': names, 't': t, 'la': la, 'lo': lo, 'g': g, 'v': v, 'c': c, 'w': w, 'z': z, 'W': W, 'pa': pa, 'ap': sorted(set(ap))}


def load_places_absolute(data_dir=DATA):
    """Absolute places for the page builder. Chunks if published, else the legacy b64 file."""
    man_p = os.path.join(data_dir, 'manifest.json')
    if os.path.exists(man_p):
        return abs_places_from_chunks(data_dir)
    import base64
    pl = json.loads(gzip.decompress(base64.b64decode(open(os.path.join(data_dir, 'places.b64.txt')).read())))
    la, lo, pa = decode_places(pl)
    pl = dict(pl); pl['la'] = la; pl['lo'] = lo; pl['pa'] = pa
    return pl


def _clear_published(data_dir):
    for name in os.listdir(data_dir):
        if re.fullmatch(r'(summary|evidence|wards)\.[0-9a-f]{8}\.bin', name):
            os.remove(os.path.join(data_dir, name))
    for sub in ('places', 'geo'):
        p = os.path.join(data_dir, sub)
        if os.path.isdir(p):
            shutil.rmtree(p)
        os.makedirs(p, exist_ok=True)


def publish(doc, pl_delta, evidence, data_dir=DATA):
    """Write summary, per-state geometry, per-state places, wards, evidence, manifest.

    doc is the lgas.json object (states, lgas with rings, borders, meta).
    pl_delta is the columnar places object export.py builds (delta la/lo, pk/pp).
    """
    la, lo, pa = decode_places(pl_delta)
    lgas = doc['lgas']; states = doc['states']; borders = doc['borders']; meta = dict(doc['meta'])
    n = len(pl_delta['n'])
    st_of = [lgas[g]['s'] for g in pl_delta['g']]
    by = {}
    for i, s in enumerate(st_of):
        by.setdefault(s, []).append(i)
    for s, ix in by.items():
        for i, p in zip(ix, (pa[i] for i in ix)):
            if p >= 0 and st_of[p] != s:
                raise SystemExit('parent of place %s crosses a state' % i)

    n_wards = sum(1 for w in pl_delta['W'] if w)
    n_ev = sum(1 for e in evidence if e['m'] == 'land_res')
    meta['nPlaces'] = n
    meta['nWards'] = n_wards
    meta['nEv'] = n_ev
    cities = []
    for i, t in enumerate(pl_delta['t']):
        if t == 0:
            cities.append({'i': i, 'n': pl_delta['n'][i], 't': 0, 'la': la[i], 'lo': lo[i],
                           'g': pl_delta['g'][i], 'v': pl_delta['v'][i], 'c': pl_delta['c'][i],
                           'z': pl_delta['z'][i], 'w': pl_delta['w'][i]})
    summary = {
        'meta': meta,
        'states': states,
        'lgas': [{k: v for k, v in g.items() if k != 'r'} for g in lgas],
        'cities': cities,
    }
    summary_blob = gz_bytes(summary)
    if len(summary_blob) > 100 * 1024:
        raise SystemExit('summary is %s bytes, over 100 KB' % len(summary_blob))

    _clear_published(data_dir)
    def put(rel, blob):
        path = os.path.join(data_dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'wb').write(blob)
        return 'data/' + rel.replace('\\', '/')

    man = {'summary': put('summary.%s.bin' % digest(summary_blob), summary_blob),
           'evidence': None, 'wards': None, 'geo': {}, 'places': {}}
    ev_blob = gz_bytes(evidence)
    man['evidence'] = put('evidence.%s.bin' % digest(ev_blob), ev_blob)
    w_blob = gz_bytes(pl_delta['W'])
    man['wards'] = put('wards.%s.bin' % digest(w_blob), w_blob)

    ap_set = set(pl_delta.get('ap') or [])
    border_by = {}
    for b in borders:
        border_by.setdefault(b['c'], []).append(b)
    for s in sorted(by):
        rings = [{'i': i, 'r': g['r']} for i, g in enumerate(lgas) if g['s'] == s]
        geo = {'r': rings, 'b': border_by.get(s, [])}
        blob = gz_bytes(geo)
        man['geo'][s] = put('geo/%s.%s.bin' % (s, digest(blob)), blob)
        ix = by[s]
        pla = plo = 0
        las, los, ids = [], [], []
        prev = None
        for i in ix:
            las.append(la[i] - pla); los.append(lo[i] - plo); pla, plo = la[i], lo[i]
            ids.append(i if prev is None else i - prev); prev = i
        chunk = {
            'id': ids, 'n': [pl_delta['n'][i] for i in ix], 't': [pl_delta['t'][i] for i in ix],
            'la': las, 'lo': los, 'g': [pl_delta['g'][i] for i in ix], 'v': [pl_delta['v'][i] for i in ix],
            'c': [pl_delta['c'][i] for i in ix], 'w': [pl_delta['w'][i] for i in ix],
            'z': [pl_delta['z'][i] for i in ix], 'pa': [pa[i] for i in ix],
            'ap': [i for i in ix if i in ap_set],
        }
        blob = gz_bytes(chunk)
        man['places'][s] = put('places/%s.%s.bin' % (s, digest(blob)), blob)

    open(os.path.join(data_dir, 'manifest.json'), 'w', encoding='utf-8').write(json.dumps(man, separators=(',', ':')) + '\n')
    # round-trip before we touch the HTML
    back = abs_places_from_chunks(data_dir)
    for key in ('n', 't', 'g', 'v', 'c', 'w', 'z'):
        if list(back[key]) != list(pl_delta[key]):
            raise SystemExit('round-trip mismatch on ' + key)
    if back['la'] != la or back['lo'] != lo or back['pa'] != pa:
        raise SystemExit('round-trip mismatch on coordinates or parents')
    if back['W'] != pl_delta['W'] or back['ap'] != sorted(ap_set):
        raise SystemExit('round-trip mismatch on wards or approximate flags')
    # geometry round-trip
    got = {}
    for s, url in man['geo'].items():
        geo = gunzip_json(os.path.join(DOCS, url))
        for row in geo['r']:
            got[row['i']] = row['r']
    for i, g in enumerate(lgas):
        if got.get(i) != g['r']:
            raise SystemExit('geometry mismatch on LGA %s' % i)
    print('split ok: summary %s bytes, places states %s, geo states %s' % (len(summary_blob), len(man['places']), len(man['geo'])))
    for legacy in ('places.b64.txt', 'evidence.json'):
        p = os.path.join(data_dir, legacy)
        if os.path.exists(p):
            os.remove(p)
    prerender(os.path.dirname(data_dir) if os.path.basename(data_dir) == 'data' else DOCS)
    return man


def esc(s):
    return html.escape(str(s), quote=True)


def trim0(s):
    return s.rstrip('0').rstrip('.') if '.' in s else s


def short(n):
    """Same compact naira format as app.js short()."""
    if n is None or not isinstance(n, (int, float)) or not math.isfinite(n):
        return '\u2013'
    if n >= 1e9:
        return '\u20a6' + trim0('%.2f' % (n / 1e9)) + 'bn'
    if n >= 1e6:
        v = n / 1e6
        d = 0 if v >= 100 else (1 if v >= 10 else 2)
        return '\u20a6' + trim0(('%.' + str(d) + 'f') % v) + 'm'
    if n >= 1e3:
        v = n / 1e3
        d = 0 if v >= 100 else 1
        return '\u20a6' + trim0(('%.' + str(d) + 'f') % v) + 'k'
    return '\u20a6' + f'{int(round(n)):,}'


def commas(n):
    return f'{int(n):,}'


def dlong(iso):
    import datetime
    d = datetime.date.fromisoformat(iso)
    return '%d %s %d' % (d.day, d.strftime('%B'), d.year)


def conf_cell(c):
    lab, name = CONF[c][0], CONF[c][1]
    cls = 'L' if lab == 'X' else lab
    return '<span class="pill c-%s">%s</span>' % (cls, name)



def prerender(docs=DOCS):
    """Write headline numbers and the first view of each table into index.html."""
    data = os.path.join(docs, 'data')
    man = json.load(open(os.path.join(data, 'manifest.json')))
    summary = gunzip_json(os.path.join(docs, man['summary']))
    evidence = gunzip_json(os.path.join(docs, man['evidence']))
    pl = abs_places_from_chunks(data)
    meta = summary['meta']; lgas = summary['lgas']; states = summary['states']
    idx_path = os.path.join(docs, 'index.html')
    h = open(idx_path, encoding='utf-8').read()

    def put_id(src, id_, text):
        pat = r'(id="%s">)(.*?)(</)' % re.escape(id_)
        out, n = re.subn(pat, lambda m: m.group(1) + text + m.group(3), src, count=1)
        if n != 1:
            raise SystemExit('missing #%s in index.html' % id_)
        return out

    when = dlong(meta['date'])
    h = put_id(h, 'edDate', esc(when))
    h = put_id(h, 'edFx', commas(meta['fx']))
    h = put_id(h, 'hPlaces', commas(meta['nPlaces']))
    h = put_id(h, 'hListings', commas(meta['nListings']))
    h = put_id(h, 'sWards', commas(meta['nWards']))
    h = put_id(h, 'sPlaces', commas(meta['nPlaces']))
    h = put_id(h, 'sListings', commas(meta['nListings']))
    h = put_id(h, 'sDate', esc(when))
    h = put_id(h, 'sEv', commas(meta['nEv']))
    h = put_id(h, 'buildRate', short(meta['build']))
    h = re.sub(r'(<span class="evDate">)(.*?)(</span>)', lambda m: m.group(1) + esc(when) + m.group(3), h)

    def th(cols, key):
        parts = []
        for c in cols:
            dk = '' if c.get('sort') is False else c['k']
            arrow = ' \u2193' if c['k'] == key else ''
            parts.append('<th data-k="%s"%s>%s%s</th>' % (dk, ' class="r"' if c.get('r') else '', c['h'], arrow))
        return '<tr>' + ''.join(parts) + '</tr>'

    st_cols = [
        {'k': 'c', 'h': 'Code'}, {'k': 'name', 'h': 'State'}, {'k': 'cap', 'h': 'Capital'},
        {'k': 'res', 'h': 'Residential \u20a6/m\u00b2', 'r': 1}, {'k': 'com', 'h': 'Commercial', 'r': 1},
        {'k': 'ind', 'h': 'Industrial', 'r': 1}, {'k': 'farm', 'h': 'Farmland \u20a6/ha', 'r': 1},
        {'k': 'resR', 'h': 'Rural land \u20a6/m\u00b2', 'r': 1}, {'k': 'nl', 'h': 'Listings', 'r': 1},
        {'k': 'conf', 'h': 'Conf.'},
    ]
    st_rows = sorted(states, key=lambda s: -(s['v'].get('res') or 0))
    def cells(v):
        keys = ('res', 'com', 'ind', 'farm')
        out = []
        for n, k in enumerate(keys):
            bit = short(v.get(k))
            out.append('<td class="r num">%s</td>' % (('<b>%s</b>' % bit) if n == 0 else bit))
        return ''.join(out)
    st_body = ''.join(
        '<tr data-go="s:%s" style="cursor:pointer"><td class="code mono">%s</td><td class="nm">%s</td><td>%s</td>%s<td class="r num">%s</td><td class="r num">%s</td><td>%s</td></tr>'
        % (s['c'], s['c'], esc(SC[s['c']]), esc(s['cap']), cells(s['v']), short(s['v'].get('resR')), commas(s['nl']), conf_cell(s['conf']))
        for s in st_rows)
    h = replace_table(h, 'stable', th(st_cols, 'res'), st_body)

    lg_cols = [
        {'k': 'n', 'h': 'LGA'}, {'k': 's', 'h': 'State'}, {'k': 'cls', 'h': 'Setting'},
        {'k': 'res', 'h': 'Residential \u20a6/m\u00b2', 'r': 1}, {'k': 'com', 'h': 'Commercial', 'r': 1},
        {'k': 'ind', 'h': 'Industrial', 'r': 1}, {'k': 'farm', 'h': 'Farmland \u20a6/ha', 'r': 1},
        {'k': 'range', 'h': 'Village \u2192 core', 'r': 1}, {'k': 'np', 'h': 'Places', 'r': 1},
        {'k': 'ev', 'h': 'Listings', 'r': 1}, {'k': 'conf', 'h': 'Conf.'}, {'k': 'x', 'h': '', 'sort': False},
    ]
    order = sorted(range(len(lgas)), key=lambda i: -(lgas[i]['v'].get('res') or 0))
    lg_body = []
    for i in order[:50]:
        g = lgas[i]
        ev = g.get('ev') or '\u2013'
        lg_body.append(
            '<tr><td class="nm">%s<small>%s km\u00b2</small></td><td class="mono">%s</td><td class="small">%s</td>%s<td class="r num">%s \u2013 %s</td><td class="r num">%s</td><td class="r num">%s</td><td>%s</td><td><button class="linkbtn" type="button" data-lga="%s">Map</button></td></tr>'
            % (esc(g['n']), commas(g['km2']), g['s'], esc(g['cls']), cells(g['v']), short(g['v'].get('lo')), short(g['v'].get('hi')),
               commas(g['np']), ev if isinstance(ev, str) else commas(ev), conf_cell(g['conf']), i))
    h = replace_table(h, 'ltable', th(lg_cols, 'res'), ''.join(lg_body))
    h = replace_pager(h, 'lpager', 0, (len(lgas) + 49) // 50, '%s rows' % commas(len(lgas)))

    # places: highest residential value first, same stable order as the original file
    porder = sorted(range(len(pl['n'])), key=lambda j: -pl['v'][j])
    zones = meta['zones']
    p_head = '<tr><th data-k="">Place</th><th data-k="">Level</th><th data-k="">Within \u00b7 LGA</th><th data-k="">State</th><th data-k="" class="r">Land \u20a6/m\u00b2</th><th data-k="" class="r">Typical plot</th><th data-k="">Zone</th><th data-k="">Conf.</th><th data-k=""></th></tr>'
    typen = ['City', 'Town', 'District', 'Area', 'Neighbourhood', 'Village', 'Hamlet', 'Locality', 'Gated estate', 'Gated area']
    urban = {0, 1, 2, 3, 4, 8, 9}
    p_body = []
    for j in porder[:50]:
        g = lgas[pl['g'][j]]
        parent = pa_name(pl, j)
        within = (esc(parent) + ' \u00b7 ') if parent else ''
        plot = g.get('plot') or 600
        z = pl['z'][j]
        p_body.append(
            '<tr><td class="nm"><button class="linkbtn" style="font-size:inherit;font-weight:600;text-decoration:none;color:var(--ink)" type="button" data-place="%s" data-st="%s">%s</button></td><td class="small"><span class="tag %s">%s</span></td><td class="small">%s%s</td><td class="mono">%s</td><td class="r num"><b>%s</b></td><td class="r num">%s</td><td class="small"><span class="zdot" style="background:%s"></span>%s</td><td>%s</td><td><button class="linkbtn" type="button" data-place="%s" data-st="%s">Map</button></td></tr>'
            % (j, g['s'], esc(pl['n'][j]), 'u' if pl['t'][j] in urban else '', typen[pl['t'][j]], within, esc(g['n']), g['s'],
               short(pl['v'][j]), short(pl['v'][j] * plot), ZONEC[z], esc(zones[z] if zones else ''), conf_cell(pl['c'][j]), j, g['s']))
    h = replace_table(h, 'ptable', p_head, ''.join(p_body))
    h = replace_pager(h, 'ppager', 0, (len(pl['n']) + 49) // 50, '%s places' % commas(len(pl['n'])))

    ev_rows = [e for e in evidence if e['m'] == 'land_res' and e['n'] >= 5]
    ev_rows.sort(key=lambda e: -e['n'])
    e_head = '<tr><th data-k="label">Location</th><th data-k="st">State</th><th data-k="med" class="r">Median</th><th data-k="p25" class="r">Middle half of listings</th><th data-k="n" class="r">Listings \u2193</th><th data-k=""></th></tr>'
    e_body = ''.join(
        '<tr><td class="nm">%s</td><td class="mono">%s</td><td class="r num"><b>%s</b></td><td class="r num">%s \u2013 %s</td><td class="r num">%s</td><td><button class="linkbtn" type="button" data-at="%s,%s">Map</button></td></tr>'
        % (esc(e['label']), e['st'], short(e['med']), short(e['p25']), short(e['p75']), e['n'], e['lat'], e['lng'])
        for e in ev_rows[:50])
    h = replace_table(h, 'etable', e_head, e_body)
    h = replace_pager(h, 'epager', 0, max(1, (len(ev_rows) + 49) // 50), '%s rows' % commas(len(ev_rows)))

    top = order[:8]
    top_html = ''.join(
        '<tr><td><button type="button" data-lga="%s">%s</button> <span class="muted small">%s</span></td><td class="r">%s</td></tr>'
        % (i, esc(lgas[i]['n']), lgas[i]['s'], short(lgas[i]['v'].get('res'))) for i in top)
    st_html = ''.join(
        '<tr><td><button type="button" data-go="s:%s">%s</button> <span class="muted small">%s</span></td><td class="r">%s</td></tr>'
        % (s['c'], esc(SC[s['c']]), esc(s['cap']), short(s['v'].get('res'))) for s in st_rows)
    panel = (
        '<div class="ptitle"><div><h3>Nigeria</h3><div class="tags"><span class="tag">37 states</span><span class="tag">774 LGAs</span><span class="tag">%s places</span></div></div></div>'
        '<p class="note">Click a state, an LGA, a dot or any house on the map, or enter coordinates above. Switch between land, building and rental values with the tabs. Each result gives the NIPOST postcode for the exact spot.</p>'
        '<div><p class="eyebrow" style="margin-bottom:4px">Highest LGAs, residential</p><table class="mini">%s</table></div>'
        '<div><p class="eyebrow" style="margin-bottom:4px">States, capital city</p><table class="mini">%s</table></div>'
    ) % (commas(meta['nPlaces']), top_html, st_html)
    h2, n = re.subn(r'(<aside class="panel" id="panel" aria-live="polite">).*?(</aside>)',
                    lambda m: m.group(1) + panel + m.group(2), h, count=1, flags=re.S)
    if n != 1:
        raise SystemExit('panel marker missing')
    h = h2
    blob = json.dumps(man, separators=(',', ':'))
    tag = '<script type="application/json" id="lb-manifest">%s</script>' % blob
    if 'id="lb-manifest"' in h:
        h = re.sub(r'<script type="application/json" id="lb-manifest">.*?</script>', tag, h, count=1, flags=re.S)
    else:
        h = h.replace('<script src="pwa.js" defer></script>', tag + '\n<script src="pwa.js" defer></script>', 1)
    # The interactive map is the original Mapbox map. Do not inject an SVG over it.
    if 'id="mapsvg"' in h:
        h = re.sub(r'<svg id="mapsvg"[\s\S]*?</svg>\s*', '', h, count=1)
    preload = '<link rel="preload" id="lb-summary-preload" as="fetch" href="%s" fetchpriority="high" crossorigin>' % man['summary']
    if 'id="lb-summary-preload"' in h:
        h = re.sub(r'<link rel="preload" id="lb-summary-preload"[^>]*>', preload, h, count=1)
    else:
        anchor = '<link rel="preload" as="script" href="https://api.mapbox.com'
        if anchor in h:
            h = h.replace(anchor, preload + '\n' + anchor, 1)
        else:
            h = h.replace('</head>', preload + '\n</head>', 1)
    open(idx_path, 'w', encoding='utf-8').write(h)
    print('prerendered index.html', when, 'summary', os.path.getsize(os.path.join(docs, man['summary'])))


def pa_name(pl, j):
    p = pl['pa'][j]
    if p >= 0:
        return pl['n'][p]
    w = pl['W'][pl['w'][j]] if pl['W'] else ''
    return w or ''


def replace_table(h, id_, head, body):
    pat = r'(<table class="t" id="%s">\s*<thead>)(.*?)(</thead>\s*<tbody>)(.*?)(</tbody>\s*</table>)' % id_
    out, n = re.subn(pat, lambda m: m.group(1) + head + m.group(3) + body + m.group(5), h, count=1, flags=re.S)
    if n != 1:
        raise SystemExit('table #%s missing' % id_)
    return out


def replace_pager(h, id_, page, pages, label):
    prev = '<button class="btn ghost sm" type="button" data-p="-1" disabled>Previous</button>'
    nxt = '<button class="btn ghost sm" type="button" data-p="1"%s>Next</button>' % (' disabled' if page >= pages - 1 else '')
    inner = '%s<span>Page %s of %s \u00b7 %s</span>%s' % (prev, page + 1, commas(pages), label, nxt)
    pat = r'(<div class="pager" id="%s">)(.*?)(</div>)' % id_
    out, n = re.subn(pat, lambda m: m.group(1) + inner + m.group(3), h, count=1, flags=re.S)
    if n != 1:
        raise SystemExit('pager #%s missing' % id_)
    return out


def patch_shells(docs=DOCS):
    """Defer gtag and the X pixel on every built page. Font weights stay as designed."""
    n_tags = 0
    for root, dirs, files in os.walk(docs):
        dirs[:] = [d for d in dirs if d not in ('.git',)]
        for fn in files:
            if not fn.endswith('.html'):
                continue
            path = os.path.join(root, fn)
            text = open(path, encoding='utf-8').read()
            orig = text
            if OLD_GA in text:
                text = text.replace(OLD_GA, TAGS, 1)
                n_tags += 1
            if OLD_X in text:
                text = text.replace(OLD_X, '', 1)
            if text != orig:
                open(path, 'w', encoding='utf-8').write(text)
    print('patched tags on', n_tags, 'pages')


if __name__ == '__main__':
    import base64
    patch_shells(DOCS)
    b64 = os.path.join(DATA, 'places.b64.txt')
    if os.path.exists(b64):
        doc = json.load(open(os.path.join(DATA, 'lgas.json')))
        pl = json.loads(gzip.decompress(base64.b64decode(open(b64).read())))
        ev = json.load(open(os.path.join(DATA, 'evidence.json')))
        publish(doc, pl, ev, DATA)
    else:
        prerender(DOCS)

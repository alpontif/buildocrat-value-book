"""Weekly crawl of the market evidence behind the Land Value Book.

    python pipeline/crawl.py            # all sources
    python pipeline/crawl.py npc jiji   # just some of: npc, avg, jiji, rates

Writes pipeline/raw/lb_npc_land.json, lb_npc_avg.json, lb_jiji.json and pipeline/raw/run.json.
A source that fails, or returns far fewer records than last week, keeps last week's file,
so one blocked site never empties the map. Exit code is 0 unless every source failed.
"""
import json, os, re, sys, time, random, datetime
import requests
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw'); OUT = os.path.join(HERE, 'out')
os.makedirs(RAW, exist_ok=True); os.makedirs(OUT, exist_ok=True)
CFG = json.load(open(os.path.join(HERE, '..', 'site-config.json')))
C = CFG.get('crawl', {})

STATES = ['abia','abuja','adamawa','akwa-ibom','anambra','bauchi','bayelsa','benue','borno','cross-river','delta','ebonyi','edo',
          'ekiti','enugu','gombe','imo','jigawa','kaduna','kano','katsina','kebbi','kogi','kwara','lagos','nasarawa','niger','ogun',
          'ondo','osun','oyo','plateau','rivers','sokoto','taraba','yobe','zamfara']

S = requests.Session()
S.headers.update({'User-Agent': C.get('user_agent', 'Mozilla/5.0 (compatible; BuildocratLandBook/1.0; +https://value.buildocrat.store/)'),
                  'Accept-Language': 'en-NG,en;q=0.9'})

# ---- time budget: the weekly job must leave time to rebuild and publish (GitHub stops it at 150 min)
T0 = time.time()
BUDGET = float(os.environ.get('CRAWL_MINUTES', C.get('budget_minutes', 100))) * 60
SHARE = {'npc': 0.33, 'avg': 0.17, 'jiji': 0.50}
class Clock:
    """per-source deadline and a 'blocked' detector (many failures in a row)"""
    def __init__(self, name):
        left = BUDGET - (time.time() - T0)
        rest = sum(v for k, v in SHARE.items() if k not in DONE_SRC) or 1
        self.until = time.time() + max(60, left * SHARE.get(name, 0.3) / rest); self.fails = 0; self.name = name; DONE_SRC.add(name)
    def up(self): return time.time() > self.until or self.fails >= 8
    def hit(self, ok): self.fails = 0 if ok else self.fails + 1
DONE_SRC = set(); FRESH = {}
# big markets first, then the rest in an order that rotates each week so every state is refreshed regularly
FIRST = ['lagos', 'abuja', 'rivers', 'oyo', 'ogun', 'enugu', 'delta', 'edo', 'anambra', 'imo', 'kwara']
_rest = [x for x in STATES if x not in FIRST]; _k = datetime.date.today().isocalendar()[1] % len(_rest)
ORDER = FIRST + _rest[_k:] + _rest[:_k]

def merge_old(fn, new, done, key='state'):
    """records for states this run did not reach come from last week's file"""
    path = os.path.join(RAW, fn)
    old = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else []
    kept = [x for x in old if x.get(key) not in done]
    print(f'{fn}: {len(done)} states refreshed, {len(STATES) - len(done)} kept from last week ({len(kept)} records)')
    FRESH[fn] = len(done)
    return new + kept

def get(url, kind='html', tries=2):
    for k in range(tries):
        try:
            r = S.get(url, timeout=40, headers={'Accept': 'application/json'} if kind == 'json' else {})
            if r.status_code == 404: return None
            if r.status_code in (403, 429, 503):
                time.sleep(6 * (k + 1)); continue
            r.raise_for_status()
            return r.json() if kind == 'json' else r.text
        except Exception as ex:
            print('  retry', k + 1, url, ex); time.sleep(4 * (k + 1))
    return None

def pause(): time.sleep(C.get('delay_s', 0.7) * (0.6 + random.random() * 0.8))

def money(s):
    """'₦9.6M' -> 9600000; '₦2,500,000' -> 2500000; '₦1.2B' -> 1.2e9"""
    m = re.search(r'₦\s*([\d.,]+)\s*([KMB])?\b', s or '', re.I)
    if not m: return None
    v = float(m.group(1).replace(',', ''))
    return v * {'K': 1e3, 'M': 1e6, 'B': 1e9}.get((m.group(2) or '').upper(), 1)

def keep_or_replace(fn, new, min_share=0.4):
    path = os.path.join(RAW, fn)
    old = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else None
    n_old = len(old) if old is not None else 0; n_new = len(new or [])
    if n_new and n_new >= min_share * n_old:
        txt = json.dumps(new, separators=(',', ':'))   # ASCII-escaped: a cut-off emoji/surrogate can't break the file
        tmp = path + '.tmp'; open(tmp, 'w', encoding='utf-8').write(txt); os.replace(tmp, path)
        print(f'{fn}: {n_new} records (last run {n_old}) -> saved'); return True
    print(f'{fn}: only {n_new} records against {n_old} last run -> KEEPING last run'); return False

# ---------------------------------------------------------------- Nigeria Property Centre: land for sale
def npc_land():
    base = 'https://nigeriapropertycentre.com/for-sale/land/{st}/showtype?page={p}'
    caps = C.get('npc_pages', {'lagos': 180, 'abuja': 160, 'ogun': 50, 'oyo': 30, 'rivers': 30, 'delta': 25, '*': 20})
    out, seen, done = [], set(), set(); ck = Clock('npc')
    for st in ORDER:
        if ck.up(): break
        cap = caps.get(st, caps['*']); got = 0
        for p in range(1, cap + 1):
            if ck.up(): break
            h = get(base.format(st=st, p=p)); pause(); ck.hit(bool(h))
            if not h: break
            arts = BeautifulSoup(h, 'html.parser').find_all('article')
            if not arts: break
            new = 0
            for a in arts:
                x = parse_npc_article(a, st)
                if x and x['href'] not in seen:
                    seen.add(x['href']); out.append(x); new += 1
            got += new
            if new == 0 or not re.search(r'[?&]page=%d\b' % (p + 1), h): break
        if got: done.add(st)
        print(f'  npc {st}: {got}  ({(time.time()-T0)/60:.0f} min)', flush=True)
    return merge_old('lb_npc_land.json', out, done)

def parse_npc_article(a, st):
    link = a.find('a', href=re.compile(r'^/for-sale/land/'))
    pr = a.find('span', class_=re.compile(r'tabular-nums'))
    if not link or not pr: return None
    price = money(pr.get_text(' ', strip=True))
    if not price: return None
    basis = pr.find_next_sibling('span'); basis = basis.get_text(' ', strip=True) if basis else ''
    kind = a.find('p', class_=re.compile(r'\btext-primary\b'))
    title = a.find('h3')
    desc = a.find('p', class_=re.compile(r'line-clamp-2'))
    addr = a.find('span', class_='truncate')
    chip = None
    for sp in a.find_all('span'):
        m = re.fullmatch(r'\s*([\d,]+(?:\.\d+)?)\s*sqm\s*', sp.get_text(' ', strip=True) or '')
        if m: chip = float(m.group(1).replace(',', '')); break
    href = link['href'].split('?')[0]; parts = href.split('/')
    # /for-sale/land/[type/]<state>/<locality>/[area/]<id-slug>
    loc = parts[parts.index(st) + 1] if st in parts[:-1] and parts.index(st) + 2 < len(parts) else st
    return {'state': st, 'loc': loc, 'price': price, 'basis': basis,
            'title': title.get_text(' ', strip=True) if title else '', 'desc': (desc.get_text(' ', strip=True) if desc else '')[:600],
            'addr': addr.get_text(' ', strip=True) if addr else '', 'kind': kind.get_text(' ', strip=True) if kind else '',
            'chip': chip, 'href': href}

# ---------------------------------------------------------------- NPC market trends: medians by state and locality
AVG = [('for-sale', 'houses', 4), ('for-sale', 'flats-apartments', 3), ('for-rent', 'houses', 4),
       ('for-rent', 'flats-apartments', 3), ('for-rent', 'flats-apartments', 2)]

def headline(soup):
    """Median from the page title ('...: ₦14.1M/year (Sept 2026)') or the 'Current avg price' card."""
    t = soup.title.get_text(' ', strip=True) if soup.title else ''
    v = money(t.split(':')[-1]) if ':' in t else None
    month = re.search(r'\(([A-Z][a-z]+\.? \d{4})\)', t)
    if v is None:
        txt = soup.get_text(' ', strip=True)
        m = re.search(r'Current avg price\s*(₦\s*[\d.,]+\s*[KMB]?)', txt)
        v = money(m.group(1)) if m else None
    n = None
    tb = soup.find('table')
    if tb and tb.find('tbody'):
        for tr in tb.find('tbody').find_all('tr'):
            tds = [td.get_text(' ', strip=True) for td in tr.find_all('td')]
            if len(tds) >= 4 and money(tds[1]):
                rng = tds[2]; n = int(re.sub(r'\D', '', tds[3]) or 0); break
    return v, n, (month.group(1) if month else '')

def npc_avg():
    root = 'https://nigeriapropertycentre.com/market-trends/average-prices/{m}/{t}/{st}?bedrooms={b}'
    out = {}; month = ''; ck = Clock('avg')
    max_loc = C.get('avg_localities', 12)
    prevp = os.path.join(RAW, 'lb_npc_avg.json'); prev = json.load(open(prevp, encoding='utf-8')) if os.path.exists(prevp) else {}
    for st in ORDER:
        if ck.up():
            out.update({k: v for k, v in prev.items() if k.endswith('|' + st)}); continue
        for m, t, b in AVG:
            h = get(root.format(m=m, t=t, st=st, b=b)); pause(); ck.hit(bool(h))
            key = f'{m}|{t}|{b}|{st}'
            if not h: out[key] = {'h': None, 'n': 0, 'rows': []}; continue
            soup = BeautifulSoup(h, 'html.parser')
            v, n, mo = headline(soup); month = month or mo
            rows = []
            loc_tbl = next((tb for tb in soup.find_all('table') if tb.find('thead') and 'Locality' in tb.find('thead').get_text()), None)
            if loc_tbl:
                cand = []
                for tr in loc_tbl.find('tbody').find_all('tr'):
                    a = tr.find('a'); tds = tr.find_all('td')
                    if not a or len(tds) < 5: continue
                    cnt = int(re.sub(r'\D', '', tds[4].get_text()) or 0)
                    cand.append((cnt, a.get_text(' ', strip=True), a['href']))
                for cnt, name, href in sorted(cand, reverse=True)[:max_loc]:
                    if cnt < 30 or ck.up(): break
                    hh = get(href.split('?')[0] + f'?bedrooms={b}'); pause()
                    if not hh: continue
                    lv, ln, _ = headline(BeautifulSoup(hh, 'html.parser'))
                    if lv and ln: rows.append([name, lv, '', ln])
            out[key] = {'h': v, 'n': n or 0, 'rows': rows}
        print(f'  avg {st}: ' + ', '.join(str(out.get(f"{m}|{t}|{b}|{st}", {}).get("h")) for m, t, b in AVG) + f'  ({(time.time()-T0)/60:.0f} min)', flush=True)
    return out, month

# ---------------------------------------------------------------- Jiji: land, houses, rentals, commercial
JIJI = [('ls', 'land-and-plots-for-sale'), ('hs', 'houses-apartments-for-sale'), ('hr', 'houses-apartments-for-rent'), ('crc', 'commercial-property-for-rent')]

def jiji():
    api = 'https://jiji.ng/api_web/v1/listing?slug={c}&region_slug={st}&page={p}&sort=new'
    cap = C.get('jiji_pages', {'lagos': 40, 'abuja': 40, 'rivers': 25, 'ogun': 25, 'oyo': 25, '*': 15})
    out, seen, done = [], set(), set(); ck = Clock('jiji')
    for st in ORDER:
        if ck.up(): break
        n0 = len(out)
        for code, slug in JIJI:
            for p in range(1, cap.get(st, cap['*']) + 1):
                if ck.up(): break
                j = get(api.format(c=slug, st=st, p=p), 'json'); pause(); ck.hit(j is not None)
                al = (j or {}).get('adverts_list') or {}
                ads = al.get('adverts') or []
                for ad in ads:
                    if ad.get('guid') in seen: continue
                    seen.add(ad.get('guid'))
                    at = {x.get('name'): x.get('value') for x in ad.get('attrs') or []}
                    po = ad.get('price_obj') or {}
                    if not po.get('value'): continue
                    num = lambda v: float(v) if isinstance(v, (int, float)) else None
                    out.append({'c': code, 'st': st, 'r': ad.get('region_name'), 'rp': ad.get('region_parent_name'),
                                'p': po.get('value'), 'per': po.get('period') or '', 'sqm': num(at.get('Square meters')),
                                'sz': num(at.get('Property size')), 'b': at.get('Bedrooms') if isinstance(at.get('Bedrooms'), int) else None,
                                't': ad.get('title') or ''})
                if not ads or p >= (al.get('total_pages') or 0): break
        if len(out) > n0 and not ck.up(): done.add(st)
        elif len(out) > n0: done.add(st)   # partly crawled: its new listings replace last week's for this state
        print(f'  jiji {st}: {len(out) - n0}  ({(time.time()-T0)/60:.0f} min)', flush=True)
    return merge_old('lb_jiji.json', out, done, key='st')

# ---------------------------------------------------------------- Rate Book: exchange rate and build cost
def rates():
    run = {}
    d = get('https://rates.buildocrat.store/rate-data.json', 'json')
    if d and d.get('meta', {}).get('fx'):
        run['fx'] = d['meta']['fx']; run['fxNote'] = d['meta'].get('fxNote', '')
    h = get('https://rates.buildocrat.store/guides/cost-to-build-3-bedroom-bungalow/')
    if h:
        txt = BeautifulSoup(h, 'html.parser').get_text(' ', strip=True)
        m = re.search(r'Cost per m²[^₦]{0,60}₦\s*([\d,]+)', txt)
        if m: run['build'] = int(m.group(1).replace(',', ''))
    return run

if __name__ == '__main__':
    want = set(sys.argv[1:]) or {'npc', 'avg', 'jiji', 'rates'}
    runp = os.path.join(RAW, 'run.json')
    run = json.load(open(runp)) if os.path.exists(runp) else {}
    ok = 0
    today = datetime.date.today()
    if 'rates' in want:
        r = rates(); run.update(r); ok += bool(r); print('rates', r)
    ok_rates = ok
    if 'npc' in want:
        try: ok += keep_or_replace('lb_npc_land.json', npc_land()) and FRESH.get('lb_npc_land.json', 0) > 0
        except Exception as ex: print('npc failed:', ex)
    if 'avg' in want:
        try:
            avg, month = npc_avg()
            good = {k: v for k, v in avg.items() if v.get('h')}
            if month and keep_or_replace('lb_npc_avg.json', avg if len(good) >= 60 else {}, 0.0): run['avgMonth'] = month; ok += 1
        except Exception as ex: print('avg failed:', ex)
    if 'jiji' in want:
        try: ok += keep_or_replace('lb_jiji.json', jiji()) and FRESH.get('lb_jiji.json', 0) > 0
        except Exception as ex: print('jiji failed:', ex)
    if ok > ok_rates:   # at least one listing source refreshed: this is a new edition
        run['date'] = today.isoformat()
        run['edition'] = f'Week {today.isocalendar()[1]}, {today.year}'
    json.dump(run, open(runp, 'w'), indent=1)
    print('run', run, '| fresh states:', FRESH, f'| {(time.time()-T0)/60:.0f} min')
    sys.exit(0 if ok else 1)

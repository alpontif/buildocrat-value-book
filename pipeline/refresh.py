"""One command for the weekly refresh:  python pipeline/refresh.py [--no-crawl]

crawl (keeps last week's file for any source that fails) -> build -> model -> export -> pages -> config.js
"""
import os, sys, subprocess, json

HERE = os.path.dirname(os.path.abspath(__file__))
py = sys.executable
def run(*a):
    print('\n==>', ' '.join(a), flush=True)
    subprocess.run([py, *a], cwd=HERE, check=True)

if '--no-crawl' not in sys.argv:
    r = subprocess.run([py, 'crawl.py'], cwd=HERE)
    if r.returncode: print('All crawls failed; rebuilding from last week\'s files.')
import shutil
prev = os.path.join(HERE, '..', 'docs', 'data', 'lgas.json')
os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
if os.path.exists(prev): shutil.copy(prev, os.path.join(HERE, 'out', 'prev_lgas.json'))
for s in ('build.py', 'run_model.py', 'export.py', 'sanity.py', 'pages.py', 'build_extension.py'):
    run(s)

# browser config (public keys only)
cfg = json.load(open(os.path.join(HERE, '..', 'site-config.json')))
pub = {'mapboxToken': cfg.get('mapbox_token', ''), 'styleSatellite': cfg.get('mapbox_style_satellite'),
       'styleStreets': cfg.get('mapbox_style_streets'), 'nipostKey': cfg.get('nipost_publishable_key', ''),
       'nipostBase': cfg.get('nipost_api_base'), 'nipostRadius': cfg.get('nipost_reverse_radius_m', 120)}
open(os.path.join(HERE, '..', 'docs', 'config.js'), 'w').write('window.LB_CONFIG=' + json.dumps(pub) + ';\n')
print('\nRefresh complete.')

# cache-busting: point index.html at the current versions of config.js and app.js
import hashlib, re
docs = os.path.join(HERE, '..', 'docs')
idx = os.path.join(docs, 'index.html'); html = open(idx, encoding='utf-8').read()
for f in ('config.js', 'app.js'):
    h = hashlib.md5(open(os.path.join(docs, f), 'rb').read()).hexdigest()[:8]
    html = re.sub(r'src="%s(\?v=[0-9a-f]+)?"' % re.escape(f), 'src="%s?v=%s"' % (f, h), html)
open(idx, 'w', encoding='utf-8').write(html)
print('cache-busted index.html')

# installed app: a new service-worker version each edition, so phones pick up the new week's shell and data
swp = os.path.join(docs, 'sw.js'); sw = open(swp, encoding='utf-8').read()
hv = hashlib.md5(b''.join(open(os.path.join(docs, f), 'rb').read() for f in ('index.html', 'app.js', 'config.js', 'pwa.js', 'sw.js', 'data/manifest.json'))).hexdigest()[:10]
open(swp, 'w', encoding='utf-8').write(re.sub(r"const VERSION = '[^']*';", "const VERSION = '%s';" % hv, sw))
print('service worker version', hv)


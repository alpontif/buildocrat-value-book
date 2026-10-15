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

/* Buildocrat Land Value Book: service worker. Makes the site installable and usable offline with the last week's values.
   Pages and data: network first (so the weekly update shows straight away), cached copy when offline or slow.
   Scripts, icons, fonts, the map library: cached copy first, refreshed in the background.
   Mapbox map tiles and postcode lookups are never stored. */
const VERSION = '35cd63589b';
const SHELL = 'lvb-shell-' + VERSION, RUNTIME = 'lvb-runtime';
const PRECACHE = ['/', '/app.js', '/config.js', '/pwa.js', '/manifest.webmanifest', '/favicon.svg', '/icons/icon-192.png', '/icons/icon-512.png',
  '/data/lgas.json', '/data/places.b64.txt', '/data/evidence.json', '/offline.html'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => Promise.all(PRECACHE.map(u => c.add(new Request(u, { cache: 'reload' })).catch(() => {})))));
  self.skipWaiting();
});
self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k.startsWith('lvb-shell-') && k !== SHELL) await caches.delete(k);
    if (self.registration.navigationPreload) await self.registration.navigationPreload.enable().catch(() => {});
    await self.clients.claim();
  })());
});

const put = async (req, res) => { if (res && res.ok && res.type !== 'opaque') { const c = await caches.open(RUNTIME); await c.put(req, res.clone()); } return res; };
const cached = async (req, opts) => (await caches.match(req, opts)) || (await caches.match(req, { ignoreSearch: true }));
const timeout = (ms, p) => Promise.race([p, new Promise((_, r) => setTimeout(() => r(new Error('timeout')), ms))]);

async function networkFirst(req, ms, preload) {
  const net = (async () => (await preload) || fetch(req))().then(res => put(req, res));
  try { return await timeout(ms, net); }
  catch (err) {
    const hit = await cached(req);
    if (hit) { net.catch(() => {}); return hit; }
    try { return await net; } catch (e2) { throw e2; }
  }
}
async function staleWhileRevalidate(req, e) {
  const hit = await caches.match(req);
  const net = fetch(req).then(res => put(req, res)).catch(() => null);
  if (hit) { e.waitUntil(net); return hit; }
  return (await net) || (await cached(req)) || Response.error();
}

self.addEventListener('fetch', e => {
  const req = e.request; if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin === location.origin) {
    if (url.pathname === '/sw.js') return;
    if (req.mode === 'navigate') {
      e.respondWith(networkFirst(req, 4500, e.preloadResponse).catch(async () =>
        (await cached(req)) || (url.pathname === '/' ? null : await caches.match('/offline.html')) || (await caches.match('/')) || Response.error()));
      return;
    }
    if (url.pathname.startsWith('/data/') && !url.pathname.endsWith('.csv')) { e.respondWith(networkFirst(req, 8000).catch(() => cached(req).then(r => r || Response.error()))); return; }
    if (/\.(js|css|png|svg|webmanifest|txt)$/.test(url.pathname)) { e.respondWith(staleWhileRevalidate(req, e)); return; }
    return;
  }
  // fonts and the pinned Mapbox GL library (versioned URL) are safe to keep
  if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com' || (url.hostname === 'api.mapbox.com' && url.pathname.startsWith('/mapbox-gl-js/')))
    e.respondWith(staleWhileRevalidate(req, e));
});
self.addEventListener('message', e => { if (e.data === 'skipWaiting') self.skipWaiting(); });

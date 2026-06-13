// ── World Cup 2026 Service Worker v3 ─────────────────────────
// Cache strategy:
//   LIVE  data  (fixtures, standings, predictions) → stale-while-revalidate, 5min TTL
//   STATIC data (team_profiles, h2h)               → cache-first, 7-day TTL
//   HTML / JS                                       → network-first, fallback cache
//   ESPN API                                        → always network, never cache

const CACHE_VER = 'wc2026-v3';
const TTL_LIVE   = 5  * 60;        // 5 minutes (seconds)
const TTL_STATIC = 7  * 24 * 3600; // 7 days

// Files to pre-cache on install
const PRECACHE = [
  '/worldcup-predict/',
  '/worldcup-predict/index.html',
];

// ── Helpers ──────────────────────────────────────────────────
function isLive(url) {
  return /\/(fixtures|standings|predictions|reviews|stats|index)\.json/.test(url.pathname);
}
function isStatic(url) {
  return /\/(team_profiles|h2h)\.json/.test(url.pathname);
}
function isHTML(url) {
  return url.pathname.endsWith('.html') || url.pathname.endsWith('/');
}
function isESPN(url) {
  return url.hostname.includes('espn.com');
}

function cacheTimestamp(response) {
  // Store fetch time in a custom header clone
  const headers = new Headers(response.headers);
  headers.set('sw-fetched-at', String(Date.now()));
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

function isFresh(response, ttlSeconds) {
  if (!response) return false;
  const fetched = response.headers.get('sw-fetched-at');
  if (!fetched) return false;
  return (Date.now() - Number(fetched)) < ttlSeconds * 1000;
}

async function openCache() {
  return caches.open(CACHE_VER);
}

// ── Install ──────────────────────────────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(
    openCache()
      .then(c => c.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

// ── Activate — purge old caches ──────────────────────────────
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE_VER).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// ── Fetch ─────────────────────────────────────────────────────
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);

  // ESPN — bypass entirely
  if (isESPN(url)) return;

  // ── LIVE data: stale-while-revalidate, 5-min TTL ──
  if (isLive(url)) {
    e.respondWith((async () => {
      const cache = await openCache();
      const cached = await cache.match(e.request);

      // If fresh enough, return cache immediately and revalidate in background
      if (isFresh(cached, TTL_LIVE)) {
        // Background revalidate
        fetch(e.request).then(r => {
          if (r.ok) cache.put(e.request, cacheTimestamp(r.clone()));
        }).catch(() => {});
        return cached;
      }

      // Otherwise fetch network; fall back to stale if offline
      try {
        const fresh = await fetch(e.request);
        if (fresh.ok) {
          cache.put(e.request, cacheTimestamp(fresh.clone()));
        }
        return fresh;
      } catch {
        return cached || new Response('{}', { status: 503 });
      }
    })());
    return;
  }

  // ── STATIC data: cache-first, 7-day TTL ──
  if (isStatic(url)) {
    e.respondWith((async () => {
      const cache = await openCache();
      const cached = await cache.match(e.request);

      if (isFresh(cached, TTL_STATIC)) return cached;

      try {
        const fresh = await fetch(e.request);
        if (fresh.ok) cache.put(e.request, cacheTimestamp(fresh.clone()));
        return fresh;
      } catch {
        return cached || new Response('{}', { status: 503 });
      }
    })());
    return;
  }

  // ── HTML/JS: network-first, fall back to cache ──
  if (isHTML(url) || url.pathname.endsWith('.js')) {
    e.respondWith((async () => {
      const cache = await openCache();
      try {
        const fresh = await fetch(e.request);
        if (fresh.ok) cache.put(e.request, fresh.clone());
        return fresh;
      } catch {
        return cache.match(e.request);
      }
    })());
    return;
  }

  // Default: cache then network
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});

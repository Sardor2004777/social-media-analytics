// Minimal service worker for PWA installability + offline shell.
// Caches the shell on install, network-first for everything else.
//
// Bumping CACHE_VERSION invalidates the old cache on next visit.
const CACHE_VERSION = "v1";
const CACHE_NAME = `social-analytics-${CACHE_VERSION}`;
const PRECACHE = [
  "/static/favicon.svg",
  "/static/manifest.json",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE_NAME).then((c) => c.addAll(PRECACHE)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  // Only handle GET requests; POSTs (forms, AJAX) go straight to network.
  if (e.request.method !== "GET") return;

  // Skip cross-origin (CDN) requests — let the browser cache handle them.
  const url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;

  // Network-first; on failure, fall back to cache (so static assets still
  // work briefly when offline). Don't cache HTML pages — they're per-user.
  e.respondWith(
    fetch(e.request)
      .then((resp) => {
        if (resp.ok && url.pathname.startsWith("/static/")) {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then((c) => c.put(e.request, clone));
        }
        return resp;
      })
      .catch(() => caches.match(e.request))
  );
});

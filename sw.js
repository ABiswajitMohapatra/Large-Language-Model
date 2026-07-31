// Minimal service worker: only needed so the browser considers the site
// an installable PWA. Does not cache/intercept anything, so it can never
// break or serve stale content - all requests just pass through to network.
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Pass-through only - no caching, no offline behavior, no risk of stale UI.
});

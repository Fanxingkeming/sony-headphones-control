/* Minimal service worker: exists so the panel is installable as a PWA.
   It deliberately does not cache anything - the panel is only meaningful
   while the local server is up, and caching API responses would lie about
   the headset state. */
self.addEventListener('install', (e) => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

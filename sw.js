// Offline cache for the website (PWA). Not used inside the Android app, which serves files from the APK.
const CACHE = 'queryopsy-v1.0.0';
self.addEventListener('install', (e) => {
  e.waitUntil(fetch('precache.json').then((r) => r.json()).then((files) => caches.open(CACHE).then((c) => c.addAll(files))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then((hit) => hit || fetch(e.request).then((res) => {
    const copy = res.clone();
    if (res.ok) caches.open(CACHE).then((c) => c.put(e.request, copy));
    return res;
  })));
});

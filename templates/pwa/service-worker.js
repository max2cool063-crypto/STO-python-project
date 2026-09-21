// Bump the version whenever the offline page changes.
const CACHE = 'sto-pwa-offline-v1';
const OFFLINE = '/offline/';
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.add(
    new Request(OFFLINE, {credentials: 'omit', cache: 'reload'})
  )));
  // Let open tabs finish their work before replacing an existing worker.
});
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith('sto-pwa-offline-') && key !== CACHE) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});
// Only a generic offline page is cached. Never cache or replay forms, API
// responses, authenticated pages, media, or errors returned by the server.
self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET' || request.mode !== 'navigate' ||
      new URL(request.url).origin !== self.location.origin) return;
  event.respondWith(fetch(request, {cache: 'no-store'}).catch(async () =>
    (await caches.match(OFFLINE, {cacheName: CACHE})) ||
    new Response('Нет соединения. Подключитесь к интернету и обновите страницу.',
      {status: 503, headers: {'Content-Type': 'text/plain; charset=utf-8'}})
  ));
});

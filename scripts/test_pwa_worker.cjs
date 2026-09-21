const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('templates/pwa/service-worker.js', 'utf8');
function worker(fetch) {
  const handlers = {}, added = [], removed = [];
  const fallback = new Response('offline');
  vm.runInNewContext(source, {
    self: {location: {origin: 'https://example.com'}, clients: {claim: async () => {}},
      addEventListener: (name, callback) => handlers[name] = callback},
    URL, Response, Request: class {constructor(url, options) {this.url = url; this.options = options;}}, fetch,
    caches: {open: async () => ({add: async request => added.push(request)}),
      keys: async () => ['unrelated-cache', 'sto-pwa-offline-v0', 'sto-pwa-offline-v1'],
      delete: async key => removed.push(key), match: async () => fallback},
  });
  return {handlers, added, removed, fallback};
}
test('only public offline page is stored, without cookies; unrelated caches survive', async () => {
  const w = worker();
  let pending;
  w.handlers.install({waitUntil: value => pending = value}); await pending;
  assert.equal(w.added.length, 1);
  assert.equal(w.added[0].url, '/offline/');
  assert.equal(w.added[0].options.credentials, 'omit');
  w.handlers.activate({waitUntil: value => pending = value}); await pending;
  assert.deepEqual(w.removed, ['sto-pwa-offline-v0']);
});
test('POSTs, API requests, media and third party requests are never intercepted', () => {
  const w = worker(() => assert.fail('must not fetch'));
  for (const [method, mode, url] of [
    ['POST', 'navigate', 'https://example.com/book/'],
    ['GET', 'cors', 'https://example.com/api/'],
    ['GET', 'no-cors', 'https://example.com/media/appointments/photo.jpg'],
    ['GET', 'navigate', 'https://other.example/'],
  ]) w.handlers.fetch({request: {method, mode, url}, respondWith: () => assert.fail('must not intercept')});
});
test('online pages and server errors pass through; offline navigation gets generic fallback', async () => {
  for (const status of [200, 403, 500, null]) {
    const response = status ? new Response('server response', {status}) : null;
    const w = worker(async (_, options) => {
      assert.equal(options.cache, 'no-store');
      if (!response) throw new Error('offline');
      return response;
    });
    let pending;
    w.handlers.fetch({request: {method: 'GET', mode: 'navigate', url: 'https://example.com/cabinet/'},
      respondWith: value => pending = value});
    assert.equal(await pending, response || w.fallback);
    assert.equal(w.added.length, 0);
  }
});

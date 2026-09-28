const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const code = fs.readFileSync('booking/static/booking/js/station-notifications-v1.js', 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));
function setup({staff = true, navigator, response} = {}) {
  const calls = [], events = {}, documentEvents = {}, logoutEvents = {};
  const elements = {};
  for (const key of ['toggle', 'panel', 'count', 'list', 'read-all']) {
    elements[key] = {hidden: true, events: {}, setAttribute() {}, addEventListener(name, fn) {this.events[name] = fn;}};
  }
  const root = {dataset: {endpoint: '/station/notifications/', readAllUrl: '/station/notifications/read-all/'},
    querySelector: s => elements[s.slice(19, -1)], contains: () => true};
  let nextResponse = response || {ok: true, json: async () => ({unread_count: 3, notifications: []})};
  vm.runInNewContext(code, {
    navigator: navigator || {setAppBadge: n => calls.push(n), clearAppBadge: () => calls.push(0)},
    document: {hidden: false, cookie: '', querySelector: s => s === '[data-station-notifications]' ? (staff ? root : null) : null,
      querySelectorAll: () => [{addEventListener: (n, fn) => logoutEvents[n] = fn}],
      addEventListener: (n, fn) => documentEvents[n] = fn},
    window: {setInterval: fn => events.poll = fn, addEventListener: (n, fn) => events[n] = fn},
    fetch: async () => typeof nextResponse === 'function' ? nextResponse() : nextResponse,
    Promise, Number, Date, String, Error,
  });
  return {calls, events, elements, logoutEvents, setResponse: r => nextResponse = r};
}
test('badge follows unread count and clears after read-all', async () => {
  const app = setup(); await flush(); assert.deepEqual(app.calls, [3]);
  assert.equal(app.elements.count.textContent, '3');
  app.setResponse({ok:true, json:async () => ({unread_count:0})});
  app.elements['read-all'].events.click(); await flush();
  assert.deepEqual(app.calls, [3,0]); assert.equal(app.elements.count.hidden,true);
});
test('unsupported and denied API leave the bell working', async () => {
  for (const navigator of [{}, {setAppBadge: () => Promise.reject(new Error('denied'))}]) {
    const app = setup({navigator}); await flush(); assert.equal(app.elements.count.textContent,'3');
  }
});
test('non-staff pages and ended sessions clear the badge', async () => {
  assert.deepEqual(setup({staff:false}).calls,[0]);
  for (const response of [{redirected:true}, {status:403}, {status:401}]) {
    const app=setup({response}); await flush(); assert.deepEqual(app.calls,[0]);
  }
});
test('offline failure retains the last known count; focus refreshes', async () => {
  const app=setup(); await flush();
  app.setResponse(() => Promise.reject(new Error('offline')));
  app.events.poll(); await flush(); assert.deepEqual(app.calls,[3]);
  app.setResponse({ok:true,json:async()=>({unread_count:5})});
  app.events.focus(); await flush(); assert.deepEqual(app.calls,[3,5]);
});
test('late response cannot restore badge after logout', async () => {
  let resolve;
  const app=setup({response:()=>new Promise(r=>resolve=r)});
  app.logoutEvents.submit();
  resolve({ok:true,json:async()=>({unread_count:4})}); await flush();
  assert.deepEqual(app.calls,[0]);
});

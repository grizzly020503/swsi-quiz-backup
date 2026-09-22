#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

class FakeResponse {
  constructor(body, ok = true) { this.body = body; this.ok = ok; }
  clone() { return new FakeResponse(this.body, this.ok); }
}

(async () => {
  const handlers = {};
  const deleted = [];
  const puts = [];
  const addRequests = [];
  let claimed = false;
  let skipped = false;
  let fetchInit = null;
  let cachePutFailure = false;
  const cacheKeys = new Set(['swsi-shell-v4', 'swsi-shell-v5', 'swsi-shell-v6', 'swsi-shell-v7', 'another-app-cache']);

  class FakeRequest {
    constructor(url, init = {}) {
      this.url = String(url);
      this.cache = init.cache;
      this.method = 'GET';
      this.mode = '';
      this.destination = '';
    }
  }

  const caches = {
    async open(name) {
      assert.strictEqual(name, 'swsi-shell-v7');
      return {
        async addAll(reqs) { addRequests.push(...reqs); },
        async put(req, response) {
          puts.push({ req, response });
          if (cachePutFailure) throw new Error('simulated quota failure');
        }
      };
    },
    async keys() { return [...cacheKeys]; },
    async delete(name) { deleted.push(name); return cacheKeys.delete(name); },
    async match(req) {
      if (req === './index.html') return new FakeResponse('cached-index');
      return null;
    }
  };

  let fetchMode = 'success';
  const context = {
    URL,
    Request: FakeRequest,
    caches,
    console,
    fetch: async (_req, init) => {
      fetchInit = init;
      if (fetchMode === 'failure') throw new Error('offline');
      return new FakeResponse('network');
    },
    self: {
      location: { origin: 'https://example.test' },
      clients: { async claim() { claimed = true; } },
      async skipWaiting() { skipped = true; },
      addEventListener(type, handler) { handlers[type] = handler; }
    }
  };
  vm.runInNewContext(fs.readFileSync('sw.js', 'utf8'), context, { filename: 'sw.js' });

  let installPromise;
  handlers.install({ waitUntil(p) { installPromise = p; } });
  await installPromise;
  assert(skipped, 'new service worker did not call skipWaiting');
  assert(addRequests.length >= 10, 'shell assets were not precached');
  assert(addRequests.every(req => req.cache === 'reload'), 'install did not bypass the old HTTP cache');

  let activatePromise;
  handlers.activate({ waitUntil(p) { activatePromise = p; } });
  await activatePromise;
  assert.deepStrictEqual(deleted.sort(), ['swsi-shell-v4', 'swsi-shell-v5', 'swsi-shell-v6']);
  assert(cacheKeys.has('another-app-cache'), 'activate deleted an unrelated origin cache');
  assert(claimed, 'new service worker did not claim existing clients');

  const mutable = new FakeRequest('https://example.test/monthly_patch.js');
  let mutablePromise;
  handlers.fetch({ request: mutable, respondWith(p) { mutablePromise = p; } });
  const mutableResponse = await mutablePromise;
  assert.strictEqual(mutableResponse.body, 'network');
  assert.strictEqual(fetchInit.cache, 'no-store');
  assert.strictEqual(puts.length, 1, 'network-first response was not persisted before resolving');

  cachePutFailure = true;
  const cacheWriteFailure = new FakeRequest('https://example.test/essay_guides.js');
  let cacheWriteFailurePromise;
  handlers.fetch({ request: cacheWriteFailure, respondWith(p) { cacheWriteFailurePromise = p; } });
  const cacheWriteFailureResponse = await cacheWriteFailurePromise;
  assert.strictEqual(cacheWriteFailureResponse.body, 'network', 'a cache quota failure replaced a fresh response with stale content');
  cachePutFailure = false;

  fetchMode = 'failure';
  const nav = new FakeRequest('https://example.test/');
  nav.mode = 'navigate';
  nav.destination = 'document';
  let navPromise;
  handlers.fetch({ request: nav, respondWith(p) { navPromise = p; } });
  const navResponse = await navPromise;
  assert.strictEqual(navResponse.body, 'cached-index', 'offline navigation did not use the cached shell');

  console.log('SERVICE WORKER UPDATE SMOKE OK');
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

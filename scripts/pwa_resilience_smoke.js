const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const base = process.argv[2] || 'http://127.0.0.1:4173/';
const QUESTION_CDN_HOST = 'wandering-wave-4418.c022050333.workers.dev';
const QUESTION_CDN_PREFIX = '/question-shards/';
const LOCAL_SHARD_DIR = path.resolve(process.cwd(), 'cdn/question-shards');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ serviceWorkers: 'allow', viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', err => pageErrors.push(String(err && err.message || err)));

  const localOrigin = new URL(base).origin;
  await page.route('**/*', route => {
    const req = route.request();
    const u = new URL(req.url());
    if (u.hostname === QUESTION_CDN_HOST && u.pathname.startsWith(QUESTION_CDN_PREFIX)) {
      const rel = decodeURIComponent(u.pathname.slice(QUESTION_CDN_PREFIX.length));
      if (!rel || rel !== path.basename(rel)) return route.fulfill({ status: 404, body: 'not found' });
      const file = path.join(LOCAL_SHARD_DIR, rel);
      if (!fs.existsSync(file)) return route.fulfill({ status: 404, body: 'not found' });
      return route.fulfill({ status: 200, contentType: 'application/json; charset=utf-8', body: fs.readFileSync(file) });
    }
    if (u.origin !== localOrigin) return route.abort();
    return route.continue();
  });

  await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await page.waitForSelector('.swsi-focus-primary', { timeout: 45000 });

  const swState = await page.evaluate(async () => {
    if (!('serviceWorker' in navigator)) throw new Error('Service Worker API unavailable');
    const ready = navigator.serviceWorker.ready;
    const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error('service worker ready timeout')), 20000));
    const reg = await Promise.race([ready, timeout]);
    if (!navigator.serviceWorker.controller) {
      await Promise.race([
        new Promise(resolve => navigator.serviceWorker.addEventListener('controllerchange', resolve, { once: true })),
        new Promise((_, reject) => setTimeout(() => reject(new Error('service worker controller timeout')), 12000))
      ]);
    }
    const keys = await caches.keys();
    return {
      controller: !!navigator.serviceWorker.controller,
      scope: reg.scope,
      caches: keys
    };
  });
  assert(swState.controller, 'service worker did not control the page');
  assert(swState.caches.includes('swsi-shell-v7'), 'expected swsi-shell-v6 cache missing: ' + JSON.stringify(swState.caches));

  // Remove the local question-shard interception before going offline. The next
  // reload must rely on the app shell cache plus the app's own persisted data,
  // not a Playwright network stub.
  await page.unroute('**/*');
  await context.setOffline(true);

  await page.reload({ waitUntil: 'domcontentloaded', timeout: 20000 });
  await page.waitForSelector('.swsi-focus-primary', { timeout: 45000 });
  assert.strictEqual(await page.evaluate(() => navigator.onLine), false, 'browser did not enter offline mode');

  const offlineShell = await page.evaluate(async () => {
    const out = {};
    for (const p of ['/index.html', '/monthly_patch.js', '/essay_guides.js', '/manifest.json']) {
      try {
        const r = await fetch(p, { cache: 'no-store' });
        out[p] = { ok: r.ok, status: r.status, size: (await r.text()).length };
      } catch (err) {
        out[p] = { ok: false, error: String(err && err.message || err) };
      }
    }
    return out;
  });
  for (const [p, row] of Object.entries(offlineShell)) {
    assert(row.ok && row.size > 20, `offline shell fetch failed for ${p}: ${JSON.stringify(row)}`);
  }

  const appText = await page.locator('#app').innerText();
  assert(/今天練 10 題|開始 10 題|今天的學習|第一次來/.test(appText), 'offline app shell rendered an unexpected/blank state');

  await context.setOffline(false);
  await page.reload({ waitUntil: 'domcontentloaded', timeout: 20000 });
  await page.waitForSelector('.swsi-focus-primary', { timeout: 45000 });

  assert.deepStrictEqual(pageErrors, [], 'page errors during PWA resilience smoke: ' + pageErrors.join(' | '));
  console.log('PWA RESILIENCE SMOKE OK', JSON.stringify({ swState, offlineShell }));
  await context.close();
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

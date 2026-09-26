const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const base = process.argv[2] || 'http://127.0.0.1:4173';
const QUESTION_CDN_HOST = 'wandering-wave-4418.c022050333.workers.dev';
const QUESTION_CDN_PREFIX = '/question-shards/';
const LOCAL_SHARD_DIR = path.resolve(process.cwd(), 'cdn/question-shards');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const browserErrors = [];
  page.on('pageerror', err => browserErrors.push(String(err && err.message || err)));

  const localOrigin = new URL(base).origin;
  await page.route('**/*', route => {
    const u = new URL(route.request().url());
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

  async function waitHome() {
    await page.waitForSelector('.swsi-focus-primary', { timeout: 30000 });
  }

  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await waitHome();

  // Quiz must never trap the user. Start a real set, then leave mid-session.
  await page.getByRole('button', { name: /直接開始 20 題/ }).click();
  await page.waitForSelector('.qcard .opt', { timeout: 45000 });
  await page.getByRole('button', { name: /結束這次練習/ }).click();
  await waitHome();

  // Essay must also be escapable with an unfinished draft on screen.
  await page.locator('#t-essay').click();
  await page.waitForSelector('#app .gcard', { timeout: 30000 });
  await page.locator('#app .gcard').first().click();
  await page.waitForSelector('#app [onclick^="toggleEssay("]', { timeout: 30000 });
  await page.locator('#app [onclick^="toggleEssay("]').first().click();
  await page.waitForSelector('.wta', { timeout: 30000 });
  await page.locator('.wta').first().fill('未完成草稿，dead-end smoke');
  await page.locator('#t-home').click();
  await waitHome();

  // Learning/support hub must remain navigable after repeated route changes.
  // Use the same direct Learning tab route students use; do not invoke legacy progress loading.
  await page.locator('#t-review').click();
  await page.waitForSelector('.swsi-myhub', { timeout: 30000 });

  // Platform/support actions are intentionally secondary behind the closed disclosure.
  const more = page.locator('.swsi-myhub-more');
  if (!(await more.evaluate(el => el.open))) await more.locator('summary').click();
  await page.waitForFunction(() => {
    const el = document.querySelector('.swsi-myhub-more');
    return !!(el && el.open);
  });

  // Sharing cancellation is not an error and must leave the page usable.
  await page.evaluate(() => {
    window.__swsiShareCalled = false;
    Object.defineProperty(navigator, 'share', {
      configurable: true,
      value: async () => {
        window.__swsiShareCalled = true;
        const e = new Error('cancelled');
        e.name = 'AbortError';
        throw e;
      }
    });
  });
  await page.getByRole('button', { name: /分享 SWSI/ }).click();
  assert.strictEqual(await page.evaluate(() => window.__swsiShareCalled), true, 'share action did not invoke Web Share');
  assert.strictEqual(await page.locator('.swsi-myhub').count(), 1, 'share cancellation left support hub');

  // Admin login may open its own layer, but the user must always have a visible return path.
  const adminLogin = page.locator('[data-swsi-admin-login]');
  if (await adminLogin.count()) {
    await adminLogin.click();
    await page.waitForSelector('#swsi-admin-layer:not([hidden])', { timeout: 10000 });
    assert(await page.locator('body').evaluate(el => el.classList.contains('swsi-admin-open')), 'admin layer did not lock background state');
    await page.getByRole('button', { name: /返回 SWSI/ }).click();
    await page.waitForFunction(() => {
      const layer = document.getElementById('swsi-admin-layer');
      return !layer || layer.hidden;
    });
    assert(!(await page.locator('body').evaluate(el => el.classList.contains('swsi-admin-open'))), 'admin close left body locked');
    assert.strictEqual(await page.locator('.swsi-myhub').count(), 1, 'admin close did not return to support hub');
  }

  // Exercise every canonical bottom navigation destination and prove Practice is always recoverable.
  for (const selector of ['#t-home', '#t-review', '#t-essay']) {
    const btn = page.locator(selector);
    if (!(await btn.count())) continue;
    await btn.click();
    await page.waitForTimeout(150);
  }
  await page.locator('#t-home').click();
  await waitHome();

  assert.deepStrictEqual(browserErrors, [], 'browser page errors: ' + browserErrors.join(' | '));
  console.log('PRELAUNCH DEADEND SMOKE OK');
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

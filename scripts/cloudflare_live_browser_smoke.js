#!/usr/bin/env node
'use strict';
// Live, read-only browser acceptance for the existing Cloudflare soft launch.
// Never submit answers, login, use the public AI, or send feedback.
const assert = require('node:assert/strict');
const { chromium, webkit } = require('playwright');
const ORIGIN = 'https://wandering-wave-4418.c022050333.workers.dev';

async function check(engine, label, width, height, practice) {
  const browser = await engine.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width, height },
    serviceWorkers: 'block', // byte parity / PWA are tested by separate gates
    reducedMotion: 'reduce'
  });
  const page = await context.newPage();
  const pageErrors = [];
  let blockedWrites = 0;
  page.on('pageerror', error => pageErrors.push(String(error.message || error)));
  // Prevent any telemetry, feedback, AI or other production mutation.
  await page.route('**/*', route => {
    const method = route.request().method().toUpperCase();
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
      blockedWrites++;
      return route.abort();
    }
    return route.continue();
  });
  try {
    const response = await page.goto(ORIGIN + '/', { waitUntil: 'domcontentloaded', timeout: 25000 });
    assert.equal(response && response.status(), 200, label + ': home HTTP status');
    assert.equal(new URL(page.url()).origin, ORIGIN, label + ': wrong origin');
    await page.waitForSelector('#app .swsi-focus-primary', { timeout: 45000 });
    await page.waitForFunction(() => document.querySelectorAll('#tabbar button').length >= 3, null, { timeout: 12000 });

    const state = await page.evaluate(() => ({
      title: document.title,
      robots: document.querySelector('meta[name="robots"]')?.content || '',
      softLaunch: document.documentElement.outerHTML.includes('SWSI CLOUDFLARE PUBLIC SOFT LAUNCH'),
      focus: document.documentElement.outerHTML.includes('目前 3 個國考重點'),
      obsolete: document.documentElement.outerHTML.includes('命題趨勢雷達'),
      runtimeTag: Array.from(document.querySelectorAll('script[src]'))
        .some(e => /^monthly_patch\.js\?v=[0-9a-f]{16}$/.test(e.getAttribute('src') || '')),
      appTextLength: (document.querySelector('#app')?.innerText || '').trim().length,
      overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth
    }));
    assert.match(state.title, /社工師國考免費題庫/, label + ': title');
    assert(state.robots.includes('noindex'), label + ': soft-launch SEO hold unexpectedly removed');
    assert(state.softLaunch && state.focus && !state.obsolete && state.runtimeTag, label + ': release/UI markers ' + JSON.stringify(state));
    assert(state.appTextLength > 100, label + ': blank homepage');
    assert(state.overflow <= 3, label + ': horizontal overflow ' + state.overflow);

    const nav = page.locator('#tabbar button:visible');
    assert((await nav.count()) >= 3, label + ': missing bottom navigation');
    if (width < 600) for (let i = 0; i < await nav.count(); i++) {
      const box = await nav.nth(i).boundingBox();
      assert(box && box.width >= 40 && box.height >= 40, label + ': tiny navigation target ' + i);
    }

    // Public-info modal and real navigation clicks; no external writes.
    assert.equal(await page.evaluate(() => typeof window.swsiOpenPublicInfo), 'function', label + ': info opener');
    await page.evaluate(() => window.swsiOpenPublicInfo('about'));
    await page.waitForSelector('.swsi-public-info-dialog', { timeout: 8000 });
    await page.keyboard.press('Escape');
    await page.waitForSelector('#swsi-public-info-backdrop', { state: 'detached', timeout: 8000 });

    await page.locator('#t-review').click();
    await page.waitForSelector('.swsi-myhub', { timeout: 25000 });
    assert.match(await page.locator('.swsi-myhub').innerText(), /學習中心/, label + ': learning route');

    await page.locator('#t-essay').click();
    await page.waitForFunction(() => {
      const text = document.querySelector('#app')?.innerText || '';
      return /申論/.test(text) && text.length > 50;
    }, null, { timeout: 18000 });

    await page.locator('#t-home').click();
    await page.waitForSelector('#app .swsi-focus-primary', { timeout: 15000 });

    if (practice) {
      // Navigation only: do not answer, score, submit or persist hosted data.
      await page.getByRole('button', { name: /開始 10 題/ }).first().click();
      await page.waitForSelector('.pcount', { timeout: 45000 });
      assert.equal((await page.locator('.pcount').innerText()).trim(), '1 / 10', label + ': practice queue');
      await page.getByRole('button', { name: /結束這次練習/ }).click();
      await page.waitForSelector('#app .swsi-focus-primary', { timeout: 20000 });
    }

    assert.deepEqual(pageErrors, [], label + ': uncaught page errors');
    console.log('CLOUDFLARE LIVE BROWSER OK ' + label + ' blockedWrites=' + blockedWrites);
  } finally {
    await context.close();
    await browser.close();
  }
}
(async () => {
  await check(chromium, 'chromium-phone', 390, 844, true);
  await check(chromium, 'chromium-desktop', 1365, 900, false);
  await check(webkit, 'webkit-iphone', 390, 844, false);
  console.log('CLOUDFLARE LIVE BROWSER ACCEPTANCE OK: read-only mobile, desktop, iPhone');
})().catch(error => {
  console.error('CLOUDFLARE LIVE BROWSER ACCEPTANCE FAILED: ' + String(error.stack || error));
  process.exit(1);
});

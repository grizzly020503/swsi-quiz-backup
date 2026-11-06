#!/usr/bin/env node
'use strict';
// Read-only acceptance of the actual Cloudflare and Netlify student homepages.
// This does not deploy, call AI, submit answers, read user data, or mutate production.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

// Release source truth is the reviewed Cloudflare V3 CSS; the root Netlify
// build must mirror it. Check live sites, not just their local build outputs.
const reviewedHtml = fs.readFileSync(path.join(__dirname, '../cdn/index.html'), 'utf8');
const reviewedStyles = [...reviewedHtml.matchAll(
  /<style id="swsi-calm-learning-ui-v3">([\s\S]*?)<\/style>/g
)];
assert.equal(reviewedStyles.length, 1, 'reviewed CDN must contain exactly one V3 style');
const reviewedV3Hash = crypto.createHash('sha256').update(reviewedStyles[0][1]).digest('hex');

const SITES = Object.freeze({
  primary: 'https://wandering-wave-4418.c022050333.workers.dev',
  backup: 'https://swsi-quiznetlify.netlify.app',
});
const EXPECTED_NAV = ['首頁', '刷題', '申論', '我的'];
const EXPECTED_PATHS = ['歷屆試題', '申論練習'];
const EXPECTED_TOOLS = ['模擬考', '錯題本', '弱點分析'];

async function examine(browser, name, origin) {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    reducedMotion: 'reduce',
    serviceWorkers: 'block',
  });
  let blockedWrites = 0;
  await context.route('**/*', route => {
    const method = route.request().method().toUpperCase();
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
      blockedWrites += 1;
      return route.abort();
    }
    return route.continue();
  });
  try {
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(String(error.message || error)));
    const response = await page.goto(origin + '/?swsi_v4_readonly=1', {
      waitUntil: 'domcontentloaded', timeout: 35000,
    });
    assert.equal(response?.status(), 200, name + ': homepage HTTP status');
    assert.equal(new URL(page.url()).origin, origin, name + ': unexpected origin');
    await page.waitForSelector('#app .swsi-v4-hero .swsi-v4-start', { timeout: 45000 });
    await page.waitForFunction(() => {
      const buttons = [...document.querySelectorAll('#tabbar button')];
      return buttons.filter(el => {
        const style = getComputedStyle(el);
        const box = el.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' &&
          Number(style.opacity) !== 0 && box.width > 0 && box.height > 0;
      }).length === 4;
    }, null, { timeout: 15000 });
    const got = await page.evaluate(() => {
      const visible = el => {
        const style = getComputedStyle(el);
        const box = el.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' &&
          Number(style.opacity) !== 0 && box.width > 0 && box.height > 0;
      };
      const hero = document.querySelector('#app .swsi-v4-hero');
      return {
        heroCount: document.querySelectorAll('#app .swsi-v4-hero').length,
        headline: hero?.querySelector('h1')?.textContent?.trim() || '',
        heroColor: hero ? getComputedStyle(hero).backgroundColor : '',
        primaryAction: hero?.querySelector('.swsi-v4-start')?.textContent?.trim() || '',
        paths: [...document.querySelectorAll('#app .swsi-v4-study-paths > .swsi-v4-path')]
          .map(el => el.querySelector('.swsi-v4-path-title')?.textContent?.trim() || ''),
        tools: [...document.querySelectorAll('#app .swsi-v4-tool-grid > button')]
          .map(el => el.querySelector('span:last-child')?.textContent?.trim() || ''),
        nav: [...document.querySelectorAll('#tabbar button')].filter(visible)
          .map(el => el.getAttribute('aria-label') || el.textContent.trim()),
      };
    });
    // Previously the backup V4 home passed while its base visual stylesheet
    // was still older than Cloudflare. Verify the *hosted* inline V3 CSS hash.
    const styles = await page.locator('style#swsi-calm-learning-ui-v3').allTextContents();
    assert.equal(styles.length, 1, name + ': V3 stylesheet absent/duplicated on hosted site');
    const hostedV3Hash = crypto.createHash('sha256').update(styles[0]).digest('hex');
    assert.equal(hostedV3Hash, reviewedV3Hash,
      name + ': hosted V3 CSS does not match reviewed CDN source; expected=' +
      reviewedV3Hash.slice(0, 16) + ' actual=' + hostedV3Hash.slice(0, 16) +
      ' (a controlled site deployment may still be needed)');
    got.v3StyleHash = hostedV3Hash;

    assert.equal(got.heroCount, 1, name + ': V4 hero must exist exactly once');
    assert.equal(got.headline, '今天，從一題開始。', name + ': homepage renderer is stale');
    assert.equal(got.heroColor, 'rgb(229, 240, 235)', name + ': approved hero color drift');
    assert(got.primaryAction.includes('開始刷題'), name + ': primary action missing');
    assert.deepEqual(got.paths, EXPECTED_PATHS, name + ': V4 study paths mismatch');
    assert.equal(got.tools.length, 3, name + ': V4 tools count');
    assert.deepEqual(got.tools.map(x => x.startsWith('錯題本') ? '錯題本' : x),
      EXPECTED_TOOLS, name + ': V4 tools labels/order mismatch');
    assert.deepEqual(got.nav, EXPECTED_NAV, name + ': V4 navigation mismatch');
    assert.equal(errors.length, 0, name + ': page JS errors: ' + errors.slice(0, 3).join('; '));
    console.log('SWSI V4 READ-ONLY HOME OK ' + name +
      ': one hero, two study paths, three tools, four navigation tabs; network writes blocked=' + blockedWrites);
    return got;
  } finally {
    await context.close();
  }
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const primary = await examine(browser, 'Cloudflare primary', SITES.primary);
    const backup = await examine(browser, 'Netlify backup', SITES.backup);
    assert.deepEqual(backup, primary, 'primary / backup V4 visible-home parity mismatch');
    console.log('SWSI PRIMARY/BACKUP V4 HOME PARITY OK (read-only, no deployment)');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error('SWSI PRIMARY/BACKUP V4 HOME PARITY NO-GO:', error.message || error);
  process.exitCode = 1;
});

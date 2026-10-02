#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const base = process.argv[2] || 'http://127.0.0.1:4173';
const overlay = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/essay_guide_overlay.json'), 'utf8'));
const autoRows = JSON.parse(fs.readFileSync(path.join(ROOT, 'auto/essays_auto.json'), 'utf8'));
const autoById = new Map(autoRows.map(row => [String(row.id), row]));
const published = overlay.records.map(row => String(row.id));
const held = overlay.held_for_review.map(row => String(row.id));

const QUESTION_CDN_HOST = 'wandering-wave-4418.c022050333.workers.dev';
const QUESTION_CDN_PREFIX = '/question-shards/';
const LOCAL_SHARD_DIR = path.join(ROOT, 'cdn/question-shards');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const pageErrors = [];
  page.on('pageerror', err => pageErrors.push(String(err && err.message || err)));

  const localOrigin = new URL(base).origin;
  await page.route('**/*', async route => {
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

  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await page.waitForSelector('.swsi-focus-primary', { timeout: 30000 });
  const allIds = [...published, ...held];
  await page.waitForFunction(ids => {
    let rows = [];
    try {
      if (typeof ESSAYS !== 'undefined' && Array.isArray(ESSAYS)) rows = ESSAYS;
      else if (Array.isArray(window.ESSAYS)) rows = window.ESSAYS;
    } catch (_e) {
      rows = Array.isArray(window.ESSAYS) ? window.ESSAYS : [];
    }
    const seen = new Set(rows.map(row => row && String(row.id)));
    return ids.every(id => seen.has(id));
  }, allIds, { timeout: 30000 });

  const snapshot = await page.evaluate(({ published, held }) => {
    let rows = [];
    try {
      if (typeof ESSAYS !== 'undefined' && Array.isArray(ESSAYS)) rows = ESSAYS;
      else if (Array.isArray(window.ESSAYS)) rows = window.ESSAYS;
    } catch (_e) {
      rows = Array.isArray(window.ESSAYS) ? window.ESSAYS : [];
    }
    function get(id) {
      const essay = rows.find(row => row && String(row.id) === id) || null;
      const guide = (window.ESSAY_GUIDES || {})[id] || null;
      return {
        id,
        q: essay ? String(essay.q || '') : '',
        guide,
        verified: typeof window.swsiEssayGuideIsVerified === 'function'
          ? window.swsiEssayGuideIsVerified(id)
          : false,
        html: guide && typeof window.guideHTML === 'function' ? window.guideHTML(guide) : ''
      };
    }
    return {
      published: published.map(get),
      held: held.map(get)
    };
  }, { published, held });

  assert.strictEqual(snapshot.published.length, published.length);
  for (const got of snapshot.published) {
    const expected = autoById.get(got.id);
    assert(expected, `official auto essay missing: ${got.id}`);
    assert.strictEqual(got.q, expected.q, `browser official question mismatch: ${got.id}`);
    assert(got.guide, `student runtime guide missing: ${got.id}`);
    assert.strictEqual(got.verified, true, `student runtime does not trust verified guide: ${got.id}`);
    assert.strictEqual(got.guide.review_status, 'verified', `review status mismatch: ${got.id}`);
    assert.strictEqual(got.guide.is_official, false, `official flag mismatch: ${got.id}`);
    assert(Array.isArray(got.guide.review_sources) && got.guide.review_sources.length >= 2, `review sources missing: ${got.id}`);
    assert(/✓ 已逐題核對/.test(got.html), `verified badge missing: ${got.id}`);
    assert(/不是考選部官方答案/.test(got.html), `non-official student note missing: ${got.id}`);
    const combined = [got.guide.kao, got.guide.dati, ...(got.guide.biaoti || []), ...(got.guide.kw || [])].join('\n');
    assert(combined.length >= 180, `guide content unexpectedly thin: ${got.id}`);
  }

  for (const got of snapshot.held) {
    const expected = autoById.get(got.id);
    assert(expected, `held official auto essay missing: ${got.id}`);
    assert.strictEqual(got.q, expected.q, `held browser official question mismatch: ${got.id}`);
    assert.strictEqual(got.guide, null, `held guide leaked into browser runtime: ${got.id}`);
    assert.strictEqual(got.verified, false, `held guide unexpectedly verified: ${got.id}`);
  }

  assert.deepStrictEqual(pageErrors, [], 'browser page errors: ' + pageErrors.join(' | '));
  console.log(`ESSAY GUIDE OVERLAY BROWSER OK: verified=${published.length}; held=${held.length}; page_errors=0`);
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

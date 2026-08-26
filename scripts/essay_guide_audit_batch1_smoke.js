const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const base = process.argv[2] || 'http://127.0.0.1:4173';
const QUESTION_CDN_HOST = 'wandering-wave-4418.c022050333.workers.dev';
const QUESTION_CDN_PREFIX = '/question-shards/';
const LOCAL_SHARD_DIR = path.resolve(process.cwd(), 'cdn/question-shards');
const norm = s => String(s || '').normalize('NFKC');

const CASES = [
  {
    id: '社會政策與社會立法-108-1-申論2',
    qMust: ['申請入住', '入住之中', '離院之後'],
    guideMust: ['申請入住', '入住之中', '離院之後', '自我決定', '離院轉銜'],
    guideMustNot: ['Reamer/Dolgoff']
  },
  {
    id: '人類行為與社會環境-110-2-申論1',
    qMust: ['2018', '強化社會安全網', '優點和限制'],
    guideMust: ['家庭社區為基石', '簡化受理窗口', '整合服務體系', '跨網絡'],
    guideMustNot: ['國家／市場／家庭／志願部門', '民營化/POSC']
  },
  {
    id: '社會工作研究方法-106-2-申論2',
    qMust: ['非反應式研究', 'non-reactive research'],
    guideMust: ['反應性', '內容分析', '既有統計', '次級資料分析'],
    guideMustNot: ['深度訪談／焦點團體／參與觀察']
  },
  {
    id: '社會工作研究方法-105-2-申論1',
    qMust: ['暫時性', '反覆論證性', '觀察', '無偏見', '透明化'],
    guideMust: ['暫時性', '反覆論證性', '觀察', '無偏見', '透明化'],
    guideMustNot: ['實證（量化） vs 詮釋（質性）']
  },
  {
    id: '社會政策與社會立法-108-2-申論1',
    qMust: ['Le Grand', '五個', '長期照顧'],
    guideMust: ['公共支出', '最終所得', '使用的平等', '成本的平等', '結果的平等'],
    guideMustNot: ['長照3.0', '國家／市場／家庭／志願部門']
  }
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [];
  page.on('pageerror', err => errors.push(String(err && err.message || err)));

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
  await page.waitForFunction(() => window.SWSI_ESSAY_AUDIT_BATCH1 && window.SWSI_ESSAY_AUDIT_BATCH1.verifiedIds.length === 5);

  const data = await page.evaluate((ids) => {
    let rows = [];
    try {
      if (typeof ESSAYS !== 'undefined' && Array.isArray(ESSAYS)) rows = ESSAYS;
      else if (Array.isArray(window.ESSAYS)) rows = window.ESSAYS;
    } catch (_e) {
      rows = Array.isArray(window.ESSAYS) ? window.ESSAYS : [];
    }
    return ids.map(id => {
      const e = rows.find(x => x && String(x.id) === id) || null;
      const g = (window.ESSAY_GUIDES || {})[id] || null;
      const html = g && typeof window.guideHTML === 'function' ? window.guideHTML(g) : '';
      return {
        id,
        q: e ? String(e.q || '') : '',
        guide: g,
        html,
        verified: typeof window.swsiEssayGuideIsVerified === 'function' ? window.swsiEssayGuideIsVerified(id) : false
      };
    });
  }, CASES.map(x => x.id));

  assert.strictEqual(data.length, 5, 'batch 1 item count mismatch');

  for (let i = 0; i < CASES.length; i++) {
    const spec = CASES[i];
    const got = data[i];
    console.log(`ESSAY AUDIT FORMAL Q ${got.id}: ${got.q}`);
    assert(got.q, `official essay missing at runtime: ${spec.id}`);
    assert(got.guide, `guide missing: ${spec.id}`);
    assert.strictEqual(got.verified, true, `guide not verified: ${spec.id}`);
    assert.strictEqual(got.guide.review_status, 'verified', `review_status mismatch: ${spec.id}`);
    assert.strictEqual(got.guide.reviewed_at, '2026-08-26', `review date missing: ${spec.id}`);
    assert(Array.isArray(got.guide.review_sources) && got.guide.review_sources.length >= 1, `review sources missing: ${spec.id}`);
    assert(/✓ 已逐題核對/.test(got.html), `verified badge not rendered: ${spec.id}`);
    assert(/不是考選部官方答案/.test(got.html), `SWSI-not-official note missing: ${spec.id}`);

    const qText = norm(got.q);
    for (const s of spec.qMust) assert(qText.includes(norm(s)), `formal question check failed for ${spec.id}: ${s}`);

    const guideText = [got.guide.kao, got.guide.dati, ...(got.guide.biaoti || []), ...(got.guide.kw || [])].join('\n');
    for (const s of spec.guideMust) assert(guideText.includes(s), `question-specific guide content missing for ${spec.id}: ${s}`);
    for (const s of spec.guideMustNot) assert(!guideText.includes(s), `old mismatched template leaked into ${spec.id}: ${s}`);
  }

  const verifiedIds = await page.evaluate(() => window.SWSI_ESSAY_AUDIT_BATCH1.verifiedIds.slice());
  assert.deepStrictEqual(verifiedIds, CASES.map(x => x.id), 'audit registry IDs mismatch');
  assert.deepStrictEqual(errors, [], 'browser page errors: ' + errors.join(' | '));

  console.log('ESSAY GUIDE AUDIT BATCH 1 SMOKE OK: verified=5');
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

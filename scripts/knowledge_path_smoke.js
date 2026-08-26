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

  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await page.waitForSelector('.swsi-focus-primary', { timeout: 30000 });
  await page.waitForFunction(() => typeof window.swsiKnowledgeSearch === 'function' && Array.isArray(window.THEORIES) && Array.isArray(window.LAWS));

  // Search should present one coherent path: understand -> MCQ -> essay.
  await page.evaluate(() => { searchQ=''; go('search'); });
  await page.waitForSelector('#searchbox');
  const theoryName = await page.evaluate(() => {
    const list = window.THEORIES || [];
    const hit = list.find(t => t && t.n && typeof searchAll === 'function' && searchAll(t.n).theories.length);
    return (hit || list[0] || {}).n || '';
  });
  assert(theoryName, 'no theory available for knowledge-path smoke');
  await page.locator('#searchbox').fill(theoryName);
  await page.waitForSelector('.swsi-k-path');
  const searchText = await page.locator('#search-results').innerText();
  assert(/1\s*先理解/.test(searchText), 'knowledge search missing understand step');
  assert(/2\s*看選擇題怎麼考/.test(searchText), 'knowledge search missing MCQ step');
  assert(/3\s*看申論怎麼出/.test(searchText), 'knowledge search missing essay step');

  // Opening a theory from search must actually expand that theory card.
  const theoryCard = page.locator('.swsi-k-card').filter({ hasText: theoryName }).first();
  assert(await theoryCard.count(), 'theory result card missing');
  await theoryCard.click();
  await page.waitForSelector('.ecard.open', { timeout: 30000 });
  const theoryOpenText = await page.locator('.ecard.open').first().innerText();
  assert(theoryOpenText.includes(theoryName), 'wrong theory opened from search');
  assert(/核心概念/.test(theoryOpenText), 'opened theory missing core concept');
  assert(/從理論接到考題/.test(theoryOpenText), 'theory missing exam linkage');
  assert(/搜尋.*全部考法/.test(theoryOpenText), 'theory missing full-search action');

  // Pick a law that really occurs in question/essay data, then verify its exam linkage.
  const lawName = await page.evaluate(() => {
    const laws = window.LAWS || [];
    const all = window.ALL || [];
    const essays = window.ESSAYS || [];
    for (const l of laws) {
      if (!l || !l.n) continue;
      const exactMcq = all.some(q => String((q && q.law) || '').includes(l.n));
      const exactEssay = essays.some(e => Array.isArray(e && e.laws) && e.laws.some(x => String(x || '').includes(l.n)));
      if (exactMcq || exactEssay) return l.n;
    }
    return (laws[0] || {}).n || '';
  });
  assert(lawName, 'no law available for knowledge-path smoke');
  await page.evaluate(name => window.swsiKnowledgeSearch(name), lawName);
  await page.waitForSelector('.swsi-k-path');
  const lawCard = page.locator('.swsi-k-card.law').filter({ hasText: lawName }).first();
  assert(await lawCard.count(), 'law result card missing');
  await lawCard.click();
  await page.waitForSelector('.ecard.open', { timeout: 30000 });
  const lawOpenText = await page.locator('.ecard.open').first().innerText();
  assert(lawOpenText.includes(lawName), 'wrong law opened from search');
  assert(/核心重點/.test(lawOpenText), 'opened law missing core summary');
  assert(/從法規接到考題/.test(lawOpenText), 'law missing exam linkage');
  assert(/搜尋.*全部考法/.test(lawOpenText), 'law missing full-search action');

  assert.deepStrictEqual(browserErrors, [], 'browser page errors: ' + browserErrors.join(' | '));
  console.log('KNOWLEDGE PATH SMOKE OK');
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

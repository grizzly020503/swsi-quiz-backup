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
  await page.waitForFunction(() => window.SWSI_LAW_TRUST && /Law Trust Layer V1/.test(window.SWSI_LAW_TRUST.version || ''));
  await page.waitForFunction(() => window.SWSI_LAW_TRUST && /Law Trust Batch 2/.test(window.SWSI_LAW_TRUST.batch2 || ''));
  await page.waitForFunction(() => window.SWSI_NEW_RESIDENT_STATUS && /New Resident Basic Act Status Fix/.test(window.SWSI_NEW_RESIDENT_STATUS.version || ''));

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

  // Pick a law that really occurs in question/essay data, then verify its exam linkage and trust panel.
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
  await page.waitForSelector('.ecard.open .swsi-law-trust', { timeout: 30000 });
  const lawOpenText = await page.locator('.ecard.open').first().innerText();
  assert(lawOpenText.includes(lawName), 'wrong law opened from search');
  assert(/核心重點/.test(lawOpenText), 'opened law missing core summary');
  assert(/從法規接到考題/.test(lawOpenText), 'law missing exam linkage');
  assert(/搜尋.*全部考法/.test(lawOpenText), 'law missing full-search action');
  assert(/官方來源/.test(lawOpenText), 'law trust panel missing official-source status');
  assert((await page.locator('.ecard.open .swsi-law-trust a').count()) >= 1, 'law trust panel missing source link');

  // P0 content correction: Social Assistance Act must not teach one national fixed amount.
  await page.evaluate(() => openLawCard('社會救助法'));
  await page.waitForSelector('.ecard.open .swsi-law-trust', { timeout: 30000 });
  const aidText = await page.locator('.ecard.open').first().innerText();
  assert(/當地區公告最低生活費/.test(aidText), 'social assistance card still lacks local-threshold wording');
  assert(/並非全國統一/.test(aidText), 'social assistance card should explicitly reject one national threshold');
  assert(/✓ 官方來源已逐卡核對/.test(aidText), 'social assistance card should be verified');

  // A policy card must be labeled as policy rather than law.
  await page.evaluate(() => openLawCard('性別平等政策綱領'));
  await page.waitForSelector('.ecard.open .swsi-law-trust', { timeout: 30000 });
  const policyTrust = await page.locator('.ecard.open .swsi-law-trust').innerText();
  assert(/政策／行政方案/.test(policyTrust), 'policy card not distinguished from law');
  assert(!/現行法律/.test(policyTrust), 'policy card incorrectly labeled as current law');

  // Promulgation and effectiveness must not be conflated for the New Resident Basic Act.
  await page.evaluate(() => openLawCard('新住民基本法'));
  await page.waitForSelector('.ecard.open .swsi-law-trust', { timeout: 30000 });
  const residentText = await page.locator('.ecard.open').first().innerText();
  const residentTrust = await page.locator('.ecard.open .swsi-law-trust').innerText();
  assert(/第19條.*施行日期.*行政院定之/.test(residentText), 'new resident act missing Article 19 effective-date caveat');
  assert(/已制定公布・施行日另定/.test(residentTrust), 'new resident act status badge missing');
  assert(!/現行法律/.test(residentTrust), 'new resident act must not be generically labeled current law while effective date is separately determined');

  // Batch 2: high-frequency legal details must be precise and verified.
  const batch2Cases = [
    ['家庭暴力防治法', /4小時/, /2年以下/, /三種/],
    ['身心障礙者權益保障法', /34人以上/, /3%/, /67人以上/],
    ['老人福利法', /年滿65歲以上/, /第41至44條|第41.*44條/, /應通報/],
    ['病人自主權利法', /預立醫療照護諮商/, /預立醫療決定/, /五類臨床條件|五種臨床條件/],
    ['少年事件處理法', /12歲以上18歲未滿/, /行政輔導先行/, /112年7月1日/]
  ];
  for (const [name, a, b, c] of batch2Cases) {
    await page.evaluate(n => openLawCard(n), name);
    await page.waitForSelector('.ecard.open .swsi-law-trust', { timeout: 30000 });
    const text = await page.locator('.ecard.open').first().innerText();
    assert(/✓ 官方來源已逐卡核對/.test(text), `${name} should be verified`);
    assert(a.test(text), `${name} missing first verified detail`);
    assert(b.test(text), `${name} missing second verified detail`);
    assert(c.test(text), `${name} missing third verified detail`);
  }

  // Missing high-priority laws should now exist in the reference layer.
  const additions = await page.evaluate(() => ['社會福利基本法','性騷擾防治法','性侵害犯罪防治法','精神衛生法','人口販運防制法','新住民基本法'].filter(n => (window.LAWS || []).some(x => x && x.n === n)));
  assert.strictEqual(additions.length, 6, 'one or more high-priority law cards are missing');

  assert.deepStrictEqual(browserErrors, [], 'browser page errors: ' + browserErrors.join(' | '));
  console.log('KNOWLEDGE PATH + LAW TRUST BATCH 2 SMOKE OK');
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

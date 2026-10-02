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
  const context = await browser.newContext({
    viewport: { width: 412, height: 915 },
    isMobile: true,
    hasTouch: true,
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', err => pageErrors.push(String(err && err.message || err)));

  const localOrigin = new URL(base).origin;
  await page.route('**/*', route => {
    const u = new URL(route.request().url());
    if (u.hostname === QUESTION_CDN_HOST && u.pathname.startsWith(QUESTION_CDN_PREFIX)) {
      const rel = decodeURIComponent(u.pathname.slice(QUESTION_CDN_PREFIX.length));
      if (!rel || rel !== path.basename(rel)) return route.fulfill({ status: 404, body: 'not found' });
      const file = path.join(LOCAL_SHARD_DIR, rel);
      if (!fs.existsSync(file)) return route.fulfill({ status: 404, body: 'not found' });
      return route.fulfill({
        status: 200,
        contentType: 'application/json; charset=utf-8',
        body: fs.readFileSync(file),
      });
    }
    if (u.origin !== localOrigin) return route.abort();
    return route.continue();
  });

  async function waitHome() {
    await page.waitForSelector('.swsi-focus-primary', { timeout: 30000 });
    await page.waitForFunction(() => !document.body.classList.contains('swsi-question-active'));
  }

  async function assertNoHorizontalOverflow(label) {
    const m = await page.evaluate(() => ({
      innerWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth,
    }));
    assert(m.documentWidth <= m.innerWidth + 3, `${label}: document overflows horizontally (${m.documentWidth}>${m.innerWidth})`);
    assert(m.bodyWidth <= m.innerWidth + 3, `${label}: body overflows horizontally (${m.bodyWidth}>${m.innerWidth})`);
  }

  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await waitHome();
  await assertNoHorizontalOverflow('android-home');

  // This test validates a real Android-like touch viewport, not just a resized desktop page.
  const mobileCaps = await page.evaluate(() => ({
    width: innerWidth,
    height: innerHeight,
    touchPoints: navigator.maxTouchPoints,
  }));
  assert.strictEqual(mobileCaps.width, 412, 'Android-like viewport width drifted');
  assert(mobileCaps.touchPoints >= 1, 'Android-like context lost touch capability');

  const start = page.getByRole('button', { name: /開始 10 題/ });
  assert.strictEqual(await start.count(), 1, '10-question primary CTA missing');
  const startBox = await start.boundingBox();
  assert(startBox && startBox.height >= 44 && startBox.width >= 44, 'primary CTA is too small for touch');
  await start.tap();

  await page.waitForSelector('.qcard .opt', { timeout: 45000 });
  assert.strictEqual((await page.locator('.pcount').innerText()).trim(), '1 / 10', 'mobile CTA did not start a 10-question queue');
  await assertNoHorizontalOverflow('android-question');

  const wrongIndex = await page.evaluate(() => {
    const item = queue && queue[idx];
    if (!item) return -1;
    const keys = ['A','B','C','D'].filter(k => item.options && item.options[k]);
    for (let i = 0; i < keys.length; i++) {
      const k = keys[i];
      let correct = false;
      try { correct = typeof isCorrectAnswer === 'function' ? !!isCorrectAnswer(item, k) : !!ansCorrect(k, item.answer); }
      catch (_e) { correct = String(k) === String(item.answer || ''); }
      if (!correct) return i;
    }
    return -1;
  });
  assert(wrongIndex >= 0, 'could not select a deterministic wrong option');

  const wrongOption = page.locator('.qcard .opt').nth(wrongIndex);
  const optionBox = await wrongOption.boundingBox();
  assert(optionBox && optionBox.height >= 40, 'answer option touch target is too small');
  await wrongOption.tap();
  await page.getByRole('button', { name: '送出答案' }).tap();

  await page.waitForSelector('.qcard .exp');
  await page.waitForSelector('.swsi-answer-line');
  await page.waitForSelector('.swsi-self-cause');
  await assertNoHorizontalOverflow('android-explanation');

  const cause = page.getByRole('button', { name: '概念不熟' });
  assert.strictEqual(await cause.count(), 1, 'self-reported wrong-cause action missing');
  await cause.tap();
  await page.waitForFunction(() => {
    const b = [...document.querySelectorAll('.swsi-cause-chip')].find(x => /概念不熟/.test(x.textContent || ''));
    return b && b.classList.contains('on');
  });

  const disclosure = page.locator('.swsi-explanation-more');
  if (await disclosure.count()) {
    assert(!(await disclosure.first().evaluate(el => el.open)), 'full explanation should start collapsed on mobile');
    await disclosure.first().locator('summary').tap();
    assert(await disclosure.first().evaluate(el => el.open), 'full explanation did not open on mobile');
    await assertNoHorizontalOverflow('android-expanded-explanation');
  }

  await page.getByRole('button', { name: /下一題|看結果/ }).tap();
  await page.waitForSelector('.qcard', { timeout: 10000 });
  assert.strictEqual((await page.locator('.pcount').innerText()).trim(), '2 / 10', 'next-question control did not advance the mobile queue');

  await page.getByRole('button', { name: /結束這次練習/ }).tap();
  await waitHome();

  // Simulate leaving/reopening the app surface. Learning evidence must survive reload.
  await page.reload({ waitUntil: 'commit' });
  await waitHome();
  await assertNoHorizontalOverflow('android-reopened-home');

  // There is intentionally no unfinished-session resume contract yet. Do not fake one.
  const reopenedHomeText = await page.locator('#app').innerText();
  assert(!/繼續上次/.test(reopenedHomeText), 'unfinished-session resume copy appeared without a durable resume contract');

  await page.locator('#t-review').tap();
  await page.waitForSelector('.swsi-myhub', { timeout: 30000 });
  await page.getByRole('button', { name: /錯題複習/ }).tap();
  await page.waitForSelector('.swsi-learning-section', { timeout: 30000 });
  const reviewText = await page.locator('#app').innerText();
  assert(/概念不熟/.test(reviewText), 'saved wrong-cause evidence did not survive mobile reopen');
  assert(/平台看到的弱點考點/.test(reviewText), 'weak-topic learning evidence missing after mobile reopen');
  await assertNoHorizontalOverflow('android-reopened-review');

  assert.deepStrictEqual(pageErrors, [], 'Android-like mobile journey page errors: ' + pageErrors.join(' | '));
  console.log('MOBILE PRIORITY P1-7 SMOKE OK: Android-like touch journey + reopen persistence');

  await context.close();
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

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
  const consoleLines = [];
  const failedRequests = [];
  const servedQuestionFiles = [];
  page.on('pageerror', err => browserErrors.push(String(err && err.message || err)));
  page.on('console', msg => consoleLines.push(msg.type()+': '+msg.text()));
  page.on('requestfailed', req => failedRequests.push(req.url()+' :: '+String(req.failure() && req.failure().errorText || 'failed')));

  const localOrigin = new URL(base).origin;
  await page.route('**/*', route => {
    const req = route.request();
    const u = new URL(req.url());
    if (u.hostname === QUESTION_CDN_HOST && u.pathname.startsWith(QUESTION_CDN_PREFIX)) {
      const rel = decodeURIComponent(u.pathname.slice(QUESTION_CDN_PREFIX.length));
      if (!rel || rel !== path.basename(rel)) return route.fulfill({ status: 404, body: 'not found' });
      const file = path.join(LOCAL_SHARD_DIR, rel);
      if (!fs.existsSync(file)) return route.fulfill({ status: 404, body: 'not found' });
      servedQuestionFiles.push(rel);
      return route.fulfill({ status: 200, contentType: 'application/json; charset=utf-8', body: fs.readFileSync(file) });
    }
    if (u.origin !== localOrigin) return route.abort();
    return route.continue();
  });

  async function dumpDiagnostics(label) {
    const snap = await page.evaluate(() => ({
      readyState: document.readyState,
      title: document.title,
      appText: ((document.querySelector('#app') || {}).textContent || '').trim().slice(0,1600),
      appHTML: ((document.querySelector('#app') || {}).innerHTML || '').slice(0,1600),
      patch: typeof window.SWSI_QB === 'object',
      manifest: !!(window.SWSI_QB && window.SWSI_QB.manifest),
      manifestSource: window.SWSI_QB && window.SWSI_QB.manifestSource,
      loadedFiles: window.SWSI_QB && window.SWSI_QB.loadedFiles ? Array.from(window.SWSI_QB.loadedFiles) : [],
      hasRenderHome: typeof window.renderHome,
      hasEssayNow: typeof window.swsiStartEssayNow
    })).catch(err => ({ evaluateError: String(err) }));
    console.log('=== SWSI QA DIAGNOSTICS: '+label+' ===');
    console.log(JSON.stringify(snap,null,2));
    console.log('served question files:', JSON.stringify(servedQuestionFiles));
    console.log('page errors:', JSON.stringify(browserErrors));
    console.log('console:', JSON.stringify(consoleLines.slice(-30)));
    console.log('failed requests:', JSON.stringify(failedRequests.slice(-30)));
  }

  async function waitHome() {
    try {
      await page.waitForSelector('.swsi-focus-primary', { timeout: 20000 });
      await page.waitForFunction(() => typeof window.swsiStartEssayNow === 'function');
    } catch (err) {
      await dumpDiagnostics('home-not-ready');
      throw err;
    }
  }

  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await waitHome();

  const fontButtons = page.locator('.fontctl button');
  assert((await fontButtons.count()) >= 3, 'font controls missing');
  await fontButtons.nth(1).click();
  await page.waitForFunction(() => document.documentElement.getAttribute('data-fs') === '1');
  await fontButtons.nth(0).click();
  await page.waitForFunction(() => document.documentElement.getAttribute('data-fs') === '0');

  // Force one genuinely wrong answer so the learning-loop UI is always exercised.
  await page.getByRole('button', { name: /直接開始 20 題/ }).click();
  await page.waitForSelector('.qcard .opt', { timeout: 45000 });
  const wrongIndex = await page.evaluate(() => {
    const item = queue && queue[idx];
    if (!item) return -1;
    const keys = ['A','B','C','D'].filter(k => item.options && item.options[k]);
    for (let i=0;i<keys.length;i++) {
      const k=keys[i];
      let ok=false;
      try { ok = typeof isCorrectAnswer==='function' ? !!isCorrectAnswer(item,k) : !!ansCorrect(k,item.answer); }
      catch (_e) { ok = String(k)===String(item.answer||''); }
      if (!ok) return i;
    }
    return -1;
  });
  assert(wrongIndex >= 0, 'could not find an intentionally wrong option');
  await page.locator('.qcard .opt').nth(wrongIndex).click();
  await page.getByRole('button', { name: '送出答案' }).click();
  await page.waitForSelector('.qcard .exp');
  await page.waitForSelector('.swsi-answer-line');
  await page.waitForSelector('.swsi-self-cause');
  assert(/這題你為什麼會錯/.test(await page.locator('.swsi-self-cause').innerText()), 'wrong-cause prompt missing');
  await page.getByRole('button', { name: '概念不熟' }).click();
  await page.waitForFunction(() => {
    const b=[...document.querySelectorAll('.swsi-cause-chip')].find(x => /概念不熟/.test(x.textContent||''));
    return b && b.classList.contains('on');
  });

  const more = page.locator('.swsi-explanation-more');
  if (await more.count()) {
    assert(!(await more.first().evaluate(el => el.open)), 'full explanation should start collapsed');
    await more.first().locator('summary').click();
    assert(await more.first().evaluate(el => el.open), 'full explanation did not expand');
  }
  await page.getByRole('button', { name: /下一題|看結果/ }).click();
  await page.waitForSelector('.qcard');
  await page.getByRole('button', { name: /結束這次練習/ }).click();
  await waitHome();

  // The simplified second tab opens Learning Center; review is one action inside it.
  await page.locator('#t-review').click();
  await page.waitForSelector('.swsi-myhub', { timeout: 30000 });
  const hubText = await page.locator('.swsi-myhub').innerText();
  assert(/學習中心/.test(hubText), 'learning tab did not open Learning Center');
  assert(/錯題複習/.test(hubText), 'review action missing from Learning Center');
  await page.getByRole('button', { name: /錯題複習/ }).click();
  await page.waitForSelector('.swsi-learning-section', { timeout: 30000 });
  const reviewText = await page.locator('#app').innerText();
  assert(/你自己標記的錯因/.test(reviewText), 'self-reported cause section missing from review');
  assert(/概念不熟/.test(reviewText), 'saved self-reported cause missing from review');
  assert(/平台看到的弱點考點/.test(reviewText), 'platform weak-topic section missing from review');

  // Progress remains available from review and exposes actionable learning data.
  await page.getByRole('button', { name: /查看完整學習進度/ }).click();
  await page.waitForSelector('.swsi-progress-hero', { timeout: 30000 });
  const progressText = await page.locator('#app').innerText();
  assert(/我的學習進度/.test(progressText), 'progress heading missing');
  assert(/今天下一步/.test(progressText), 'recommended next step missing');
  assert(/不同題目/.test(progressText), 'unique-question progress missing');
  assert(/題庫覆蓋/.test(progressText), 'coverage progress missing');

  await page.locator('#t-home').click();
  await waitHome();

  // Essay flow remains intact after learning-center simplification.
  await page.getByRole('button', { name: '直接練一題' }).click();
  await page.waitForSelector('.wta', { timeout: 30000 });
  const textarea = page.locator('.wta').first();
  await textarea.fill('一、測試作答\n（一）測試內容');
  assert((await textarea.inputValue()).includes('測試作答'), 'essay textarea did not accept input');

  let sawConfirm = false;
  page.once('dialog', async dialog => {
    sawConfirm = true;
    assert(/清空|清除/.test(dialog.message()), 'unexpected clear confirmation text');
    await dialog.accept();
  });
  await page.getByRole('button', { name: /清除.*作答/ }).click();
  await page.waitForFunction(() => {
    const ta = document.querySelector('.wta');
    return ta && ta.value === '';
  });
  assert(sawConfirm, 'clear draft did not ask for confirmation');

  await page.locator('#t-home').click();
  await waitHome();
  await page.locator('#t-essay').click();
  await page.waitForFunction(() => {
    const h = document.querySelector('#app .section-h');
    return h && /申論題/.test(h.textContent || '');
  }, null, { timeout: 30000 });
  assert((await page.locator('.wta').count()) === 0, 'bottom Essay nav should open the library, not force a random question');

  // Learning tab must still land on the hub rather than bypassing it into raw review.
  await page.locator('#t-review').click();
  await page.waitForSelector('.swsi-myhub', { timeout: 30000 });
  assert(/錯題複習/.test(await page.locator('.swsi-myhub').innerText()), 'learning hub lost its review entry');

  assert.deepStrictEqual(browserErrors, [], 'browser page errors: ' + browserErrors.join(' | '));
  console.log('BROWSER INTERACTION SMOKE OK');
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

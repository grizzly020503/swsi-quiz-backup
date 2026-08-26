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

    // Use the exact production-shaped manifest/shards committed in this repo, but serve
    // them locally inside Playwright. CI therefore tests SWSI interactions deterministically
    // instead of testing whether a GitHub runner happens to reach Cloudflare/Supabase.
    if (u.hostname === QUESTION_CDN_HOST && u.pathname.startsWith(QUESTION_CDN_PREFIX)) {
      const rel = decodeURIComponent(u.pathname.slice(QUESTION_CDN_PREFIX.length));
      if (!rel || rel !== path.basename(rel)) {
        return route.fulfill({ status: 404, body: 'not found' });
      }
      const file = path.join(LOCAL_SHARD_DIR, rel);
      if (!fs.existsSync(file)) {
        return route.fulfill({ status: 404, body: 'not found' });
      }
      servedQuestionFiles.push(rel);
      return route.fulfill({
        status: 200,
        contentType: 'application/json; charset=utf-8',
        body: fs.readFileSync(file)
      });
    }

    // Everything required for the interaction smoke is now local. External fonts,
    // SDKs, AI and fallback APIs are intentionally irrelevant to these core journeys.
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

  // For this SPA the real readiness signal is the rendered SWSI home, not a browser load event.
  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await waitHome();

  // Font controls must actually change the root scale state.
  const fontButtons = page.locator('.fontctl button');
  assert((await fontButtons.count()) >= 3, 'font controls missing');
  await fontButtons.nth(1).click();
  await page.waitForFunction(() => document.documentElement.getAttribute('data-fs') === '1');
  await fontButtons.nth(0).click();
  await page.waitForFunction(() => document.documentElement.getAttribute('data-fs') === '0');

  // Home -> one-tap MCQ -> choose -> submit -> compact explanation -> expand -> next.
  await page.getByRole('button', { name: /直接開始 20 題/ }).click();
  await page.waitForSelector('.qcard .opt', { timeout: 45000 });
  await page.locator('.qcard .opt').first().click();
  await page.getByRole('button', { name: '送出答案' }).click();
  await page.waitForSelector('.qcard .exp');
  await page.waitForSelector('.swsi-answer-line');
  const more = page.locator('.swsi-explanation-more');
  if (await more.count()) {
    assert(!(await more.first().evaluate(el => el.open)), 'full explanation should start collapsed');
    await more.first().locator('summary').click();
    assert(await more.first().evaluate(el => el.open), 'full explanation did not expand');
  }
  await page.getByRole('button', { name: /下一題|看結果/ }).click();
  await page.waitForSelector('.qcard');

  // Return home using the actual UI.
  await page.getByRole('button', { name: /結束這次練習/ }).click();
  await waitHome();

  // Home -> one-tap essay should open an actual writing box, not just a subject list.
  await page.getByRole('button', { name: '直接練一題' }).click();
  await page.waitForSelector('.wta', { timeout: 30000 });
  const textarea = page.locator('.wta').first();
  await textarea.fill('一、測試作答\n（一）測試內容');
  assert((await textarea.inputValue()).includes('測試作答'), 'essay textarea did not accept input');

  // Clear is destructive and must still require confirmation.
  let sawConfirm = false;
  page.once('dialog', async dialog => {
    sawConfirm = true;
    assert(/清空|清除/.test(dialog.message()), 'unexpected clear confirmation text');
    await dialog.accept();
  });
  await page.getByRole('button', { name: /清除作答/ }).click();
  await page.waitForFunction(() => {
    const ta = document.querySelector('.wta');
    return ta && ta.value === '';
  });
  assert(sawConfirm, 'clear draft did not ask for confirmation');

  // Bottom Home then Bottom Essay must open the essay library (navigation semantics),
  // while the home card remains the one-tap practice entry.
  await page.getByRole('button', { name: '首頁' }).click();
  await waitHome();
  await page.getByRole('button', { name: '申論' }).click();
  await page.waitForFunction(() => {
    const h = document.querySelector('#app .section-h');
    return h && /申論題/.test(h.textContent || '');
  }, { timeout: 30000 });
  assert((await page.locator('.wta').count()) === 0, 'bottom Essay nav should open the library, not force a random question');

  // Bottom Review must navigate and render rather than silently failing.
  await page.getByRole('button', { name: '複習' }).click();
  await page.waitForFunction(() => {
    const app = document.querySelector('#app');
    return app && (/今日複習|未熟練|今天到期/.test(app.textContent || ''));
  }, { timeout: 60000 });

  // Fail on real JS exceptions. Network/font console noise is intentionally ignored.
  assert.deepStrictEqual(browserErrors, [], 'browser page errors: ' + browserErrors.join(' | '));

  console.log('BROWSER INTERACTION SMOKE OK');
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

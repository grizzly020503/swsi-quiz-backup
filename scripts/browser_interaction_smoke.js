const assert = require('assert');
const { chromium } = require('playwright');

const base = process.argv[2] || 'http://127.0.0.1:4173';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const browserErrors = [];
  page.on('pageerror', err => browserErrors.push(String(err && err.message || err)));

  // These are optional presentation/client helpers. Abort them in CI so a slow third-party
  // CDN cannot block DOMContentLoaded; the app already has a native REST fallback.
  await page.route('**/*', route => {
    const u = route.request().url();
    if (u.includes('fonts.googleapis.com') || u.includes('fonts.gstatic.com') || u.includes('cdn.jsdelivr.net/npm/@supabase/')) {
      return route.abort();
    }
    return route.continue();
  });

  async function waitHome() {
    await page.waitForSelector('.swsi-focus-primary', { timeout: 45000 });
    await page.waitForFunction(() => typeof window.swsiStartEssayNow === 'function');
  }

  await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 20000 });
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
})().catch(async err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

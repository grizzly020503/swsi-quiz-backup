const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const base = process.argv[2] || 'http://127.0.0.1:4173';
const QUESTION_CDN_HOST = 'wandering-wave-4418.c022050333.workers.dev';
const QUESTION_CDN_PREFIX = '/question-shards/';
const LOCAL_SHARD_DIR = path.resolve(process.cwd(), 'cdn/question-shards');
const FEEDBACK_URL = 'https://yumjtrdctaxyczpspuyo.supabase.co/functions/v1/swsi-feedback';

async function optionTexts(page) {
  return page.locator('#swsi-report-category option').allTextContents();
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [];
  const feedbackRequests = [];
  page.on('pageerror', err => errors.push(String(err && err.message || err)));

  const localOrigin = new URL(base).origin;
  await page.route('**/*', async route => {
    const req = route.request();
    const u = new URL(req.url());
    if (req.url() === FEEDBACK_URL) {
      const headers = await req.allHeaders();
      let body = {};
      try { body = JSON.parse(req.postData() || '{}'); } catch (_e) {}
      feedbackRequests.push({ headers, body, method: req.method() });
      return route.fulfill({
        status: 201,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({ ok: true, report_no: 999, message: '收到，我們會核對這個問題。你可以繼續作答。' })
      });
    }
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
  await page.waitForFunction(() => window.SWSI_FEEDBACK && /Feedback V1/.test(window.SWSI_FEEDBACK.version || ''));
  await page.waitForFunction(() => window.SWSI_FEEDBACK_COMPACT && window.SWSI_FEEDBACK_COMPACT.version === 'V2');

  assert((await page.locator('footer .swsi-report-footer-btn').count()) === 1, 'general feedback footer entry missing');

  // Official MCQ: compact form, official trust note, and only question-related categories.
  await page.getByRole('button', { name: /開始 10 題/ }).click();
  await page.waitForSelector('.qcard .swsi-report-mini', { timeout: 45000 });
  assert.strictEqual((await page.locator('.pcount').innerText()).trim(), '1 / 10', 'feedback smoke did not start the default 10-question queue');
  await page.locator('.qcard .swsi-report-mini').click();
  await page.waitForSelector('.swsi-report-dialog[data-swsi-compact="2"]');
  let modalText = await page.locator('.swsi-report-dialog').innerText();
  assert(/回報這個問題/.test(modalText), 'compact report title missing');
  assert(/歷屆題目會先核對考選部資料後再處理/.test(modalText), 'compact official trust wording missing');
  assert(!/目前位置/.test(modalText), 'technical context should be hidden from student-facing compact form');
  assert.deepStrictEqual(await optionTexts(page), ['答案好像不對', '解析有疑問', '題目顯示異常', '其他'], 'MCQ compact categories incorrect');
  assert(!/功能建議/.test(modalText), 'question report must not contain general feature suggestion category');
  await page.locator('#swsi-report-message').fill('測試：這題解析內容可能需要再確認。');
  await page.locator('#swsi-report-form').evaluate(form => form.requestSubmit());
  await page.waitForSelector('.swsi-report-receipt');
  assert(/回報編號 #999/.test(await page.locator('.swsi-report-receipt').innerText()), 'feedback receipt number missing');
  await page.getByRole('button', { name: /繼續使用 SWSI/ }).click();
  assert.strictEqual(feedbackRequests.length, 1, 'feedback API was not called exactly once');
  const sent = feedbackRequests[0];
  assert.strictEqual(sent.method, 'POST', 'feedback API must use POST');
  assert(sent.headers['x-swsi-client-id'] && sent.headers['x-swsi-client-id'].length >= 16, 'stable anonymous client id header missing');
  assert.strictEqual(sent.body.context_type, 'mcq', 'MCQ feedback context type missing');
  assert.strictEqual(sent.body.source_kind, 'official_exam', 'official MCQ must be marked official_exam');
  assert(sent.body.context_id, 'MCQ feedback missing question id');
  assert(sent.body.subject, 'MCQ feedback missing subject');
  assert(sent.body.message.includes('解析內容'), 'feedback message not sent');

  // Theory entry: only theory question + other, with a short SWSI trust line.
  await page.evaluate(() => openTheory('生態系統理論'));
  await page.waitForSelector('.ecard.open .swsi-report-inline .swsi-report-mini', { timeout: 30000 });
  await page.locator('.ecard.open .swsi-report-mini').click();
  await page.waitForSelector('.swsi-report-dialog[data-swsi-compact="2"]');
  modalText = await page.locator('.swsi-report-dialog').innerText();
  assert(/SWSI 整理內容收到回報後會先核對再修正/.test(modalText), 'compact SWSI theory trust wording missing');
  assert.deepStrictEqual(await optionTexts(page), ['理論內容疑問', '其他'], 'theory compact categories incorrect');
  assert.strictEqual(await page.locator('#swsi-report-category').inputValue(), 'theory_question', 'theory report should default to theory category');
  await page.getByRole('button', { name: /關閉回報視窗/ }).click();

  // Law entry: only law outdated + other.
  await page.evaluate(() => openLawCard('社會救助法'));
  await page.waitForSelector('.ecard.open .swsi-report-inline .swsi-report-mini', { timeout: 30000 });
  await page.locator('.ecard.open .swsi-report-mini').click();
  await page.waitForSelector('.swsi-report-dialog[data-swsi-compact="2"]');
  assert.deepStrictEqual(await optionTexts(page), ['法規可能過期', '其他'], 'law compact categories incorrect');
  assert.strictEqual(await page.locator('#swsi-report-category').inputValue(), 'law_outdated', 'law report should default to law-outdated category');
  await page.getByRole('button', { name: /關閉回報視窗/ }).click();

  // Essay entry uses the same short question-report choices, not feature suggestions.
  await page.evaluate(() => swsiStartEssayNow());
  await page.waitForSelector('.wta', { timeout: 30000 });
  await page.waitForSelector('.swsi-report-inline[data-swsi-essay-report="1"] .swsi-report-mini');
  await page.locator('.swsi-report-inline[data-swsi-essay-report="1"] .swsi-report-mini').click();
  await page.waitForSelector('.swsi-report-dialog[data-swsi-compact="2"]');
  modalText = await page.locator('.swsi-report-dialog').innerText();
  assert(/回報這個問題/.test(modalText), 'essay compact report title missing');
  assert.deepStrictEqual(await optionTexts(page), ['答案好像不對', '解析有疑問', '題目顯示異常', '其他'], 'essay compact categories incorrect');
  await page.getByRole('button', { name: /關閉回報視窗/ }).click();

  // General feature suggestions live in the public footer, and the layered shell
  // intentionally exposes that footer on Home rather than repeating it on every
  // internal study page. Return through the real navigation before testing it.
  await page.locator('#t-home').click();
  await page.waitForSelector('.swsi-focus-primary', { timeout: 30000 });
  await page.waitForFunction(() => document.body.getAttribute('data-swsi-page') === 'home');
  const footerFeedback = page.locator('footer .swsi-report-footer-btn');
  await footerFeedback.waitFor({ state: 'visible', timeout: 10000 });
  await footerFeedback.click();
  await page.waitForSelector('.swsi-report-dialog[data-swsi-compact="2"]');
  modalText = await page.locator('.swsi-report-dialog').innerText();
  assert(/回報／提供建議/.test(modalText), 'general feedback compact title missing');
  assert.deepStrictEqual(await optionTexts(page), ['網站功能異常', 'AI 回饋問題', '功能建議', '其他'], 'general feedback categories incorrect');
  await page.getByRole('button', { name: /關閉回報視窗/ }).click();

  assert.deepStrictEqual(errors, [], 'browser page errors: ' + errors.join(' | '));
  console.log('FEEDBACK COMPACT V2 SMOKE OK');
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

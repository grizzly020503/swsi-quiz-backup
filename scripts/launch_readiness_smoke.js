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

  async function waitHome() {
    await page.waitForSelector('.swsi-focus-primary', { timeout: 30000 });
  }

  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await waitHome();

  // First-time guidance must be visible once, dismissible, and stay dismissed.
  const guide = page.locator('.swsi-launch-guide');
  assert.strictEqual(await guide.count(), 1, 'first-use guide missing on fresh localStorage');
  assert(/30 秒看懂 SWSI/.test(await guide.innerText()), 'first-use guide copy missing');
  await guide.getByRole('button', { name: /不再顯示首次使用說明/ }).click();
  await page.waitForFunction(() => !document.querySelector('.swsi-launch-guide'));
  assert.strictEqual(await page.evaluate(() => localStorage.getItem('swsi_launch_guide_dismissed_v1')), '1', 'guide dismissal was not persisted');

  await page.reload({ waitUntil: 'commit' });
  await waitHome();
  assert.strictEqual(await page.locator('.swsi-launch-guide').count(), 0, 'dismissed guide returned after reload');

  // Existing interaction smoke owns seeded review navigation. This launch smoke
  // enters progress directly so it remains valid for a completely new user.
  await page.evaluate(() => {
    if (typeof go !== 'function') throw new Error('go() route helper missing');
    go('progress');
  });
  await page.waitForSelector('.swsi-myhub', { timeout: 30000 });
  await page.waitForSelector('.swsi-launch-reminder', { timeout: 10000 });

  const reminderText = await page.locator('.swsi-launch-reminder').innerText();
  assert(/今日提醒/.test(reminderText), 'daily reminder missing');
  assert(/考試倒數/.test(reminderText), 'exam countdown entry missing');

  // Exam-date modal must stay inside a phone viewport, lock background scroll,
  // support Escape, focus its input, and restore focus to the opener.
  const examButton = page.locator('.swsi-exam-reminder-btn');
  await examButton.click();
  await page.waitForSelector('#swsi-exam-backdrop');
  await page.waitForFunction(() => document.body.classList.contains('swsi-modal-open'));
  await page.waitForFunction(() => document.activeElement && document.activeElement.id === 'swsi-exam-date-input');
  const dialogBox = await page.locator('.swsi-exam-dialog').boundingBox();
  assert(dialogBox, 'exam dialog has no layout box');
  assert(dialogBox.y >= -1, 'exam dialog extends above the viewport');
  assert(dialogBox.y + dialogBox.height <= 845, 'exam dialog extends below the viewport');
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.querySelector('#swsi-exam-backdrop'));
  assert(!(await page.evaluate(() => document.body.classList.contains('swsi-modal-open'))), 'body remained scroll-locked after Escape close');
  await page.waitForFunction(() => document.activeElement && document.activeElement.classList.contains('swsi-exam-reminder-btn'));

  // Target exam date must remain device-local and support save / clear.
  await examButton.click();
  await page.waitForSelector('#swsi-exam-backdrop');
  const dateInput = page.locator('#swsi-exam-date-input');
  await dateInput.fill('2099-12-31');
  await page.getByRole('button', { name: '儲存日期' }).click();
  await page.waitForFunction(() => !document.querySelector('#swsi-exam-backdrop'));
  assert(!(await page.evaluate(() => document.body.classList.contains('swsi-modal-open'))), 'body remained scroll-locked after save');
  assert.strictEqual(await page.evaluate(() => localStorage.getItem('swsi_target_exam_date_v1')), '2099-12-31', 'exam date was not stored locally');
  assert(/距離考試還有/.test(await page.locator('.swsi-exam-reminder-copy').innerText()), 'saved exam countdown was not rendered');

  await examButton.click();
  await page.waitForSelector('#swsi-exam-backdrop');
  await page.getByRole('button', { name: '清除日期' }).click();
  await page.waitForFunction(() => !document.querySelector('#swsi-exam-backdrop'));
  assert.strictEqual(await page.evaluate(() => localStorage.getItem('swsi_target_exam_date_v1')), null, 'exam date did not clear');
  assert(/尚未設定日期/.test(await page.locator('.swsi-exam-reminder-copy').innerText()), 'cleared countdown did not return to unset state');

  // Public footer must reserve enough room for the mobile fixed bottom navigation.
  const footerPadding = await page.evaluate(() => {
    const footer = document.querySelector('.wrap > footer') || document.querySelector('footer');
    return footer ? parseFloat(getComputedStyle(footer).paddingBottom || '0') : -1;
  });
  assert(footerPadding >= 128, 'mobile footer does not reserve clearance for bottom navigation');

  // Admin remains visually secondary for ordinary users.
  const adminLogin = page.locator('[data-swsi-admin-login]');
  if (await adminLogin.count()) {
    assert(/管理者入口/.test(await adminLogin.innerText()), 'admin entry is not using the launch-safe label');
  }

  assert.deepStrictEqual(browserErrors, [], 'browser page errors: ' + browserErrors.join(' | '));
  console.log('LAUNCH READINESS SMOKE OK');
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

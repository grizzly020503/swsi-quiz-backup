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

  async function dumpFirstPaintDiagnostics(label) {
    let state = {};
    try {
      state = await page.evaluate(() => ({
        readyState: document.readyState,
        bootVersion: window.__SWSI_FAST_BOOT_VERSION__ || null,
        bootDeferred: window.__SWSI_BOOT_DEFERRED__,
        view: typeof view === 'undefined' ? null : view,
        hasGo: typeof window.go === 'function' || typeof go === 'function',
        hasRenderHome: typeof window.renderHome === 'function' || typeof renderHome === 'function',
        hasManifestLoader: typeof window.loadQuestionManifest === 'function' || typeof loadQuestionManifest === 'function',
        appText: (document.querySelector('#app')?.innerText || '').slice(0, 1200),
        appHtml: (document.querySelector('#app')?.innerHTML || '').slice(0, 1800),
        scriptSrcs: Array.from(document.scripts).map(s => s.src).filter(Boolean),
        resources: performance.getEntriesByType('resource').map(r => ({
          name: r.name,
          duration: Math.round(r.duration),
          initiatorType: r.initiatorType
        })).slice(-30)
      }));
    } catch (err) {
      state = { diagnosticEvaluateError: String(err && err.message || err) };
    }
    console.error('SWSI FIRST PAINT DIAGNOSTICS [' + label + '] ' + JSON.stringify({
      browserErrors,
      state
    }, null, 2));
  }

  async function waitHome() {
    try {
      await page.waitForSelector('.swsi-focus-primary', { timeout: 30000 });
    } catch (err) {
      await dumpFirstPaintDiagnostics('home-timeout');
      throw err;
    }
  }

  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await waitHome();

  const guide = page.locator('.swsi-launch-guide');
  assert.strictEqual(await guide.count(), 1, 'first-use guide missing on fresh localStorage');
  const guideText = await guide.innerText();
  assert(/不用先學整個平台/.test(guideText), 'compact first-use guide copy missing');
  assert(/練題/.test(guideText) && /學習/.test(guideText) && /申論/.test(guideText), 'first-use guide does not explain the three primary areas');
  await guide.getByRole('button', { name: /不再顯示首次使用說明/ }).click();
  await page.waitForFunction(() => !document.querySelector('.swsi-launch-guide'));
  assert.strictEqual(await page.evaluate(() => localStorage.getItem('swsi_launch_guide_dismissed_v2')), '1', 'guide dismissal was not persisted');

  await page.reload({ waitUntil: 'commit' });
  await waitHome();
  assert.strictEqual(await page.locator('.swsi-launch-guide').count(), 0, 'dismissed guide returned after reload');

  const visibleTabs = await page.locator('#tabbar button:visible').allInnerTexts();
  const tabText = visibleTabs.join(' ');
  assert(/練題/.test(tabText) && /學習/.test(tabText) && /申論/.test(tabText), 'simplified bottom navigation labels missing');

  // Homepage subtraction: the bottom navigation already owns Learning/Essay,
  // so Home must not repeat them as large cards. Keep only primary practice,
  // two compact high-frequency actions, and one closed advanced-tools disclosure.
  assert.strictEqual(await page.locator('#app .swsi-study-card').count(), 0, 'homepage repeated large study cards returned');
  const quickActions = page.locator('#app .swsi-home-quick button');
  assert.strictEqual(await quickActions.count(), 2, 'homepage compact quick actions missing');
  const quickText = (await quickActions.allInnerTexts()).join(' ');
  assert(/錯題複習/.test(quickText) && /計時模擬考/.test(quickText), 'homepage quick actions are not focused on review + mock exam');

  const moreTools = page.locator('#app details.swsi-other-tools');
  assert.strictEqual(await moreTools.count(), 1, 'homepage advanced-tools disclosure missing');
  assert.strictEqual(await moreTools.getAttribute('open'), null, 'advanced tools should be collapsed by default');
  assert(/更多學習工具/.test(await moreTools.locator('summary').innerText()), 'advanced-tools summary copy missing');
  const hiddenToolText = (await moreTools.locator('button').allTextContents()).join(' ');
  assert(/學習中心/.test(hiddenToolText) && /申論練習/.test(hiddenToolText) && /理論、法規與時事/.test(hiddenToolText), 'collapsed advanced tools lost a study destination');

  const learningTab = page.locator('#t-review');
  await learningTab.click();
  await page.waitForSelector('.swsi-myhub', { timeout: 30000 });
  await page.waitForSelector('.swsi-exam-reminder', { timeout: 10000 });

  const hubText = await page.locator('.swsi-myhub').innerText();
  assert(/學習中心/.test(hubText), 'learning center heading missing');
  assert(/錯題複習/.test(hubText) && /快速刷題/.test(hubText) && /申論練習/.test(hubText), 'learning center primary study actions missing');
  const reminderText = await page.locator('.swsi-exam-reminder').innerText();
  assert(/考試倒數/.test(reminderText), 'exam countdown entry missing');

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

  // Mobile fixed-nav clearance has one owner: .wrap. Footer itself must stay compact.
  const footerLayout = await page.evaluate(() => {
    const footer = document.querySelector('.wrap > footer') || document.querySelector('footer');
    const wrap = document.querySelector('.wrap');
    if (!footer || !wrap) return null;
    return {
      footerPadding: parseFloat(getComputedStyle(footer).paddingBottom || '0'),
      wrapPadding: parseFloat(getComputedStyle(wrap).paddingBottom || '0')
    };
  });
  assert(footerLayout, 'mobile footer layout missing');
  assert(footerLayout.footerPadding <= 40, 'mobile footer regained an oversized blank slab: '+footerLayout.footerPadding+'px');
  assert(footerLayout.wrapPadding >= 70, 'wrap no longer reserves fixed-nav clearance: '+footerLayout.wrapPadding+'px');

  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await page.waitForTimeout(80);
  const footerClearance = await page.evaluate(() => {
    const footer = document.querySelector('.wrap > footer') || document.querySelector('footer');
    const tab = document.querySelector('.tabbar');
    if (!footer || !tab) return null;
    const fr = footer.getBoundingClientRect();
    const tr = tab.getBoundingClientRect();
    return { footerBottom: fr.bottom, tabTop: tr.top };
  });
  assert(footerClearance, 'footer or bottom nav missing after scroll');
  assert(footerClearance.footerBottom <= footerClearance.tabTop + 1,
    'footer is covered by fixed bottom navigation: footerBottom='+footerClearance.footerBottom+' tabTop='+footerClearance.tabTop);
  await page.evaluate(() => window.scrollTo(0, 0));

  const adminLogin = page.locator('[data-swsi-admin-login]');
  if (await adminLogin.count()) {
    const adminLabel = ((await adminLogin.locator('.label').textContent()) || '').trim();
    assert.strictEqual(adminLabel, '管理者入口', 'admin entry is not using the canonical launch-safe label');
    assert.strictEqual(await adminLogin.isVisible(), false, 'admin entry is visible before the secondary More disclosure is opened');
  }

  assert.deepStrictEqual(browserErrors, [], 'browser page errors: ' + browserErrors.join(' | '));
  console.log('LAUNCH READINESS SMOKE OK');
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

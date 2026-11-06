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

  // Public candidate visuals only: no secrets, private user data or hosted writes.
  // Snapshots are generated locally from this PR branch, not from a preview site.
  const visualDir = process.env.SWSI_VISUAL_ARTIFACT_DIR || '';
  async function visual(name) {
    if (!visualDir) return;
    fs.mkdirSync(visualDir, { recursive: true });
    await page.screenshot({ path: path.join(visualDir, name + '.png'), fullPage: true, animations: 'disabled' });
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


  // The visible homepage, not an unused CSS selector, must match the approved
  // mobile concept. This guards against later runtime renderHome overrides.
  const actualHome = await page.evaluate(() => {
    const hero = document.querySelector('#app .swsi-v4-hero');
    const primary = document.querySelector('#app .swsi-v4-start');
    const nav = document.querySelector('#tabbar');
    const wrap = document.querySelector('.wrap');
    return {
      paper: getComputedStyle(document.documentElement).getPropertyValue('--paper').trim().toUpperCase(),
      heroBackground: hero && getComputedStyle(hero).backgroundColor,
      heroTitle: hero && hero.querySelector('h1')?.textContent,
      primaryHeight: primary && primary.getBoundingClientRect().height,
      navMaxWidth: nav && getComputedStyle(nav).maxWidth,
      wrapMaxWidth: wrap && getComputedStyle(wrap).maxWidth,
      tabs: Array.from(nav.querySelectorAll('button')).filter(b => getComputedStyle(b).display !== 'none').map(b => b.getAttribute('aria-label')),
      v4Installed: !!document.getElementById('swsi-calm-navigation-v4')
    };
  });
  // Netlify now shares the reviewed V3 stylesheet with Cloudflare. Check
  // the actual computed color against the primary's V3 source, not an
  // obsolete pre-V3 token. Accessibility tests still check visible contrast.
  const primaryHtml = fs.readFileSync(path.resolve(__dirname, '../cdn/index.html'), 'utf8');
  const v3Style = primaryHtml.match(/<style id="swsi-calm-learning-ui-v3">([\s\S]*?)<\/style>/);
  assert(v3Style, 'reviewed Cloudflare V3 stylesheet missing');
  const v3Paper = v3Style[1].match(/--paper:\s*(#[0-9A-Fa-f]{6})\s*;/);
  assert(v3Paper, 'reviewed Cloudflare V3 paper token missing');
  assert.strictEqual(actualHome.paper, v3Paper[1].toUpperCase(),
    'Netlify V4 paper token differs from reviewed Cloudflare V3');
  assert.strictEqual(actualHome.heroBackground, 'rgb(229, 240, 235)', 'approved pale green CTA hero is not rendered');
  assert(/今天，從一題開始/.test(actualHome.heroTitle || ''), 'live renderHome still uses old copy');
  assert(actualHome.primaryHeight >= 48, 'primary CTA touch height is too small');
  assert.strictEqual(actualHome.wrapMaxWidth, '660px', 'mobile reading width regressed');
  assert(actualHome.v4Installed, 'V4 navigation owner missing');
  assert.deepStrictEqual(actualHome.tabs, ['首頁','刷題','申論','我的'], 'mobile navigation has wrong labels/order');
  await visual('01-home-mobile');

  const pathCards = page.locator('#app .swsi-v4-study-paths button');
  assert.strictEqual(await pathCards.count(), 2, 'historical/essay entry cards missing');
  assert(/歷屆試題/.test(await pathCards.nth(0).innerText()), 'historical past-exam entry missing');
  assert(/申論練習/.test(await pathCards.nth(1).innerText()), 'handwriting-first essay entry missing');
  const toolButtons = page.locator('#app .swsi-v4-tool-grid button');
  assert.strictEqual(await toolButtons.count(), 3, 'three optional learning tools missing');
  const toolText = (await toolButtons.allInnerTexts()).join(' ');
  assert(/模擬考/.test(toolText) && /錯題本/.test(toolText) && /弱點分析/.test(toolText),
    'mock/review/progress tools are not reachable');
  assert.strictEqual(await page.locator('#app .swsi-v4-hero button').count(), 1,
    'hero must have exactly one prominent primary action');
  assert.strictEqual(await page.locator('#app details.swsi-other-tools').count(), 0,
    'old redundant advanced-tools disclosure returned');

  // The simplified CTA must change behavior as well as copy: it starts 10 questions.
  await page.getByRole('button', { name: '開始刷題' }).click();
  await page.waitForSelector('.pcount', { timeout: 30000 });
  assert.strictEqual((await page.locator('.pcount').innerText()).trim(), '1 / 10', '10-question CTA did not start a 10-question queue');
  // Visual regression: disabled submit previously rendered dark green with nearly
  // invisible muted text. It must have the explicit, readable disabled state.
  const disabledSubmit = page.locator('.qcard .btn:disabled');
  assert.strictEqual(await disabledSubmit.count(), 1, 'expected one disabled submit button before selection');
  const disabledStyle = await disabledSubmit.evaluate(el => ({
    bg: getComputedStyle(el).backgroundColor,
    ink: getComputedStyle(el).color,
    opacity: getComputedStyle(el).opacity
  }));
  assert.strictEqual(disabledStyle.bg, 'rgb(229, 236, 231)', 'disabled submit background is not visibly inactive');
  assert.strictEqual(disabledStyle.ink, 'rgb(62, 85, 74)', 'disabled submit label is not readable');
  assert.strictEqual(disabledStyle.opacity, '1', 'disabled submit label is faded by opacity');
  await visual('02-question-mobile');
  await page.getByRole('button', { name: /結束這次練習/ }).click();
  await waitHome();

  const learningTab = page.locator('#t-review');
  await learningTab.click();
  await page.waitForSelector('.swsi-myhub', { timeout: 30000 });
  await page.waitForSelector('.swsi-exam-reminder', { timeout: 10000 });

  const hubText = await page.locator('.swsi-myhub').innerText();
  assert(/學習中心/.test(hubText), 'learning center heading missing');
  assert(/錯題複習/.test(hubText) && /快速刷題/.test(hubText) && /申論練習/.test(hubText), 'learning center primary study actions missing');
  const reminderText = await page.locator('.swsi-exam-reminder').innerText();
  assert(/考試倒數/.test(reminderText), 'exam countdown entry missing');
  await visual('03-learning-mobile');

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

  // Capture remaining navigation and the wide layout from the same clean,
  // synthetic local browser context. No answer is submitted or AI invoked.
  await page.locator('#t-essay').click();
  await page.waitForFunction(() => {
    const app = document.querySelector('#app');
    return app && app.innerText.length > 50 && app.innerText.includes('申論');
  }, null, { timeout: 20000 });
  await visual('04-essay-mobile');
  await page.locator('#t-home').click();
  await waitHome();
  await page.setViewportSize({ width: 1365, height: 900 });
  assert.strictEqual(await page.locator('.wrap').evaluate(el => getComputedStyle(el).maxWidth),
    '790px', 'desktop reading surface unexpectedly narrow');
  const desktopNav = await page.evaluate(() => {
    const nav = document.querySelector('#tabbar');
    const wrap = document.querySelector('.wrap');
    const r = nav.getBoundingClientRect();
    const w = wrap.getBoundingClientRect();
    return {
      layout: getComputedStyle(nav).flexDirection,
      left: r.left,
      right: r.right,
      top: r.top,
      height: r.height,
      computedBottom: getComputedStyle(nav).bottom,
      visibleButtons: Array.from(nav.querySelectorAll('button'))
        .filter(btn => getComputedStyle(btn).display !== 'none').length,
      wrapRight: w.right,
      viewportWidth: innerWidth,
      minButtonHeight: Math.min(...Array.from(nav.querySelectorAll('button'))
        .filter(btn => getComputedStyle(btn).display !== 'none')
        .map(btn => btn.getBoundingClientRect().height))
    };
  });
  await visual('05-home-desktop');
  console.log('SWSI DESKTOP NAV GEOMETRY ' + JSON.stringify(desktopNav));
  assert.strictEqual(desktopNav.layout, 'column', 'wide-screen navigation still uses the mobile bottom bar');
  assert(desktopNav.left >= desktopNav.wrapRight + 8,
    'desktop navigation overlaps the main reading surface: ' + JSON.stringify(desktopNav));
  assert(desktopNav.right <= desktopNav.viewportWidth - 12,
    'desktop navigation clips off the right edge');
  assert(desktopNav.top >= 85, 'desktop navigation overlaps the header');
  assert(desktopNav.height >= 48 * desktopNav.visibleButtons &&
    desktopNav.height <= 65 * desktopNav.visibleButtons + 32,
    'desktop nav still stretches to the bottom of the screen: ' + JSON.stringify(desktopNav));
  assert(desktopNav.minButtonHeight >= 44, 'desktop navigation targets are too small');
  await page.setViewportSize({ width: 1024, height: 800 });
  assert.strictEqual(await page.locator('#tabbar').evaluate(el => getComputedStyle(el).flexDirection),
    'row', 'intermediate viewport should keep the wide mobile navigation bar');

  assert.deepStrictEqual(browserErrors, [], 'browser page errors: ' + browserErrors.join(' | '));
  console.log('LAUNCH READINESS SMOKE OK');
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

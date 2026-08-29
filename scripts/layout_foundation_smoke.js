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

  async function pageDiagnostic() {
    return page.evaluate(() => {
      const app = document.getElementById('app');
      const essayTab = document.getElementById('t-essay');
      const sectionH = app && app.querySelector('.section-h');
      let routerView = 'unavailable';
      try { routerView = typeof view === 'undefined' ? 'undefined' : String(view); } catch (_e) { routerView = 'error'; }
      return {
        dataPage: document.body && document.body.getAttribute('data-swsi-page'),
        bodyClass: document.body && document.body.className,
        routerView,
        essayTabClass: essayTab && essayTab.className,
        essayTabOnclick: essayTab && essayTab.getAttribute('onclick'),
        sectionHeading: sectionH && sectionH.textContent,
        hasHomeHero: !!(app && app.querySelector('.swsi-focus-hero')),
        hasHomePrimary: !!(app && app.querySelector('.swsi-focus-primary')),
        hasQuestionCard: !!(app && app.querySelector('.qcard')),
        hasResultCard: !!(app && app.querySelector('.sumcard')),
        hasEssayWriter: !!(app && app.querySelector('.wta,.wbox')),
        hasLearningHub: !!(app && app.querySelector('.swsi-myhub')),
        hasLearningDetail: !!(app && app.querySelector('.swsi-learning-section,.swsi-progress-hero')),
        appText: ((app && app.textContent) || '').trim().replace(/\s+/g, ' ').slice(0, 400)
      };
    });
  }

  async function waitPage(kind, timeout = 30000) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      const current = await page.evaluate(() => document.body && document.body.getAttribute('data-swsi-page'));
      if (current === kind) return;
      await page.waitForTimeout(100);
    }
    let diagnostic = null;
    try { diagnostic = await pageDiagnostic(); } catch (diagErr) { diagnostic = { diagnostic_error: String(diagErr) }; }
    const message = `LAYOUT WAIT TIMEOUT expected=${kind} snapshot=${JSON.stringify(diagnostic)}`;
    console.error(message);
    throw new Error(message);
  }

  async function shellSnapshot() {
    return page.evaluate(() => {
      const wrap = document.querySelector('.wrap');
      const main = document.querySelector('main');
      const footer = document.querySelector('.wrap > footer') || document.querySelector('footer');
      const tab = document.querySelector('.tabbar');
      const rect = el => el ? el.getBoundingClientRect().toJSON() : null;
      const style = el => el ? getComputedStyle(el) : null;
      const ws = style(wrap), ms = style(main), fs = style(footer), ts = style(tab);
      return {
        page: document.body.getAttribute('data-swsi-page'),
        viewport: { width: innerWidth, height: innerHeight },
        wrap: { rect: rect(wrap), minHeight: ws && ws.minHeight, paddingBottom: ws && parseFloat(ws.paddingBottom || '0') },
        main: { rect: rect(main), flexGrow: ms && ms.flexGrow, flexShrink: ms && ms.flexShrink },
        footer: { rect: rect(footer), display: fs && fs.display, paddingBottom: fs && parseFloat(fs.paddingBottom || '0') },
        tab: { rect: rect(tab), display: ts && ts.display, position: ts && ts.position, bottom: ts && ts.bottom }
      };
    });
  }

  function assertDocked(s, label) {
    assert(s.tab && s.tab.rect, label + ': bottom nav missing');
    assert.strictEqual(s.tab.display, 'flex', label + ': bottom nav is not visible');
    assert.strictEqual(s.tab.position, 'fixed', label + ': bottom nav is not fixed');
    assert(Math.abs(s.tab.rect.bottom - s.viewport.height) <= 2,
      label + ': bottom nav drifted from viewport bottom: ' + JSON.stringify(s.tab.rect));
    assert(s.wrap.paddingBottom >= 80, label + ': shell lost bottom-nav clearance');
  }

  function assertInternal(s, label, options = {}) {
    if (options.focusedQuiz) {
      assert(s.tab && s.tab.rect, label + ': bottom nav element missing');
      assert.strictEqual(s.tab.display, 'none', label + ': focused quiz should hide bottom nav');
    } else {
      assertDocked(s, label);
    }
    assert.strictEqual(s.footer.display, 'none', label + ': internal app page repeated public footer');
    assert(Number(s.main.flexGrow) >= 1, label + ': internal page main no longer owns flexible body space');
  }

  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await page.waitForSelector('.swsi-focus-primary', { timeout: 30000 });
  await waitPage('home');

  let s = await shellSnapshot();
  assertDocked(s, 'home');
  assert.notStrictEqual(s.footer.display, 'none', 'home: public footer should be visible');
  assert(s.footer.paddingBottom <= 40, 'home: footer regained oversized bottom padding');

  // Layer 2 — Learning template: same shell, no repeated public footer.
  await page.locator('#t-review').click();
  await page.waitForSelector('.swsi-myhub', { timeout: 30000 });
  await waitPage('learning');
  s = await shellSnapshot();
  assertInternal(s, 'learning');

  // Layer 2 — Essay library template. Layout classification follows stable nav
  // state/structure, not a particular heading sentence that product copy may change.
  await page.locator('#t-essay').click();
  await waitPage('essay-library');
  assert.strictEqual(await page.locator('.swsi-myhub').count(), 0, 'essay route left Learning Center content mounted');
  s = await shellSnapshot();
  assertInternal(s, 'essay-library');

  // Layer 2 — Quiz template. The active-question contract intentionally hides
  // both the public footer and bottom navigation to reduce accidental exits while
  // answering. Navigation must return on the result/home templates afterwards.
  await page.locator('#t-home').click();
  await page.waitForSelector('.swsi-focus-primary', { timeout: 30000 });
  await page.getByRole('button', { name: /直接開始 20 題/ }).click();
  await page.waitForSelector('.qcard', { timeout: 45000 });
  await waitPage('quiz', 10000);
  s = await shellSnapshot();
  assertInternal(s, 'quiz', { focusedQuiz: true });
  assert(await page.evaluate(() => document.body.classList.contains('swsi-question-active')),
    'quiz: compatibility active-question marker missing');

  // Result is a distinct page template even when content is short. Use the same
  // DOM marker as the real result renderer so this assertion does not require
  // answering all 20 questions just to test shell ownership.
  await page.evaluate(() => {
    document.getElementById('app').innerHTML = '<section class="sumcard"><div class="big">20 / 20</div><button>再來一輪</button></section>';
  });
  await waitPage('result', 10000);
  s = await shellSnapshot();
  assertInternal(s, 'result');

  // Return through the real router and prove the public entry shell is restored.
  await page.evaluate(() => { if (typeof go !== 'function') throw new Error('go() missing'); go('home'); });
  await page.waitForSelector('.swsi-focus-primary', { timeout: 30000 });
  await waitPage('home');
  s = await shellSnapshot();
  assertDocked(s, 'home-return');
  assert.notStrictEqual(s.footer.display, 'none', 'home-return: public footer did not restore');

  assert.deepStrictEqual(browserErrors, [], 'browser page errors: ' + browserErrors.join(' | '));
  console.log('LAYOUT FOUNDATION SMOKE OK');
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});
#!/usr/bin/env node
'use strict';
// Live, read-only browser acceptance for the existing Cloudflare soft launch.
// Never login, use public AI or feedback. Local answer/grading interactions
// use only an ephemeral browser profile; all network writes stay blocked.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium, webkit } = require('playwright');
const ORIGIN = 'https://wandering-wave-4418.c022050333.workers.dev';

// PR checks exercise the CURRENT hosted site. On main/workflow_dispatch, additionally
// require the deployed CSS to equal the reviewed CDN source. This prevents old live UI
// from earning a misleading green check while Cloudflare is still deploying.
const sourceHtml = fs.readFileSync(path.resolve(__dirname, '../cdn/index.html'), 'utf8');
const cssMatches = [...sourceHtml.matchAll(/<style id="swsi-calm-student-design-v2">([\s\S]*?)<\/style>/g)];
assert(cssMatches.length <= 1, 'duplicate reviewed calm design CSS in CDN source');
const expectedCalmCss = cssMatches.length ? cssMatches[0][1] : null;
const requireCalmParity = process.env.GITHUB_EVENT_NAME !== 'pull_request' && expectedCalmCss !== null;

async function awaitReviewedDesign(page, label) {
  if (!requireCalmParity) {
    console.log('LIVE DESIGN PARITY DEFERRED ' + label + ': source has no calm CSS or this is an unmerged PR');
    return;
  }
  const deadline = Date.now() + 4 * 60 * 1000;
  let attempts = 0;
  let last = 'style not seen';
  while (Date.now() < deadline) {
    const deployed = await page.evaluate(() => {
      const style = document.getElementById('swsi-calm-student-design-v2');
      return {
        css: style ? style.textContent : null,
        paper: getComputedStyle(document.body).backgroundColor,
        pine: getComputedStyle(document.documentElement).getPropertyValue('--pine-deep').trim()
      };
    });
    if (deployed.css === expectedCalmCss) {
      assert.equal(deployed.paper, 'rgb(244, 247, 245)', label + ': new body background not applied');
      assert.equal(deployed.pine.toUpperCase(), '#1F544B', label + ': new CTA palette not applied');
      console.log('LIVE REVIEWED DESIGN PARITY OK ' + label + ' refreshes=' + attempts);
      return;
    }
    last = deployed.css === null ? 'new design marker absent' : 'live CSS differs from reviewed CDN source';
    attempts++;
    await page.waitForTimeout(7000);
    const next = await page.goto(ORIGIN + '/?swsi_ui_acceptance=' +
      encodeURIComponent(process.env.GITHUB_RUN_ID || 'manual') + '-' + attempts, {
      waitUntil: 'domcontentloaded', timeout: 25000
    });
    assert(next && next.status() === 200, label + ': live site unavailable while awaiting deployment');
  }
  throw new Error(label + ': deployment never matched the reviewed visual source within 4 minutes: ' + last);
}

// The source's latest ten exam IDs and official text are immutable inputs for
// this smoke. Browser rendering and guides must come from the LIVE Cloudflare
// host, not from local mocks or a bare static SHA check.
const latestExam = JSON.parse(fs.readFileSync(
  path.resolve(__dirname, '../cdn/auto/essays_auto.json'), 'utf8'
));
const latestIds = latestExam.map(row => String(row.id));
// Canonical 240-guide asset is a strict release contract. The runtime may
// additionally expose compatibility aliases, which are not extra official
// exam questions and must not make all 240 reviewed guides look absent.
const guideAsset = fs.readFileSync(
  path.resolve(__dirname, '../cdn/essay_guides.js'), 'utf8'
);
const guidePayload = guideAsset.match(/window\.ESSAY_GUIDES\s*=\s*(\{[\s\S]*?\})\s*;\s*$/);
assert(guidePayload, 'tracked 240-guide JSON asset missing');
const canonicalGuideIds = Object.keys(JSON.parse(guidePayload[1]));
assert.equal(canonicalGuideIds.length, 240, 'tracked canonical guide count drift');
assert.equal(latestIds.length, 10, 'expected ten latest exam essays');
assert.equal(new Set(latestIds).size, 10, 'duplicate latest essay IDs');
function normalized(s) { return String(s || '').replace(/\s/g, ''); }

async function verifyHostedLatestEssayGuides(page, label) {
  await page.waitForFunction(ids => {
    let rows = [];
    try {
      if (typeof ESSAYS !== 'undefined' && Array.isArray(ESSAYS)) rows = ESSAYS;
      else if (Array.isArray(window.ESSAYS)) rows = window.ESSAYS;
    } catch (_e) {
      rows = Array.isArray(window.ESSAYS) ? window.ESSAYS : [];
    }
    const present = new Set(rows.map(e => e && String(e.id)));
    const guides = window.ESSAY_GUIDES || {};
    return ids.every(id => present.has(id) && guides[id]);
  }, latestIds, { timeout: 45000 });

  const coverage = await page.evaluate(ids => {
    const runtime = window.ESSAY_GUIDES || {};
    return {
      total: Object.keys(runtime).length,
      missing: ids.filter(id => !runtime[id]),
      aliases: Object.keys(runtime).filter(id => !ids.includes(id))
    };
  }, canonicalGuideIds);
  assert.deepEqual(coverage.missing, [],
    label + ': live student runtime missing canonical guides');
  console.log('HOSTED GUIDE COVERAGE ' + label + ': canonical=240/' +
    canonicalGuideIds.length + ', runtime_keys=' + coverage.total +
    ', compatibility_keys=' + coverage.aliases.length);

  for (const [index, expected] of latestExam.entries()) {
    const id = String(expected.id);
    await page.evaluate(essayId => {
      if (typeof toggleEssay !== 'function') throw Error('essay detail route unavailable');
      toggleEssay(essayId); // existing actual student detail rendering
    }, id);
    const question = await page.locator('#app .ebody').first().textContent();
    assert.equal(normalized(question), normalized(expected.q),
      label + ': latest official essay question text drift ' + id);
    assert.equal(await page.locator('#ta_' + id).count(), 1,
      label + ': missing actual student writing editor for ' + id);

    if (index === 0) {
      // Exercise the student-facing editor and guide button in an isolated
      // ephemeral browser profile. Only localStorage changes; all POST/PUT/
      // PATCH/DELETE requests remain blocked at the context network layer.
      const draft = '一、社會工作應先辨認服務需求與當事人處境。\n二、整合社會支持、尊重自主，並定期檢視服務成效。';
      await page.locator('#ta_' + id).fill(draft);
      assert.equal(await page.evaluate(essayId =>
        localStorage.getItem('essay_draft_' + essayId), id), draft,
        label + ': input must auto-save only to isolated localStorage');
      assert(await page.locator('#gbtn_' + id).isVisible(),
        label + ': answer-first guide button must appear after writing');
      await page.locator('#gbtn_' + id).click();
      assert.equal(await page.locator('#app .guide .gsec').count(), 4,
        label + ': guide must display four student-facing sections');

      await page.reload({ waitUntil: 'domcontentloaded', timeout: 25000 });
      await page.waitForSelector('#app .swsi-focus-primary', { timeout: 45000 });
      await page.locator('#t-essay').click();
      await page.waitForFunction(essayId => {
        let rows = [];
        try { rows = typeof ESSAYS !== 'undefined' && Array.isArray(ESSAYS)
          ? ESSAYS : (window.ESSAYS || []); } catch (_) { rows = window.ESSAYS || []; }
        return rows.some(row => row && row.id === essayId);
      }, id, { timeout: 45000 });
      await page.evaluate(essayId => toggleEssay(essayId), id);
      assert.equal(await page.locator('#ta_' + id).inputValue(), draft,
        label + ': answer must survive a real page reload');
      assert(await page.locator('#gbtn_' + id).isVisible(),
        label + ': saved answer should expose its guide after reload');
      // The test leaves no fake student answer, even inside its throwaway profile.
      await page.evaluate(essayId => localStorage.removeItem('essay_draft_' + essayId), id);
    }

    // All ten new essays must genuinely render their own guide in the
    // hosted browser, not merely exist in the downloaded JS object.
    await page.evaluate(essayId => showGuide(essayId), id);
    const rendered = page.locator('#app .guide');
    await rendered.waitFor({ timeout: 8000 });
    const guide = await page.evaluate(essayId =>
      (window.ESSAY_GUIDES || {})[essayId], id);
    assert(guide && guide.kao && guide.dati,
      label + ': missing source-reviewed learning guidance for ' + id);
    const visibleText = await rendered.innerText();
    assert(visibleText.includes(guide.kao) && visibleText.includes(guide.dati),
      label + ': guide visible text does not match runtime content for ' + id);
    assert.equal(await page.locator('#app .guide .gsec').count(), 4,
      label + ': guide lacks one of four sections for ' + id);
    await page.evaluate(() => closeEssay());
  }
  console.log('CLOUDFLARE HOSTED LATEST ESSAYS OK ' + label +
    ': 10/10 real question views, 10/10 guides, local draft survives reload, zero AI submissions');
}

// Exercise the *hosted* grading UI without writing any student/server data.
// The Playwright context is fresh, isolated, and destroyed after this run;
// its network route rejects all non-GET/HEAD/OPTIONS requests.
async function verifyHostedLocalGrading(page, label) {
  await page.evaluate(async () => {
    if (typeof ensureAllQuestionsLoaded !== 'function')
      throw Error('official question loader not available');
    await ensureAllQuestionsLoaded();
  });
  const baseline = await page.evaluate(() => {
    if (typeof loadHist !== 'function') throw Error('history helper not found');
    return loadHist().length;
  });

  // Actual regular practice: option -> submit -> local-only recorded attempt
  // -> answer explanation. Do not complete any real user work on their device.
  const homeStart = page.locator('#app button[onclick="startFocusedQuiz()"]');
  if (!(await homeStart.isVisible())) {
    await page.locator('#app .gcard[onclick="toggleHomeQuiz()"]').click();
  }
  await page.locator('#app select[onchange="setHomeQuizCount(this.value)"]').selectOption('10');
  await homeStart.click();
  await page.waitForSelector('.pcount', { timeout: 25000 });
  assert.equal((await page.locator('.pcount').innerText()).trim(), '1 / 10',
    label + ': practice start');
  let practiceIndex = -1;
  for (let i = 0; i < 10; i++) {
    if (await page.locator('#app .opt').count() > 0) {
      practiceIndex = i;
      break;
    }
    await page.evaluate(() => next());
  }
  assert(practiceIndex >= 0, label + ': practice lacked an answerable item');
  await page.locator('#app .opt').first().click();
  await page.getByRole('button', { name: '送出答案' }).click();
  await page.waitForSelector('#app .exp', { timeout: 12000 });
  const afterPractice = await page.evaluate(() => ({
    history: loadHist(),
    reviewCount: document.querySelectorAll('#app .exp').length,
    answered: typeof answered !== 'undefined' ? answered : null
  }));
  assert.equal(afterPractice.history.length, baseline + 1,
    label + ': practice answer must save exactly one local attempt');
  assert.equal(afterPractice.answered, true,
    label + ': practice answer must enter explanation state');
  assert.equal(afterPractice.reviewCount, 1, label + ': missing explanation');
  await page.getByRole('button', { name: /結束這次練習/ }).click();
  await page.waitForSelector('#app .swsi-focus-primary', { timeout: 16000 });

  // Actual 20-question timed-mock engine: select one answer, leave others
  // unanswered, explicitly confirm partial submission, view 0/1 out of 20.
  await page.evaluate(() => MK.open());
  await page.waitForSelector('.mk-ov .mk-toggle', { timeout: 12000 });
  await page.evaluate(() => { MK.toggleTimed(); MK.begin(20); });
  assert.match(await page.locator('.mk-ov .mk-prog').innerText(), /第 1 \/ 20 題/,
    label + ': mock paper did not start with 20 questions');
  let answerable = -1;
  for (let i = 0; i < 20; i++) {
    if (await page.locator('.mk-ov .mk-opt').count() > 0) {
      answerable = i;
      break;
    }
    await page.evaluate(() => MK.go(1));
  }
  assert(answerable >= 0, label + ': mock paper lacked an answerable item');
  await page.locator('.mk-ov .mk-opt').first().click();
  assert.equal(await page.locator('.mk-ov .mk-opt.sel').count(), 1,
    label + ': mock answer not selected');
  // There must be a confirm dialog when a student attempts to hand in
  // an incomplete paper. Accept it; all scoring is purely in the browser.
  let confirmed = false;
  page.once('dialog', dialog => {
    confirmed = /未作答|交卷/.test(dialog.message());
    return dialog.accept();
  });
  await page.locator('.mk-ov .mk-top button', { hasText: '交卷' }).click();
  await page.waitForSelector('.mk-ov .mk-score .big', { timeout: 12000 });
  assert(confirmed, label + ': partial mock submission skipped confirmation');
  const score = (await page.locator('.mk-ov .mk-score .big').innerText()).trim();
  assert(/^[01] \/ 20$/.test(score),
    label + ': mock score should count exactly one answer of twenty, got ' + score);
  assert.match(await page.locator('.mk-ov .mk-score .pct').innerText(),
    /作答 1 題/, label + ': mock answered count');
  const afterMock = await page.evaluate(() => loadHist().length);
  assert.equal(afterMock, baseline + 2,
    label + ': mock exam must store only the single answered attempt');
  await page.evaluate(() => MK.close());
  await page.waitForSelector('.mk-ov', { state: 'detached', timeout: 8000 });
  console.log('CLOUDFLARE HOSTED LOCAL GRADING OK ' + label +
    ': practice answer/review, 20-question mock partial-submit/score, local attempts=2, network writes blocked');
}

async function check(engine, label, width, height, practice) {
  const browser = await engine.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width, height },
    serviceWorkers: 'block', // byte parity / PWA are tested by separate gates
    reducedMotion: 'reduce'
  });
  const page = await context.newPage();
  const pageErrors = [];
  let blockedWrites = 0;
  page.on('pageerror', error => pageErrors.push(String(error.message || error)));
  // Prevent any telemetry, feedback, AI or other production mutation.
  await page.route('**/*', route => {
    const method = route.request().method().toUpperCase();
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
      blockedWrites++;
      return route.abort();
    }
    return route.continue();
  });
  try {
    const response = await page.goto(ORIGIN + '/', { waitUntil: 'domcontentloaded', timeout: 25000 });
    assert.equal(response && response.status(), 200, label + ': home HTTP status');
    assert.equal(new URL(page.url()).origin, ORIGIN, label + ': wrong origin');
    await awaitReviewedDesign(page, label);
    await page.waitForSelector('#app .swsi-focus-primary', { timeout: 45000 });
    // The app initializes nav visibility after first paint; assert usable buttons, not merely DOM presence.
    await page.waitForFunction(() => [...document.querySelectorAll('#tabbar button')].filter(el => {
      const style = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' &&
        Number(style.opacity) !== 0 && rect.width > 0 && rect.height > 0;
    }).length >= 3, null, { timeout: 15000 });

    const state = await page.evaluate(() => ({
      title: document.title,
      robots: document.querySelector('meta[name="robots"]')?.content || '',
      softLaunch: document.documentElement.outerHTML.includes('SWSI CLOUDFLARE PUBLIC SOFT LAUNCH'),
      focus: document.documentElement.outerHTML.includes('目前 3 個國考重點'),
      obsolete: document.documentElement.outerHTML.includes('命題趨勢雷達'),
      runtimeTag: Array.from(document.querySelectorAll('script[src]'))
        .some(e => /^monthly_patch\.js\?v=[0-9a-f]{16}$/.test(e.getAttribute('src') || '')),
      appTextLength: (document.querySelector('#app')?.innerText || '').trim().length,
      overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth
    }));
    assert.match(state.title, /社工師國考免費題庫/, label + ': title');
    assert(state.robots.includes('noindex'), label + ': soft-launch SEO hold unexpectedly removed');
    assert(state.softLaunch && state.focus && !state.obsolete && state.runtimeTag, label + ': release/UI markers ' + JSON.stringify(state));
    assert(state.appTextLength > 100, label + ': blank homepage');
    assert(state.overflow <= 3, label + ': horizontal overflow ' + state.overflow);

    const nav = page.locator('#tabbar button:visible');
    assert((await nav.count()) >= 3, label + ': missing bottom navigation');
    if (width < 600) for (let i = 0; i < await nav.count(); i++) {
      const box = await nav.nth(i).boundingBox();
      assert(box && box.width >= 40 && box.height >= 40, label + ': tiny navigation target ' + i);
    }

    // Public-info modal and real navigation clicks; no external writes.
    assert.equal(await page.evaluate(() => typeof window.swsiOpenPublicInfo), 'function', label + ': info opener');
    await page.evaluate(() => window.swsiOpenPublicInfo('about'));
    await page.waitForSelector('.swsi-public-info-dialog', { timeout: 8000 });
    await page.keyboard.press('Escape');
    await page.waitForSelector('#swsi-public-info-backdrop', { state: 'detached', timeout: 8000 });

    await page.locator('#t-review').click();
    await page.waitForSelector('.swsi-myhub', { timeout: 25000 });
    assert.match(await page.locator('.swsi-myhub').innerText(), /學習中心/, label + ': learning route');

    await page.locator('#t-essay').click();
    await page.waitForFunction(() => {
      const text = document.querySelector('#app')?.innerText || '';
      return /申論/.test(text) && text.length > 50;
    }, null, { timeout: 18000 });

    if (practice) await verifyHostedLatestEssayGuides(page, label);

    await page.locator('#t-home').click();
    await page.waitForSelector('#app .swsi-focus-primary', { timeout: 15000 });

    if (practice) {
      await verifyHostedLocalGrading(page, label);
    }

    assert.deepEqual(pageErrors, [], label + ': uncaught page errors');
    console.log('CLOUDFLARE LIVE BROWSER OK ' + label + ' blockedWrites=' + blockedWrites);
  } finally {
    await context.close();
    await browser.close();
  }
}
(async () => {
  await check(chromium, 'chromium-phone', 390, 844, true);
  await check(chromium, 'chromium-desktop', 1365, 900, false);
  await check(webkit, 'webkit-iphone', 390, 844, false);
  console.log('CLOUDFLARE LIVE BROWSER ACCEPTANCE OK: read-only mobile, desktop, iPhone');
})().catch(error => {
  console.error('CLOUDFLARE LIVE BROWSER ACCEPTANCE FAILED: ' + String(error.stack || error));
  process.exit(1);
});

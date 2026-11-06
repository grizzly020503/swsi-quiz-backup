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
const designId = sourceHtml.includes('<style id="swsi-calm-learning-ui-v3">') ? 'swsi-calm-learning-ui-v3' : 'swsi-calm-student-design-v2';
const cssMatches = [...sourceHtml.matchAll(new RegExp('<style id="' + designId + '">([\\s\\S]*?)</style>', 'g'))];
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
    const deployed = await page.evaluate(id => {
      const style = document.getElementById(id);
      return {
        css: style ? style.textContent : null,
        paper: getComputedStyle(document.body).backgroundColor,
        pine: getComputedStyle(document.documentElement).getPropertyValue('--pine-deep').trim()
      };
    }, designId);
    if (deployed.css === expectedCalmCss) {
      assert.equal(deployed.paper, designId.endsWith('v3') ? 'rgb(247, 249, 247)' : 'rgb(244, 247, 245)', label + ': new body background not applied');
      assert.equal(deployed.pine.toUpperCase(), designId.endsWith('v3') ? '#204F48' : '#1F544B', label + ': new CTA palette not applied');
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
// Validate the *actual hosted* 4,800 MCQ runtime rows against the pinned
// 120 official MOEX PDF identities. URL parameter order is insignificant;
// a wrong exam code, PDF c/s identifier, path, missing metadata or duplicate
// ID is NOT. This tests what the student receives after shard loading.
const moexRegistry = JSON.parse(fs.readFileSync(
  path.resolve(__dirname, '../data/moex_source_subjects.v1.json'), 'utf8'
));
assert.equal(moexRegistry.scope, 'source_identity_only_not_stem_answer_or_rubric_approval',
  'pinned registry scope changed unexpectedly');
assert.equal(moexRegistry.records.length, 120, 'official registry must contain 120 papers');
const moexExpected = moexRegistry.records.map(r => ({
  session: r.session, subject: r.subject, code: r.exam_code,
  c: String(r.c), s: String(r.s)
}));

async function verifyHostedOfficialSourceIdentity(page, label) {
  const result = await page.evaluate(expected => {
    const rows = (typeof ALL !== 'undefined' && Array.isArray(ALL)) ? ALL : [];
    const byPaper = new Map(expected.map(p => [p.session + '|' + p.subject, p]));
    const seenIds = new Set();
    const paperCounts = new Map();
    const problems = [];
    for (const row of rows) {
      const id = String(row?.id || '');
      if (!id || seenIds.has(id)) {
        problems.push({ id, reason: 'missing_or_duplicate_id' }); continue;
      }
      seenIds.add(id);
      const rd = row.round === '第一次' ? '1' : row.round === '第二次' ? '2' : '?';
      const paper = String(row.year) + '-' + rd + '|' + row.subject;
      const expectedPaper = byPaper.get(paper);
      paperCounts.set(paper, (paperCounts.get(paper) || 0) + 1);
      if (!expectedPaper) {
        problems.push({ id, reason: 'no_pinned_official_paper' }); continue;
      }
      if (String(row.source_exam_code || '') !== expectedPaper.code ||
          /時事|預測|自製/.test(String(row.qtype || '') + ' ' + id)) {
        problems.push({ id, reason: 'student_origin_identity_drift' }); continue;
      }
      try {
        const url = new URL(String(row.source_url || ''));
        const search = url.searchParams;
        if (url.origin !== 'https://wwwq.moex.gov.tw' ||
            url.pathname !== '/exam/wHandExamQandA_File.ashx' ||
            search.get('code') !== expectedPaper.code ||
            search.get('c') !== expectedPaper.c ||
            search.get('s') !== expectedPaper.s ||
            search.get('t') !== 'Q' || search.get('q') !== '1') {
          problems.push({ id, reason: 'wrong_official_pdf_identity' });
        }
      } catch (_e) {
        problems.push({ id, reason: 'unparseable_source_url' });
      }
    }
    for (const [paper, count] of paperCounts) {
      if (count !== 40) problems.push({ paper, count, reason: 'paper_not_40_mcqs' });
    }
    for (const item of expected) {
      const paper = item.session + '|' + item.subject;
      if (!paperCounts.has(paper)) problems.push({ paper, reason: 'missing_paper' });
    }
    return {
      total: rows.length,
      papers: paperCounts.size,
      uniqueIds: seenIds.size,
      problemCount: problems.length,
      firstProblems: problems.slice(0, 12)
    };
  }, moexExpected);
  assert.deepEqual(result, { total: 4800, papers: 120, uniqueIds: 4800,
    problemCount: 0, firstProblems: [] },
  label + ': hosted official-source misclassification/drift ' + JSON.stringify(result));
  console.log('CLOUDFLARE HOSTED OFFICIAL SOURCE TRUST OK ' + label +
    ': 4800 official MCQs, 120/120 pinned papers, no invalid PDF identities');
}

async function verifyHostedLocalGrading(page, label) {
  await page.evaluate(async () => {
    if (typeof ensureAllQuestionsLoaded !== 'function')
      throw Error('official question loader not available');
    await ensureAllQuestionsLoaded();
  });
  await verifyHostedOfficialSourceIdentity(page, label);
  const baseline = await page.evaluate(() => {
    if (typeof loadHist !== 'function') throw Error('history helper not found');
    return loadHist().length;
  });

  // Actual regular practice: option -> submit -> local-only recorded attempt
  // -> answer explanation. Do not complete any real user work on their device.
  // The primary homepage entry was already tested in the previous live
  // acceptance job. Use the shipped practice engine to isolate its grading
  // and persistence behavior from optional homepage/UI entry variations.
  await page.evaluate(() => startQuiz(() => true, 10));
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
  // The student-visible post-answer trust panel must call the question
  // "考選部歷屆試題", never "平台自製"; interpretation and source labels
  // must distinguish official question/answer from SWSI's explanation.
  await page.waitForSelector('#app .swsi-answer-trust summary', { timeout: 12000 });
  const trustBadge = await page.locator('#app .swsi-answer-trust summary').innerText();
  assert(trustBadge.includes('考選部歷屆試題') && !trustBadge.includes('平台自製'),
    label + ': student-facing official question mislabeled ' + trustBadge);
  await page.locator('#app .swsi-answer-trust summary').click();
  const bodyText = await page.locator('#app .swsi-answer-trust .swsi-trust-body').innerText();
  assert(bodyText.includes('本題為考選部歷屆試題') &&
    bodyText.includes('不是考選部官方解析'),
    label + ': official source/independent explanation distinction missing');
  const link = await page.locator('#app .swsi-answer-trust .swsi-trust-links a')
    .filter({ hasText: '開啟官方題目來源' }).first().getAttribute('href');
  assert(link && /^https:\/\/wwwq\.moex\.gov\.tw\/exam\/wHandExamQandA_File\.ashx\?/.test(link),
    label + ': student official-source PDF link missing or wrong host');
  console.log('CLOUDFLARE HOSTED OFFICIAL SOURCE BADGE OK ' + label +
    ': official paper, SWSI explanation distinction, MOEX PDF link');

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
  // The shipped mock engine excludes source-held or unloaded-figure items
  // from scoring. A random 20-question paper may therefore have only 19 (or
  // fewer) eligible questions. Verify the score denominator *exactly* agrees
  // with the explicit exclusion notice; never treat an omitted item as wrong
  // or silently accept arbitrary totals.
  const notices = await page.locator('.mk-ov [role="status"]').allInnerTexts();
  const exclusionNotices = notices.filter(x => /題原圖未載入，已排除計分/.test(x));
  assert(exclusionNotices.length <= 1,
    label + ': multiple contradictory mock exclusion notices: ' + notices.join(' | '));
  const excluded = exclusionNotices.length
    ? Number((exclusionNotices[0].match(/(\\d+)\\s*題原圖未載入，已排除計分/) || [])[1])
    : 0;
  assert(Number.isInteger(excluded) && excluded >= 0 && excluded < 20,
    label + ': invalid explicitly reported excluded questions: ' + notices.join(' | '));
  const expectedScore = new RegExp('^[01] \\/ ' + (20 - excluded) + '
  // The deployed monthly_patch Unified Grading Contract deliberately
  // records unanswered ordinary questions as wrong for spaced repetition.
  // Unanswered all_credit questions are the one explicit exception.
  // That is separate from the UI's actual answered count of one.
  const mockHistory = await page.evaluate(offset => loadHist().slice(offset),
    afterPractice.history.length);
  assert(mockHistory.length >= 1 && mockHistory.length <= 20,
    label + ': wrong number of scored mock history entries');
  assert(mockHistory.every(row => row && typeof row.id === 'string' &&
    typeof row.correct === 'boolean'),
    label + ': mock entries missing official IDs or score booleans');
  assert.equal(new Set(mockHistory.map(row => row.id)).size, mockHistory.length,
    label + ': duplicate mock question history entries on a single submission');
  await page.evaluate(() => MK.close());
  await page.waitForSelector('.mk-ov', { state: 'detached', timeout: 8000 });
  console.log('CLOUDFLARE HOSTED LOCAL GRADING OK ' + label +
    ': practice answer/review, 20-question mock partial-submit/score, actual_answers=1, mock_history_rows=' +
    mockHistory.length + ', all network writes blocked');
}

// The *hosted* Cloudflare runtime must quarantine the five confirmed
// malformed official imports, not only pass a local candidate smoke. This
// never POSTs, writes student records, or marks a PDF source as approved.
async function verifyHostedSourceHoldQuarantine(page, label) {
  // Before this PR merges, production still correctly holds all five.
  // Once deployed, only the three still-unapproved 104-1 sources may be held.
  const oldIds = ['DS-104-1-22', 'DS-104-1-27', 'DS-104-1-29',
    'R-107-2-40', 'SP111-2-34'];
  const releasedIds = ['R-107-2-40', 'SP111-2-34'];
  const threeIds = oldIds.slice(0, 3);
  const ids = await page.evaluate(() => Array.from(SWSI_SOURCE_HOLD_IDS));
  assert.deepEqual(ids.length === 5 ? ids : ids.length === 3 ? ids : [],
    ids.length === 5 ? oldIds : threeIds,
    label + ': deployed hold list is neither guarded pre-release nor approved post-release');
  const result = await page.evaluate(heldIds => {
    if (typeof swsiSourceHeld !== 'function' ||
        typeof swsiOfficialFigureReady !== 'function') {
      throw Error('deployed source-hold policy missing');
    }
    if (typeof ALL === 'undefined' || !Array.isArray(ALL) || ALL.length !== 4800) {
      throw Error('deployed official corpus not loaded');
    }
    return heldIds.map(id => {
      const item = ALL.find(q => q && q.id === id);
      if (!item) throw Error('held official question absent: ' + id);
      const unchangedRow = JSON.stringify(item);
      const beforeHistory = loadHist().length;
      const beforeStorage = JSON.stringify(localStorage);
      view = 'quiz'; queue = [item]; idx = 0; selected = null; answered = false;
      sessionStats = { done: 0, correct: 0, wrongTopics: [] };
      renderQuiz();
      const app = document.getElementById('app');
      const initial = app.querySelector('[data-source-hold="' + id + '"]');
      const excluded = !!initial &&
        initial.textContent.includes('本題暫停作答') &&
        initial.textContent.includes('不計分') &&
        app.querySelectorAll('.opt').length === 0 &&
        !app.innerText.includes(item.q) &&
        swsiSourceHeld(item) && !swsiOfficialFigureReady(item);
      // Try a stale, scripted answer and the already-answered cache path.
      // Neither may bypass quarantine or mutate local scoring/history.
      selected = 'B'; submit();
      const blocked = !answered && sessionStats.done === 0 &&
        sessionStats.correct === 0 && loadHist().length === beforeHistory;
      answered = true; renderQuiz();
      const hiddenAfterAnswer = !!app.querySelector('[data-source-hold="' + id + '"]') &&
        app.querySelectorAll('.opt, .exp').length === 0 &&
        !app.innerText.includes(item.q);
      return { id, excluded, blocked, hiddenAfterAnswer,
        dataUnchanged: JSON.stringify(item) === unchangedRow,
        storageUnchanged: JSON.stringify(localStorage) === beforeStorage };
    });
  }, ids);
  assert.equal(result.length, ids.length, label + ': source-hold case count');
  for (const item of result) {
    assert(item.excluded && item.blocked && item.hiddenAfterAnswer &&
      item.dataUnchanged && item.storageUnchanged,
    label + ': live source-hold quiz leak ' + JSON.stringify(item));
  }

  if (ids.length === 3) {
    const released = await page.evaluate(() => {
      const research = ALL.find(x => x.id === 'R-107-2-40');
      const policy = ALL.find(x => x.id === 'SP111-2-34');
      if (!research || !policy) throw Error('approved source rows absent');
      return {
        unheld: !swsiSourceHeld(research) && !swsiSourceHeld(policy),
        researchAnswer: research.answer,
        policyAnswer: policy.answer,
        researchD: research.options.D,
        policyOptions: [policy.options.A, policy.options.B,
          policy.options.C, policy.options.D]
      };
    });
    assert(released.unheld && released.researchAnswer === 'D' &&
      released.policyAnswer === 'C' &&
      released.researchD === '兩個變項間有高度相關，則非常可能有因果關係' &&
      JSON.stringify(released.policyOptions) ===
        JSON.stringify(['1 至 3 個月', '2 至 4 個月', '3 至 6 個月', '4 至 6 個月']),
      label + ': released two official options differ from original MOEX PDFs: ' +
        JSON.stringify(released));
  }

  // One real hosted mock exam through the shipped UI. Unlike local fixture
  // tests, the row comes from Cloudflare's actual loaded 4,800-question feed.
  const before = await page.evaluate(() => JSON.stringify(localStorage));
  await page.evaluate(async () => {
    const item = ALL.find(q => q && q.id === 'DS-104-1-22');
    if (!item) throw Error('hosted mock source-hold item absent');
    ALL = [item];
    SUBJECTS = [item.subject];
    window.SWSI_QB.allComplete = true;
    await MK.open();
    MK.setMode('exam');
    MK.setPaper(item.year + '|' + item.round);
    MK.beginExam();
  });
  assert.equal(await page.locator('.mk-ov .mk-opt').count(), 0,
    label + ': held official item exposed mock options');
  assert((await page.locator('.mk-ov').innerText()).includes('待官方原卷覆核'),
    label + ': held mock question lacks explanation of temporary exclusion');
  await page.evaluate(() => { MK.pick('B'); MK.submit(); });
  const score = (await page.locator('.mk-ov .mk-score .big').innerText()).trim();
  assert.equal(score, '0 / 0',
    label + ': held source question must not alter mock score');
  assert((await page.locator('.mk-ov').innerText()).includes('已排除計分'),
    label + ': held source question not explicitly excluded from scoring');
  assert.equal(await page.evaluate(() => JSON.stringify(localStorage)), before,
    label + ': held mock leaked into student records');
  await page.evaluate(() => MK.close());
  console.log('CLOUDFLARE HOSTED SOURCE HOLDS OK ' + label +
    ': ' + ids.length + ' official IDs hidden before/after stale grading, one hosted mock excluded 0/0');
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

    // Guard the actual deployed V4 DOM against a late renderHome override.
    // CSS/artifact byte parity alone did not catch the previous homepage regression.
    await page.waitForSelector('#app .swsi-v4-hero .swsi-v4-start', { timeout: 15000 });
    const homeV4 = await page.evaluate(() => {
      const hero = document.querySelector('#app .swsi-v4-hero');
      const paths = [...document.querySelectorAll('#app .swsi-v4-study-paths > .swsi-v4-path')]
        .map(el => el.querySelector('.swsi-v4-path-title')?.textContent?.trim() || '');
      const tools = [...document.querySelectorAll('#app .swsi-v4-tool-grid > button')]
        .map(el => el.querySelector('span:last-child')?.textContent?.trim() || '');
      const nav = [...document.querySelectorAll('#tabbar button')].filter(el => {
        const style = getComputedStyle(el);
        const box = el.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' &&
          Number(style.opacity) !== 0 && box.width > 0 && box.height > 0;
      }).map(el => el.getAttribute('aria-label') || el.textContent.trim());
      return {
        heroCount: document.querySelectorAll('#app .swsi-v4-hero').length,
        headline: hero?.querySelector('h1')?.textContent?.trim() || '',
        heroColor: hero ? getComputedStyle(hero).backgroundColor : '',
        paths, tools, nav
      };
    });
    assert.equal(homeV4.heroCount, 1, label + ': missing/duplicate V4 primary hero');
    assert.equal(homeV4.headline, '今天，從一題開始。', label + ': old homepage renderer active');
    assert.equal(homeV4.heroColor, 'rgb(229, 240, 235)', label + ': approved pale-green hero missing');
    assert.deepEqual(homeV4.paths, ['歷屆試題', '申論練習'], label + ': V4 study paths');
    assert.equal(homeV4.tools.length, 3, label + ': V4 study tools count');
    assert(homeV4.tools[0] === '模擬考' &&
      homeV4.tools[1].startsWith('錯題本') &&
      homeV4.tools[2] === '弱點分析', label + ': V4 tool labels/order ' + JSON.stringify(homeV4.tools));
    assert.deepEqual(homeV4.nav, ['首頁', '刷題', '申論', '我的'],
      label + ': active four-tab V4 navigation ' + JSON.stringify(homeV4.nav));
    console.log('CLOUDFLARE LIVE V4 HOME OK ' + label +
      ': one hero, two paths, three tools, four visible navigation tabs');

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
      await verifyHostedSourceHoldQuarantine(page, label);
    }

    assert.deepEqual(pageErrors, [], label + ': uncaught page errors');
    console.log('CLOUDFLARE LIVE BROWSER OK ' + label + ' blockedWrites=' + blockedWrites);
  } finally {
    await context.close();
    await browser.close();
  }
}
// A separate real Cloudflare browser profile tests the PWA path that the
// normal UI/byte parity smoke intentionally disables (serviceWorkers: block).
// All answers and drafts remain on the disposable local browser profile.
// No network writes to production (analytics, AI, feedback) are permitted.
async function verifyHostedPwaOffline() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    serviceWorkers: 'allow',
    reducedMotion: 'reduce'
  });
  let blockedWrites = 0;
  await context.route('**/*', route => {
    const method = route.request().method().toUpperCase();
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
      blockedWrites++;
      return route.abort();
    }
    return route.continue();
  });
  const page = await context.newPage();
  try {
    const live = await page.goto(ORIGIN + '/', { waitUntil: 'load', timeout: 30000 });
    assert.equal(live && live.status(), 200, 'PWA online warm-up HTTP');
    await page.waitForSelector('#app .swsi-focus-primary', { timeout: 45000 });
    const registration = await page.evaluate(async () => {
      if (!('serviceWorker' in navigator)) throw Error('PWA Service Worker unsupported');
      const reg = await Promise.race([
        navigator.serviceWorker.ready,
        new Promise((_, reject) => setTimeout(() => reject(Error('PWA worker ready timeout')), 30000))
      ]);
      return { scope: reg.scope };
    });
    assert(registration.scope.startsWith(ORIGIN + '/'),
      'PWA worker does not control hosted origin');
    await page.waitForFunction(() => !!navigator.serviceWorker.controller,
      null, { timeout: 20000 });

    try {
      await page.evaluate(() => ensureAllQuestionsLoaded());
    } catch (error) {
      // This occasionally fails only on the first, real hosted PWA warm-up.
      // Log a bounded, read-only integrity snapshot to distinguish a short
      // network/cache race from leaked/duplicated official rows. Never retry
      // or silently downgrade the full-corpus fail-closed gate here.
      let details;
      try {
        details = await page.evaluate(() => {
          const qb = window.SWSI_QB || {};
          const rows = typeof ALL !== 'undefined' && Array.isArray(ALL) ? ALL : [];
          const owners = qb.questionOwners instanceof Map ? qb.questionOwners : new Map();
          const seen = new Set(), duplicates = [], missingOwnerIds = [];
          let blankIds = 0;
          for (const row of rows) {
            const id = row && typeof row.id === 'string' ? row.id.trim() : '';
            if (!id) { blankIds++; continue; }
            if (seen.has(id) && duplicates.length < 8) duplicates.push(id);
            seen.add(id);
            if (!owners.has(id) && missingOwnerIds.length < 8) missingOwnerIds.push(id);
          }
          return {
            manifestRevision: qb.manifest?.dataset_revision || null,
            expectedTotal: qb.manifest?.total_questions ?? null,
            expectedShards: qb.manifest?.shards?.length ?? null,
            actualRows: rows.length,
            uniqueIds: seen.size,
            blankIds,
            ownerCount: owners.size,
            loadedFiles: qb.loadedFiles instanceof Set ? [...qb.loadedFiles].sort() : [],
            loadingFiles: qb.loading instanceof Map ? [...qb.loading.keys()].sort() : [],
            duplicateIds: duplicates,
            missingOwnerIds,
            usingOffline: qb.usingOffline,
            manifestSource: qb.manifestSource,
            integrityError: String(qb.error?.message || '')
          };
        });
      } catch (diagnosticError) {
        details = { diagnosticError: String(diagnosticError?.message || diagnosticError) };
      }
      console.error('CLOUDFLARE PWA FULL-CORPUS FAILURE DIAGNOSTIC ' + JSON.stringify(details));
      throw error;
    }
    await page.waitForFunction(async () => {
      try { const record = await loadOfflineQuestions();
        return record?.rows?.length === 4800; } catch (_e) { return false; }
    }, null, { timeout: 45000 });
    const warm = await page.evaluate(async () => ({
      online: navigator.onLine,
      all: typeof ALL !== 'undefined' && Array.isArray(ALL) ? ALL.length : -1,
      cached: (await loadOfflineQuestions()).rows.length,
      cacheNames: await caches.keys(),
      controlled: !!navigator.serviceWorker.controller
    }));
    assert.equal(warm.online, true, 'PWA warmup online flag wrong');
    assert.equal(warm.all, 4800, 'PWA warmup question count');
    assert.equal(warm.cached, 4800, 'PWA IndexedDB did not persist all questions');
    assert(warm.controlled && warm.cacheNames.includes('swsi-shell-v7'),
      'PWA cache/SW missing after warm-up');

    const draftId = latestIds[0];
    const draft = '一、先完成需求評估；二、尊重案主自決；三、追蹤服務結果。';
    await page.locator('#t-essay').click();
    await page.waitForFunction(id => {
      try { return Array.isArray(ESSAYS) && ESSAYS.some(x => x?.id === id); }
      catch (_) { return Array.isArray(window.ESSAYS) && window.ESSAYS.some(x => x?.id === id); }
    }, draftId, { timeout: 30000 });
    await page.evaluate(id => toggleEssay(id), draftId);
    await page.locator('#ta_' + draftId).fill(draft);
    assert.equal(await page.evaluate(id => localStorage.getItem('essay_draft_' + id), draftId),
      draft, 'PWA source draft not saved before disconnection');

    await context.setOffline(true);
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector('#app .swsi-focus-primary', { timeout: 45000 });
    const offline = await page.evaluate(async id => {
      const data = await loadOfflineQuestions();
      return { online: navigator.onLine, cached: data.rows.length,
        controlled: !!navigator.serviceWorker.controller,
        draft: localStorage.getItem('essay_draft_' + id) };
    }, draftId);
    assert.equal(offline.online, false, 'browser did not actually disconnect');
    assert.equal(offline.cached, 4800, 'offline IndexedDB no longer has 4800 questions');
    assert.equal(offline.draft, draft, 'offline reload lost handwritten-text draft');
    assert(offline.controlled, 'offline app lost Service Worker control');
    await page.evaluate(() => ensureAllQuestionsLoaded());
    const offlineCount = await page.evaluate(() =>
      typeof ALL !== 'undefined' && Array.isArray(ALL) ? ALL.length : -1);
    assert.equal(offlineCount, 4800, 'offline reload could not load all questions');

    // A cached PWA must apply the same fail-closed source quarantine as the
    // online site. Use only the browser's already-persisted offline question
    // rows, with no official corpus write or AI/network request.
    const offlineHoldResult = await page.evaluate(() => {
      const heldIds = ['DS-104-1-22', 'DS-104-1-27', 'DS-104-1-29'];
      const releasedIds = ['R-107-2-40', 'SP111-2-34'];
      if (typeof swsiSourceHeld !== 'function' || ALL.length !== 4800)
        throw Error('offline source quarantine/corpus missing');
      const beforeStorage = JSON.stringify(localStorage);
      const beforeHistory = loadHist().length;
      const cases = [];
      const releasedCases = [];
      for (const id of heldIds) {
        const item = ALL.find(q => q.id === id);
        if (!item) throw Error('offline source-held question absent: ' + id);
        const beforeRow = JSON.stringify(item);
        view = 'quiz'; queue = [item]; idx = 0; selected = null;
        answered = false;
        sessionStats = { done: 0, correct: 0, wrongTopics: [] };
        renderQuiz();
        const app = document.getElementById('app');
        const notice = app.querySelector('[data-source-hold="' + id + '"]');
        const hidden = swsiSourceHeld(item) && !!notice &&
          notice.textContent.includes('暫停作答') &&
          app.querySelectorAll('.opt, .exp').length === 0 &&
          !app.innerText.includes(item.q);
        selected = 'B'; submit();
        const blocked = !answered && sessionStats.done === 0 &&
          sessionStats.correct === 0 && loadHist().length === beforeHistory;
        answered = true; renderQuiz();
        const afterStaleAnswer = !!app.querySelector('[data-source-hold="' + id + '"]') &&
          app.querySelectorAll('.opt, .exp').length === 0 &&
          !app.innerText.includes(item.q);
        cases.push({ id, hidden, blocked, afterStaleAnswer,
          originalUnchanged: JSON.stringify(item) === beforeRow });
      }
      // Owner-approved #542 source fixes must be answerable offline. Do not
      // submit them or modify progress; verify rendered options and exact rows.
      for (const id of releasedIds) {
        const item = ALL.find(q => q.id === id);
        if (!item) throw Error('offline approved question absent: ' + id);
        const beforeRow = JSON.stringify(item);
        view = 'quiz'; queue = [item]; idx = 0; selected = null;
        answered = false;
        sessionStats = { done: 0, correct: 0, wrongTopics: [] };
        renderQuiz();
        const app = document.getElementById('app');
        const answerable = !swsiSourceHeld(item) &&
          !app.querySelector('[data-source-hold="' + id + '"]') &&
          app.querySelectorAll('.opt').length === 4 &&
          app.innerText.includes(item.q);
        releasedCases.push({ id, answerable,
          originalUnchanged: JSON.stringify(item) === beforeRow });
      }
      view = 'home'; queue = []; selected = null; answered = false;
      render();
      return { online: navigator.onLine, cases, releasedCases,
        storageUnchanged: JSON.stringify(localStorage) === beforeStorage,
        historyUnchanged: loadHist().length === beforeHistory };
    });
    assert.equal(offlineHoldResult.online, false, 'offline hold test accidentally online');
    assert.equal(offlineHoldResult.cases.length, 3, 'offline held-source case count');
    assert(offlineHoldResult.cases.every(c => c.hidden && c.blocked &&
      c.afterStaleAnswer && c.originalUnchanged),
      'offline PWA leaked an unapproved held question: ' + JSON.stringify(offlineHoldResult.cases));
    assert.equal(offlineHoldResult.releasedCases.length, 2, 'offline approved-source case count');
    assert(offlineHoldResult.releasedCases.every(c => c.answerable && c.originalUnchanged),
      'offline PWA still blocked an owner-approved source repair: ' +
      JSON.stringify(offlineHoldResult.releasedCases));
    assert(offlineHoldResult.storageUnchanged && offlineHoldResult.historyUnchanged,
      'offline source check mutated student progress or attempt history');
    console.log('CLOUDFLARE HOSTED PWA OFFLINE SOURCE HOLDS OK: ' +
      '3/3 unapproved held stems blocked; 2/2 owner-approved questions answerable; zero history writes');

    await page.locator('#t-essay').click();
    await page.waitForFunction(id => {
      try { return Array.isArray(ESSAYS) && ESSAYS.some(x => x?.id === id); }
      catch (_) { return Array.isArray(window.ESSAYS) && window.ESSAYS.some(x => x?.id === id); }
    }, draftId, { timeout: 18000 });
    await page.evaluate(id => toggleEssay(id), draftId);
    assert.equal(await page.locator('#ta_' + draftId).inputValue(), draft,
      'offline student editor did not restore draft');
    await page.evaluate(() => startQuiz(() => true, 10));
    await page.waitForSelector('#app .pcount', { timeout: 16000 });
    assert.equal((await page.locator('#app .pcount').innerText()).trim(), '1 / 10',
      'offline practice failed to start');

    await context.setOffline(false);
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForSelector('#app .swsi-focus-primary', { timeout: 45000 });
    assert.equal(await page.evaluate(id =>
      localStorage.getItem('essay_draft_' + id), draftId), draft,
      'online restoration overwrote saved draft');
    await page.evaluate(id => localStorage.removeItem('essay_draft_' + id), draftId);
    console.log('CLOUDFLARE HOSTED PWA OFFLINE OK: SW v7 active, 4800/4800 IDB, offline reload, offline practice, essay draft persistence, online recovery, blockedWrites=' + blockedWrites);
  } finally {
    await context.close();
    await browser.close();
  }
}

(async () => {
  await check(chromium, 'chromium-phone', 390, 844, true);
  await check(chromium, 'chromium-desktop', 1365, 900, false);
  await check(webkit, 'webkit-iphone', 390, 844, false);
  await verifyHostedPwaOffline();
  console.log('CLOUDFLARE LIVE BROWSER ACCEPTANCE OK: read-only mobile, desktop, iPhone');
})().catch(error => {
  console.error('CLOUDFLARE LIVE BROWSER ACCEPTANCE FAILED: ' + String(error.stack || error));
  process.exit(1);
});
);
  assert(expectedScore.test(score),
    label + ': mock score must count exactly one answer over the ' +
    (20 - excluded) + ' eligible questions (20 minus ' + excluded +
    ' visibly excluded), got ' + score);
  assert.match(await page.locator('.mk-ov .mk-score .pct').innerText(),
    /作答 1 題/, label + ': mock answered count');
  // The deployed monthly_patch Unified Grading Contract deliberately
  // records unanswered ordinary questions as wrong for spaced repetition.
  // Unanswered all_credit questions are the one explicit exception.
  // That is separate from the UI's actual answered count of one.
  const mockHistory = await page.evaluate(offset => loadHist().slice(offset),
    afterPractice.history.length);
  assert(mockHistory.length >= 1 && mockHistory.length <= 20,
    label + ': wrong number of scored mock history entries');
  assert(mockHistory.every(row => row && typeof row.id === 'string' &&
    typeof row.correct === 'boolean'),
    label + ': mock entries missing official IDs or score booleans');
  assert.equal(new Set(mockHistory.map(row => row.id)).size, mockHistory.length,
    label + ': duplicate mock question history entries on a single submission');
  await page.evaluate(() => MK.close());
  await page.waitForSelector('.mk-ov', { state: 'detached', timeout: 8000 });
  console.log('CLOUDFLARE HOSTED LOCAL GRADING OK ' + label +
    ': practice answer/review, 20-question mock partial-submit/score, actual_answers=1, mock_history_rows=' +
    mockHistory.length + ', all network writes blocked');
}

// The *hosted* Cloudflare runtime must quarantine the five confirmed
// malformed official imports, not only pass a local candidate smoke. This
// never POSTs, writes student records, or marks a PDF source as approved.
async function verifyHostedSourceHoldQuarantine(page, label) {
  // Before this PR merges, production still correctly holds all five.
  // Once deployed, only the three still-unapproved 104-1 sources may be held.
  const oldIds = ['DS-104-1-22', 'DS-104-1-27', 'DS-104-1-29',
    'R-107-2-40', 'SP111-2-34'];
  const releasedIds = ['R-107-2-40', 'SP111-2-34'];
  const threeIds = oldIds.slice(0, 3);
  const ids = await page.evaluate(() => Array.from(SWSI_SOURCE_HOLD_IDS));
  assert.deepEqual(ids.length === 5 ? ids : ids.length === 3 ? ids : [],
    ids.length === 5 ? oldIds : threeIds,
    label + ': deployed hold list is neither guarded pre-release nor approved post-release');
  const result = await page.evaluate(heldIds => {
    if (typeof swsiSourceHeld !== 'function' ||
        typeof swsiOfficialFigureReady !== 'function') {
      throw Error('deployed source-hold policy missing');
    }
    if (typeof ALL === 'undefined' || !Array.isArray(ALL) || ALL.length !== 4800) {
      throw Error('deployed official corpus not loaded');
    }
    return heldIds.map(id => {
      const item = ALL.find(q => q && q.id === id);
      if (!item) throw Error('held official question absent: ' + id);
      const unchangedRow = JSON.stringify(item);
      const beforeHistory = loadHist().length;
      const beforeStorage = JSON.stringify(localStorage);
      view = 'quiz'; queue = [item]; idx = 0; selected = null; answered = false;
      sessionStats = { done: 0, correct: 0, wrongTopics: [] };
      renderQuiz();
      const app = document.getElementById('app');
      const initial = app.querySelector('[data-source-hold="' + id + '"]');
      const excluded = !!initial &&
        initial.textContent.includes('本題暫停作答') &&
        initial.textContent.includes('不計分') &&
        app.querySelectorAll('.opt').length === 0 &&
        !app.innerText.includes(item.q) &&
        swsiSourceHeld(item) && !swsiOfficialFigureReady(item);
      // Try a stale, scripted answer and the already-answered cache path.
      // Neither may bypass quarantine or mutate local scoring/history.
      selected = 'B'; submit();
      const blocked = !answered && sessionStats.done === 0 &&
        sessionStats.correct === 0 && loadHist().length === beforeHistory;
      answered = true; renderQuiz();
      const hiddenAfterAnswer = !!app.querySelector('[data-source-hold="' + id + '"]') &&
        app.querySelectorAll('.opt, .exp').length === 0 &&
        !app.innerText.includes(item.q);
      return { id, excluded, blocked, hiddenAfterAnswer,
        dataUnchanged: JSON.stringify(item) === unchangedRow,
        storageUnchanged: JSON.stringify(localStorage) === beforeStorage };
    });
  }, ids);
  assert.equal(result.length, ids.length, label + ': source-hold case count');
  for (const item of result) {
    assert(item.excluded && item.blocked && item.hiddenAfterAnswer &&
      item.dataUnchanged && item.storageUnchanged,
    label + ': live source-hold quiz leak ' + JSON.stringify(item));
  }

  if (ids.length === 3) {
    const released = await page.evaluate(() => {
      const research = ALL.find(x => x.id === 'R-107-2-40');
      const policy = ALL.find(x => x.id === 'SP111-2-34');
      if (!research || !policy) throw Error('approved source rows absent');
      return {
        unheld: !swsiSourceHeld(research) && !swsiSourceHeld(policy),
        researchAnswer: research.answer,
        policyAnswer: policy.answer,
        researchD: research.options.D,
        policyOptions: [policy.options.A, policy.options.B,
          policy.options.C, policy.options.D]
      };
    });
    assert(released.unheld && released.researchAnswer === 'D' &&
      released.policyAnswer === 'C' &&
      released.researchD === '兩個變項間有高度相關，則非常可能有因果關係' &&
      JSON.stringify(released.policyOptions) ===
        JSON.stringify(['1 至 3 個月', '2 至 4 個月', '3 至 6 個月', '4 至 6 個月']),
      label + ': released two official options differ from original MOEX PDFs: ' +
        JSON.stringify(released));
  }

  // One real hosted mock exam through the shipped UI. Unlike local fixture
  // tests, the row comes from Cloudflare's actual loaded 4,800-question feed.
  const before = await page.evaluate(() => JSON.stringify(localStorage));
  await page.evaluate(async () => {
    const item = ALL.find(q => q && q.id === 'DS-104-1-22');
    if (!item) throw Error('hosted mock source-hold item absent');
    ALL = [item];
    SUBJECTS = [item.subject];
    window.SWSI_QB.allComplete = true;
    await MK.open();
    MK.setMode('exam');
    MK.setPaper(item.year + '|' + item.round);
    MK.beginExam();
  });
  assert.equal(await page.locator('.mk-ov .mk-opt').count(), 0,
    label + ': held official item exposed mock options');
  assert((await page.locator('.mk-ov').innerText()).includes('待官方原卷覆核'),
    label + ': held mock question lacks explanation of temporary exclusion');
  await page.evaluate(() => { MK.pick('B'); MK.submit(); });
  const score = (await page.locator('.mk-ov .mk-score .big').innerText()).trim();
  assert.equal(score, '0 / 0',
    label + ': held source question must not alter mock score');
  assert((await page.locator('.mk-ov').innerText()).includes('已排除計分'),
    label + ': held source question not explicitly excluded from scoring');
  assert.equal(await page.evaluate(() => JSON.stringify(localStorage)), before,
    label + ': held mock leaked into student records');
  await page.evaluate(() => MK.close());
  console.log('CLOUDFLARE HOSTED SOURCE HOLDS OK ' + label +
    ': ' + ids.length + ' official IDs hidden before/after stale grading, one hosted mock excluded 0/0');
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

    // Guard the actual deployed V4 DOM against a late renderHome override.
    // CSS/artifact byte parity alone did not catch the previous homepage regression.
    await page.waitForSelector('#app .swsi-v4-hero .swsi-v4-start', { timeout: 15000 });
    const homeV4 = await page.evaluate(() => {
      const hero = document.querySelector('#app .swsi-v4-hero');
      const paths = [...document.querySelectorAll('#app .swsi-v4-study-paths > .swsi-v4-path')]
        .map(el => el.querySelector('.swsi-v4-path-title')?.textContent?.trim() || '');
      const tools = [...document.querySelectorAll('#app .swsi-v4-tool-grid > button')]
        .map(el => el.querySelector('span:last-child')?.textContent?.trim() || '');
      const nav = [...document.querySelectorAll('#tabbar button')].filter(el => {
        const style = getComputedStyle(el);
        const box = el.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' &&
          Number(style.opacity) !== 0 && box.width > 0 && box.height > 0;
      }).map(el => el.getAttribute('aria-label') || el.textContent.trim());
      return {
        heroCount: document.querySelectorAll('#app .swsi-v4-hero').length,
        headline: hero?.querySelector('h1')?.textContent?.trim() || '',
        heroColor: hero ? getComputedStyle(hero).backgroundColor : '',
        paths, tools, nav
      };
    });
    assert.equal(homeV4.heroCount, 1, label + ': missing/duplicate V4 primary hero');
    assert.equal(homeV4.headline, '今天，從一題開始。', label + ': old homepage renderer active');
    assert.equal(homeV4.heroColor, 'rgb(229, 240, 235)', label + ': approved pale-green hero missing');
    assert.deepEqual(homeV4.paths, ['歷屆試題', '申論練習'], label + ': V4 study paths');
    assert.equal(homeV4.tools.length, 3, label + ': V4 study tools count');
    assert(homeV4.tools[0] === '模擬考' &&
      homeV4.tools[1].startsWith('錯題本') &&
      homeV4.tools[2] === '弱點分析', label + ': V4 tool labels/order ' + JSON.stringify(homeV4.tools));
    assert.deepEqual(homeV4.nav, ['首頁', '刷題', '申論', '我的'],
      label + ': active four-tab V4 navigation ' + JSON.stringify(homeV4.nav));
    console.log('CLOUDFLARE LIVE V4 HOME OK ' + label +
      ': one hero, two paths, three tools, four visible navigation tabs');

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
      await verifyHostedSourceHoldQuarantine(page, label);
    }

    assert.deepEqual(pageErrors, [], label + ': uncaught page errors');
    console.log('CLOUDFLARE LIVE BROWSER OK ' + label + ' blockedWrites=' + blockedWrites);
  } finally {
    await context.close();
    await browser.close();
  }
}
// A separate real Cloudflare browser profile tests the PWA path that the
// normal UI/byte parity smoke intentionally disables (serviceWorkers: block).
// All answers and drafts remain on the disposable local browser profile.
// No network writes to production (analytics, AI, feedback) are permitted.
async function verifyHostedPwaOffline() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    serviceWorkers: 'allow',
    reducedMotion: 'reduce'
  });
  let blockedWrites = 0;
  await context.route('**/*', route => {
    const method = route.request().method().toUpperCase();
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
      blockedWrites++;
      return route.abort();
    }
    return route.continue();
  });
  const page = await context.newPage();
  try {
    const live = await page.goto(ORIGIN + '/', { waitUntil: 'load', timeout: 30000 });
    assert.equal(live && live.status(), 200, 'PWA online warm-up HTTP');
    await page.waitForSelector('#app .swsi-focus-primary', { timeout: 45000 });
    const registration = await page.evaluate(async () => {
      if (!('serviceWorker' in navigator)) throw Error('PWA Service Worker unsupported');
      const reg = await Promise.race([
        navigator.serviceWorker.ready,
        new Promise((_, reject) => setTimeout(() => reject(Error('PWA worker ready timeout')), 30000))
      ]);
      return { scope: reg.scope };
    });
    assert(registration.scope.startsWith(ORIGIN + '/'),
      'PWA worker does not control hosted origin');
    await page.waitForFunction(() => !!navigator.serviceWorker.controller,
      null, { timeout: 20000 });

    try {
      await page.evaluate(() => ensureAllQuestionsLoaded());
    } catch (error) {
      // This occasionally fails only on the first, real hosted PWA warm-up.
      // Log a bounded, read-only integrity snapshot to distinguish a short
      // network/cache race from leaked/duplicated official rows. Never retry
      // or silently downgrade the full-corpus fail-closed gate here.
      let details;
      try {
        details = await page.evaluate(() => {
          const qb = window.SWSI_QB || {};
          const rows = typeof ALL !== 'undefined' && Array.isArray(ALL) ? ALL : [];
          const owners = qb.questionOwners instanceof Map ? qb.questionOwners : new Map();
          const seen = new Set(), duplicates = [], missingOwnerIds = [];
          let blankIds = 0;
          for (const row of rows) {
            const id = row && typeof row.id === 'string' ? row.id.trim() : '';
            if (!id) { blankIds++; continue; }
            if (seen.has(id) && duplicates.length < 8) duplicates.push(id);
            seen.add(id);
            if (!owners.has(id) && missingOwnerIds.length < 8) missingOwnerIds.push(id);
          }
          return {
            manifestRevision: qb.manifest?.dataset_revision || null,
            expectedTotal: qb.manifest?.total_questions ?? null,
            expectedShards: qb.manifest?.shards?.length ?? null,
            actualRows: rows.length,
            uniqueIds: seen.size,
            blankIds,
            ownerCount: owners.size,
            loadedFiles: qb.loadedFiles instanceof Set ? [...qb.loadedFiles].sort() : [],
            loadingFiles: qb.loading instanceof Map ? [...qb.loading.keys()].sort() : [],
            duplicateIds: duplicates,
            missingOwnerIds,
            usingOffline: qb.usingOffline,
            manifestSource: qb.manifestSource,
            integrityError: String(qb.error?.message || '')
          };
        });
      } catch (diagnosticError) {
        details = { diagnosticError: String(diagnosticError?.message || diagnosticError) };
      }
      console.error('CLOUDFLARE PWA FULL-CORPUS FAILURE DIAGNOSTIC ' + JSON.stringify(details));
      throw error;
    }
    await page.waitForFunction(async () => {
      try { const record = await loadOfflineQuestions();
        return record?.rows?.length === 4800; } catch (_e) { return false; }
    }, null, { timeout: 45000 });
    const warm = await page.evaluate(async () => ({
      online: navigator.onLine,
      all: typeof ALL !== 'undefined' && Array.isArray(ALL) ? ALL.length : -1,
      cached: (await loadOfflineQuestions()).rows.length,
      cacheNames: await caches.keys(),
      controlled: !!navigator.serviceWorker.controller
    }));
    assert.equal(warm.online, true, 'PWA warmup online flag wrong');
    assert.equal(warm.all, 4800, 'PWA warmup question count');
    assert.equal(warm.cached, 4800, 'PWA IndexedDB did not persist all questions');
    assert(warm.controlled && warm.cacheNames.includes('swsi-shell-v7'),
      'PWA cache/SW missing after warm-up');

    const draftId = latestIds[0];
    const draft = '一、先完成需求評估；二、尊重案主自決；三、追蹤服務結果。';
    await page.locator('#t-essay').click();
    await page.waitForFunction(id => {
      try { return Array.isArray(ESSAYS) && ESSAYS.some(x => x?.id === id); }
      catch (_) { return Array.isArray(window.ESSAYS) && window.ESSAYS.some(x => x?.id === id); }
    }, draftId, { timeout: 30000 });
    await page.evaluate(id => toggleEssay(id), draftId);
    await page.locator('#ta_' + draftId).fill(draft);
    assert.equal(await page.evaluate(id => localStorage.getItem('essay_draft_' + id), draftId),
      draft, 'PWA source draft not saved before disconnection');

    await context.setOffline(true);
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector('#app .swsi-focus-primary', { timeout: 45000 });
    const offline = await page.evaluate(async id => {
      const data = await loadOfflineQuestions();
      return { online: navigator.onLine, cached: data.rows.length,
        controlled: !!navigator.serviceWorker.controller,
        draft: localStorage.getItem('essay_draft_' + id) };
    }, draftId);
    assert.equal(offline.online, false, 'browser did not actually disconnect');
    assert.equal(offline.cached, 4800, 'offline IndexedDB no longer has 4800 questions');
    assert.equal(offline.draft, draft, 'offline reload lost handwritten-text draft');
    assert(offline.controlled, 'offline app lost Service Worker control');
    await page.evaluate(() => ensureAllQuestionsLoaded());
    const offlineCount = await page.evaluate(() =>
      typeof ALL !== 'undefined' && Array.isArray(ALL) ? ALL.length : -1);
    assert.equal(offlineCount, 4800, 'offline reload could not load all questions');

    // A cached PWA must apply the same fail-closed source quarantine as the
    // online site. Use only the browser's already-persisted offline question
    // rows, with no official corpus write or AI/network request.
    const offlineHoldResult = await page.evaluate(() => {
      const heldIds = ['DS-104-1-22', 'DS-104-1-27', 'DS-104-1-29'];
      const releasedIds = ['R-107-2-40', 'SP111-2-34'];
      if (typeof swsiSourceHeld !== 'function' || ALL.length !== 4800)
        throw Error('offline source quarantine/corpus missing');
      const beforeStorage = JSON.stringify(localStorage);
      const beforeHistory = loadHist().length;
      const cases = [];
      const releasedCases = [];
      for (const id of heldIds) {
        const item = ALL.find(q => q.id === id);
        if (!item) throw Error('offline source-held question absent: ' + id);
        const beforeRow = JSON.stringify(item);
        view = 'quiz'; queue = [item]; idx = 0; selected = null;
        answered = false;
        sessionStats = { done: 0, correct: 0, wrongTopics: [] };
        renderQuiz();
        const app = document.getElementById('app');
        const notice = app.querySelector('[data-source-hold="' + id + '"]');
        const hidden = swsiSourceHeld(item) && !!notice &&
          notice.textContent.includes('暫停作答') &&
          app.querySelectorAll('.opt, .exp').length === 0 &&
          !app.innerText.includes(item.q);
        selected = 'B'; submit();
        const blocked = !answered && sessionStats.done === 0 &&
          sessionStats.correct === 0 && loadHist().length === beforeHistory;
        answered = true; renderQuiz();
        const afterStaleAnswer = !!app.querySelector('[data-source-hold="' + id + '"]') &&
          app.querySelectorAll('.opt, .exp').length === 0 &&
          !app.innerText.includes(item.q);
        cases.push({ id, hidden, blocked, afterStaleAnswer,
          originalUnchanged: JSON.stringify(item) === beforeRow });
      }
      // Owner-approved #542 source fixes must be answerable offline. Do not
      // submit them or modify progress; verify rendered options and exact rows.
      for (const id of releasedIds) {
        const item = ALL.find(q => q.id === id);
        if (!item) throw Error('offline approved question absent: ' + id);
        const beforeRow = JSON.stringify(item);
        view = 'quiz'; queue = [item]; idx = 0; selected = null;
        answered = false;
        sessionStats = { done: 0, correct: 0, wrongTopics: [] };
        renderQuiz();
        const app = document.getElementById('app');
        const answerable = !swsiSourceHeld(item) &&
          !app.querySelector('[data-source-hold="' + id + '"]') &&
          app.querySelectorAll('.opt').length === 4 &&
          app.innerText.includes(item.q);
        releasedCases.push({ id, answerable,
          originalUnchanged: JSON.stringify(item) === beforeRow });
      }
      view = 'home'; queue = []; selected = null; answered = false;
      render();
      return { online: navigator.onLine, cases, releasedCases,
        storageUnchanged: JSON.stringify(localStorage) === beforeStorage,
        historyUnchanged: loadHist().length === beforeHistory };
    });
    assert.equal(offlineHoldResult.online, false, 'offline hold test accidentally online');
    assert.equal(offlineHoldResult.cases.length, 3, 'offline held-source case count');
    assert(offlineHoldResult.cases.every(c => c.hidden && c.blocked &&
      c.afterStaleAnswer && c.originalUnchanged),
      'offline PWA leaked an unapproved held question: ' + JSON.stringify(offlineHoldResult.cases));
    assert.equal(offlineHoldResult.releasedCases.length, 2, 'offline approved-source case count');
    assert(offlineHoldResult.releasedCases.every(c => c.answerable && c.originalUnchanged),
      'offline PWA still blocked an owner-approved source repair: ' +
      JSON.stringify(offlineHoldResult.releasedCases));
    assert(offlineHoldResult.storageUnchanged && offlineHoldResult.historyUnchanged,
      'offline source check mutated student progress or attempt history');
    console.log('CLOUDFLARE HOSTED PWA OFFLINE SOURCE HOLDS OK: ' +
      '3/3 unapproved held stems blocked; 2/2 owner-approved questions answerable; zero history writes');

    await page.locator('#t-essay').click();
    await page.waitForFunction(id => {
      try { return Array.isArray(ESSAYS) && ESSAYS.some(x => x?.id === id); }
      catch (_) { return Array.isArray(window.ESSAYS) && window.ESSAYS.some(x => x?.id === id); }
    }, draftId, { timeout: 18000 });
    await page.evaluate(id => toggleEssay(id), draftId);
    assert.equal(await page.locator('#ta_' + draftId).inputValue(), draft,
      'offline student editor did not restore draft');
    await page.evaluate(() => startQuiz(() => true, 10));
    await page.waitForSelector('#app .pcount', { timeout: 16000 });
    assert.equal((await page.locator('#app .pcount').innerText()).trim(), '1 / 10',
      'offline practice failed to start');

    await context.setOffline(false);
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForSelector('#app .swsi-focus-primary', { timeout: 45000 });
    assert.equal(await page.evaluate(id =>
      localStorage.getItem('essay_draft_' + id), draftId), draft,
      'online restoration overwrote saved draft');
    await page.evaluate(id => localStorage.removeItem('essay_draft_' + id), draftId);
    console.log('CLOUDFLARE HOSTED PWA OFFLINE OK: SW v7 active, 4800/4800 IDB, offline reload, offline practice, essay draft persistence, online recovery, blockedWrites=' + blockedWrites);
  } finally {
    await context.close();
    await browser.close();
  }
}

(async () => {
  await check(chromium, 'chromium-phone', 390, 844, true);
  await check(chromium, 'chromium-desktop', 1365, 900, false);
  await check(webkit, 'webkit-iphone', 390, 844, false);
  await verifyHostedPwaOffline();
  console.log('CLOUDFLARE LIVE BROWSER ACCEPTANCE OK: read-only mobile, desktop, iPhone');
})().catch(error => {
  console.error('CLOUDFLARE LIVE BROWSER ACCEPTANCE FAILED: ' + String(error.stack || error));
  process.exit(1);
});

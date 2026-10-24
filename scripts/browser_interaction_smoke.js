const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { chromium, webkit } = require('playwright');

const base = process.argv[2] || 'http://127.0.0.1:4173';
const engine = process.argv[3] || 'chromium';
assert(['chromium', 'webkit'].includes(engine), 'unsupported browser engine');
const QUESTION_CDN_HOST = 'wandering-wave-4418.c022050333.workers.dev';
const QUESTION_CDN_PREFIX = '/question-shards/';
const LOCAL_SHARD_DIR = path.resolve(process.cwd(), 'cdn/question-shards');

(async () => {
  const browser = await ({ chromium, webkit })[engine].launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const browserErrors = [];
  const consoleLines = [];
  const failedRequests = [];
  const servedQuestionFiles = [];
  // WebKit performs cross-origin preflight before Playwright route handling.
  // Stub the read-only feedback health probe before transport; never contact
  // production or accept a feedback write from this local UI fixture.
  await page.addInitScript(() => {
    const realFetch = window.fetch;
    window.fetch = function(input, options) {
      const url = typeof input === 'string' ? input : input.url;
      if (url === 'https://yumjtrdctaxyczpspuyo.supabase.co/functions/v1/swsi-feedback') {
        if (String(options && options.method || 'GET').toUpperCase() === 'OPTIONS') return Promise.resolve(new Response(null, { status: 204 }));
        window.__swsiUnexpectedFeedbackWrite = true;
        return Promise.reject(new Error('unexpected feedback operation in local fixture'));
      }
      return realFetch.apply(this, arguments);
    };
  });
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

  async function assertCompactHomeFooter() {
    const dataDetails = page.locator('details.swsi-data-version');
    if (await dataDetails.count()) {
      await dataDetails.first().evaluate(el => { el.open = true; });
      await page.waitForTimeout(50);
    }
    const layout = await page.evaluate(() => {
      const app = document.querySelector('#app');
      const footer = document.querySelector('.wrap > footer') || document.querySelector('footer');
      const tab = document.querySelector('.tabbar');
      const brand = footer && footer.querySelector('.swsi-public-footer-brand');
      if (!app || !footer || !tab) return null;
      const ar = app.getBoundingClientRect();
      const fr = footer.getBoundingClientRect();
      return { gap: fr.top - ar.bottom, tabDisplay: getComputedStyle(tab).display };
    });
    assert(layout, 'home/footer layout elements missing');
    assert(layout.gap <= 48, 'home leaves an artificial blank slab before footer: '+layout.gap+'px');

    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await page.waitForTimeout(80);
    const clearance = await page.evaluate(() => {
      const footer = document.querySelector('.wrap > footer') || document.querySelector('footer');
      const brand = footer && footer.querySelector('.swsi-public-footer-brand');
      const tab = document.querySelector('.tabbar');
      if (!brand || !tab) return null;
      const br = brand.getBoundingClientRect();
      const tr = tab.getBoundingClientRect();
      return { brandBottom: br.bottom, tabTop: tr.top };
    });
    assert(clearance, 'footer brand or bottom nav missing');
    assert(clearance.brandBottom <= clearance.tabTop + 1,
      'footer content is covered by fixed bottom navigation: brandBottom='+clearance.brandBottom+' tabTop='+clearance.tabTop);
    await page.evaluate(() => window.scrollTo(0, 0));
  }

  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await waitHome();
  await assertCompactHomeFooter();

  // Public monitoring controls must remain clickable inside the modal.
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await page.getByRole('button', { name: '監測', exact: true }).click();
  await page.waitForSelector('#swsi-public-monitor', { timeout: 10000 });
  await page.waitForFunction(() => {
    const root = document.querySelector('#swsi-public-monitor');
    return root && root.dataset.running === '0';
  }, null, { timeout: 15000 });
  const refresh = page.locator('[data-swsi-monitor-refresh]');
  assert.strictEqual(await refresh.count(), 1, 'monitor refresh button missing');
  await refresh.click();
  await page.waitForFunction(() => {
    const root = document.querySelector('#swsi-public-monitor');
    return root && root.dataset.running === '1';
  }, null, { timeout: 5000 });
  await page.waitForFunction(() => {
    const root = document.querySelector('#swsi-public-monitor');
    return root && root.dataset.running === '0';
  }, null, { timeout: 15000 });
  await page.locator('[data-swsi-info-nav="privacy"]').click();
  await page.waitForFunction(() => {
    const h = document.querySelector('#swsi-public-info-title');
    return h && /隱私說明/.test(h.textContent || '');
  }, null, { timeout: 5000 });
  await page.locator('.swsi-public-info-close').click();
  await page.waitForSelector('#swsi-public-info-backdrop', { state: 'detached' });
  await page.evaluate(() => window.scrollTo(0, 0));

  const fontButtons = page.locator('.fontctl button');
  assert((await fontButtons.count()) >= 3, 'font controls missing');
  await fontButtons.nth(1).click();
  await page.waitForFunction(() => document.documentElement.getAttribute('data-fs') === '1');
  await fontButtons.nth(0).click();
  await page.waitForFunction(() => document.documentElement.getAttribute('data-fs') === '0');

  // Force one genuinely wrong answer so the learning-loop UI is always exercised.
  await page.getByRole('button', { name: /開始 10 題/ }).click();
  await page.waitForSelector('.qcard .opt', { timeout: 45000 });
  assert.strictEqual((await page.locator('.pcount').innerText()).trim(), '1 / 10', 'default home CTA did not start a 10-question queue');
  await page.waitForFunction(() => document.body.classList.contains('swsi-question-active'));
  const quizFooter = page.locator('.wrap > footer');
  assert.strictEqual(await quizFooter.isVisible(), false, 'public footer should stay hidden during an active question');
  const wrongIndex = await page.evaluate(() => {
    // Random practice can start with official all_credit/any_answer items,
    // where every option is correct. Find a real wrong option elsewhere in
    // the existing queue without changing any question or grading metadata.
    for (let attempt=0;queue && attempt<queue.length;attempt++) {
      const item = queue[idx];
      const keys = ['A','B','C','D'].filter(k => item.options && item.options[k]);
      for (let i=0;i<keys.length;i++) {
        const k=keys[i];
        let ok=false;
        try { ok = typeof isCorrectAnswer==='function' ? !!isCorrectAnswer(item,k) : !!ansCorrect(k,item.answer); }
        catch (_e) { ok = String(k)===String(item.answer||''); }
        if (!ok) return i;
      }
      idx=(idx+1)%queue.length;
      renderQuiz();
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
  await page.waitForFunction(() => !document.body.classList.contains('swsi-question-active'));
  assert.strictEqual(await quizFooter.isVisible(), true, 'public footer did not return after leaving the active quiz');

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

  // Essay stays in bottom navigation; choose a subject and a real essay through the visible UI.
  await page.locator('#t-essay').click();
  await page.waitForSelector('#app .gcard', { timeout: 30000 });
  await page.locator('#app .gcard').first().click();
  await page.waitForSelector('#app [onclick^="toggleEssay("]', { timeout: 30000 });
  await page.locator('#app [onclick^="toggleEssay("]').first().click();
  await page.waitForSelector('.wta', { timeout: 30000 });
  const textarea = page.locator('.wta').first();
  await textarea.fill('一、測試作答\n（一）測試內容');
  assert((await textarea.inputValue()).includes('測試作答'), 'essay textarea did not accept input');

  // A student may revise a saved draft while the AI request is in flight.
  // Mock only the provider response; exercise the real handler/cache/UI.
  const feedbackRace = await page.evaluate(async () => {
    const ta = document.querySelector('.wta');
    const id = ta.id.slice(3);
    const answerA = '第一版作答說明社會工作者評估案主需求與資源並共同討論服務目標。'.repeat(3);
    const answerB = '第二版作答補充案主自主決定與生態系統資源連結及後續服務評估。'.repeat(3);
    const originalFetch = window.swsiFetchWithTimeout;
    let resolveFirst;
    let calls = 0;
    const requests = [];
    const response = text => ({ ok: true, status: 200, json: async () => ({ choices: [{ message: { content: text } }] }) });
    window.swsiFetchWithTimeout = async (url, options) => {
      requests.push(JSON.parse(options.body));
      calls++;
      if (calls === 1) return await new Promise(resolve => { resolveFirst = resolve; });
      return response('SYNTHETIC_FEEDBACK_B');
    };
    try {
      localStorage.removeItem(window.swsiAICacheKey(id));
      ta.value = answerA;
      window.saveDraft(id);
      const inFlight = window.runAIFeedback(id);
      if (!resolveFirst) throw new Error('AI request did not reach the synthetic provider');
      ta.value = answerB;
      window.saveDraft(id);
      resolveFirst(response('SYNTHETIC_FEEDBACK_A'));
      await inFlight;
      const cacheA = window.swsiGetAICache(id, answerA);
      const cacheB = window.swsiGetAICache(id, answerB);
      const afterRevision = document.getElementById('airesult_' + id).textContent;
      const draftPreserved = getDraft(id) === answerB;
      await window.runAIFeedback(id);
      const revisedFeedback = document.getElementById('airesult_' + id).textContent;
      const revisedCache = window.swsiGetAICache(id, answerB);
      await window.runAIFeedback(id);
      localStorage.removeItem(window.swsiAICacheKey(id));
      window.swsiFetchWithTimeout = async () => ({
        ok: false, status: 429, headers: { get: () => null },
        clone: () => ({ json: async () => ({ error: { code: 'CLIENT_DAILY_QUOTA', message: '合成配額訊息' } }) })
      });
      await window.runAIFeedback(id);
      const quotaFeedback = document.getElementById('airesult_' + id).textContent;
      window.swsiFetchWithTimeout = async () => { const error = new Error('synthetic timeout'); error.name = 'AbortError'; throw error; };
      await window.runAIFeedback(id);
      const timeoutFeedback = document.getElementById('airesult_' + id).textContent;
      const afterErrors = { saved: getDraft(id) === answerB, enabled: !document.getElementById('aitype_' + id).disabled, cached: window.swsiGetAICache(id, answerB) };
      return { cacheA, cacheB, afterRevision, draftPreserved, revisedFeedback, revisedCache, calls, quotaFeedback, timeoutFeedback, afterErrors, requests, cacheKey: window.swsiAICacheKey(id) };
    } finally {
      window.swsiFetchWithTimeout = originalFetch;
    }
  });
  assert(feedbackRace.cacheA && feedbackRace.cacheA.feedback === 'SYNTHETIC_FEEDBACK_A', 'submitted-answer feedback was not cached');
  assert.strictEqual(feedbackRace.cacheB, null, 'old AI response was cached under the revised draft');
  assert(!feedbackRace.afterRevision.includes('SYNTHETIC_FEEDBACK_A'), 'old AI response was displayed against the revised draft');
  assert(feedbackRace.draftPreserved, 'editing during AI request lost the saved draft');
  assert(feedbackRace.revisedFeedback.includes('SYNTHETIC_FEEDBACK_B'), 'revised answer did not receive its own feedback');
  assert(feedbackRace.revisedCache && feedbackRace.revisedCache.feedback === 'SYNTHETIC_FEEDBACK_B', 'revised feedback cache mismatch');
  assert.strictEqual(feedbackRace.calls, 2, 'cache hit called the provider or stale cache skipped the revised request');
  assert(feedbackRace.quotaFeedback.includes('合成配額訊息'), 'typed quota error was not shown');
  assert(feedbackRace.timeoutFeedback.includes('時間過久'), 'timeout did not degrade safely');
  assert(feedbackRace.afterErrors.saved && feedbackRace.afterErrors.enabled, 'AI failure lost the draft or left retry disabled');
  assert.strictEqual(feedbackRace.afterErrors.cached, null, 'AI failure was cached as feedback');

  // Different learners may write in different structures. Verify the REAL
  // request builder preserves each answer verbatim and treats the guide as
  // optional, without contacting an AI provider or grading either answer.
  const answerDiversityTransport = await page.evaluate(async () => {
    const ta = document.querySelector('.wta');
    const id = ta && ta.id.slice(3);
    const question = (window.ESSAYS || []).find(e => e && e.id === id);
    if (!id || !question || !question.q) throw new Error('official essay question unavailable');

    const answers = [
      '第一位練習者先從服務對象的生活需求與可動用資源說起，再分析安全風險、自主決定與服務目標，最後提出介入及追蹤方式。',
      '另一位練習者選擇以倫理與專業評估為起點，先分辨已知事實和仍需確認的資訊，再談共同決策、正式及非正式支持與成效檢視。'
    ];
    const saved = {
      fetch: window.swsiFetchWithTimeout,
      getCache: window.swsiGetAICache,
      setCache: window.swsiSetAICache,
      isVerified: window.swsiEssayGuideIsVerified
    };
    const captured = [];
    const sample = text => ({
      ok: true, status: 200,
      json: async () => ({ choices: [{ message: { content: text } }] })
    });

    try {
      // Isolate the transport contract from pre-existing draft/cache state.
      window.swsiGetAICache = () => null;
      window.swsiSetAICache = () => {};
      let currentVerified = true;
      window.swsiEssayGuideIsVerified = () => currentVerified;
      window.swsiFetchWithTimeout = async (_url, options) => {
        const request = JSON.parse(options.body);
        const content = request.messages?.[0]?.content;
        captured.push({ content, model: request.model });
        return sample('SYNTHETIC_DIVERSE_ESSAY_FEEDBACK');
      };

      for (let i = 0; i < answers.length; i++) {
        currentVerified = i === 0; // verified reference vs intentionally withheld reference
        ta.value = answers[i];
        window.saveDraft(id);
        await window.runAIFeedback(id);
      }

      return { question: question.q, answers, captured };
    } finally {
      window.swsiFetchWithTimeout = saved.fetch;
      window.swsiGetAICache = saved.getCache;
      window.swsiSetAICache = saved.setCache;
      window.swsiEssayGuideIsVerified = saved.isVerified;
    }
  });
  assert.strictEqual(answerDiversityTransport.captured.length, 2, 'alternate essay submissions did not each reach provider transport');
  for (let i = 0; i < 2; i++) {
    const payload = answerDiversityTransport.captured[i].content;
    assert.strictEqual(typeof payload, 'string', 'essay transport must contain the actual prompt');
    assert(
      payload.includes('【正式考題】\n' + answerDiversityTransport.question + '\n\n【學生作答】\n' + answerDiversityTransport.answers[i]),
      'essay transport changed, omitted or replaced a differently structured student answer'
    );
    assert(payload.includes('不得強迫學生照參考架構回答'), 'answer-diversity guard missing from submitted AI request');
    assert(payload.includes('正式考題本身'), 'official question priority missing from submitted AI request');
  }
  assert(answerDiversityTransport.captured[0].content.includes('【SWSI 已逐題核對的參考架構】'), 'simulated verified reference not supplied');
  assert(!answerDiversityTransport.captured[1].content.includes('【SWSI 已逐題核對的參考架構】'), 'withheld study guide leaked into alternative student answer');
  assert(!answerDiversityTransport.captured[0].content.includes(answerDiversityTransport.answers[1]), 'second student answer leaked into first request');
  assert(!answerDiversityTransport.captured[1].content.includes(answerDiversityTransport.answers[0]), 'first student answer leaked into second request');
  // Inspect actual handler payloads: both entry points must send the same
  // teaching rules; unverified references stay outside the provider request.
  const photoPrompt = await page.evaluate(async () => {
    const id = document.querySelector('.wta').id.slice(3);
    const originalFetch = window.swsiFetchWithTimeout;
    const originalShrink = window.shrinkImage;
    const originalGuide = window.ESSAY_GUIDES[id];
    let request;
    const untrustedReference = 'SYNTHETIC_UNVERIFIED_REFERENCE_DO_NOT_SEND';
    try {
      window.ESSAY_GUIDES[id] = { review_status: 'needs_review', kao: untrustedReference };
      window.shrinkImage = async () => 'data:image/jpeg;base64,AA==';
      window.swsiFetchWithTimeout = async (url, options) => {
        request = JSON.parse(options.body);
        return { ok: true, status: 200, json: async () => ({ choices: [{ message: { content: 'SYNTHETIC_PHOTO_FEEDBACK' } }] }) };
      };
      await window.gradePhoto(id, { files: [new File(['synthetic'], 'fixture.jpg', { type: 'image/jpeg' })], value: '' });
      return { request, untrustedReference };
    } finally {
      window.swsiFetchWithTimeout = originalFetch;
      window.shrinkImage = originalShrink;
      if (originalGuide === undefined) delete window.ESSAY_GUIDES[id];
      else window.ESSAY_GUIDES[id] = originalGuide;
    }
  });
  assert(feedbackRace.cacheKey.includes('essay-trust-v2-20261024'), 'old feedback cache namespace reused');
  assert.strictEqual(feedbackRace.requests.length, 2, 'submitted/revised text requests were not captured');
  assert(photoPrompt.request, 'photo handler did not reach synthetic transport');
  const photoText = photoPrompt.request.messages[0].content.find(x => x.type === 'text').text;
  assert(!photoText.includes(photoPrompt.untrustedReference), 'unverified reference reached photo provider');
  const requiredRules = ['肯定必須有作答證據', '題目線索→判斷依據→可考慮的行動', '不沿用可疑理論階段繼續教學', '不能估分', '最後留一個可執行的修改任務'];
  for (const prompt of [...feedbackRace.requests.map(x => x.messages[0].content), photoText]) {
    for (const rule of requiredRules) assert(prompt.includes(rule), 'handler lost teaching rule: ' + rule);
  }
  assert(photoText.includes('看不清楚的字用「◌」'), 'photo uncertainty instruction was lost');

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

  if (browserErrors.length) await dumpDiagnostics('page-errors');
  assert.strictEqual(await page.evaluate(() => !!window.__swsiUnexpectedFeedbackWrite), false, 'local fixture attempted a feedback write');
  assert.deepStrictEqual(browserErrors, [], 'browser page errors: ' + browserErrors.join(' | '));
  console.log('BROWSER INTERACTION SMOKE OK');
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

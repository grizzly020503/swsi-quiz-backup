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

  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await page.waitForSelector('.swsi-focus-primary', { timeout: 30000 });
  await page.waitForFunction(() => Array.isArray(window.THEORIES) && window.SWSI_THEORY_TRUST && typeof window.SWSI_THEORY_TRUST.verifiedCount === 'function');

  const stats = await page.evaluate(() => ({
    total: window.SWSI_THEORY_TRUST.totalCount(),
    verified: window.SWSI_THEORY_TRUST.verifiedCount(),
    bowen: (window.THEORIES || []).some(t => t && t.n === 'Bowen 家庭系統理論'),
    minuchin: (window.THEORIES || []).some(t => t && t.n === 'Minuchin 結構家庭治療'),
    checked: (window.THEORIES || []).filter(t => t && t.theory_verify_status === 'checked').map(t => t.n),
    all: (window.THEORIES || []).filter(Boolean).map(t => t.n)
  }));
  console.log('THEORY TRUST DIAG checked=' + JSON.stringify(stats.checked));
  console.log('THEORY TRUST DIAG all=' + JSON.stringify(stats.all));
  assert(stats.total >= 37, 'theory split cards were not added');
  assert(stats.verified >= 14, `Theory Trust Batch 1 verified too few cards: verified=${stats.verified}; checked=${stats.checked.join('|')}`);
  assert(stats.bowen, 'Bowen family systems card missing');
  assert(stats.minuchin, 'Minuchin structural family therapy card missing');

  async function openTheoryAndRead(name) {
    await page.evaluate(n => openTheory(n), name);
    await page.waitForSelector('.ecard.open .swsi-theory-trust', { timeout: 30000 });
    const card = page.locator('.ecard.open').first();
    const text = await card.innerText();
    assert(text.includes(name), `wrong theory opened for ${name}`);
    assert(/✓ 理論內容已逐卡核對/.test(text), `${name} missing verified trust badge`);
    return text;
  }

  let text = await openTheoryAndRead('家庭系統理論');
  assert(/Bowen/.test(text) && /Minuchin/.test(text), 'family systems umbrella must distinguish Bowen and Minuchin');
  assert(/自我分化/.test(text) && /界限/.test(text), 'family systems umbrella missing school-specific concepts');
  assert(/Bowen ≠ Minuchin|Bowen.*Minuchin/.test(text), 'family systems umbrella missing explicit school distinction');

  text = await openTheoryAndRead('Bowen 家庭系統理論');
  assert(/自我分化/.test(text), 'Bowen card missing differentiation of self');
  assert(/三角關係/.test(text), 'Bowen card missing triangles');
  assert(/多世代/.test(text), 'Bowen card missing multigenerational process');

  text = await openTheoryAndRead('Minuchin 結構家庭治療');
  assert(/次系統/.test(text), 'Minuchin card missing subsystems');
  assert(/界限/.test(text), 'Minuchin card missing boundaries');
  assert(/階層/.test(text), 'Minuchin card missing hierarchy');

  text = await openTheoryAndRead('生態系統理論');
  assert(/時間系統/.test(text), 'ecological systems card missing chronosystem');
  assert(/不等同生活模型|不是同一套理論|並不完全相同/.test(text), 'ecological systems card still conflates Life Model');
  assert(/Germain/.test(text) && /Gitterman/.test(text), 'ecological systems card should name Life Model authors when distinguishing it');

  text = await openTheoryAndRead('依附理論');
  assert(/Main/.test(text) && /Solomon/.test(text), 'attachment card missing Main & Solomon for disorganized attachment');
  assert(/後續研究|後續.*提出|後由/.test(text), 'attachment card should mark disorganized pattern as later development');
  assert(/不是.*終身|不能.*終身|不宜直接.*診斷/.test(text), 'attachment card needs non-deterministic / non-diagnostic caution');

  text = await openTheoryAndRead('Erikson 心理社會發展理論');
  assert(/大致範圍|不是硬切/.test(text), 'Erikson card should not treat ages as hard diagnostic boundaries');
  assert(/危機.*不是|危機.*不等於/.test(text), 'Erikson card should explain psychosocial crisis is not pathology');

  text = await openTheoryAndRead('Piaget 認知發展理論');
  assert(/平衡化/.test(text), 'Piaget card missing equilibration');
  assert(/不是硬性|不是硬切|不是.*診斷/.test(text), 'Piaget card should caution against hard age cutoffs');

  text = await openTheoryAndRead('Kohlberg 道德發展理論');
  assert(/理由|推理/.test(text), 'Kohlberg card should focus on moral reasoning');
  assert(/年齡不保證|年齡.*不.*階段|年齡不等於階段/.test(text), 'Kohlberg card should not map age mechanically to stage');
  assert(/不是人人|不.*必然達到/.test(text), 'Kohlberg card should state postconventional reasoning is not inevitable');

  text = await openTheoryAndRead('優勢觀點');
  assert(/不是否認|不.*否認/.test(text), 'strengths card should not erase real risk/problems');
  assert(/風險/.test(text), 'strengths card should retain safety/risk assessment');

  text = await openTheoryAndRead('復原力觀點');
  assert(/動態/.test(text), 'resilience card should frame resilience as dynamic');
  assert(/不是.*固定|不.*固定人格/.test(text), 'resilience card should not frame resilience as a fixed trait');

  text = await openTheoryAndRead('增強權能觀點');
  assert(/不是.*把權力|不是由社工/.test(text), 'empowerment card should not imply worker gives power');
  assert(/參與/.test(text) && /資源/.test(text), 'empowerment card missing participation/resource access');

  text = await openTheoryAndRead('任務中心模式');
  assert(/共同/.test(text), 'task-centered card should emphasize jointly agreed target problems/tasks');
  assert(/不是社工替案主列/.test(text), 'task-centered card should reject simple worker-created to-do list framing');
  assert(/不要把.*6–12次|6–12次.*固定/.test(text), 'task-centered card should not teach session count as invariant');

  text = await openTheoryAndRead('危機介入模式');
  assert(/安全/.test(text) && /風險/.test(text), 'crisis intervention should start with safety/risk assessment');
  assert(/不要只背.*黃金期|沒有.*固定.*黃金/.test(text), 'crisis intervention should not teach a universal golden period');
  assert(/行動/.test(text) && /追蹤/.test(text), 'crisis intervention missing action/follow-up');

  assert.deepStrictEqual(browserErrors, [], 'browser page errors: ' + browserErrors.join(' | '));
  console.log(`THEORY TRUST BATCH 1 SMOKE OK: total=${stats.total} verified=${stats.verified}`);
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

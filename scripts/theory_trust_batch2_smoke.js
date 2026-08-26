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
  const errors = [];
  page.on('pageerror', err => errors.push(String(err && err.message || err)));

  const localOrigin = new URL(base).origin;
  await page.route('**/*', route => {
    const u = new URL(route.request().url());
    if (u.hostname === QUESTION_CDN_HOST && u.pathname.startsWith(QUESTION_CDN_PREFIX)) {
      const rel = decodeURIComponent(u.pathname.slice(QUESTION_CDN_PREFIX.length));
      const file = path.join(LOCAL_SHARD_DIR, rel);
      if (!rel || rel !== path.basename(rel) || !fs.existsSync(file)) return route.fulfill({ status: 404, body: 'not found' });
      return route.fulfill({ status: 200, contentType: 'application/json; charset=utf-8', body: fs.readFileSync(file) });
    }
    if (u.origin !== localOrigin) return route.abort();
    return route.continue();
  });

  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await page.waitForSelector('.swsi-focus-primary', { timeout: 30000 });
  await page.waitForFunction(() => window.SWSI_THEORY_TRUST && /Theory Trust Batch 2/.test(window.SWSI_THEORY_TRUST.batch2 || ''));

  const stats = await page.evaluate(() => ({
    total: window.SWSI_THEORY_TRUST.totalCount(),
    verified: window.SWSI_THEORY_TRUST.verifiedCount(),
    checked: (window.THEORIES || []).filter(t => t && t.theory_verify_status === 'checked').map(t => t.n)
  }));
  assert(stats.total >= 37, 'theory catalog unexpectedly shrank');
  assert(stats.verified >= 28, `Theory Trust Batch 2 verified too few cards: ${stats.verified}; checked=${stats.checked.join('|')}`);

  async function read(name) {
    await page.evaluate(n => openTheory(n), name);
    await page.waitForSelector('.ecard.open .swsi-theory-trust', { timeout: 30000 });
    const text = await page.locator('.ecard.open').first().innerText();
    assert(text.includes(name), `wrong theory opened: ${name}`);
    assert(/✓ 理論內容已逐卡核對/.test(text), `${name} missing checked badge`);
    return text;
  }

  let t = await read('社會工作價值與專業倫理');
  assert(/尊嚴/.test(t) && /社會正義/.test(t), 'ethics card missing dignity/social justice');
  assert(/自我決定/.test(t) && /保密/.test(t), 'ethics card missing self-determination/confidentiality');
  assert(/不是無條件絕對|不是.*絕對/.test(t), 'ethics card should not teach self-determination/confidentiality as absolute');

  t = await read('倫理兩難與抉擇');
  assert(/不是.*唯一|多種/.test(t), 'ethical decision card should not claim one universal formula');
  assert(/法律/.test(t) && /倫理/.test(t) && /紀錄/.test(t), 'ethical decision card missing law/ethics/documentation');

  t = await read('社會學習理論');
  assert(/Bandura/.test(t), 'social learning card missing Bandura');
  assert(/觀察學習/.test(t) && /自我效能/.test(t), 'social learning card missing observation/self-efficacy');
  assert(/不等於單純操作制約|不要.*獎勵.*處罰/.test(t), 'social learning card still reduced to reinforcement');

  t = await read('綜融取向與四系統模型');
  for (const word of ['改變媒介系統','案主系統','標的系統','行動系統']) assert(t.includes(word), `four systems missing ${word}`);
  assert(/案主.*不一定.*標的|案主不一定是標的/.test(t), 'four systems card should distinguish client and target systems');

  t = await read('認知行為理論');
  assert(/Beck/.test(t) && /Ellis/.test(t), 'CBT card missing Beck/Ellis distinction');
  assert(/不是.*正向思考|不要把 CBT 寫成.*正向思考/.test(t), 'CBT card should reject positive-thinking simplification');
  assert(/認知.*情緒.*行為|情境.*認知.*情緒/.test(t), 'CBT card missing cognition-emotion-behavior interaction');

  t = await read('心理暨社會學派');
  assert(/人在情境中/.test(t), 'psychosocial card missing person-in-situation');
  assert(/心理.*社會|社會.*心理/.test(t), 'psychosocial card missing dual focus');
  assert(/不能簡化成.*精神分析|不是只.*童年/.test(t), 'psychosocial card still over-reduced to psychoanalysis');

  t = await read('個案管理');
  assert(/非單一理論|不是一套單一.*理論/.test(t), 'case management should be labeled a method/strategy, not one theory');
  assert(/不要把個案管理等同.*轉介/.test(t), 'case management should not equal referral');
  assert(/協調/.test(t) && /監測/.test(t) && /再評估/.test(t), 'case management missing coordination/monitoring/reassessment');

  t = await read('Biestek 專業關係原則');
  for (const word of ['個別化','有目的的情感表達','適度的情感涉入','接納','非批判','自我決定','保密']) assert(t.includes(word), `Biestek card missing ${word}`);
  assert(/不是.*照做|不是.*任何情況都不能揭露/.test(t), 'Biestek card needs limits to self-determination/confidentiality');

  t = await read('家庭生命週期理論');
  assert(/McGoldrick/.test(t) && /Carter/.test(t), 'family life cycle card missing Carter/McGoldrick');
  assert(/不同版本|階段數量.*不同/.test(t), 'family life cycle card should acknowledge model variation');
  assert(/多元家庭|不是.*唯一標準|不必走同一條/.test(t), 'family life cycle card should avoid normative family path');

  t = await read('反壓迫觀點');
  assert(/權力/.test(t) && /制度/.test(t), 'anti-oppressive card missing power/structure');
  assert(/反思.*專業權力/.test(t), 'anti-oppressive card missing worker power reflection');
  assert(/不要預設所有.*問題|不是看到弱勢.*自動/.test(t), 'anti-oppressive card should avoid automatic oppression assumptions');

  t = await read('女性主義觀點');
  assert(/性別化.*權力|性別.*權力/.test(t), 'feminist card missing gendered power');
  assert(/交織性/.test(t), 'feminist card missing intersectionality');
  assert(/不是.*只服務女性|不要把.*只服務女性/.test(t), 'feminist card should not reduce feminism to women-only services');

  t = await read('文化能力');
  assert(/文化謙遜/.test(t), 'cultural competence card missing cultural humility');
  assert(/終身.*反思|終身自我反思/.test(t), 'cultural competence card missing lifelong reflection');
  assert(/權力/.test(t), 'cultural competence card missing power imbalance');
  assert(/不要靠族群標籤|不等於把.*族群.*背熟/.test(t), 'cultural competence card should reject stereotyping/mastery');

  t = await read('障礙的社會模式');
  assert(/UPIAS/.test(t) && /Mike Oliver/.test(t), 'social model card missing UPIAS/Oliver provenance');
  assert(/環境.*制度.*障礙|社會.*障礙/.test(t), 'social model card missing disabling barriers');
  assert(/不是否認.*醫療|不是.*否定醫療/.test(t), 'social model card should not deny impairment/medical needs');

  t = await read('結構社會工作／批判理論');
  assert(/結構性不平等|制度性權力|資源分配/.test(t), 'structural card missing structural inequality');
  assert(/個人能動性/.test(t), 'structural card should retain individual agency');
  assert(/不要把所有.*化約|不.*所有.*都是結構/.test(t), 'structural card should avoid total structural reductionism');

  assert.deepStrictEqual(errors, [], 'browser page errors: ' + errors.join(' | '));
  console.log(`THEORY TRUST BATCH 2 SMOKE OK: total=${stats.total} verified=${stats.verified}`);
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

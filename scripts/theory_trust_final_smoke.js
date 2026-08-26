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
  await page.waitForFunction(() => window.SWSI_THEORY_TRUST && window.SWSI_THEORY_TRUST_FINAL && /Theory Trust Final/.test(window.SWSI_THEORY_TRUST.version || ''));

  const stats = await page.evaluate(() => ({
    total: window.SWSI_THEORY_TRUST.totalCount(),
    verified: window.SWSI_THEORY_TRUST.verifiedCount(),
    pending: window.SWSI_THEORY_TRUST.pendingCount(),
    allChecked: window.SWSI_THEORY_TRUST.allChecked(),
    pendingNames: window.SWSI_THEORY_TRUST_FINAL.pending(),
    names: (window.THEORIES || []).filter(Boolean).map(t => t.n),
    unchecked: (window.THEORIES || []).filter(t => t && t.theory_verify_status !== 'checked').map(t => t.n)
  }));
  console.log('THEORY TRUST FINAL DIAG ' + JSON.stringify(stats));
  assert.strictEqual(stats.total, 39, `expected exactly 39 theory cards, got ${stats.total}`);
  assert.strictEqual(stats.verified, 39, `expected 39 checked theory cards, got ${stats.verified}; pending=${stats.pendingNames.join('|')}`);
  assert.strictEqual(stats.pending, 0, `expected zero pending cards, got ${stats.pending}: ${stats.pendingNames.join('|')}`);
  assert.strictEqual(stats.allChecked, true, 'SWSI_THEORY_TRUST.allChecked() is not true');
  assert.deepStrictEqual(stats.unchecked, [], 'some theory cards are still unchecked');
  assert(stats.names.includes('資產建構／資產累積理論'), 'asset-building split card missing');
  assert(stats.names.includes('無條件基本收入 UBI'), 'UBI split card missing');

  async function read(name) {
    await page.evaluate(n => openTheory(n), name);
    await page.waitForSelector('.ecard.open .swsi-theory-trust', { timeout: 30000 });
    const text = await page.locator('.ecard.open').first().innerText();
    assert(text.includes(name), `wrong theory opened: ${name}`);
    assert(/✓ 理論內容已逐卡核對/.test(text), `${name} missing checked badge`);
    return text;
  }

  let t = await read('Rothman 社區工作三模式');
  for (const word of ['地方發展','社會計畫','社會行動']) assert(t.includes(word), `Rothman card missing ${word}`);
  assert(/不是依序.*階段|不是.*固定.*階段|非固定階段/.test(t), 'Rothman card must reject sequential-stage framing');
  assert(/混合運用/.test(t), 'Rothman card should allow mixed use');

  t = await read('資產基礎社區發展 ABCD');
  assert(/Kretzmann/.test(t) && /McKnight/.test(t), 'ABCD card missing Kretzmann/McKnight');
  assert(/居民主導/.test(t) && /資產盤點/.test(t), 'ABCD card missing resident-led asset focus');
  assert(/不等於.*Sherraden|不等於.*資產建構|不等於.*金融資產/.test(t), 'ABCD card must distinguish Sherraden asset building');
  assert(/不是.*否認需求|不是假裝.*沒有需求/.test(t), 'ABCD card must not erase needs');

  t = await read('團體發展階段理論');
  assert(/Tuckman/.test(t) && /Garland/.test(t), 'group stages card must distinguish Tuckman and Garland');
  assert(/形成/.test(t) && /風暴/.test(t) && /規範/.test(t) && /表現/.test(t), 'Tuckman stages incomplete');
  assert(/權力與控制/.test(t) && /分化/.test(t) && /分離/.test(t), 'Garland stages incomplete');
  assert(/不是.*翻譯|不能.*混/.test(t), 'group-stage models must not be merged');
  assert(/重疊|回到先前|非線性|不代表.*線性/.test(t), 'group stages should not be taught as rigidly linear');

  t = await read('社會學三大觀點');
  for (const word of ['結構功能','衝突','符號互動']) assert(t.includes(word), `sociology card missing ${word}`);
  assert(/符號互動.*微觀|微觀.*符號互動/.test(t), 'symbolic interactionism must be marked primarily micro-level');
  assert(/權力/.test(t) && /資源/.test(t), 'conflict perspective missing power/resources');

  t = await read('福利意識形態');
  for (const word of ['反集體主義','勉強集體主義','費邊社會主義','馬克思主義']) assert(t.includes(word), `welfare ideology card missing ${word}`);
  assert(/不是唯一|非唯一/.test(t), 'George & Wilding classification must not be framed as the only map');

  t = await read('Titmuss 福利三模式');
  for (const word of ['殘補福利','工業成就表現','制度再分配']) assert(t.includes(word), `Titmuss card missing ${word}`);
  assert(/理想型/.test(t), 'Titmuss models should be presented as ideal types');
  assert(/不要把.*工業成就.*繳多少|不.*簡化.*繳多少/.test(t), 'industrial achievement-performance model is still oversimplified');

  t = await read('福利混合經濟與服務輸送');
  for (const word of ['國家','市場','家庭','可近性','連續性']) assert(t.includes(word), `welfare mix card missing ${word}`);
  assert(/整合|協調/.test(t), 'service delivery missing integration/coordination');
  assert(/POSC.*工具|工具.*POSC|只是可能的政策工具/.test(t), 'POSC should be a tool, not definition');
  assert(/不等於.*退出|不直接.*等同.*退出/.test(t), 'outsourcing should not equal state withdrawal');

  t = await read('資產累積與基本收入');
  assert(/Sherraden/.test(t) && /UBI/.test(t), 'comparison card missing both approaches');
  assert(/不是同一.*理論|不同.*政策路徑|兩條不同/.test(t), 'asset building and UBI must be explicitly separate');
  assert(/IDA/.test(t) && /無條件/.test(t), 'comparison card missing key policy mechanics');

  t = await read('資產建構／資產累積理論');
  assert(/Sherraden/.test(t), 'asset-building card missing Sherraden');
  assert(/IDA/.test(t) && /配合/.test(t), 'asset-building card missing IDA/matching');
  assert(/不等於.*ABCD|不等於.*社區資產/.test(t), 'asset-building card must distinguish ABCD');
  assert(/不要寫成.*所得移轉沒有用|不.*必然脫貧/.test(t), 'asset-building card should not overclaim');

  t = await read('無條件基本收入 UBI');
  for (const word of ['定期','現金','個人','普遍','無條件']) assert(t.includes(word), `UBI card missing ${word}`);
  assert(/資產調查/.test(t) && /工作要求/.test(t), 'UBI card missing means/work-condition distinction');
  assert(/不要寫成.*必然取代|不.*必然.*取代|不是.*必然.*取代/.test(t), 'UBI card must not claim mandatory welfare replacement');
  assert(/不同.*提案|方案差異/.test(t), 'UBI card should acknowledge proposal variation');

  t = await read('社會投資觀點');
  assert(/生命歷程/.test(t), 'social investment card missing life-course orientation');
  assert(/兒童/.test(t) && /教育/.test(t) && /工作.*家庭|家庭.*工作/.test(t), 'social investment card missing core investment areas');
  assert(/社會保護.*互補|所得保障.*重要|不是.*不再做所得保障/.test(t), 'social investment must retain social protection/income protection');
  assert(/不是把所有福利支出都叫.*投資|不是.*所有.*福利.*投資/.test(t), 'social investment card still overgeneralizes all welfare as investment');

  assert.deepStrictEqual(errors, [], 'browser page errors: ' + errors.join(' | '));
  console.log('THEORY TRUST FINAL SMOKE OK: total=39 verified=39 pending=0');
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

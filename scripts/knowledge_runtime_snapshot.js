const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const base = process.argv[2] || 'http://127.0.0.1:4173';
const outDir = path.resolve(process.argv[3] || '/tmp/swsi-knowledge-runtime');
const QUESTION_CDN_HOST = 'wandering-wave-4418.c022050333.workers.dev';
const QUESTION_CDN_PREFIX = '/question-shards/';
const LOCAL_SHARD_DIR = path.resolve(process.cwd(), 'cdn/question-shards');

function stableStringify(value) {
  function sortValue(v) {
    if (Array.isArray(v)) return v.map(sortValue);
    if (v && typeof v === 'object') {
      const out = {};
      for (const key of Object.keys(v).sort()) out[key] = sortValue(v[key]);
      return out;
    }
    return v;
  }
  return JSON.stringify(sortValue(value), null, 2) + '\n';
}

function sha256(text) {
  return crypto.createHash('sha256').update(text, 'utf8').digest('hex');
}

function assertUniqueNames(rows, label) {
  const names = rows.map(row => String(row && row.n || '').trim());
  assert(names.every(Boolean), `${label} contains an empty name`);
  assert.strictEqual(new Set(names).size, names.length, `${label} contains duplicate names`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const browserErrors = [];
  page.on('pageerror', err => browserErrors.push(String(err && err.message || err)));

  const localOrigin = new URL(base).origin;
  await page.route('**/*', route => {
    const u = new URL(route.request().url());
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
  await page.waitForFunction(() =>
    Array.isArray(window.LAWS) &&
    Array.isArray(window.THEORIES) &&
    window.SWSI_KNOWLEDGE_CANONICAL_BOOTSTRAP &&
    window.SWSI_KNOWLEDGE_CANONICAL_BOOTSTRAP.version === '2026-08-27.canonical-build.v1' &&
    window.SWSI_LAW_TRUST_FINAL &&
    /Law Trust Final Batch/.test(window.SWSI_LAW_TRUST_FINAL.version || '') &&
    window.SWSI_THEORY_TRUST_FINAL &&
    /Theory Trust Final Batch/.test(window.SWSI_THEORY_TRUST_FINAL.version || ''),
    null,
    { timeout: 30000 }
  );

  const effective = await page.evaluate(() => ({
    laws: JSON.parse(JSON.stringify(window.LAWS || [])),
    theories: JSON.parse(JSON.stringify(window.THEORIES || [])),
    bootstrap: JSON.parse(JSON.stringify(window.SWSI_KNOWLEDGE_CANONICAL_BOOTSTRAP || {})),
    markers: {
      law_final: window.SWSI_LAW_TRUST_FINAL && window.SWSI_LAW_TRUST_FINAL.version || '',
      law_checked_at: window.SWSI_LAW_TRUST_FINAL && window.SWSI_LAW_TRUST_FINAL.checkedAt || '',
      theory_final: window.SWSI_THEORY_TRUST_FINAL && window.SWSI_THEORY_TRUST_FINAL.version || '',
      theory_total: window.SWSI_THEORY_TRUST_FINAL && typeof window.SWSI_THEORY_TRUST_FINAL.total === 'function' ? window.SWSI_THEORY_TRUST_FINAL.total() : null,
      theory_checked: window.SWSI_THEORY_TRUST_FINAL && typeof window.SWSI_THEORY_TRUST_FINAL.checked === 'function' ? window.SWSI_THEORY_TRUST_FINAL.checked() : null,
      theory_pending: window.SWSI_THEORY_TRUST_FINAL && typeof window.SWSI_THEORY_TRUST_FINAL.pending === 'function' ? window.SWSI_THEORY_TRUST_FINAL.pending() : []
    }
  }));

  assertUniqueNames(effective.laws, 'LAWS');
  assertUniqueNames(effective.theories, 'THEORIES');
  assert(effective.laws.length > 0, 'LAWS runtime snapshot is empty');
  assert(effective.theories.length > 0, 'THEORIES runtime snapshot is empty');
  assert.strictEqual(effective.markers.theory_total, effective.theories.length, 'theory final marker total does not match runtime array');
  assert.strictEqual(effective.markers.theory_checked, effective.theories.length, 'not every theory is final-checked');
  assert.deepStrictEqual(effective.markers.theory_pending, [], 'theory final marker still has pending rows');
  assert.deepStrictEqual(browserErrors, [], 'browser page errors: ' + browserErrors.join(' | '));

  fs.mkdirSync(outDir, { recursive: true });
  const lawsText = stableStringify(effective.laws);
  const theoriesText = stableStringify(effective.theories);
  const lawsHash = sha256(lawsText);
  const theoriesHash = sha256(theoriesText);
  assert.strictEqual(effective.bootstrap.version, '2026-08-27.canonical-build.v1', 'canonical bootstrap version missing');
  assert.strictEqual(Number(effective.bootstrap.laws && effective.bootstrap.laws.count), effective.laws.length, 'canonical law count differs from final runtime');
  assert.strictEqual(Number(effective.bootstrap.theories && effective.bootstrap.theories.count), effective.theories.length, 'canonical theory count differs from final runtime');
  assert.strictEqual(effective.bootstrap.laws && effective.bootstrap.laws.sha256, lawsHash, 'canonical law hash differs from final runtime');
  assert.strictEqual(effective.bootstrap.theories && effective.bootstrap.theories.sha256, theoriesHash, 'canonical theory hash differs from final runtime');

  fs.writeFileSync(path.join(outDir, 'laws.runtime.json'), lawsText, 'utf8');
  fs.writeFileSync(path.join(outDir, 'theories.runtime.json'), theoriesText, 'utf8');

  const manifest = {
    schema_version: 1,
    source: 'production-shaped browser runtime after monthly_patch_parts lexicographic application',
    laws: { count: effective.laws.length, sha256: lawsHash },
    theories: { count: effective.theories.length, sha256: theoriesHash },
    markers: effective.markers
  };
  fs.writeFileSync(path.join(outDir, 'manifest.json'), stableStringify(manifest), 'utf8');

  console.log(`KNOWLEDGE RUNTIME SNAPSHOT OK: laws=${effective.laws.length} theories=${effective.theories.length}`);
  console.log(`laws_sha256=${manifest.laws.sha256}`);
  console.log(`theories_sha256=${manifest.theories.sha256}`);
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

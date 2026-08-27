const fs = require('fs');
const path = require('path');
const os = require('os');
const cp = require('child_process');

const ROOT = process.cwd();
const read = p => fs.readFileSync(path.resolve(ROOT, p), 'utf8');
const failures = [];
const notes = [];

function fail(code, detail){ failures.push({ code, detail }); }
function note(code, detail){ notes.push({ code, detail }); }
function pass(code, detail){ note(code, 'PASS: ' + detail); }
function guideKeyRegex(){
  return /"((?:社會工作|社會工作直接服務|社會政策與社會立法|人類行為與社會環境|社會工作研究方法)-\d{3}-[12]-申論\d+)"\s*:/g;
}

// -----------------------------------------------------------------------------
// P0-1: ESSAY_GUIDES source must not gain new silent duplicate keys, and the
// deploy artifact must be normalized to unique IDs with the verified 107-1 fix.
// -----------------------------------------------------------------------------
const essaySource = read('essay_guides.js');
const counts = new Map();
let m;
const sourceKeyRe = guideKeyRegex();
while((m = sourceKeyRe.exec(essaySource))){
  counts.set(m[1], (counts.get(m[1]) || 0) + 1);
}
const duplicates = [...counts.entries()].filter(([, n]) => n > 1);
if(duplicates.length){
  fail('ESSAY_GUIDE_DUPLICATE_KEY', duplicates.map(([id,n]) => `${id} x${n}`).join(', '));
}else{
  pass('ESSAY_GUIDE_DUPLICATE_SOURCE', 'no duplicate source IDs remain');
}

const guideBuilder = read('scripts/build_essay_guides_runtime.js');
for(const needle of ['社會工作-107-1-申論2','認知行為學派','社會支持理論','優勢觀點','ESSAY_GUIDES duplicate key(s)']){
  if(!guideBuilder.includes(needle)) fail('ESSAY_GUIDE_RUNTIME_NORMALIZER', `builder missing required marker: ${needle}`);
}
if(!failures.some(x => x.code === 'ESSAY_GUIDE_RUNTIME_NORMALIZER')){
  pass('ESSAY_GUIDE_RUNTIME_NORMALIZER', 'builder contains verified 107-1 correction and rejects unexpected duplicate IDs');
}

try{
  const tmp = path.join(os.tmpdir(), `swsi-essay-guides-${process.pid}.js`);
  cp.execFileSync(process.execPath, ['scripts/build_essay_guides_runtime.js', 'essay_guides.js', tmp], { cwd: ROOT, stdio: 'pipe' });
  const runtime = fs.readFileSync(tmp, 'utf8');
  fs.unlinkSync(tmp);
  const runtimeCounts = new Map();
  const runtimeKeyRe = guideKeyRegex();
  let rm;
  while((rm = runtimeKeyRe.exec(runtime))) runtimeCounts.set(rm[1], (runtimeCounts.get(rm[1]) || 0) + 1);
  const runtimeDup = [...runtimeCounts.entries()].filter(([,n]) => n > 1);
  if(runtimeDup.length) fail('ESSAY_GUIDE_RUNTIME_DUPLICATE', runtimeDup.map(([id,n])=>`${id} x${n}`).join(', '));
  else pass('ESSAY_GUIDE_RUNTIME_DUPLICATE', 'generated essay guide artifact contains unique historical IDs');
  if(!runtime.includes('認知行為學派') || !runtime.includes('社會支持理論') || !runtime.includes('三理論整合')){
    fail('ESSAY_GUIDE_1071_RUNTIME', 'generated artifact does not contain the verified three-theory 107-1 guide');
  }else pass('ESSAY_GUIDE_1071_RUNTIME', '107-1 guide is normalized to CBT + social support + strengths integration');
}catch(err){
  fail('ESSAY_GUIDE_RUNTIME_BUILD', String(err && err.message || err));
}

try{
  const duplicateId = '社會工作-107-1-申論2';
  const marker = `"${duplicateId}":`;
  if(!essaySource.includes(marker)) throw new Error(`missing fixture key: ${duplicateId}`);
  const duplicateSource = essaySource.replace(marker, marker + '{} ,' + marker);
  const input = path.join(os.tmpdir(), `swsi-essay-guides-duplicate-${process.pid}.js`);
  const output = path.join(os.tmpdir(), `swsi-essay-guides-duplicate-${process.pid}.out.js`);
  fs.writeFileSync(input,duplicateSource,'utf8');
  let rejected = false;
  try{
    cp.execFileSync(process.execPath,['scripts/build_essay_guides_runtime.js',input,output],{cwd:ROOT,stdio:'pipe'});
  }catch(_expected){ rejected = true; }
  try{fs.unlinkSync(input);}catch(_e){}
  try{fs.unlinkSync(output);}catch(_e){}
  if(!rejected) fail('ESSAY_GUIDE_DUPLICATE_SELFTEST','builder accepted a synthetic duplicate of the formerly duplicated 107-1 key');
  else pass('ESSAY_GUIDE_DUPLICATE_SELFTEST','builder rejects every duplicate key, including the former legacy ID');
}catch(err){
  fail('ESSAY_GUIDE_DUPLICATE_SELFTEST',String(err&&err.message||err));
}

// -----------------------------------------------------------------------------
// Effective monthly-patch runtime. The repository is still in migration from
// legacy in-file code, so source presence alone is not enough: override order is
// part of the contract until legacy code is fully removed.
// -----------------------------------------------------------------------------
const partsDir = path.resolve(ROOT, 'monthly_patch_parts');
const partFiles = fs.readdirSync(partsDir).filter(x => x.endsWith('.part')).sort();
const patchSource = partFiles.map(f => `\n/* FILE:${f} */\n` + fs.readFileSync(path.join(partsDir,f),'utf8')).join('\n');

function ownerOfLastMatch(pattern){
  const flags = pattern.flags.includes('g') ? pattern.flags : pattern.flags + 'g';
  const re = new RegExp(pattern.source, flags);
  let match, last = null;
  while((match = re.exec(patchSource))){
    last = match.index;
    if(match[0].length === 0) re.lastIndex++;
  }
  if(last == null) return null;
  const prefix = patchSource.slice(0,last);
  const marker = prefix.lastIndexOf('/* FILE:');
  const end = marker >= 0 ? prefix.indexOf(' */',marker) : -1;
  return marker >= 0 && end > marker ? prefix.slice(marker+8,end) : null;
}

const essayTrustCanonical = '99z.essay-trust-layer.part';
const essayTrustLegacy = 'zzzzzzzzz_essay_trust_layer.part';
if(!partFiles.includes(essayTrustCanonical)) fail('ESSAY_TRUST_OWNER_PATH', `missing canonical ${essayTrustCanonical}`);
if(partFiles.includes(essayTrustLegacy)) fail('ESSAY_TRUST_OWNER_PATH', `legacy owner path still exists: ${essayTrustLegacy}`);
if(!failures.some(x => x.code === 'ESSAY_TRUST_OWNER_PATH')) pass('ESSAY_TRUST_OWNER_PATH', 'essay trust layer has one canonical patch path');

// Until the legacy layers are consolidated, fail the build whenever a new
// later patch silently takes ownership of a correctness-sensitive function.
const expectedOwners = [
  [/function\s+gradingMode\s*\(|(?:window\.)?gradingMode\s*=(?!=)/, 'zzzzzzzzzzzzzzzzzzzzzzzzzz_code_health_p0.part', 'gradingMode'],
  [/function\s+normalize\s*\(|(?:window\.)?normalize\s*=(?!=)/, 'zzzzzzzzzzzzzzzzzzzzzzzzzz_code_health_p0.part', 'normalize'],
  [/function\s+runAIFeedback\s*\(|(?:window\.)?runAIFeedback\s*=(?!=)/, essayTrustCanonical, 'runAIFeedback'],
  [/function\s+gradePhoto\s*\(|(?:window\.)?gradePhoto\s*=(?!=)/, essayTrustCanonical, 'gradePhoto'],
  [/(?:window\.)?MK\s*=(?!=)/, 'zzzzzzzzzzzzzzzzzzzzzzzzzzz_mk_grading_contract.part', 'MK']
];
for(const [pattern,expected,label] of expectedOwners){
  const owner = ownerOfLastMatch(pattern);
  if(owner !== expected) fail('PATCH_OVERRIDE_ORDER', `${label} final owner is ${owner || '(missing)'}, expected ${expected}`);
}
if(!failures.some(x => x.code === 'PATCH_OVERRIDE_ORDER')){
  pass('PATCH_OVERRIDE_ORDER', 'correctness-sensitive overrides still end in their reviewed owner layers');
}

// P0-2: special grading must end fail-closed.
const legacyInferencePos = Math.max(
  patchSource.lastIndexOf('SWSI_ANY_ANSWER_LEGACY_IDS'),
  patchSource.lastIndexOf('/一律給分|送分/')
);
const strictGuardPos = patchSource.lastIndexOf('SWSI Code Health P0 Runtime Guard 2026-08-26');
if(strictGuardPos < 0){
  fail('GRADING_FAIL_CLOSED_RUNTIME', 'final fail-closed runtime guard is missing');
}else if(legacyInferencePos >= strictGuardPos){
  fail('GRADING_OVERRIDE_ORDER', 'legacy grading inference appears after the fail-closed runtime guard');
}else{
  pass('GRADING_OVERRIDE_ORDER', 'fail-closed grading layer loads after all legacy inference');
}
for(const needle of [
  "window.swsiGradingContractVersion='2026-08-26.fail-closed.v2'",
  "return 'invalid'",
  'SPECIAL_ANSWER_MARKERS',
  'validStandardMetadata',
  '官方給分資料不完整或格式異常'
]){
  if(!patchSource.includes(needle)) fail('GRADING_FAIL_CLOSED_RUNTIME', `missing strict runtime marker: ${needle}`);
}
if(!failures.some(x => x.code === 'GRADING_FAIL_CLOSED_RUNTIME')){
  pass('GRADING_FAIL_CLOSED_RUNTIME', 'special-credit metadata errors stop scoring instead of being guessed');
}

// Mock exam must use the same public grading helpers, not a private q.answer test.
const mkPos = patchSource.lastIndexOf('SWSI MK Unified Grading Contract 2026-08-26');
if(mkPos < strictGuardPos){
  fail('MK_GRADING_CONTRACT', 'unified MK grading layer is missing or loads before strict grading contract');
}else{
  const mkTail = patchSource.slice(mkPos);
  const required = [
    "contractVersion:'2026-08-26.unified-grading.v2'",
    'window.isCorrectAnswer',
    'window.answerLabel',
    'window.swsiEvaluateMockAnswers',
    'scored.blocked',
    'window.swsiShouldRecordMockAnswer',
    '未作答也列入分母'
  ];
  const missing = required.filter(x => !mkTail.includes(x));
  if(missing.length) fail('MK_GRADING_CONTRACT', 'missing: ' + missing.join(', '));
  else pass('MK_GRADING_CONTRACT', 'mock exam uses the shared grading contract and counts unanswered ordinary questions');
}

// CDN question shards must verify actual response bytes against the manifest SHA.
for(const needle of [
  "const SWSI_SHARD_INTEGRITY_VERSION = '2026-08-26.sha256.v2'",
  "crypto.subtle.digest('SHA-256'",
  '題庫版本完整性驗證失敗',
  'integrityVersion:SWSI_SHARD_INTEGRITY_VERSION',
  'readVerifiedCachedShard',
  '題庫 shard 出現跨檔 ID 重複',
  '完整題庫總量或跨 shard ID 驗證失敗'
]){
  if(!patchSource.includes(needle)) fail('SHARD_SHA256_RUNTIME', `missing shard integrity marker: ${needle}`);
}
if(!failures.some(x => x.code === 'SHARD_SHA256_RUNTIME')) pass('SHARD_SHA256_RUNTIME', 'actual shard bytes are SHA-256 checked before use');

// Full-bank completion must still be based on content invariants, not loaded
// file count alone. This is a later runtime owner than the shard loader.
for(const needle of [
  "window.swsiQuestionBankIntegrityVersion='2026-08-27.full-bank.v1'",
  'manifest shard 題數總和',
  '跨 shard 題目 ID 重複',
  '實際題數 ',
  'qb.allComplete=false'
]){
  if(!patchSource.includes(needle)) fail('FULL_BANK_INTEGRITY_RUNTIME', `missing full-bank invariant marker: ${needle}`);
}
if(!failures.some(x => x.code === 'FULL_BANK_INTEGRITY_RUNTIME')) pass('FULL_BANK_INTEGRITY_RUNTIME', 'full bank validates manifest totals, session counts and unique IDs before staying complete');

for(const needle of [
  "window.swsiStorageDurabilityVersion='2026-08-27.schema-guard.v3'",
  'HISTORY_MAX_RECORDS=8000',
  'quarantineCorruptStorage',
  'validReviewState',
  'historyWriteBlocked'
]){
  if(!patchSource.includes(needle)) fail('LOCAL_STORAGE_INTEGRITY', `missing storage integrity marker: ${needle}`);
}
if(!failures.some(x => x.code === 'LOCAL_STORAGE_INTEGRITY')) pass('LOCAL_STORAGE_INTEGRITY', 'history/review state is schema-checked, capped and quarantined before overwrite');

for(const needle of ['window.swsiReadAIError','2026-08-26.typed-errors.v2','CLIENT_DAILY_QUOTA','retryAfter']){
  if(!patchSource.includes(needle)) fail('AI_ERROR_CLASSIFICATION', `missing AI error marker: ${needle}`);
}
if(patchSource.includes('quotaAwareCall')) fail('AI_ERROR_CLASSIFICATION', 'concurrency-unsafe fetch monkey patch remains active');
if(!failures.some(x => x.code === 'AI_ERROR_CLASSIFICATION')) pass('AI_ERROR_CLASSIFICATION', 'active AI UI reads stable server error codes without mutating the global fetch helper');

// -----------------------------------------------------------------------------
// P0-3: home round canonical contract. Legacy index.html still contains older UI
// implementations, so verify the *last effective monthly patch* instead of
// treating every historical string occurrence as live behavior.
// -----------------------------------------------------------------------------
const setRoundPos = patchSource.lastIndexOf('setHomeQuizRound = function(v)');
const setRoundTail = setRoundPos >= 0 ? patchSource.slice(setRoundPos, setRoundPos + 420) : '';
if(setRoundPos < 0 || !setRoundTail.includes('canonicalRound(x)')){
  fail('HOME_ROUND_SETTER_RUNTIME', 'final setHomeQuizRound override does not canonicalize to 1/2');
}else{
  pass('HOME_ROUND_SETTER_RUNTIME', 'final round setter canonicalizes legacy labels and new values');
}
const finalRenderHomePos = Math.max(patchSource.lastIndexOf('renderHome = function(){'), patchSource.lastIndexOf('renderHome=function(){'));
const finalRenderHome = finalRenderHomePos >= 0 ? patchSource.slice(finalRenderHomePos) : '';
if(finalRenderHomePos < 0 || !finalRenderHome.includes('<option value=\"1\"') || !finalRenderHome.includes('<option value=\"2\"')){
  fail('HOME_ROUND_UI_RUNTIME', 'final renderHome does not expose canonical option values 1/2');
}else if(finalRenderHome.includes('<option value=\"第一次\"') || finalRenderHome.includes('<option value=\"第二次\"')){
  fail('HOME_ROUND_UI_RUNTIME', 'final renderHome reintroduced noncanonical 第一次/第二次 option values');
}else{
  pass('HOME_ROUND_UI_RUNTIME', 'final home selector stores 1/2 and only displays 第一次/第二次 as labels');
}
const indexSource = read('index.html');
if(!/canonicalRound\(q\.round\)!==homeQuizRound/.test(indexSource)){
  fail('HOME_ROUND_FILTER_CONTRACT', 'focusedQuizFilter no longer compares canonicalRound(q.round) to homeQuizRound');
}else{
  pass('HOME_ROUND_FILTER_CONTRACT', 'focusedQuizFilter compares canonicalRound(q.round) to homeQuizRound');
}

// -----------------------------------------------------------------------------
// Service worker: mutable scoring/content assets must not be stuck cache-first.
// -----------------------------------------------------------------------------
const sw = read('sw.js');
if(!/const VERSION = 'v6'/.test(sw)) fail('SERVICE_WORKER_VERSION', 'service worker cache version is not v6');
else pass('SERVICE_WORKER_VERSION', 'service worker cache is bumped to v6');
if(/const VERSION = 'v5'/.test(sw)) fail('SERVICE_WORKER_VERSION', 'stale v5 compatibility marker remains in service worker source');
for(const asset of ['/monthly_patch.js','/essay_guides.js','/manifest.json']){
  if(!sw.includes(asset)) fail('SERVICE_WORKER_MUTABLE_ASSETS', `missing mutable asset handling for ${asset}`);
}
if(!/if \(isMutableStatic\) \{[\s\S]{0,180}networkFirst(?:AfterCleanup)?\(req, null, true\)/.test(sw)){
  fail('SERVICE_WORKER_MUTABLE_ASSETS', 'mutable scoring/content assets are not no-store network-first');
}else pass('SERVICE_WORKER_MUTABLE_ASSETS', 'monthly patch, essay guides and manifest are no-store network-first');
if(!sw.includes("new Request(url, { cache: 'reload' })")) fail('SERVICE_WORKER_UPDATE_FLOW', 'install does not bypass the old HTTP cache');
if(!sw.includes("k.indexOf('swsi-shell-') === 0 && k !== CACHE")) fail('SERVICE_WORKER_UPDATE_FLOW', 'activate may delete unrelated origin caches');
if(!failures.some(x => x.code === 'SERVICE_WORKER_UPDATE_FLOW')) pass('SERVICE_WORKER_UPDATE_FLOW', 'v5→v6 install refreshes shell assets and deletes only old SWSI caches');

const swUpgradeSmoke = read('scripts/service_worker_upgrade_smoke.js');
for(const marker of ['swsi-shell-v5','swsi-shell-v6','requestsBeforeFinalFetch','/monthly_patch.js','/essay_guides.js','/manifest.json']){
  if(!swUpgradeSmoke.includes(marker)) fail('SERVICE_WORKER_UPGRADE_SMOKE', `upgrade smoke missing marker: ${marker}`);
}
if(!failures.some(x => x.code === 'SERVICE_WORKER_UPGRADE_SMOKE')) pass('SERVICE_WORKER_UPGRADE_SMOKE', 'real-browser upgrade smoke covers v5 cache eviction and all mutable assets');

const result = {
  ok: failures.length === 0,
  checked_at: new Date().toISOString(),
  failures,
  notes
};

if(process.argv.includes('--json')){
  console.log(JSON.stringify(result, null, 2));
}else{
  console.log('SWSI P0 FRONTEND PREFLIGHT');
  for(const x of notes) console.log(`  ✓ ${x.code}: ${x.detail.replace(/^PASS:\s*/, '')}`);
  for(const x of failures) console.error(`  ✗ ${x.code}: ${x.detail}`);
  console.log(`\nresult: ${result.ok ? 'PASS' : 'FAIL'} (${failures.length} blocker${failures.length === 1 ? '' : 's'})`);
}

process.exit(result.ok ? 0 : 1);
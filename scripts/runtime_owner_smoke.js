const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const partsDir = path.join(root, 'monthly_patch_parts');
const files = fs.readdirSync(partsDir).filter(name => name.endsWith('.part')).sort();

function ownersFor(regex) {
  const owners = [];
  for (const file of files) {
    const source = fs.readFileSync(path.join(partsDir, file), 'utf8');
    regex.lastIndex = 0;
    let count = 0;
    while (regex.exec(source)) count += 1;
    for (let i = 0; i < count; i += 1) owners.push(file);
  }
  return owners;
}

function sourceOf(file) {
  return fs.readFileSync(path.join(partsDir, file), 'utf8');
}

function filesContaining(test) {
  return files.filter(file => test(sourceOf(file)));
}

const homeOwners = ownersFor(/\brenderHome\s*=\s*function\b/g);
assert(homeOwners.length >= 1, 'renderHome ownership chain is empty');
assert.strictEqual(
  homeOwners[homeOwners.length - 1],
  '20.product-philosophy.part',
  `unexpected final renderHome owner: ${homeOwners.join(' -> ')}`
);

const canonicalHome = sourceOf('20.product-philosophy.part');
assert(canonicalHome.includes("homeQuizRound=homeQuizRound==='all'?'all':canonicalRound(homeQuizRound)"), 'canonical home owner no longer normalizes homeQuizRound');
assert(canonicalHome.includes('<option value="1"') && canonicalHome.includes('<option value="2"'), 'canonical home owner no longer exposes round values 1/2');

const learningLoop = sourceOf('70.learning-loop.part');
assert(!/\brenderHome\s*=\s*function\b/.test(learningLoop), 'learning-loop must not wrap renderHome');
assert(learningLoop.includes('function decorateHomeProgressEntry()'), 'learning-loop no longer defines the progress-entry enhancer');
assert(learningLoop.includes('decorateWrongCause();decorateHomeProgressEntry();'), 'learning-loop observer no longer runs both DOM enhancers');
assert(learningLoop.includes('swsi-progress-entry'), 'learning-loop no longer owns the progress entry');

const finalRuntime = sourceOf('zzzzzzzzzzzzzzzzzzzzzzzzzzzzzz_final_runtime_contract.part');
assert(!/\brenderHome\s*=\s*function\b/.test(finalRuntime), 'final runtime contract must not wrap renderHome');
assert(finalRuntime.includes('window.swsiShouldRecordMockAnswer=function'), 'final runtime contract lost mock record policy');
assert(finalRuntime.includes("window.swsiFinalRuntimeContractVersion='2026-08-27.v2'"), 'final runtime contract version not updated');

const reviewOwners = ownersFor(/\brenderReview\s*=\s*function\b/g);
assert.deepStrictEqual(
  reviewOwners.slice(-2),
  ['00.part', '70.learning-loop.part'],
  `unexpected final renderReview ownership chain: ${reviewOwners.join(' -> ')}`
);

const normalizeOwners = ownersFor(/\bnormalize\s*=\s*function\b/g);
assert.strictEqual(
  normalizeOwners[normalizeOwners.length - 1],
  '00.part',
  `normalize final owner changed unexpectedly: ${normalizeOwners.join(' -> ')}`
);

const gradingOwners = ownersFor(/function\s+gradingMode\s*\b|(?:^|[^\w])gradingMode\s*=\s*(?:function|strictMode)\b/g);
assert.strictEqual(
  gradingOwners[gradingOwners.length - 1],
  'zzzzzzzzzzzzzzzzzzzzzzzzzz_code_health_p0.part',
  `gradingMode final owner changed unexpectedly: ${gradingOwners.join(' -> ')}`
);

const codeHealth = sourceOf('zzzzzzzzzzzzzzzzzzzzzzzzzz_code_health_p0.part');
assert(!codeHealth.includes('var previousNormalize=normalize;'), 'code-health must not wrap normalize again');
assert(codeHealth.includes('normalize is owned by 00.part'), 'code-health normalize ownership note is missing');
assert(codeHealth.includes('var oldRenderQuiz='), 'late invalid-question render guard disappeared');

const legacyIdOwners = filesContaining(source => source.includes('SWSI_ANY_ANSWER_LEGACY_IDS'));
const legacyAnswerGuessOwners = filesContaining(source => /\/一律給分\|送分\//.test(source));

console.log('RUNTIME OWNER SMOKE OK');
console.log('renderHome: ' + homeOwners.join(' -> '));
console.log('renderReview: ' + reviewOwners.join(' -> '));
console.log('normalize: ' + normalizeOwners.join(' -> '));
console.log('gradingMode: ' + gradingOwners.join(' -> '));
console.log('legacy any-answer ID inference: ' + (legacyIdOwners.join(' -> ') || '(none)'));
console.log('legacy answer-text inference: ' + (legacyAnswerGuessOwners.join(' -> ') || '(none)'));
console.log('debt: gradingMode remains intentionally late-owned until the grading contract itself is consolidated');

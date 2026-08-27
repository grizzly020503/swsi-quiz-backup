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

const homeOwners = ownersFor(/\brenderHome\s*=\s*function\b/g);
assert(homeOwners.length >= 3, `renderHome ownership chain unexpectedly short: ${homeOwners.join(' -> ')}`);

const expectedHomeTail = [
  '20.product-philosophy.part',
  '70.learning-loop.part',
  'zzzzzzzzzzzzzzzzzzzzzzzzzzzzzz_final_runtime_contract.part'
];
assert.deepStrictEqual(
  homeOwners.slice(-expectedHomeTail.length),
  expectedHomeTail,
  `unexpected final renderHome ownership chain: ${homeOwners.join(' -> ')}`
);

const canonicalHome = sourceOf(expectedHomeTail[0]);
assert(canonicalHome.includes("homeQuizRound=homeQuizRound==='all'?'all':canonicalRound(homeQuizRound)"), 'canonical home owner no longer normalizes homeQuizRound');
assert(canonicalHome.includes('<option value="1"') && canonicalHome.includes('<option value="2"'), 'canonical home owner no longer exposes round values 1/2');

const learningLoop = sourceOf(expectedHomeTail[1]);
assert(learningLoop.includes('var oldHome=renderHome;'), 'learning-loop home layer no longer wraps the prior owner explicitly');
assert(learningLoop.includes('swsi-progress-entry'), 'learning-loop home wrapper no longer owns the progress entry');

const finalRuntime = sourceOf(expectedHomeTail[2]);
assert(finalRuntime.includes('var previousRenderHome=renderHome;'), 'final runtime home layer no longer wraps the prior owner explicitly');
assert(finalRuntime.includes('final round selector normalization skipped'), 'final runtime home wrapper no longer owns round-selector normalization');

const reviewOwners = ownersFor(/\brenderReview\s*=\s*function\b/g);
const normalizeOwners = ownersFor(/\bnormalize\s*=\s*function\b/g);

console.log('RUNTIME OWNER SMOKE OK');
console.log('renderHome: ' + homeOwners.join(' -> '));
console.log('renderReview: ' + (reviewOwners.join(' -> ') || '(none)'));
console.log('normalize: ' + (normalizeOwners.join(' -> ') || '(none)'));

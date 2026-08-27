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
assert.strictEqual(homeOwners[homeOwners.length - 1], '20.product-philosophy.part', `unexpected final renderHome owner: ${homeOwners.join(' -> ')}`);

const canonicalHome = sourceOf('20.product-philosophy.part');
assert(canonicalHome.includes("homeQuizRound=homeQuizRound==='all'?'all':canonicalRound(homeQuizRound)"), 'canonical home owner no longer normalizes homeQuizRound');
assert(canonicalHome.includes('<option value="1"') && canonicalHome.includes('<option value="2"'), 'canonical home owner no longer exposes round values 1/2');

const learningLoop = sourceOf('70.learning-loop.part');
assert(!/\brenderHome\s*=\s*function\b/.test(learningLoop), 'learning-loop must not wrap renderHome');
assert(learningLoop.includes('function decorateHomeProgressEntry()'), 'learning-loop no longer defines the progress-entry enhancer');
assert(learningLoop.includes('decorateWrongCause();decorateHomeProgressEntry();'), 'learning-loop observer no longer runs both DOM enhancers');
assert(learningLoop.includes('swsi-progress-entry'), 'learning-loop no longer owns the progress entry');

const finalRuntimePath = 'zzzzzzzzzzzzzzzzzzzzzzzzzzzzzz_final_runtime_contract.part';
assert(!files.includes(finalRuntimePath), 'obsolete final runtime shim must stay deleted');
const lawEscapeShimPath = '85.escape-helper.part';
assert(!files.includes(lawEscapeShimPath), 'obsolete law escape helper shim must stay deleted');
const newResidentStatusShimPath = '87.new-resident-law-status-ui.part';
assert(!files.includes(newResidentStatusShimPath), 'obsolete new resident law status wrapper must stay deleted');
const lawTrustUI = sourceOf('86.law-trust-ui.part');
assert(/function\s+H\s*\(v\)/.test(lawTrustUI), 'law trust UI must own its private escape helper');
assert(!lawTrustUI.includes('window.H='), 'law trust UI must not recreate a global H escape helper');
assert(lawTrustUI.includes("window.SWSI_NEW_RESIDENT_STATUS={version:'SWSI New Resident Basic Act Status Fix 2026-08-26'}"), 'law trust UI lost the new resident status marker');
assert(lawTrustUI.includes("badge.textContent='已制定公布・施行日另定'"), 'law trust UI lost the new resident not-yet-effective badge');
const lawRenderOwners = ownersFor(/\brenderLaws\s*=\s*function\b/g);
assert(!lawRenderOwners.includes(newResidentStatusShimPath), 'new resident status wrapper unexpectedly owns renderLaws again');
const mockPolicyPath = 'zzzzzzzzzzzzzzzzzzzzzzzzzz_mk_record_policy.part';
assert(files.includes(mockPolicyPath), 'mock record policy owner is missing');
const mockPolicy = sourceOf(mockPolicyPath);
assert(mockPolicy.includes('window.swsiShouldRecordMockAnswer=function'), 'mock record policy function is missing');
assert(mockPolicy.includes("window.swsiMockRecordPolicyVersion='2026-08-27.v1'"), 'mock record policy version is missing');
const recordPolicyOwners = ownersFor(/(?:window\.)?swsiShouldRecordMockAnswer\s*=\s*function\b/g);
assert.deepStrictEqual(recordPolicyOwners, [mockPolicyPath], `unexpected mock record policy owners: ${recordPolicyOwners.join(' -> ')}`);

const reviewOwners = ownersFor(/\brenderReview\s*=\s*function\b/g);
assert.deepStrictEqual(reviewOwners.slice(-2), ['00.part', '70.learning-loop.part'], `unexpected final renderReview ownership chain: ${reviewOwners.join(' -> ')}`);

const normalizeOwners = ownersFor(/\bnormalize\s*=\s*function\b/g);
assert.strictEqual(normalizeOwners[normalizeOwners.length - 1], '00.part', `normalize final owner changed unexpectedly: ${normalizeOwners.join(' -> ')}`);

const gradingOwners = ownersFor(/function\s+gradingMode\s*\b|(?:^|[^\w])gradingMode\s*=\s*(?:function|strictMode)\b/g);
assert.strictEqual(gradingOwners[gradingOwners.length - 1], '00.part', `gradingMode final owner changed unexpectedly: ${gradingOwners.join(' -> ')}`);

const codeHealth = sourceOf('zzzzzzzzzzzzzzzzzzzzzzzzzz_code_health_p0.part');
assert(!codeHealth.includes('var previousNormalize=normalize;'), 'code-health must not wrap normalize again');
assert(codeHealth.includes('normalize is owned by 00.part'), 'code-health normalize ownership note is missing');
assert(!codeHealth.includes('function strictMode'), 'code-health must not redefine gradingMode');
assert(!codeHealth.includes('function strictCorrect'), 'code-health must not redefine isCorrectAnswer');
assert(!codeHealth.includes('function strictLabel'), 'code-health must not redefine answerLabel');
assert(codeHealth.includes('var baseAcceptedAnswers='), 'invalid accepted-answer edge guard disappeared');
assert(codeHealth.includes("gradingMode(item)==='invalid'"), 'accepted-answer edge guard no longer fails closed');
assert(codeHealth.includes('var oldRenderQuiz='), 'late invalid-question render guard disappeared');

const legacyIdOwners = filesContaining(source => source.includes('SWSI_ANY_ANSWER_LEGACY_IDS'));
const legacyAnswerGuessOwners = filesContaining(source => /\/一律給分\|送分\//.test(source));
assert.deepStrictEqual(legacyIdOwners, [], `legacy any-answer ID inference remains: ${legacyIdOwners.join(' -> ')}`);
assert.deepStrictEqual(legacyAnswerGuessOwners, [], `legacy answer-text inference remains: ${legacyAnswerGuessOwners.join(' -> ')}`);

const essayNavigationPath = 'zzz_fix_essay_navigation.part';
const essayOpenOwners = ownersFor(/(?:window\.)?swsiOpenEssay\s*=\s*(?:async\s+)?function\b/g);
assert.deepStrictEqual(essayOpenOwners, [essayNavigationPath], `unexpected swsiOpenEssay ownership chain: ${essayOpenOwners.join(' -> ')}`);
const essayNavigation = sourceOf(essayNavigationPath);
assert(essayNavigation.includes('await loadAutoEssays();'), 'canonical essay navigation lost slow/cache reload recovery');
assert(essayNavigation.includes('renderEssaySafely();'), 'canonical essay navigation lost render retry boundary');
assert(essayNavigation.includes('markEssayTab();'), 'canonical essay navigation lost tab state handling');
assert(essayNavigation.includes('resetEssayState();'), 'canonical essay navigation lost product reset policy');

// Deliberate late product/runtime owners. Keep these visible so future cleanup
// does not mistake intentional ownership for a removable shim.
const mkOwners = ownersFor(/(?:window\.)?\bMK\s*=\s*(?![=])/g);
assert.deepStrictEqual(mkOwners, ['zzzzzzzzzzzzzzzzzzzzzzzzzzz_mk_grading_contract.part'], `unexpected MK ownership chain: ${mkOwners.join(' -> ')}`);

const aiGuardrailsPath = '99_p0_mobile_ai_guardrails.part';
const stableClientShimPath = 'zz_p0_stable_ai_client_id.part';
assert(!files.includes(stableClientShimPath), 'obsolete stable AI client shim must stay deleted');
const aiGuardrails = sourceOf(aiGuardrailsPath);
assert(!/(?:window\.)?aiFeedbackHTML\s*=\s*function\b/.test(aiGuardrails), 'mobile AI guardrails must not own essay feedback UI');
assert(!/(?:window\.)?runAIFeedback\s*=\s*(?:async\s+)?function\b/.test(aiGuardrails), 'mobile AI guardrails must not own runAIFeedback');
assert(!/(?:window\.)?gradePhoto\s*=\s*(?:async\s+)?function\b/.test(aiGuardrails), 'mobile AI guardrails must not own gradePhoto');
assert(aiGuardrails.includes('window.swsiGetClientId=function'), 'mobile AI utilities lost stable client id helper');
assert(aiGuardrails.includes("headers.set('X-SWSI-Client-ID',window.swsiGetClientId())"), 'AI timeout helper no longer attaches stable client id');
assert(aiGuardrails.includes('window.swsiFetchWithTimeout=async function'), 'mobile AI guardrails lost timeout helper');
assert(aiGuardrails.includes('window.swsiSetAIBusy=function'), 'mobile AI guardrails lost busy-state helper');
const clientIdOwners = ownersFor(/(?:window\.)?swsiGetClientId\s*=\s*function\b/g);
assert.deepStrictEqual(clientIdOwners, [aiGuardrailsPath], `unexpected swsiGetClientId owners: ${clientIdOwners.join(' -> ')}`);
const timeoutOwners = ownersFor(/(?:window\.)?swsiFetchWithTimeout\s*=\s*(?:async\s+)?function\b/g);
assert.deepStrictEqual(timeoutOwners, [aiGuardrailsPath], `unexpected swsiFetchWithTimeout owners: ${timeoutOwners.join(' -> ')}`);

const aiUIOwners = ownersFor(/function\s+aiFeedbackHTML\s*\b|(?:window\.)?aiFeedbackHTML\s*=\s*function\b/g);
assert.strictEqual(aiUIOwners[aiUIOwners.length - 1], '99z.essay-trust-layer.part', `unexpected final aiFeedbackHTML owner: ${aiUIOwners.join(' -> ')}`);

const aiFeedbackOwners = ownersFor(/function\s+runAIFeedback\s*\b|(?:window\.)?runAIFeedback\s*=\s*(?:async\s+)?function\b/g);
assert.deepStrictEqual(aiFeedbackOwners.slice(-2), ['00.part', '99z.essay-trust-layer.part'], `unexpected runAIFeedback ownership chain: ${aiFeedbackOwners.join(' -> ')}`);

const photoGradeOwners = ownersFor(/function\s+gradePhoto\s*\b|(?:window\.)?gradePhoto\s*=\s*(?:async\s+)?function\b/g);
assert.deepStrictEqual(photoGradeOwners.slice(-2), ['00.part', '99z.essay-trust-layer.part'], `unexpected gradePhoto ownership chain: ${photoGradeOwners.join(' -> ')}`);

console.log('RUNTIME OWNER SMOKE OK');
console.log('renderHome: ' + homeOwners.join(' -> '));
console.log('renderReview: ' + reviewOwners.join(' -> '));
console.log('normalize: ' + normalizeOwners.join(' -> '));
console.log('gradingMode: ' + gradingOwners.join(' -> '));
console.log('law render owners: ' + lawRenderOwners.join(' -> '));
console.log('law escape helper: 86.law-trust-ui.part (private)');
console.log('new resident law status: 86.law-trust-ui.part');
console.log('mock record policy: ' + recordPolicyOwners.join(' -> '));
console.log('essay navigation: ' + essayOpenOwners.join(' -> '));
console.log('MK: ' + mkOwners.join(' -> '));
console.log('stable client id: ' + clientIdOwners.join(' -> '));
console.log('AI timeout helper: ' + timeoutOwners.join(' -> '));
console.log('aiFeedbackHTML: ' + aiUIOwners.join(' -> '));
console.log('runAIFeedback: ' + aiFeedbackOwners.join(' -> '));
console.log('gradePhoto: ' + photoGradeOwners.join(' -> '));
console.log('legacy any-answer ID inference: (none)');
console.log('legacy answer-text inference: (none)');
console.log('grading edge guard: acceptedAnswers(invalid) remains late fail-closed without taking grading ownership');

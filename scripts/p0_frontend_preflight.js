const fs = require('fs');
const path = require('path');

const ROOT = process.cwd();
const read = p => fs.readFileSync(path.resolve(ROOT, p), 'utf8');
const failures = [];
const notes = [];

function fail(code, detail){ failures.push({ code, detail }); }
function note(code, detail){ notes.push({ code, detail }); }

// P0-1: duplicate ESSAY_GUIDES keys must not be allowed to silently overwrite.
const essaySource = read('essay_guides.js');
const keyRe = /"((?:社會工作|社會工作直接服務|社會政策與社會立法|人類行為與社會環境|社會工作研究方法)-\d{3}-[12]-申論\d+)"\s*:/g;
const counts = new Map();
let m;
while((m = keyRe.exec(essaySource))){
  counts.set(m[1], (counts.get(m[1]) || 0) + 1);
}
const duplicates = [...counts.entries()].filter(([, n]) => n > 1);
if(duplicates.length){
  fail('ESSAY_GUIDE_DUPLICATE_KEY', duplicates.map(([id,n]) => `${id} x${n}`).join(', '));
}else{
  note('ESSAY_GUIDE_DUPLICATE_KEY', 'PASS: no duplicate historical essay IDs found in essay_guides.js');
}

// P0-2: special grading must be explicit. Never infer give-credit semantics from legacy IDs or answer text.
const gradingSource = read('monthly_patch_parts/00.part');
if(/SWSI_ANY_ANSWER_LEGACY_IDS/.test(gradingSource)){
  fail('GRADING_LEGACY_ID_INFERENCE', 'monthly_patch_parts/00.part still contains SWSI_ANY_ANSWER_LEGACY_IDS');
}else{
  note('GRADING_LEGACY_ID_INFERENCE', 'PASS: no legacy-ID grading inference');
}
if(/一律給分\|送分/.test(gradingSource) || /\/一律給分\|送分\//.test(gradingSource)){
  fail('GRADING_ANSWER_TEXT_INFERENCE', 'grading_mode is still inferred from answer text such as 一律給分／送分');
}else{
  note('GRADING_ANSWER_TEXT_INFERENCE', 'PASS: no grading inference from answer text');
}
if(/grading_mode\s*=.*gradingMode\(/s.test(gradingSource) || /q\.grading_mode[\s\S]{0,260}gradingMode\(/.test(gradingSource)){
  fail('NORMALIZE_GRADING_INFERENCE', 'normalize() still falls back to gradingMode(...) instead of preserving explicit mode / failing closed for special cases');
}else{
  note('NORMALIZE_GRADING_INFERENCE', 'PASS: normalize() does not synthesize grading_mode by inference');
}

// P0-3: home round selector must use the same canonical values as focusedQuizFilter/canonicalRound.
const indexSource = read('index.html');
const badRoundOption = /<option value=\\?"第一次\\?"[^>]*>第一次<\/option>|<option value=\\?"第二次\\?"[^>]*>第二次<\/option>/;
const badRoundState = /homeQuizRound===['"]第一次['"]|homeQuizRound===['"]第二次['"]/;
if(badRoundOption.test(indexSource) || badRoundState.test(indexSource)){
  fail('HOME_ROUND_NONCANONICAL_VALUE', 'index.html still contains a home round selector/state using 第一次／第二次 instead of canonical 1／2');
}else{
  note('HOME_ROUND_NONCANONICAL_VALUE', 'PASS: home round UI uses canonical values');
}
if(!/canonicalRound\(q\.round\)!==homeQuizRound/.test(indexSource)){
  fail('HOME_ROUND_FILTER_CONTRACT', 'focusedQuizFilter no longer visibly compares canonicalRound(q.round) to homeQuizRound; review contract');
}else{
  note('HOME_ROUND_FILTER_CONTRACT', 'PASS: focusedQuizFilter compares canonicalRound(q.round) to homeQuizRound');
}

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

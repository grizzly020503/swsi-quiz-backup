const fs = require('fs');

const path = 'supabase/functions/import-moex-social-worker/index.ts';
const src = fs.readFileSync(path, 'utf8');
const failures = [];
const need = s => { if(!src.includes(s)) failures.push(`missing marker: ${s}`); };

for (const marker of [
  'swsi-supabase-moex-importer/1.5',
  'const REPO_ID = 1345053575',
  'verifyGitHubRepoWriteToken',
  'Number(repo?.id) === REPO_ID',
  'repo?.permissions?.push === true',
  'GitHub token lacks write access to the SWSI repository',
  'function assertSameIdentity',
  '["source_exam_code", incoming.source_exam_code, existing.source_exam_code]',
  '["year", String(incoming.year ?? ""), String(existing.year ?? "")]',
  '["round", incoming.round, existing.round]',
  '["subject", incoming.subject, existing.subject]',
  '["qno", String(incoming.qno ?? ""), String(existing.qno ?? "")]',
  'questions preflight read',
  'essays preflight read',
  'No writes occur above this line',
  'ID collision'
]) need(marker);

if(src.includes('repo?.private === true')) {
  failures.push('private-repo readability must not be used as importer authentication');
}

const qPreflight = src.indexOf('questions preflight read');
const ePreflight = src.indexOf('essays preflight read');
const qGuard = src.indexOf('assertSameIdentity("選擇題"');
const eGuard = src.indexOf('assertSameIdentity("申論題"');
const firstQuestionWrite = src.indexOf('.from("questions").upsert');
const firstEssayWrite = src.indexOf('.from("essays").upsert');

if(qPreflight < 0 || ePreflight < 0 || qGuard < 0 || eGuard < 0) {
  failures.push('identity preflight blocks are incomplete');
}
if(firstQuestionWrite < 0 || firstEssayWrite < 0) {
  failures.push('expected importer upserts are missing');
}
if(qPreflight >= firstQuestionWrite || ePreflight >= firstQuestionWrite || qGuard >= firstQuestionWrite || eGuard >= firstQuestionWrite) {
  failures.push('an importer write occurs before the complete question+essay identity preflight');
}

if(failures.length){
  console.error('MOEX IMPORTER INTEGRITY SMOKE FAIL');
  for(const f of failures) console.error(' - '+f);
  process.exit(1);
}

console.log('MOEX IMPORTER INTEGRITY SMOKE OK');

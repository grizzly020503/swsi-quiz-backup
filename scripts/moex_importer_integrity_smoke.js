const fs = require('fs');

const path = 'supabase/functions/import-moex-social-worker/index.ts';
const src = fs.readFileSync(path, 'utf8');
const workflow = fs.readFileSync('.github/workflows/moex-social-worker-sync.yml', 'utf8');
const oidc = fs.readFileSync('supabase/functions/_shared/github_actions_oidc.ts', 'utf8');
const failures = [];
const need = s => { if(!src.includes(s)) failures.push(`missing marker: ${s}`); };

for (const marker of [
  'verifyGitHubActionsOidcToken',
  'IMPORT_SYNC_POLICY',
  'moex-social-worker-sync.yml@refs/heads/main',
  'new Set(["schedule", "workflow_dispatch", "push"])',
  'GitHub Actions OIDC authorization rejected',
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

for (const forbidden of [
  'verifyGitHubRepoWriteToken',
  'permissions?.push',
  'api.github.com/repos/',
  'repo?.private === true'
]) {
  if(src.includes(forbidden)) failures.push(`legacy or weak importer auth remains: ${forbidden}`);
}

for (const marker of [
  'GITHUB_ACTIONS_OIDC_ISSUER = "https://token.actions.githubusercontent.com"',
  'SWSI_SYNC_AUDIENCE = "swsi-supabase-sync"',
  'SWSI_REPOSITORY_ID = "1345053575"',
  'algorithms: ["RS256"]'
]) {
  if(!oidc.includes(marker)) failures.push(`shared OIDC verifier missing: ${marker}`);
}

for (const marker of [
  'Import only changed verified exams to Supabase with GitHub OIDC',
  'ACTIONS_ID_TOKEN_REQUEST_TOKEN',
  'ACTIONS_ID_TOKEN_REQUEST_URL',
  'audience=swsi-supabase-sync',
  'https://yumjtrdctaxyczpspuyo.supabase.co/functions/v1/import-moex-social-worker'
]) {
  if(!workflow.includes(marker)) failures.push(`MOEX workflow importer OIDC marker missing: ${marker}`);
}
if(workflow.includes('GH_REPO_TOKEN: ${{ github.token }}')) failures.push('MOEX writer steps must not use legacy GH_REPO_TOKEN auth');
if(workflow.includes('SUPABASE_SERVICE_ROLE_KEY')) failures.push('service-role secret must not enter MOEX workflow');

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

console.log('MOEX IMPORTER INTEGRITY + OIDC SMOKE OK');

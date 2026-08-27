#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');

const importer = fs.readFileSync('supabase/functions/import-moex-social-worker/index.ts', 'utf8');
const recoveryAlignment = fs.readFileSync(
  'supabase/migrations/20260827031000_align_recovery_reset_with_grading_mode.sql',
  'utf8'
);

for (const marker of [
  'swsi-supabase-moex-importer/1.4',
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
]) {
  assert(importer.includes(marker), `importer integrity marker missing: ${marker}`);
}

const questionPreflight = importer.indexOf('questions preflight read');
const essayPreflight = importer.indexOf('essays preflight read');
const questionGuard = importer.indexOf('assertSameIdentity("選擇題"');
const essayGuard = importer.indexOf('assertSameIdentity("申論題"');
const firstWrite = Math.min(
  importer.indexOf('.from("questions").upsert'),
  importer.indexOf('.from("essays").upsert')
);
assert(questionPreflight >= 0 && essayPreflight >= 0, 'importer preflight reads are incomplete');
assert(questionGuard >= 0 && essayGuard >= 0, 'importer identity guards are incomplete');
assert(firstWrite > questionPreflight && firstWrite > essayPreflight, 'importer writes before all existing IDs are read');
assert(firstWrite > questionGuard && firstWrite > essayGuard, 'importer writes before all identity checks finish');

for (const marker of [
  'create or replace function public.reset_ai_analysis_on_official_change()',
  'new.grading_mode is distinct from old.grading_mode',
  'before update of question, opt_a, opt_b, opt_c, opt_d, answer, accepted_answers, grading_mode',
  'for each row execute function public.reset_ai_analysis_on_official_change()'
]) {
  assert(recoveryAlignment.includes(marker), `recovery alignment marker missing: ${marker}`);
}
assert(
  /security definer\s+set search_path to ''/m.test(recoveryAlignment),
  'recovery trigger function must pin an empty search_path'
);

console.log('SUPABASE IMPORTER / RECOVERY DRIFT CONTRACT OK');

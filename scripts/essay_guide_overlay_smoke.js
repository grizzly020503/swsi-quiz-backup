#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const vm = require('vm');
const cp = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const OVERLAY = path.join(ROOT, 'data/essay_guide_overlay.json');
const AUTO = path.join(ROOT, 'auto/essays_auto.json');
const INCOMING = path.join(ROOT, 'incoming/115100.json');
const BUILDER = path.join(ROOT, 'scripts/build_essay_guides_runtime.js');
const LEGACY = path.join(ROOT, 'essay_guides.js');

function readJson(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }
function sessionOf(id) {
  const m = String(id).match(/^E-(\d{3})-([12])-(?:HBSE|SW|DS|R|SP)-[12]$/);
  return m ? `${m[1]}-${m[2]}` : null;
}
function sorted(values) { return [...values].sort(); }

const overlay = readJson(OVERLAY);
const autoRows = readJson(AUTO);
const incoming = readJson(INCOMING);
assert.strictEqual(overlay.schema_version, 1);
assert(Array.isArray(overlay.coverage_sessions) && overlay.coverage_sessions.length > 0);
assert(Array.isArray(overlay.records));
assert(Array.isArray(overlay.held_for_review));

const autoById = new Map(autoRows.map(row => [String(row.id), row]));
const incomingById = new Map((incoming.essays || []).map(row => [String(row.id), row]));
const recordIds = overlay.records.map(row => String(row.id));
const holdIds = overlay.held_for_review.map(row => String(row.id));
assert.strictEqual(new Set(recordIds).size, recordIds.length, 'duplicate published guide IDs');
assert.strictEqual(new Set(holdIds).size, holdIds.length, 'duplicate held guide IDs');
for (const id of recordIds) assert(!holdIds.includes(id), `published/held overlap: ${id}`);

for (const session of overlay.coverage_sessions) {
  const officialIds = autoRows.map(row => String(row.id)).filter(id => sessionOf(id) === session);
  const covered = [...recordIds, ...holdIds].filter(id => sessionOf(id) === session);
  assert.deepStrictEqual(sorted(covered), sorted(officialIds), `${session} overlay must partition every official auto essay into published or held`);
}

for (const row of overlay.records) {
  const id = String(row.id);
  assert(autoById.has(id), `overlay target missing from auto essays: ${id}`);
  assert(incomingById.has(id), `overlay target missing from official incoming payload: ${id}`);
  assert.strictEqual(autoById.get(id).q, incomingById.get(id).q, `official question text drifted: ${id}`);
  assert.strictEqual(row.review_status, 'verified', `${id} must be verified before runtime publication`);
  assert.strictEqual(row.is_official, false, `${id} must remain explicitly non-official`);
  assert(Array.isArray(row.review_sources) && row.review_sources.length >= 2, `${id} review sources missing`);
  assert(row.review_sources.some(source => /考選部/.test(source)), `${id} official source missing`);
  assert(/非考選部官方標準答案/.test(row.guide_source || ''), `${id} non-official provenance missing`);
}
for (const row of overlay.held_for_review) {
  assert(autoById.has(String(row.id)), `held target missing from auto essays: ${row.id}`);
  assert(String(row.reason || '').trim().length >= 12, `held reason too vague: ${row.id}`);
}

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'swsi-essay-guides-'));
const runtime = path.join(tmp, 'essay_guides.js');
cp.execFileSync('node', [BUILDER, LEGACY, runtime, OVERLAY], { cwd: ROOT, stdio: 'inherit' });
const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(runtime, 'utf8'), sandbox, { filename: runtime, timeout: 5000 });
const guides = sandbox.window.ESSAY_GUIDES || {};
for (const id of recordIds) {
  assert(guides[id], `published overlay missing from generated runtime: ${id}`);
  assert.strictEqual(guides[id].review_status, 'verified', `generated review status mismatch: ${id}`);
  assert.strictEqual(guides[id].is_official, false, `generated official flag mismatch: ${id}`);
}
for (const id of holdIds) assert(!guides[id], `held guide leaked into student runtime: ${id}`);

// Fail-closed mutation test: an unverified record must never enter the student
// runtime. When held items still exist, promote one illegally; once coverage is
// fully verified, replace one verified record with an unverified version instead.
const tampered = JSON.parse(JSON.stringify(overlay));
const held = tampered.held_for_review.shift();
let tamperedId;
if (held) {
  tamperedId = held.id;
} else {
  const verified = tampered.records.shift();
  assert(verified, 'overlay must contain at least one verified record for fail-closed mutation test');
  tamperedId = verified.id;
}
tampered.records.push({
  id: tamperedId,
  kao: 'tamper', dati: 'tamper', biaoti: ['a', 'b'], kw: ['a', 'b', 'c'],
  review_status: 'needs_review', reviewed_at: '2026-10-02', review_batch: 'tamper',
  review_sources: ['考選部 tamper', 'tamper source'], is_official: false,
  guide_source: 'SWSI tamper，非考選部官方標準答案'
});
const tamperedPath = path.join(tmp, 'tampered.json');
fs.writeFileSync(tamperedPath, JSON.stringify(tampered), 'utf8');
const bad = cp.spawnSync('node', [BUILDER, LEGACY, path.join(tmp, 'bad.js'), tamperedPath], { cwd: ROOT, encoding: 'utf8' });
assert.notStrictEqual(bad.status, 0, 'builder must reject non-verified student guide publication');
assert(/review_status must be verified/.test((bad.stderr || '') + (bad.stdout || '')), 'expected fail-closed review-status error');

console.log(
  `ESSAY GUIDE OVERLAY CONTRACT OK: sessions=${overlay.coverage_sessions.join(',')}; ` +
  `verified=${recordIds.length}; held=${holdIds.length}; official_question_text_unchanged=yes`
);
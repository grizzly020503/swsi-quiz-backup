#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { loadHistoricalVerifiedRegistry } = require('./historical_essay_verified_registry');

const ROOT = path.resolve(__dirname, '..');
const runtimePath = process.argv[2] || path.join(ROOT, '_site', 'essay_guides.js');

function fail(message) {
  throw new Error(`historical essay runtime smoke: ${message}`);
}

function sameArray(actual, expected) {
  return Array.isArray(actual) &&
    actual.length === expected.length &&
    actual.every((value, index) => value === expected[index]);
}

if (!fs.existsSync(runtimePath)) fail(`runtime file missing: ${runtimePath}`);

const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(runtimePath, 'utf8'), sandbox, {
  filename: runtimePath,
  timeout: 5000
});

const guides = sandbox.window.ESSAY_GUIDES;
if (!guides || typeof guides !== 'object' || Array.isArray(guides)) {
  fail('runtime did not expose window.ESSAY_GUIDES');
}

const registry = loadHistoricalVerifiedRegistry(ROOT);
let checked = 0;
for (const row of registry.records) {
  const guide = guides[row.id];
  if (!guide) fail(`verified guide missing from runtime: ${row.id}`);
  if (guide.kao !== row.kao) fail(`${row.id}: kao differs from verified audit`);
  if (guide.dati !== row.dati) fail(`${row.id}: dati differs from verified audit`);
  if (!sameArray(guide.biaoti, row.biaoti)) fail(`${row.id}: biaoti differs from verified audit`);
  if (!sameArray(guide.kw, row.kw)) fail(`${row.id}: kw differs from verified audit projection`);
  if (guide.review_status !== 'verified') fail(`${row.id}: review_status is not verified`);
  if (guide.is_official !== false) fail(`${row.id}: is_official must remain false`);
  if (guide.reviewed_at !== row.reviewed_at) fail(`${row.id}: reviewed_at mismatch`);
  if (guide.review_batch !== row.review_batch) fail(`${row.id}: review_batch mismatch`);
  if (guide.guide_source !== row.guide_source) fail(`${row.id}: guide_source mismatch`);
  checked += 1;
}

if (checked !== registry.records.length) {
  fail(`checked ${checked} but registry contains ${registry.records.length}`);
}

console.log(
  `HISTORICAL ESSAY VERIFIED RUNTIME OK: ${checked} audit-verified guides projected exactly into ${runtimePath}`
);

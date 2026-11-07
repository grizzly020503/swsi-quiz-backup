#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { expectedPapers } = require('./future_exam_public_source_contract');
const registry = JSON.parse(fs.readFileSync(
  path.join(__dirname, '../data/moex_source_subjects.v1.json'), 'utf8'));

function manifest(with116) {
  const shards = [];
  for (let y = 104; y <= 115; y++) for (const round of [1, 2]) {
    shards.push({ year: String(y), round: round === 1 ? '第一次' : '第二次',
      file: y + '-' + round + '.json', question_count: 200 });
  }
  if (with116) shards.push({year: '116', round: '第一次',
    file: '116-1.json', question_count: 200});
  return {schema_version: 1, shard_count: shards.length,
    baseline_shard_count: 24, total_questions: shards.length * 200, shards};
}
function reject(fn) {
  assert.throws(fn, assert.AssertionError);
}
let historic = expectedPapers(registry, manifest(false));
assert.equal(historic.total, 4800);
assert.equal(historic.papers.length, 120);
let next = expectedPapers(registry, manifest(true));
assert.equal(next.total, 5000);
assert.equal(next.papers.length, 125);
assert.equal(next.papers.filter(x => x.session === '116-1').length, 5);
assert(next.papers.filter(x => x.session === '116-1')
  .every(x => x.code === '116030' && x.c === '103' && /^030[1-5]$/.test(x.s)));

let bad = manifest(true);
bad.shards[0] = {...bad.shards[0], file: '116-1.json'};
reject(() => expectedPapers(registry, bad));
bad = manifest(true);
bad.shards[0] = {...bad.shards[0], question_count: 199};
reject(() => expectedPapers(registry, bad));
bad = manifest(true);
bad.shards[24] = {...bad.shards[24], year: '115'};
reject(() => expectedPapers(registry, bad));
bad = manifest(true);
bad.total_questions = 4800;
reject(() => expectedPapers(registry, bad));
console.log('FUTURE PUBLIC BROWSER SOURCE CONTRACT PASS: 120 pinned historical + 5 future PDFs, 5000 MCQs; drift blocked');

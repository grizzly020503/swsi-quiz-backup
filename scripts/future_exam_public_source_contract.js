#!/usr/bin/env node
'use strict';
// A public, read-only source-identity contract for historical and future exams.
// Historical 120 official PDFs remain pinned; approved same-shape future exams
// inherit only the reviewed five subject code identities from 115-2.
const assert = require('node:assert/strict');

function expectedPapers(registry, manifest) {
  assert.equal(registry?.scope, 'source_identity_only_not_stem_answer_or_rubric_approval');
  assert(Array.isArray(registry.records) && registry.records.length === 120,
    'historical 120 PDF identity registry must remain pinned');
  const shards = manifest?.shards;
  assert.equal(manifest?.schema_version, 1, 'manifest schema');
  assert(Array.isArray(shards) && shards.length >= 24, 'missing baseline manifests');
  assert.equal(manifest.shard_count, shards.length, 'shard count does not match');
  assert.equal(manifest.baseline_shard_count, 24, 'historical baseline changed');
  const baseline = new Set();
  for (let year = 104; year <= 115; year++) for (const round of [1, 2]) {
    baseline.add(year + '-' + round + '.json');
  }
  const seen = new Set();
  const future = [];
  let total = 0;
  for (const shard of shards) {
    const name = shard?.file;
    assert(typeof name === 'string' && /^\d{3}-[12]\.json$/.test(name),
      'invalid exam shard name');
    assert(!seen.has(name), 'duplicate exam shard name');
    seen.add(name);
    assert.equal(shard.question_count, 200, 'approved current structure needs 200 MCQ');
    total += shard.question_count;
    const year = Number(name.slice(0, 3));
    const round = Number(name.charAt(4));
    assert.equal(String(shard.year), String(year), 'year identity');
    assert.equal(shard.round, round === 1 ? '第一次' : '第二次', 'round identity');
    if (year >= 116) future.push({ session: year + '-' + round,
      exam_code: String(year) + (round === 1 ? '030' : '100') });
  }
  for (const name of baseline) assert(seen.has(name), 'missing pinned historical exam ' + name);
  assert.equal(manifest.total_questions, total, 'manifest question total differs');
  assert.equal(total, shards.length * 200, 'approved session count arithmetic');

  const historical = registry.records.map(r => ({
    session: r.session, subject: r.subject, code: String(r.exam_code),
    c: String(r.c), s: String(r.s)
  }));
  const latestTemplates = historical.filter(r => r.session === '115-2');
  assert.equal(latestTemplates.length, 5, 'approved 115-2 five-subject adapter missing');
  assert.equal(new Set(latestTemplates.map(r => r.subject)).size, 5,
    'approved subject identities ambiguous');
  assert(latestTemplates.every(x => x.code === '115100'), 'current profile anchor drift');
  const newlyExpected = future.flatMap(candidate => latestTemplates.map(src => ({
    session: candidate.session, subject: src.subject, code: candidate.exam_code,
    c: src.c, s: src.s
  })));
  const keys = [...historical, ...newlyExpected].map(x => x.session + '|' + x.subject);
  assert.equal(new Set(keys).size, keys.length, 'duplicate session/subject official identity');
  assert.equal(keys.length * 40, total, 'official paper total mismatches manifest');
  return { papers: [...historical, ...newlyExpected], total };
}
module.exports = { expectedPapers };

import assert from 'node:assert/strict';
import {
  parseCouncilTask,
  findExistingResult,
  findActiveClaim,
  claimMarker,
  resultMarker,
  RESULT_MARKER_PREFIX,
  CLAIM_MARKER_PREFIX,
} from '../lib/task.mjs';
import { _test as agyTest } from '../adapters/antigravity.mjs';

const issue = {
  number: 123,
  url: 'https://github.com/example/repo/issues/123',
  title: '[Council Task] Review parser contract',
  body: `Please review the parser contract.\n\n<!-- swsi-council-task\n${JSON.stringify({
    schema_version: 1,
    task_id: 'council-20261002-001',
    mode: 'important',
    action: 'review',
    base_ref: 'main',
    base_sha: 'abcdef1234567',
    related_issue: 99,
  }, null, 2)}\n-->`,
};

const task = parseCouncilTask(issue);
assert.equal(task.task_id, 'council-20261002-001');
assert.equal(task.issue_number, 123);
assert.equal(task.human_body, 'Please review the parser contract.');

const claim = claimMarker({ taskId: task.task_id, relayId: 'relay-a', baseSha: 'abcdef1234567', at: '2026-10-02T12:00:00Z' });
assert.equal(findActiveClaim([{ body: claim, createdAt: '2026-10-02T12:00:00Z' }], task.task_id, Date.parse('2026-10-02T12:30:00Z'), 60 * 60 * 1000).marker.relay_id, 'relay-a');
assert.equal(findActiveClaim([{ body: claim, createdAt: '2026-10-02T12:00:00Z' }], task.task_id, Date.parse('2026-10-02T14:30:00Z'), 60 * 60 * 1000), null);

const result = { verdict: 'PASS', summary: 'ok', findings: [], evidence_freshness: [], recommended_next_action: 'none' };
const marker = resultMarker({ taskId: task.task_id, adapter: 'gemini-antigravity', baseSha: 'abcdef1234567', result });
assert.ok(marker.startsWith(RESULT_MARKER_PREFIX));
assert.ok(findExistingResult([{ body: marker }], task.task_id, 'gemini-antigravity'));
assert.ok(claim.startsWith(CLAIM_MARKER_PREFIX));

const terminal = agyTest.parseTerminalResult([
  JSON.stringify({ event: 'init', init: { cwd: '/tmp' } }),
  JSON.stringify({ event: 'step_update', step_update: { state: 'DONE' } }),
  JSON.stringify({ event: 'result', result: { status: 'SUCCESS', structured_output: result } }),
].join('\n'));
assert.equal(terminal.status, 'SUCCESS');
assert.equal(terminal.structured_output.verdict, 'PASS');

assert.throws(() => parseCouncilTask({ ...issue, body: '<!-- swsi-council-task {"schema_version":2} -->' }), /missing task_id|unsupported task schema/);
const unsafeRefIssue = {
  ...issue,
  body: issue.body.replace('"base_ref": "main"', '"base_ref": "main;rm-all"'),
};
assert.throws(() => parseCouncilTask(unsafeRefIssue), /invalid base_ref/);
const unsafeTaskIdIssue = {
  ...issue,
  body: issue.body.replace('council-20261002-001', 'bad task id'),
};
assert.throws(() => parseCouncilTask(unsafeTaskIdIssue), /invalid task_id/);

console.log('SWSI Council Relay selftest: PASS');

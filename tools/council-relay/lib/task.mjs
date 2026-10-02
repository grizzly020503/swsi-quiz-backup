import crypto from 'node:crypto';

export const TASK_TITLE_PREFIX = '[Council Task]';
export const TASK_MARKER_START = '<!-- swsi-council-task';
export const TASK_MARKER_END = '-->';
export const RESULT_MARKER_PREFIX = '<!-- swsi-council-result ';
export const CLAIM_MARKER_PREFIX = '<!-- swsi-council-claim ';

function extractJsonComment(body, prefix) {
  const text = String(body ?? '');
  const start = text.indexOf(prefix);
  if (start < 0) return null;
  const jsonStart = start + prefix.length;
  const end = text.indexOf(TASK_MARKER_END, jsonStart);
  if (end < 0) throw new Error(`unterminated marker: ${prefix}`);
  const raw = text.slice(jsonStart, end).trim();
  if (!raw) throw new Error(`empty marker payload: ${prefix}`);
  return JSON.parse(raw);
}

export function parseCouncilTask(issue) {
  if (!issue || typeof issue !== 'object') throw new Error('issue object required');
  if (!String(issue.title ?? '').startsWith(TASK_TITLE_PREFIX)) return null;

  const payload = extractJsonComment(issue.body, TASK_MARKER_START);
  if (!payload) throw new Error(`Council task issue #${issue.number} is missing task marker`);

  const required = ['schema_version', 'task_id', 'mode', 'action', 'base_ref', 'base_sha'];
  for (const field of required) {
    if (payload[field] === undefined || payload[field] === null || payload[field] === '') {
      throw new Error(`Council task ${payload.task_id ?? issue.number} missing ${field}`);
    }
  }
  if (payload.schema_version !== 1) throw new Error(`unsupported task schema: ${payload.schema_version}`);
  if (!['normal', 'important', 'high_risk'].includes(payload.mode)) throw new Error(`invalid mode: ${payload.mode}`);
  if (payload.action !== 'review') throw new Error(`Phase 1 supports action=review only, got ${payload.action}`);
  if (!/^[0-9a-f]{7,40}$/i.test(String(payload.base_sha))) throw new Error(`invalid base_sha: ${payload.base_sha}`);
  if (!/^[A-Za-z0-9][A-Za-z0-9._\/-]{0,120}$/.test(String(payload.base_ref))
      || String(payload.base_ref).includes('..')
      || String(payload.base_ref).includes('//')
      || String(payload.base_ref).endsWith('/')
      || String(payload.base_ref).endsWith('.lock')) {
    throw new Error(`invalid base_ref: ${payload.base_ref}`);
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$/.test(String(payload.task_id))) {
    throw new Error(`invalid task_id: ${payload.task_id}`);
  }

  return {
    ...payload,
    issue_number: Number(issue.number),
    issue_url: String(issue.url ?? ''),
    issue_title: String(issue.title ?? ''),
    human_body: String(issue.body ?? '').replace(/<!-- swsi-council-task[\s\S]*?-->/, '').trim(),
  };
}

export function parseMachineMarker(body, prefix) {
  try {
    return extractJsonComment(body, prefix);
  } catch {
    return null;
  }
}

export function findExistingResult(comments, taskId, adapter) {
  for (const comment of comments ?? []) {
    const marker = parseMachineMarker(comment.body, RESULT_MARKER_PREFIX);
    if (marker?.task_id === taskId && marker?.adapter === adapter && marker?.status === 'done') {
      return { marker, comment };
    }
  }
  return null;
}

export function findActiveClaim(comments, taskId, nowMs = Date.now(), ttlMs = 2 * 60 * 60 * 1000) {
  let newest = null;
  for (const comment of comments ?? []) {
    const marker = parseMachineMarker(comment.body, CLAIM_MARKER_PREFIX);
    if (marker?.task_id !== taskId || marker?.status !== 'claimed') continue;
    const at = Date.parse(marker.at ?? comment.createdAt ?? '');
    if (!Number.isFinite(at)) continue;
    if (!newest || at > newest.at) newest = { marker, comment, at };
  }
  if (!newest) return null;
  return nowMs - newest.at < ttlMs ? newest : null;
}

export function claimMarker({ taskId, relayId, baseSha, at = new Date().toISOString() }) {
  return `${CLAIM_MARKER_PREFIX}${JSON.stringify({
    schema_version: 1,
    task_id: taskId,
    relay_id: relayId,
    status: 'claimed',
    base_sha: baseSha,
    at,
  })} -->`;
}

export function resultMarker({ taskId, adapter, baseSha, result }) {
  const digest = crypto.createHash('sha256').update(JSON.stringify(result)).digest('hex');
  return `${RESULT_MARKER_PREFIX}${JSON.stringify({
    schema_version: 1,
    task_id: taskId,
    adapter,
    status: 'done',
    base_sha: baseSha,
    result_sha256: digest,
    at: new Date().toISOString(),
  })} -->`;
}

export function renderReviewComment({ task, adapter, baseSha, result, envelopeMeta = {} }) {
  const findings = Array.isArray(result.findings) ? result.findings : [];
  const evidence = Array.isArray(result.evidence_freshness) ? result.evidence_freshness : [];
  const lines = [
    `## Council Review — ${adapter}`,
    '',
    `- Task: \`${task.task_id}\``,
    `- Mode: \`${task.mode}\``,
    `- Exact reviewed base: \`${baseSha}\``,
    `- Verdict: **${result.verdict}**`,
    envelopeMeta.conversation_id ? `- Antigravity conversation: \`${envelopeMeta.conversation_id}\`` : null,
    envelopeMeta.duration_seconds != null ? `- Duration: ${envelopeMeta.duration_seconds}s` : null,
    '',
    '### Summary',
    '',
    String(result.summary ?? '').trim() || '_No summary returned._',
    '',
    '### Findings',
    '',
  ].filter((x) => x !== null);

  if (!findings.length) {
    lines.push('_No findings._', '');
  } else {
    findings.forEach((finding, index) => {
      lines.push(
        `${index + 1}. **[${finding.severity ?? 'INFO'}] ${finding.title ?? 'Finding'}**`,
        `   - Evidence: ${finding.evidence ?? 'Not supplied'}`,
        `   - Why it matters: ${finding.rationale ?? 'Not supplied'}`,
        `   - Recommendation: ${finding.recommendation ?? 'Not supplied'}`,
        '',
      );
    });
  }

  lines.push('### Evidence freshness', '');
  if (!evidence.length) {
    lines.push('_No structured evidence freshness records returned._', '');
  } else {
    evidence.forEach((item) => {
      const bits = [
        `source=${item.source ?? 'unknown'}`,
        `freshness=${item.freshness ?? 'unknown'}`,
        item.timestamp ? `timestamp=${item.timestamp}` : null,
        item.sha ? `sha=${item.sha}` : null,
      ].filter(Boolean);
      lines.push(`- ${bits.join(' | ')}`);
    });
    lines.push('');
  }

  lines.push(
    '### Recommended next action',
    '',
    String(result.recommended_next_action ?? '').trim() || '_None supplied._',
    '',
    '<details><summary>Structured result</summary>',
    '',
    '```json',
    JSON.stringify(result, null, 2),
    '```',
    '',
    '</details>',
    '',
    resultMarker({ taskId: task.task_id, adapter, baseSha, result }),
  );

  return lines.join('\n');
}

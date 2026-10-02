#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runProcess, runJson } from './lib/process.mjs';
import {
  TASK_TITLE_PREFIX,
  parseCouncilTask,
  findExistingResult,
  findActiveClaim,
  claimMarker,
  renderReviewComment,
} from './lib/task.mjs';
import { ADAPTER_ID, reviewWithAntigravity } from './adapters/antigravity.mjs';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_CONFIG = {
  repository: 'grizzly020503/swsi-quiz-backup',
  workspace: process.env.SWSI_COUNCIL_WORKSPACE || '',
  ghCommand: process.env.SWSI_COUNCIL_GH_CMD || 'gh',
  agyCommand: process.env.SWSI_COUNCIL_AGY_CMD || 'agy',
  pollSeconds: Number(process.env.SWSI_COUNCIL_POLL_SECONDS || 120),
  reviewTimeoutMinutes: Number(process.env.SWSI_COUNCIL_REVIEW_TIMEOUT_MINUTES || 15),
  claimTtlMinutes: Number(process.env.SWSI_COUNCIL_CLAIM_TTL_MINUTES || 120),
  relayId: process.env.SWSI_COUNCIL_RELAY_ID || `${os.hostname()}-${os.userInfo().username}`,
  maxIssueScan: Number(process.env.SWSI_COUNCIL_MAX_ISSUES || 100),
};

function log(message, details = null) {
  const prefix = `[${new Date().toISOString()}]`;
  process.stdout.write(`${prefix} ${message}${details ? ` ${JSON.stringify(details)}` : ''}\n`);
}

function configPathFromArgs(argv) {
  const i = argv.indexOf('--config');
  return i >= 0 ? argv[i + 1] : process.env.SWSI_COUNCIL_CONFIG || '';
}

function loadConfig(argv) {
  const configPath = configPathFromArgs(argv);
  let fileConfig = {};
  if (configPath) {
    fileConfig = JSON.parse(fs.readFileSync(path.resolve(configPath), 'utf8'));
  }
  const cfg = { ...DEFAULT_CONFIG, ...fileConfig };
  if (!cfg.workspace) throw new Error('workspace is required (config.workspace or SWSI_COUNCIL_WORKSPACE)');
  cfg.workspace = path.resolve(cfg.workspace);
  cfg.schemaPath = path.join(ROOT, 'schemas', 'review-result.schema.json');
  return cfg;
}

async function ghJson(cfg, args) {
  return (await runJson(cfg.ghCommand, [...args, '--repo', cfg.repository], { timeoutMs: 60_000 })).json;
}

async function ghComment(cfg, issueNumber, body) {
  const result = await runProcess(cfg.ghCommand, [
    'issue', 'comment', String(issueNumber), '--repo', cfg.repository, '--body-file', '-',
  ], { input: body, timeoutMs: 60_000 });
  if (result.code !== 0) throw new Error(`gh issue comment failed: ${result.stderr.trim()}`);
}

async function listTaskIssues(cfg) {
  const issues = await ghJson(cfg, [
    'issue', 'list', '--state', 'open', '--limit', String(cfg.maxIssueScan),
    '--json', 'number,title,body,url,updatedAt',
  ]);
  return (issues ?? []).filter((issue) => String(issue.title ?? '').startsWith(TASK_TITLE_PREFIX));
}

async function loadComments(cfg, issueNumber) {
  const issue = await ghJson(cfg, [
    'issue', 'view', String(issueNumber), '--json', 'comments',
  ]);
  return issue.comments ?? [];
}

async function git(cfg, args, timeoutMs = 120_000) {
  const result = await runProcess('git', ['-C', cfg.workspace, ...args], { timeoutMs });
  if (result.code !== 0) throw new Error(`git ${args.join(' ')} failed: ${result.stderr.trim()}`);
  return result.stdout.trim();
}

async function prepareWorkspace(cfg, task) {
  if (!fs.existsSync(path.join(cfg.workspace, '.git'))) {
    throw new Error(`workspace is not a Git repository: ${cfg.workspace}`);
  }
  const dirty = await git(cfg, ['status', '--porcelain']);
  if (dirty) throw new Error('relay workspace is dirty; refusing to review against mixed local state');

  await git(cfg, ['fetch', '--prune', 'origin']);
  const remoteSha = await git(cfg, ['rev-parse', `origin/${task.base_ref}`]);
  if (!remoteSha.startsWith(task.base_sha) && !task.base_sha.startsWith(remoteSha)) {
    throw new Error(`task base_sha ${task.base_sha} no longer matches origin/${task.base_ref} ${remoteSha}`);
  }

  // Dedicated read-only workspace: safe to detach exactly to the reviewed remote SHA.
  await git(cfg, ['checkout', '--detach', remoteSha]);
  const head = await git(cfg, ['rev-parse', 'HEAD']);
  return { remoteSha, head };
}

async function fetchRelatedIssue(cfg, relatedIssue) {
  if (!relatedIssue) return null;
  try {
    return await ghJson(cfg, [
      'issue', 'view', String(relatedIssue), '--json', 'number,title,body,url,comments,updatedAt',
    ]);
  } catch (error) {
    return { error: error.message, number: relatedIssue };
  }
}

function buildReviewPrompt({ task, workspaceState, relatedIssue }) {
  const related = relatedIssue
    ? JSON.stringify({
        number: relatedIssue.number,
        title: relatedIssue.title,
        body: relatedIssue.body,
        url: relatedIssue.url,
        updatedAt: relatedIssue.updatedAt,
        comments: (relatedIssue.comments ?? []).slice(-20).map((c) => ({
          author: c.author?.login ?? c.author?.name ?? 'unknown',
          body: c.body,
          createdAt: c.createdAt,
        })),
        error: relatedIssue.error,
      }, null, 2)
    : 'null';

  return `You are the read-only reviewer for SWSI Council task ${task.task_id}.

HARD SAFETY BOUNDARY FOR THIS PHASE:
- READ ONLY. Do not modify, create, delete, rename, or format any repository file.
- Do not run deployment, push, merge, commit, checkout, package installation, or paid API/service activation.
- Do not change production systems.
- Do not attempt to bypass permissions.
- Use the repository files available in this workspace as read-only evidence.
- If evidence is missing, return EVIDENCE_MISSING or BLOCKED rather than guessing.

Before concluding, read at minimum:
1. AGENTS.md
2. AI_PROJECT_CONTEXT.md
3. PROJECT_HANDOFF.md
4. AI_COLLABORATION.md
5. docs/AI_COUNCIL_RELAY_ARCHITECTURE.md (if present)
6. files relevant to the task

Evidence freshness:
- workspace exact HEAD: ${workspaceState.head}
- origin/${task.base_ref}: ${workspaceState.remoteSha}
- task requested base_sha: ${task.base_sha}
- evidence timestamp: ${new Date().toISOString()}
- Treat docs/handoffs as snapshots when they conflict with current source.

TASK BODY:
${task.human_body || '(no human-readable body)'}

RELATED ISSUE SNAPSHOT (provided by the relay; do not assume it is newer than the timestamp shown):
${related}

Review the task independently. Do not assume another AI's conclusion is correct. Distinguish facts from suggestions. Return only the structured result required by the JSON schema.`;
}

async function processTask(cfg, issue) {
  const task = parseCouncilTask(issue);
  if (!task) return { skipped: true, reason: 'not a council task' };

  const comments = await loadComments(cfg, task.issue_number);
  if (findExistingResult(comments, task.task_id, ADAPTER_ID)) {
    return { skipped: true, reason: 'already completed', taskId: task.task_id };
  }

  const activeClaim = findActiveClaim(
    comments,
    task.task_id,
    Date.now(),
    cfg.claimTtlMinutes * 60_000,
  );
  if (activeClaim && activeClaim.marker.relay_id !== cfg.relayId) {
    return { skipped: true, reason: `claimed by ${activeClaim.marker.relay_id}`, taskId: task.task_id };
  }

  const workspaceState = await prepareWorkspace(cfg, task);
  await ghComment(cfg, task.issue_number, [
    'Council Relay claimed this read-only review task.',
    '',
    `- Relay: \`${cfg.relayId}\``,
    `- Exact base: \`${workspaceState.head}\``,
    '',
    claimMarker({ taskId: task.task_id, relayId: cfg.relayId, baseSha: workspaceState.head }),
  ].join('\n'));

  const relatedIssue = await fetchRelatedIssue(cfg, task.related_issue);
  const prompt = buildReviewPrompt({ task, workspaceState, relatedIssue });
  const { result, meta } = await reviewWithAntigravity({
    workspace: cfg.workspace,
    prompt,
    schemaPath: cfg.schemaPath,
    command: cfg.agyCommand,
    timeoutMs: cfg.reviewTimeoutMinutes * 60_000,
  });

  const comment = renderReviewComment({
    task,
    adapter: ADAPTER_ID,
    baseSha: workspaceState.head,
    result,
    envelopeMeta: meta,
  });
  await ghComment(cfg, task.issue_number, comment);
  return { skipped: false, taskId: task.task_id, verdict: result.verdict };
}

async function runOnce(cfg) {
  const issues = await listTaskIssues(cfg);
  log(`found ${issues.length} open Council task issue(s)`);
  for (const issue of issues) {
    try {
      const outcome = await processTask(cfg, issue);
      log(`issue #${issue.number}`, outcome);
    } catch (error) {
      log(`issue #${issue.number} failed`, { error: error.message });
      try {
        await ghComment(cfg, issue.number, [
          '## Council Relay — BLOCKED',
          '',
          'The local read-only relay could not complete this task.',
          '',
          `Reason: \`${String(error.message).replaceAll('`', "'")}\``,
          '',
          'No implementation/deploy action was attempted.',
        ].join('\n'));
      } catch {
        // Keep the original error in local log if GitHub is unavailable.
      }
    }
  }
}

async function acquireLock() {
  const base = process.env.LOCALAPPDATA || os.tmpdir();
  const dir = path.join(base, 'SWSI', 'CouncilRelay');
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, 'relay.lock');
  try {
    const fd = fs.openSync(file, 'wx');
    fs.writeFileSync(fd, JSON.stringify({ pid: process.pid, startedAt: new Date().toISOString() }));
    const release = () => { try { fs.closeSync(fd); } catch {} try { fs.unlinkSync(file); } catch {} };
    process.on('exit', release);
    process.on('SIGINT', () => { release(); process.exit(130); });
    process.on('SIGTERM', () => { release(); process.exit(143); });
    return release;
  } catch (error) {
    if (error.code === 'EEXIST') throw new Error(`relay lock already exists: ${file}`);
    throw error;
  }
}

async function main() {
  const argv = process.argv.slice(2);
  const once = argv.includes('--once') || !argv.includes('--watch');
  const cfg = loadConfig(argv);
  const release = await acquireLock();
  try {
    do {
      await runOnce(cfg);
      if (once) break;
      await new Promise((resolve) => setTimeout(resolve, cfg.pollSeconds * 1000));
    } while (true);
  } finally {
    release();
  }
}

if (import.meta.url === `file://${process.argv[1]?.replaceAll('\\\\', '/')}` || process.argv[1]?.endsWith('relay.mjs')) {
  main().catch((error) => {
    log('fatal relay error', { error: error.message });
    process.exitCode = 1;
  });
}

export const _test = { buildReviewPrompt };

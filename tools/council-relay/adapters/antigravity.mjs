import path from 'node:path';
import { runProcess } from '../lib/process.mjs';

export const ADAPTER_ID = 'gemini-antigravity';

function parseTerminalResult(ndjson) {
  let terminal = null;
  for (const rawLine of String(ndjson ?? '').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    let event;
    try {
      event = JSON.parse(line);
    } catch {
      continue;
    }
    if (event.event === 'result' && event.result) terminal = event.result;
  }
  if (!terminal) throw new Error('Antigravity stream did not contain a terminal result event');
  return terminal;
}

export async function reviewWithAntigravity({
  workspace,
  prompt,
  schemaPath,
  command = 'agy',
  timeoutMs = 15 * 60 * 1000,
}) {
  const schema = path.resolve(schemaPath);
  const args = [
    '--input-format', 'stream-json',
    '--output-format', 'stream-json',
    '--mode=plan',
    '--json-schema', schema,
    '--print-timeout', `${Math.ceil(timeoutMs / 60000)}m`,
    '--cwd', path.resolve(workspace),
  ];

  const input = JSON.stringify({
    event: 'user',
    message: { content: prompt },
  }) + '\n';

  const processResult = await runProcess(command, args, {
    cwd: workspace,
    input,
    timeoutMs: timeoutMs + 30_000,
  });

  if (processResult.code !== 0) {
    const error = new Error(processResult.timedOut
      ? 'Antigravity review timed out'
      : `Antigravity review failed (${processResult.code}): ${processResult.stderr.trim()}`);
    error.processResult = processResult;
    throw error;
  }

  const terminal = parseTerminalResult(processResult.stdout);
  if (terminal.status !== 'SUCCESS') {
    throw new Error(`Antigravity terminal status ${terminal.status}: ${terminal.error ?? 'unknown error'}`);
  }
  if (!terminal.structured_output || typeof terminal.structured_output !== 'object') {
    throw new Error('Antigravity did not return structured_output');
  }

  return {
    result: terminal.structured_output,
    meta: {
      conversation_id: terminal.conversation_id,
      duration_seconds: terminal.duration_seconds,
      usage: terminal.usage,
    },
  };
}

export const _test = { parseTerminalResult };

import { spawn } from 'node:child_process';

export function runProcess(command, args = [], options = {}) {
  const {
    cwd,
    env = process.env,
    input = null,
    timeoutMs = 5 * 60 * 1000,
    shell = process.platform === 'win32',
  } = options;

  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd,
      env,
      shell,
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill();
    }, timeoutMs);

    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('error', (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on('close', (code, signal) => {
      clearTimeout(timer);
      resolve({ code, signal, stdout, stderr, timedOut });
    });

    if (input != null) child.stdin.write(input);
    child.stdin.end();
  });
}

export async function runJson(command, args, options = {}) {
  const result = await runProcess(command, args, options);
  if (result.code !== 0) {
    const message = result.timedOut
      ? `${command} timed out`
      : `${command} exited ${result.code}: ${result.stderr.trim()}`;
    const error = new Error(message);
    error.processResult = result;
    throw error;
  }
  try {
    return { ...result, json: JSON.parse(result.stdout) };
  } catch (cause) {
    const error = new Error(`${command} returned invalid JSON`);
    error.cause = cause;
    error.processResult = result;
    throw error;
  }
}

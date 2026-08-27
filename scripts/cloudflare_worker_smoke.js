#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const { webcrypto } = require('crypto');

function makeDb(mode = 'ok') {
  return {
    prepare(sql) {
      return {
        bind() {
          return {
            async first() {
              if (mode === 'failure') throw new Error('simulated D1 outage');
              if (/FROM ai_daily_global_usage/.test(sql) && mode === 'globalFull') {
                return { text_count: 50, photo_count: 10 };
              }
              return null;
            },
            async run() {
              if (/INSERT INTO ai_daily_client_usage/.test(sql) && mode === 'clientFull') return { meta: { changes: 0 } };
              return { meta: { changes: 1 } };
            }
          };
        }
      };
    },
    async batch() { return []; }
  };
}

function request(body) {
  return new Request('https://worker.test/', {
    method: 'POST',
    headers: {
      Origin: 'https://swsi-quiznetlify.netlify.app',
      'Content-Type': 'application/json',
      'X-SWSI-Client-ID': 'swsi_worker_smoke_client_20260826'
    },
    body: JSON.stringify(body)
  });
}

(async () => {
  let upstreamStatus = 200;
  let upstreamPayload = null;
  const context = {
    crypto: webcrypto,
    Request,
    Response,
    Headers,
    URL,
    TextEncoder,
    Intl,
    Date,
    console,
    fetch: async (_url, options) => {
      upstreamPayload = JSON.parse(options.body);
      if (upstreamStatus === 429) return new Response('{}', { status: 429, headers: { 'retry-after': '17' } });
      return new Response(JSON.stringify({ choices: [{ message: { content: 'ok' } }] }), { status: 200 });
    }
  };
  const source = fs.readFileSync('cloudflare/wandering-wave-4418/worker.js', 'utf8')
    .replace(/^export default /, 'globalThis.worker = ');
  vm.runInNewContext(source, context, { filename: 'worker.js' });
  const worker = context.worker;

  function env(overrides = {}) {
    return {
      SWSI_INTERNAL_KEY: 'internal-secret',
      GROQ_KEY: 'groq-secret',
      AI_RATE_LIMIT: { async limit() { return { success: true }; } },
      AI_IP_LIMIT: { async limit() { return { success: true }; } },
      AI_QUOTA_DB: makeDb(),
      ...overrides
    };
  }
  const body = {
    model: 'qwen/qwen3.6-27b',
    messages: [{ role: 'user', content: 'test' }],
    temperature: 0,
    max_tokens: 200
  };

  let response = await worker.fetch(new Request('https://worker.test/', {
    method:'POST',
    headers:{Origin:'https://attacker.invalid','Content-Type':'application/json'},
    body:JSON.stringify(body)
  }), env());
  assert.strictEqual(response.status, 403);
  assert.strictEqual(response.headers.get('cache-control'), 'no-store');

  response = await worker.fetch(request(body), env({
    AI_RATE_LIMIT: { async limit() { return { success: false }; } }
  }));
  assert.strictEqual(response.status, 429);
  assert.strictEqual((await response.json()).error.code, 'CLIENT_MINUTE_RATE_LIMIT');
  assert.strictEqual(response.headers.get('retry-after'), '60');

  response = await worker.fetch(request(body), env({
    AI_IP_LIMIT: { async limit() { return { success: false }; } }
  }));
  assert.strictEqual((await response.json()).error.code, 'IP_MINUTE_RATE_LIMIT');

  response = await worker.fetch(request(body), env({ AI_QUOTA_DB: makeDb('clientFull') }));
  assert.strictEqual((await response.json()).error.code, 'CLIENT_DAILY_QUOTA');
  assert(Number(response.headers.get('retry-after')) > 0);

  response = await worker.fetch(request(body), env({ AI_QUOTA_DB: makeDb('globalFull') }));
  assert.strictEqual((await response.json()).error.code, 'GLOBAL_DAILY_QUOTA');

  response = await worker.fetch(request(body), env({ AI_QUOTA_DB: makeDb('failure') }));
  assert.strictEqual(response.status, 503);
  assert.strictEqual((await response.json()).error.code, 'QUOTA_SERVICE_UNAVAILABLE');

  response = await worker.fetch(request(body), env());
  assert.strictEqual(response.status, 200);
  assert.strictEqual(upstreamPayload.temperature, 0, 'explicit temperature=0 was not preserved');
  assert.strictEqual(response.headers.get('cache-control'), 'no-store');

  upstreamStatus = 429;
  response = await worker.fetch(request({ ...body, temperature: null }), env());
  const upstreamError = await response.json();
  assert.strictEqual(upstreamError.error.code, 'UPSTREAM_RATE_LIMIT');
  assert.strictEqual(response.headers.get('retry-after'), '17');
  assert.strictEqual(upstreamPayload.temperature, 0.4, 'null temperature should use the safe default');

  console.log('CLOUDFLARE WORKER SMOKE OK');
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

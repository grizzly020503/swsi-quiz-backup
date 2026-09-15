#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const { webcrypto } = require('crypto');

function makeDb(mode = 'ok') {
  const db = {
    telemetryWrites: 0,
    prepare(sql) {
      return {
        async run() {
          if (mode === 'failure') throw new Error('simulated D1 outage');
          return { meta: { changes: 1 } };
        },
        bind() {
          return {
            async first() {
              if (mode === 'failure') throw new Error('simulated D1 outage');
              if (/FROM ai_daily_global_usage/.test(sql) && mode === 'globalFull') {
                return { text_count: 50, photo_count: 10 };
              }
              if (/FROM ai_telemetry_hourly/.test(sql)) {
                return {
                  requests: 5,
                  successes: 4,
                  rate_limited: 1,
                  service_errors: 0,
                  client_rejected: 0,
                  total_latency_ms: 5000,
                  max_latency_ms: 2000,
                  last_bucket: '2026-09-15T14:00:00Z'
                };
              }
              return null;
            },
            async run() {
              if (/INSERT INTO ai_daily_client_usage/.test(sql) && mode === 'clientFull') return { meta: { changes: 0 } };
              if (/INSERT INTO ai_telemetry_hourly/.test(sql)) db.telemetryWrites++;
              return { meta: { changes: 1 } };
            }
          };
        }
      };
    },
    async batch() { return []; }
  };
  return db;
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

  let response;

  response = await worker.fetch(new Request('https://worker.test/api/ai-health', {
    method: 'GET'
  }), env());
  assert.strictEqual(response.status, 200);
  const health = await response.json();
  assert.strictEqual(health.enabled, true);
  assert.strictEqual(health.status, 'ok');
  assert.strictEqual(health.window_hours, 24);
  assert.strictEqual(health.requests, 5);
  assert.strictEqual(health.successes, 4);
  assert.strictEqual(health.rate_limited, 1);
  assert.strictEqual(health.service_errors, 0);
  assert.strictEqual(health.avg_latency_ms, 1000);

  response = await worker.fetch(new Request('https://worker.test/', {
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

  const telemetryDb = makeDb();
  response = await worker.fetch(request(body), env({ AI_QUOTA_DB: telemetryDb }));
  assert.strictEqual(response.status, 200);
  assert.strictEqual(upstreamPayload.temperature, 0, 'explicit temperature=0 was not preserved');
  assert.strictEqual(response.headers.get('cache-control'), 'no-store');
  assert(telemetryDb.telemetryWrites >= 1, 'successful public AI request did not record telemetry');

  upstreamStatus = 429;
  response = await worker.fetch(request({ ...body, temperature: null }), env());
  const upstreamError = await response.json();
  assert.strictEqual(upstreamError.error.code, 'UPSTREAM_RATE_LIMIT');
  assert.strictEqual(response.headers.get('retry-after'), '17');
  assert.strictEqual(upstreamPayload.temperature, 0.4, 'null temperature should use the safe default');

  console.log('CLOUDFLARE WORKER SMOKE OK — quota + AI telemetry health');
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

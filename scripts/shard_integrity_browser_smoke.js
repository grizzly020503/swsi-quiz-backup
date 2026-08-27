#!/usr/bin/env node
'use strict';

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const base = process.argv[2] || 'http://127.0.0.1:4173/';
const cdnHost = 'wandering-wave-4418.c022050333.workers.dev';
const cdnPrefix = '/question-shards/';
const shardDir = path.resolve(process.cwd(), 'cdn/question-shards');
const manifestBytes = fs.readFileSync(path.join(shardDir, 'manifest.json'));
const manifest = JSON.parse(manifestBytes.toString('utf8'));
const meta = manifest.shards.find(row => row.file === '115-2.json');
const shardBytes = fs.readFileSync(path.join(shardDir, '115-2.json'));

assert(meta, '115-2 shard metadata is missing');
assert.strictEqual(
  crypto.createHash('sha256').update(shardBytes).digest('hex'),
  meta.sha256,
  'checked-in shard bytes do not match the checked-in manifest'
);

async function runCase(browser, options = {}) {
  const { tampered = false, offlineShard = false, seedLegacyCache = false } = options;
  const context = await browser.newContext();
  const page = await context.newPage();
  const localOrigin = new URL(base).origin;
  const pageErrors = [];
  page.on('pageerror', err => pageErrors.push(String(err && err.message || err)));

  await page.route('**/*', route => {
    const requestUrl = new URL(route.request().url());
    if (requestUrl.hostname === cdnHost && requestUrl.pathname.startsWith(cdnPrefix)) {
      const name = decodeURIComponent(requestUrl.pathname.slice(cdnPrefix.length));
      if (name === 'manifest.json') {
        return route.fulfill({status:200,contentType:'application/json; charset=utf-8',body:manifestBytes});
      }
      if (name === meta.file) {
        if (offlineShard) {
          return route.fulfill({status:503,contentType:'application/json; charset=utf-8',body:'{}'});
        }
        const body = tampered ? Buffer.concat([shardBytes, Buffer.from(' ')]) : shardBytes;
        return route.fulfill({status:200,contentType:'application/json; charset=utf-8',body});
      }
      return route.fulfill({status:404,contentType:'application/json',body:'{}'});
    }
    if (requestUrl.origin !== localOrigin) return route.abort();
    return route.continue();
  });

  await page.goto(base, {waitUntil:'commit',timeout:20000});
  await page.waitForFunction(
    () => typeof window.loadQuestionManifest === 'function' && typeof window.loadQuestionShard === 'function',
    null,
    {timeout:30000}
  );

  const outcome = await page.evaluate(async ({file,seedLegacyCache,legacyPayload,expectedSha}) => {
    const manifestValue = await window.loadQuestionManifest();
    const shardMeta = manifestValue.shards.find(row => row.file === file);

    if(seedLegacyCache){
      const db = await new Promise((resolve,reject) => {
        const request = indexedDB.open('swsi-quiz-offline');
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      try{
        await new Promise((resolve,reject) => {
          const tx = db.transaction('cache','readwrite');
          tx.objectStore('cache').put({
            payload:legacyPayload,
            sha256:expectedSha,
            verified_sha256:true,
            savedAt:Date.now()
          },'question-shard:'+file);
          tx.oncomplete=resolve;
          tx.onerror=()=>reject(tx.error);
          tx.onabort=()=>reject(tx.error);
        });
      }finally{db.close();}
    }

    let error = '';
    try {
      await window.loadQuestionShard(shardMeta);
    } catch (err) {
      error = String(err && err.message || err);
    }

    async function readRecord() {
      const db = await new Promise((resolve,reject) => {
        const request = indexedDB.open('swsi-quiz-offline');
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      try {
        return await new Promise((resolve,reject) => {
          const tx = db.transaction('cache','readonly');
          const request = tx.objectStore('cache').get('question-shard:'+file);
          request.onsuccess = () => resolve(request.result || null);
          request.onerror = () => reject(request.error);
        });
      } finally {
        db.close();
      }
    }

    let record = null;
    for (let i=0;i<40;i++) {
      record = await readRecord();
      if (record || error) break;
      await new Promise(resolve => setTimeout(resolve,50));
    }
    return {
      error,
      loaded: !!(window.SWSI_QB && window.SWSI_QB.loadedFiles.has(file)),
      integrityVersion: record && record.integrityVersion,
      sha256: record && record.sha256,
      rawByteLength: record && record.rawBytes && record.rawBytes.byteLength,
      recordExists: !!record
    };
  }, {
    file:meta.file,
    seedLegacyCache,
    legacyPayload:seedLegacyCache?JSON.parse(shardBytes.toString('utf8')):null,
    expectedSha:meta.sha256
  });

  assert.deepStrictEqual(pageErrors, [], 'browser errors: '+pageErrors.join(' | '));
  await context.close();
  return outcome;
}

(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const valid = await runCase(browser);
    assert.strictEqual(valid.error, '');
    assert.strictEqual(valid.loaded, true, 'valid shard was not loaded');
    assert.strictEqual(valid.integrityVersion, '2026-08-26.sha256.v2');
    assert.strictEqual(valid.sha256, meta.sha256);
    assert.strictEqual(valid.rawByteLength, shardBytes.length);

    const invalid = await runCase(browser, {tampered:true});
    assert.match(invalid.error, /題庫版本完整性驗證失敗/);
    assert.strictEqual(invalid.loaded, false, 'tampered shard reached the active question bank');
    assert.strictEqual(invalid.recordExists, false, 'tampered shard was written to IndexedDB');

    const legacy = await runCase(browser, {offlineShard:true,seedLegacyCache:true});
    assert.notStrictEqual(legacy.error, '', 'offline loader accepted a legacy self-asserted hash record');
    assert.strictEqual(legacy.loaded, false, 'legacy payload-only cache reached the active question bank');
    assert.strictEqual(legacy.recordExists, true, 'legacy fixture was not seeded');
    assert.strictEqual(legacy.integrityVersion, undefined, 'legacy fixture unexpectedly acquired verified provenance');
    assert.strictEqual(legacy.rawByteLength, undefined, 'legacy fixture unexpectedly acquired source bytes');
  } finally {
    await browser.close();
  }
  console.log('SHARD INTEGRITY BROWSER SMOKE OK');
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

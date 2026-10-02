#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const input = process.argv[2] || 'essay_guides.js';
const output = process.argv[3] || '_site/essay_guides.js';
const overlayInput = process.argv[4] || 'data/essay_guide_overlay.json';
const source = fs.readFileSync(input, 'utf8');

const legacyIdRe = /^(?:社會工作|社會工作直接服務|社會政策與社會立法|人類行為與社會環境|社會工作研究方法)-\d{3}-[12]-申論\d+$/;
const autoIdRe = /^E-(\d{3})-([12])-(HBSE|SW|DS|R|SP)-([12])$/;
const keyRe = /"((?:社會工作|社會工作直接服務|社會政策與社會立法|人類行為與社會環境|社會工作研究方法)-\d{3}-[12]-申論\d+)"\s*:/g;
const counts = new Map();
let m;
while ((m = keyRe.exec(source))) counts.set(m[1], (counts.get(m[1]) || 0) + 1);

const duplicates = [...counts.entries()].filter(([, n]) => n > 1);
if (duplicates.length) {
  throw new Error('ESSAY_GUIDES duplicate key(s): ' + duplicates.map(([id,n]) => `${id} x${n}`).join(', '));
}
const VERIFIED_107_1_ID = '社會工作-107-1-申論2';

const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(source, sandbox, { filename: input, timeout: 5000 });
const guides = sandbox.window.ESSAY_GUIDES;
if (!guides || typeof guides !== 'object' || Array.isArray(guides)) {
  throw new Error('essay_guides.js did not produce window.ESSAY_GUIDES object');
}

/*
 * 107-1 社會工作申論第 2 題的官方題幹要求同時說明並整合：
 * 1) 認知行為學派 2) 社會支持理論 3) 優勢觀點。
 * Legacy source 曾以「增強權能」與「優勢／復原力」兩個 generic template
 * 重複使用同一 key；兩者都沒有完整回答官方三理論要求。
 */
guides[VERIFIED_107_1_ID] = {
  kao: '考認知行為學派、社會支持理論與優勢觀點三種理論的核心重點，並能在同一服務案例中說明三者如何互補運用。',
  dati: '先分三段準確界定三個觀點，再用一個具體案例整合：認知行為處理不利認知與行為循環；社會支持盤點並連結正式／非正式支持；優勢觀點從能力、資源、成功經驗與希望出發。最後說明三者如何共同形成處遇，而不是各寫各的。',
  biaoti: [
    '認知行為學派：認知、情緒與行為互相影響；辨識不利認知，運用認知重建與行為練習促進改變',
    '社會支持理論：盤點正式與非正式支持網絡，以及情緒性、工具性、資訊性與評價性支持',
    '優勢觀點：聚焦案主能力、資源、成功經驗、希望與自我決定，避免只以缺陷／病理看待問題',
    '同一服務案例的整合運用：個人認知與行為改變＋支持網絡建構＋優勢與資源動員，並說明三者互補關係'
  ],
  kw: [
    '認知行為學派', '認知重建', '行為練習',
    '社會支持理論', '正式/非正式支持', '情緒/工具/資訊/評價支持',
    '優勢觀點', '資源盤點', '希望與自我決定', '三理論整合'
  ],
  review_status: 'verified',
  is_official: false,
  guide_source: 'SWSI 自製複習參考架構；依 107 年第一次社會工作師「社會工作」申論第 2 題題幹校正'
};

function fail(message) { throw new Error(message); }
function isObject(value) { return !!value && typeof value === 'object' && !Array.isArray(value); }
function exactKeys(value, allowed, label) {
  const unknown = Object.keys(value).filter(key => !allowed.has(key));
  if (unknown.length) fail(`${label} unsupported field(s): ${unknown.sort().join(', ')}`);
}
function text(value, label) {
  if (typeof value !== 'string' || !value.trim()) fail(`${label} must be a non-empty string`);
  return value.trim();
}
function uniqueStrings(value, label, min = 1) {
  if (!Array.isArray(value) || value.length < min) fail(`${label} must contain at least ${min} item(s)`);
  const out = value.map((item, i) => text(item, `${label}[${i}]`));
  if (new Set(out).size !== out.length) fail(`${label} contains duplicate values`);
  return out;
}

let overlayRecordCount = 0;
let overlayHoldCount = 0;
if (fs.existsSync(overlayInput)) {
  let overlay;
  try { overlay = JSON.parse(fs.readFileSync(overlayInput, 'utf8')); }
  catch (err) { fail(`${overlayInput} invalid JSON: ${err.message}`); }
  if (!isObject(overlay)) fail(`${overlayInput} must be an object`);
  exactKeys(overlay, new Set(['schema_version', 'purpose', 'coverage_sessions', 'records', 'held_for_review']), 'overlay');
  if (overlay.schema_version !== 1) fail('essay guide overlay schema_version must equal 1');
  text(overlay.purpose, 'overlay.purpose');
  const coverage = uniqueStrings(overlay.coverage_sessions, 'overlay.coverage_sessions');
  for (const session of coverage) if (!/^\d{3}-[12]$/.test(session)) fail(`invalid coverage session: ${session}`);
  if (!Array.isArray(overlay.records)) fail('overlay.records must be an array');
  if (!Array.isArray(overlay.held_for_review)) fail('overlay.held_for_review must be an array');

  const recordFields = new Set([
    'id', 'kao', 'dati', 'biaoti', 'kw', 'review_status', 'reviewed_at', 'review_batch',
    'review_sources', 'is_official', 'guide_source'
  ]);
  const holdFields = new Set(['id', 'reason']);
  const recordIds = new Set();
  const holdIds = new Set();

  for (let i = 0; i < overlay.records.length; i++) {
    const row = overlay.records[i];
    if (!isObject(row)) fail(`overlay.records[${i}] must be an object`);
    exactKeys(row, recordFields, `overlay.records[${i}]`);
    const id = text(row.id, `overlay.records[${i}].id`);
    const idMatch = id.match(autoIdRe);
    if (!idMatch) fail(`overlay guide id must be an auto essay E-ID: ${id}`);
    const session = `${idMatch[1]}-${idMatch[2]}`;
    if (!coverage.includes(session)) fail(`overlay guide ${id} is outside coverage_sessions`);
    if (recordIds.has(id)) fail(`duplicate overlay guide id: ${id}`);
    if (guides[id]) fail(`overlay guide unexpectedly collides with an existing runtime key: ${id}`);
    recordIds.add(id);

    const kao = text(row.kao, `${id}.kao`);
    const dati = text(row.dati, `${id}.dati`);
    const biaoti = uniqueStrings(row.biaoti, `${id}.biaoti`, 2);
    const kw = uniqueStrings(row.kw, `${id}.kw`, 3);
    if (row.review_status !== 'verified') fail(`${id}.review_status must be verified before student runtime publication`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(text(row.reviewed_at, `${id}.reviewed_at`))) fail(`${id}.reviewed_at must be YYYY-MM-DD`);
    const review_batch = text(row.review_batch, `${id}.review_batch`);
    const review_sources = uniqueStrings(row.review_sources, `${id}.review_sources`, 2);
    if (!review_sources.some(source => source.includes('考選部'))) fail(`${id}.review_sources must include the official MOEX question source`);
    if (row.is_official !== false) fail(`${id}.is_official must be false`);
    const guide_source = text(row.guide_source, `${id}.guide_source`);
    if (!guide_source.includes('SWSI') || !guide_source.includes('非考選部官方標準答案')) {
      fail(`${id}.guide_source must clearly identify SWSI authorship and non-official status`);
    }

    guides[id] = {
      kao, dati, biaoti, kw,
      review_status: 'verified',
      reviewed_at: row.reviewed_at,
      review_batch,
      review_sources,
      is_official: false,
      guide_source
    };
  }

  for (let i = 0; i < overlay.held_for_review.length; i++) {
    const row = overlay.held_for_review[i];
    if (!isObject(row)) fail(`overlay.held_for_review[${i}] must be an object`);
    exactKeys(row, holdFields, `overlay.held_for_review[${i}]`);
    const id = text(row.id, `overlay.held_for_review[${i}].id`);
    const idMatch = id.match(autoIdRe);
    if (!idMatch) fail(`held guide id must be an auto essay E-ID: ${id}`);
    const session = `${idMatch[1]}-${idMatch[2]}`;
    if (!coverage.includes(session)) fail(`held guide ${id} is outside coverage_sessions`);
    text(row.reason, `${id}.reason`);
    if (holdIds.has(id)) fail(`duplicate held guide id: ${id}`);
    if (recordIds.has(id)) fail(`guide cannot be both published and held: ${id}`);
    holdIds.add(id);
  }
  overlayRecordCount = recordIds.size;
  overlayHoldCount = holdIds.size;
}

const ids = Object.keys(guides);
if (!ids.length) throw new Error('ESSAY_GUIDES is empty after normalization');

const out = '/* Generated from essay_guides.js by scripts/build_essay_guides_runtime.js. Verified E-ID overlays may be merged from data/essay_guide_overlay.json. */\n' +
  'window.ESSAY_GUIDES = ' + JSON.stringify(guides) + ';\n';
fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, out, 'utf8');

const seen = new Set();
for (const id of Object.keys(guides)) {
  if (!legacyIdRe.test(id) && !autoIdRe.test(id)) continue;
  if (seen.has(id)) throw new Error(`Generated ESSAY_GUIDES still contains duplicate ID: ${id}`);
  seen.add(id);
}

console.log(
  `ESSAY GUIDES RUNTIME OK: ${ids.length} unique guides -> ${output}; ` +
  `overlay_verified=${overlayRecordCount}; held=${overlayHoldCount}`
);

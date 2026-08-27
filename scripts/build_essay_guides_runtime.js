#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const input = process.argv[2] || 'essay_guides.js';
const output = process.argv[3] || '_site/essay_guides.js';
const source = fs.readFileSync(input, 'utf8');

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

const ids = Object.keys(guides);
if (!ids.length) throw new Error('ESSAY_GUIDES is empty after normalization');

const out = '/* Generated from essay_guides.js by scripts/build_essay_guides_runtime.js. */\n' +
  'window.ESSAY_GUIDES = ' + JSON.stringify(guides) + ';\n';
fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, out, 'utf8');

const seen = new Set();
const runtimeKeyRe = /"([^"\\]+)"\s*:/g;
let duplicateRuntime = false;
const guideLiteral = JSON.stringify(guides);
while ((m = runtimeKeyRe.exec(guideLiteral))) {
  // This generic scan includes nested keys; only historical IDs matter.
  if (!/^(?:社會工作|社會工作直接服務|社會政策與社會立法|人類行為與社會環境|社會工作研究方法)-\d{3}-[12]-申論\d+$/.test(m[1])) continue;
  if (seen.has(m[1])) duplicateRuntime = true;
  seen.add(m[1]);
}
if (duplicateRuntime) throw new Error('Generated ESSAY_GUIDES still contains duplicate historical IDs');

console.log(`ESSAY GUIDES RUNTIME OK: ${ids.length} unique guides -> ${output}`);

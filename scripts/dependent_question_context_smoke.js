#!/usr/bin/env node
'use strict';

const fs = require('fs');
const vm = require('vm');
const path = require('path');

const root = path.resolve(__dirname, '..');
const ownerPath = path.join(root, 'monthly_patch_parts/zzzzzzzzzzzzzzzzzzzzzzzzzz_code_health_p0.part');
const source = fs.readFileSync(ownerPath, 'utf8');

let renderedStem = null;
const q30 = {
  id: 'R-115-1-30', subject: '社會工作研究方法', year: '115', round: '第一次', qno: '30',
  q: '某研究使用司法院裁判書系統蒐集權勢性交判決書，分析判決內容。這個研究的分析單位為何？'
};
const q31 = {
  id: 'R-115-1-31', subject: '社會工作研究方法', year: '115', round: '第一次', qno: '31',
  q: '承上題，這個研究所採用的研究方法是下列何者？'
};
const standalone = {
  id: 'R-115-1-32', subject: '社會工作研究方法', year: '115', round: '第一次', qno: '32',
  q: '下列何者為內容分析法的特性？'
};

const context = {
  console,
  window: {},
  ALL: [q30, q31, standalone],
  queue: [q31],
  idx: 0,
  renderQuiz() { renderedStem = context.queue[context.idx].q; }
};
vm.createContext(context);
vm.runInContext(source, context, {filename: 'code_health_p0.part'});

context.renderQuiz();
if (!renderedStem || !renderedStem.includes('【前題情境】')) throw new Error('dependent stem did not receive context label');
if (!renderedStem.includes(q30.q)) throw new Error('previous question stem was not included');
if (!renderedStem.endsWith(q31.q)) throw new Error('original dependent stem was not preserved');
if (q31.q !== '承上題，這個研究所採用的研究方法是下列何者？') throw new Error('official/runtime source stem was mutated persistently');

context.queue = [standalone];
context.idx = 0;
renderedStem = null;
context.renderQuiz();
if (renderedStem !== standalone.q) throw new Error('standalone question was changed');

const helper = context.window.swsiDependentQuestionContext;
if (!helper || helper.version !== '2026-09-06.v2-owner-folded') throw new Error('context helper/version missing');
if (!helper.isDependent(q31) || helper.isDependent(standalone)) throw new Error('dependency detection is incorrect');

console.log('DEPENDENT QUESTION CONTEXT SMOKE PASS');

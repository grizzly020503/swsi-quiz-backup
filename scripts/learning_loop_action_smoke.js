#!/usr/bin/env node
'use strict';

// Executes the actual learning-loop part in an isolated Node VM.
// No production calls, real student records, network, DOM packages or browser installs.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(ROOT, 'monthly_patch_parts/70.learning-loop.part'), 'utf8');

function decodeAttr(value) {
  const entities = { '&quot;': '"', '&#39;': "'", '&amp;': '&', '&lt;': '<', '&gt;': '>' };
  return value.replace(/&(?:quot|amp|lt|gt|#39);/g, m => entities[m]);
}

function actions(html, name) {
  // The exact onclick attribute becomes JS AFTER a browser decodes HTML entities.
  const candidates = [...html.matchAll(/\bonclick="([^"]*)"/g)]
    .map(m => decodeAttr(m[1]));
  return candidates.filter(s => s.startsWith(name + '('));
}

function runFixture(topic, subject) {
  const calls = [];
  const q = { id: 'TEST-Q-001', subject };
  if (topic !== '未分類') q.topic = topic;
  const history = [
    { id: q.id, subject, correct: false, ts: Date.now() },
    { id: q.id, subject, correct: false, ts: Date.now() }
  ];
  const sandbox = {
    app: { innerHTML: '' },
    ALL: [q],
    loadHist: () => history,
    reviewSummary: () => ({ dueCount: 0, activeCount: 0, masteredCount: 0 }),
    localStorage: { length: 0, getItem: () => null, key: () => null },
    document: { getElementById: () => ({}), querySelector: () => null },
    renderProgress() {},
    renderReview() {},
    view: 'nothing',
    startQuiz: (predicate, count) => calls.push({ type: 'practice', count, matched: predicate(q), rejectsOther: !predicate({ id: 'OTHER', subject: 'another', topic: 'another' }) }),
    swsiKnowledgeSearch: name => calls.push({ type: 'material', name }),
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { timeout: 1000 });
  sandbox.renderProgress();

  const html = sandbox.app.innerHTML;
  assert(html.includes('這個考點已累計錯 2 次'), 'repeated wrong topic should generate a next-step recommendation');
  assert(html.includes('練 5 題確認'), 'bounded retest action missing');

  for (const [fn, callbackName] of [
    ['swsiKnowledgeSearch', 'material'],
    ['swsiPracticeTopic', 'practice'],
    ['swsiPracticeSubject', 'practice']
  ]) {
    const handlers = actions(html, fn);
    assert(handlers.length, 'missing action: ' + fn);
    for (const handler of handlers) {
      vm.runInContext(handler, sandbox, { timeout: 1000 });
    }
    if (fn === 'swsiKnowledgeSearch') {
      assert(calls.some(c => c.type === callbackName && c.name === topic), 'material lookup received a changed topic: ' + topic);
    }
    if (fn === 'swsiPracticeTopic') {
      assert(calls.some(c => c.type === callbackName && c.count === 5 && c.matched && c.rejectsOther), 'topic retest failed for: ' + topic);
    }
    if (fn === 'swsiPracticeSubject') {
      assert(calls.some(c => c.type === callbackName && c.count === 20 && c.matched && c.rejectsOther), 'subject practice failed for: ' + subject);
    }
  }

  assert(!sandbox.__swsiLearningInjected, 'untrusted topic escaped the JS handler');
  assert(!/\bonclick="[^"]*"\s+on(?:error|load)=/i.test(html), 'topic escaped onclick into an extra event handler');
  return actions(html, 'swsiPracticeTopic').length;
}

const fixtures = [
  ['家庭系統', '社會工作'],
  ["O'Brien & 抗壓", "社會'工作"],
  ['社區"培力"與合作', '科目"雙引號"'],
  ["');window.__swsiLearningInjected=true;//", '引用資料'],
  ['<img src=x onerror=window.__swsiLearningInjected=true>', '測驗'],
  ['換行\\n與\\t標籤', '研究'],
  ['未分類', '社會工作']
];

let checked = 0;
for (const [topic, subject] of fixtures) checked += runFixture(topic, subject);
console.log('LEARNING LOOP ACTION SMOKE OK: ' + fixtures.length + ' isolated topics / ' + checked + ' correctly bound topic-retake handlers');


// Regression: the wrong-answer self-reflection chips also embed a dynamic ID
// in inline event-handler JavaScript. HTML-escaped quotes alone are unsafe
// after the browser decodes entities; verify round-trip against actual part.
function runCauseButtonActionFixture(id) {
  const section = { dataset: {}, innerHTML: '' };
  const exp = {
    querySelector: () => null,
    appendChild(node) { this.section = node; }
  };
  const doc = {
    querySelector: selector => selector === '#app .qcard .exp' ? exp : null,
    getElementById: () => ({}),
    createElement: tag => tag === 'section' ? section : {},
    head: { appendChild() {} },
    body: {}
  };
  const sandbox = {
    document: doc,
    window: null,
    app: { innerHTML: '' },
    queue: [{ id, answer: 'A' }],
    idx: 0,
    selected: 'B',
    answered: true,
    localStorage: { getItem: () => null, setItem() {}, length: 0, key: () => null },
    renderProgress() {},
    renderReview() {},
    view: 'nothing'
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { timeout: 1000 });
  const handlers = actions(section.innerHTML, 'swsiSetWrongCause');
  assert.strictEqual(handlers.length, 5, 'wrong-cause buttons were not generated');
  const called = [];
  sandbox.swsiSetWrongCause = (receivedId, receivedCause) => called.push({ receivedId, receivedCause });
  vm.runInContext(handlers[0], sandbox, { timeout: 1000 });
  assert.strictEqual(called.length, 1, 'wrong-cause button did not call its safe action once');
  assert.strictEqual(called[0].receivedId, id, 'question ID was modified by decoded event handler');
  assert.strictEqual(called[0].receivedCause, '概念不熟', 'wrong-cause choice was modified');
  assert(!sandbox.__swsiLearningInjected, 'untrusted question ID executed inline JavaScript');
}
for (const id of [
  'TEST-Q-001',
  "Q-O'Brien & school",
  'Q-"double quote"',
  '");window.__swsiLearningInjected=true;//',
  '<img src=x onerror=window.__swsiLearningInjected=true>'
]) runCauseButtonActionFixture(id);
console.log('WRONG-CAUSE ACTION SMOKE OK: 5 isolated escaped question-ID cases');

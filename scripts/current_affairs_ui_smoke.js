#!/usr/bin/env node
'use strict';

// Exercise the installed student UI, including the optional signal feed.
// No network, browser profile, model request or database write is required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const marker = '<!-- SWSI CURRENT AFFAIRS RADAR V1 -->';
const html = fs.readFileSync('index.html', 'utf8');
assert.equal(html.split(marker).length, 2, 'expected one current-affairs UI owner');
const match = html.split(marker)[1].match(/<script>([\s\S]*?)<\/script>/);
assert(match, 'installed current-affairs script is missing');
const script = new vm.Script(match[1], { filename: 'installed-current-affairs-ui.js' });

const news = {
  id: 'fixture-news', title: '兒少保護制度', source_name: 'Fixture source',
  source_url: 'https://example.test/news', category: '兒少保護',
  subjects: ['社會工作'], exam_tags: ['責任通報'], relevance_score: 8,
};
const signal = {
  id: news.id, signal_confidence: 'high', signal_score: 9,
  exam_point_summary: '複習方向，不代表命題保證',
  essay_direction: '分析服務體系，不代表命題保證',
  mcq_focus: ['責任通報 <img src=x onerror=alert(1)>'],
  related_exam_questions: [{ id: 'SW-115-1-01', subject: '社會工作', topic: '兒少保護' }],
};

async function scenario({ missingSignals = false, newsFailure = false } = {}) {
  const nodes = new Map();
  const calls = [];
  let opened = 0, filtered = 0;
  const wrap = {
    querySelector() { return null; },
    appendChild(node) { nodes.set(node.id, node); },
  };
  const document = {
    head: { appendChild(node) { nodes.set(node.id, node); } },
    getElementById(id) { return nodes.get(id) || null; },
    querySelector(selector) { return selector === '.nl-wrap' ? wrap : null; },
    createElement() { return { remove() { nodes.delete(this.id); } }; },
  };
  const window = { NL: {
    open() { opened++; },
    filter() { filtered++; },
  } };
  const fetch = async (url, init) => {
    calls.push(url);
    assert.equal(init.cache, 'no-store');
    if (url === './auto/current_affairs.json') {
      if (newsFailure) throw new Error('offline');
      return { ok: true, json: async () => ({ items: [news] }) };
    }
    assert.equal(url, './auto/current_affairs_signals.json');
    return { ok: !missingSignals, status: missingSignals ? 404 : 200,
      json: async () => ({ items: [signal] }) };
  };
  script.runInNewContext({ window, document, fetch });
  window.NL.open();
  await new Promise(setImmediate);
  assert.equal(opened, 1, 'existing current-affairs entry must remain connected');
  const content = nodes.get('nl-live-radar')?.innerHTML || '';
  if (newsFailure) {
    assert.equal(content, '', 'unavailable news must preserve the existing page');
    assert.equal(calls.length, 1);
    return;
  }
  assert(content.includes(news.title), 'news card disappeared');
  assert.deepEqual(calls, ['./auto/current_affairs.json', './auto/current_affairs_signals.json']);
  if (missingSignals) {
    assert(!content.includes('命題訊號：'), 'missing signals must not be invented');
  } else {
    for (const value of ['命題訊號：高', '值得練習的申論方向', '選擇題可能抓哪些事實？',
      '歷屆相關題', 'SW-115-1-01', '不代表命題保證']) {
      assert(content.includes(value), `missing student signal content: ${value}`);
    }
    assert(content.includes('&lt;img'));
    assert(!content.includes('<img'), 'signal content must be escaped');
  }
  window.NL.filter('社會政策與社會立法');
  await new Promise(setImmediate);
  assert.equal(filtered, 1);
  assert(nodes.get('nl-live-radar').innerHTML.includes('這個科目目前沒有新的高關聯時事'));
  window.NL.filter('全部');
  await new Promise(setImmediate);
  assert(nodes.get('nl-live-radar').innerHTML.includes(news.title));
  assert.equal(calls.length, 2, 'filter changes should reuse the loaded feeds');
}

(async () => {
  await scenario();
  await scenario({ missingSignals: true });
  await scenario({ newsFailure: true });
  console.log('CURRENT AFFAIRS UI SMOKE OK: signals, fallback, filtering, escaping');
})().catch(error => { console.error(error); process.exitCode = 1; });

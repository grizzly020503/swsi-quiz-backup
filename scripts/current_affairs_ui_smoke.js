#!/usr/bin/env node
'use strict';

// Exercise the installed student UI, including V2 event/trend feeds and V1 fallback.
// No network, browser profile, model request or database write is required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const marker = '<!-- SWSI CURRENT AFFAIRS RADAR V1 -->';
const html = fs.readFileSync('index.html', 'utf8');
assert.equal(html.split(marker).length, 2, 'expected one current-affairs UI owner');
const match = html.split(marker)[1].match(/<script>([\s\S]*?)<\/script>/);
assert(match, 'installed current-affairs script is missing');
assert(match[1].includes('}).slice(0,3);'), 'student current-affairs view must cap the ranked list at three items');
const script = new vm.Script(match[1], { filename: 'installed-current-affairs-ui.js' });

// Evergreen history cases must stay off the main current-affairs screen.
// Exercise real NL navigation in a tiny DOM stub, without a browser or network.
(function verifyEvergreenHistoryNavigation() {
  const from = html.indexOf('/* ===== 時事庫注入 START');
  const to = html.indexOf('/* ===== 時事庫注入 END', from);
  assert(from >= 0 && to > from, 'evergreen news module must exist');
  const moduleSource = html.slice(from, to);
  const moduleMatch = moduleSource.match(/\(function\(\)\{[\s\S]*?\}\)\(\);/);
  assert(moduleMatch, 'evergreen module IIFE not found');

  const primary = { style: {} };
  function node(tag) {
    return {
      tag, className: '', style: {}, children: [], parentNode: null, innerHTML: '', scrollTop: 0,
      appendChild(child) { child.parentNode = this; this.children.push(child); },
      removeChild(child) {
        const i = this.children.indexOf(child);
        assert(i >= 0, 'attempted to remove a detached archive screen');
        this.children.splice(i, 1); child.parentNode = null;
      },
      querySelector(selector) {
        if (this.className === 'nl-ov' && selector === '.nl-wrap') return primary;
        if (this.className === 'nl-history-page' && selector === '.nl-back') {
          return { focus() {} };
        }
        return null;
      },
    };
  }
  const document = {
    head: node('head'), body: node('body'), documentElement: { getAttribute() { return null; } },
    createElement: node,
  };
  const window = { scrollTo() {} };
  new vm.Script(moduleMatch[0], { filename: 'evergreen-history.js' }).runInNewContext({window, document});
  window.NL.open();
  const overlay = document.body.children[0];
  assert(overlay, 'news overlay is missing');
  assert(overlay.innerHTML.includes('NL.history()'), 'single history entry missing from main screen');
  assert(!overlay.innerHTML.includes('class="nl-card"'), 'legacy article cards must not appear on main screen');
  assert(overlay.innerHTML.includes('class="nl-chips"'), 'live radar filter hook must remain available');

  overlay.scrollTop = 167;
  window.NL.history();
  assert.equal(primary.style.display, 'none', 'main screen should be hidden while reading archive');
  assert.equal(overlay.children.length, 1, 'only one archive screen should be mounted');
  const archive = overlay.children[0];
  assert(archive.innerHTML.includes('class="nl-card"'), 'archived case cards disappeared');
  assert(archive.innerHTML.includes('剴剴案'), 'child protection case was lost');
  assert(archive.innerHTML.includes('NL.back()'), 'archive back action is missing');

  window.NL.historyFilter('人類行為');
  assert(archive.innerHTML.includes('nl-chip on'), 'archive subject filter did not update');
  window.NL.back();
  assert.equal(overlay.children.length, 0, 'archive screen must unmount on back');
  assert.equal(primary.style.display, '', 'main screen should be restored');
  assert.equal(overlay.scrollTop, 167, 'main reading position should be restored');
  window.NL.close();
  assert.equal(document.body.children.length, 0, 'closing news should remove the overlay');
})();


const news = {
  id: 'fixture-news', title: '兒少保護制度', source_name: 'Fixture source',
  source_url: 'https://example.test/news', category: '兒少保護',
  subjects: ['社會工作'], exam_tags: ['責任通報'], relevance_score: 8,
  knowledge_root: '社會工作管理',
  management_domains: ['品質與風險管理', '服務輸送與跨網絡'],
  primary_exam_subject_axes: ['社會工作'],
  supporting_exam_subject_axes: ['社會工作直接服務'],
  subject_topics: {
    '社會工作': ['專業倫理與兒童最佳利益'],
    '社會工作直接服務': ['兒少保護風險評估'],
  },
};
const signal = {
  id: news.id, signal_confidence: 'high', signal_score: 9,
  exam_point_summary: '複習方向，不代表命題保證',
  essay_direction: '分析服務體系，不代表命題保證',
  mcq_focus: ['責任通報 <img src=x onerror=alert(1)>'],
  related_exam_questions: [{ id: 'SW-115-1-01', subject: '社會工作', topic: '兒少保護' }],
};
const event = {
  canonical_event_id: 'event-1',
  title: '兒少保護制度跨來源事件',
  category: '兒少保護',
  subjects: ['社會工作'],
  knowledge_root: '社會工作管理',
  knowledge_model: 'management-hierarchy-over-five-exam-subjects-v3',
  management_domains: ['品質與風險管理', '服務輸送與跨網絡'],
  exam_subject_axes: ['社會工作', '社會工作直接服務'],
  primary_exam_subject_axes: ['社會工作直接服務'],
  supporting_exam_subject_axes: ['社會工作'],
  subject_topics: {
    '社會工作': ['專業倫理與兒童最佳利益'],
    '社會工作直接服務': ['兒少保護風險評估'],
  },
  knowledge_paths: ['社會工作管理 > 品質與風險管理 > 社會工作直接服務 > 兒少保護風險評估'],
  source_count: 3,
  official_source_count: 2,
  last_seen: '2026-09-25T08:00:00Z',
  exam_point_summary: '事件級考點摘要，不代表命題保證',
  essay_direction: '事件級申論方向',
  mcq_focus: ['第13條 <img src=x onerror=alert(1)>'],
  related_exam_questions: [{ id: 'SW-115-1-02', subject: '社會工作', topic: '兒少權法', match_score: 6.2 }],
  evidence: [
    { source_name: '衛福部', source_url: 'https://example.test/a', published_at: '2026-09-25T01:00:00Z' },
    { source_name: '中央社', source_url: 'https://example.test/b', published_at: '2026-09-25T02:00:00Z' },
    { source_name: '行政院', source_url: 'https://example.test/c', published_at: '2026-09-25T03:00:00Z' },
  ],
};
const trend = {
  canonical_event_id: event.canonical_event_id,
  trend_state: 'rising',
  trend_score: 8.4,
  why: ['3 個來源交叉確認', '2 個官方來源', '關聯 5 題歷屆題'],
  essay_direction: event.essay_direction,
  mcq_focus: event.mcq_focus,
  related_exam_questions: event.related_exam_questions,
  historical_high_confidence_match_count: 1,
};

const oneOffEvent = {
  canonical_event_id: 'event-one-off',
  title: '單一官方來源制度提醒',
  category: '勞動與社會保障',
  subjects: ['社會工作'],
  source_count: 1,
  official_source_count: 1,
  observation_count: 1,
  last_seen: '2026-09-22T13:50:55Z',
  exam_point_summary: '制度或給付已有明確變動；這段不應在單次觀察直接公開。',
  essay_direction: '可作制度複習方向。',
  mcq_focus: ['65歲', '20%'],
  related_exam_questions: [{ id: 'SW-113-2-27', subject: '社會工作', topic: '倫理抉擇', match_score: 3.2 }],
  evidence: [{ source_name: '勞動部新聞稿', source_url: 'https://example.test/mol', published_at: '2026-09-22T13:50:55Z' }],
};
const oneOffTrend = {
  canonical_event_id: oneOffEvent.canonical_event_id,
  // Backend age analysis may call an old single observation "cooling". Student UI
  // must still fail closed to "單次觀察" until trend evidence is actually ready.
  trend_state: 'cooling',
  trend_score: 5.5,
  observation_count: 1,
  why: ['1 個官方來源', '有政策／制度訊號', '歷屆同概念關聯 11 題'],
  related_exam_questions: oneOffEvent.related_exam_questions,
  historical_high_confidence_match_count: 0,
};

async function scenario({
  missingV2 = false,
  newsFailure = false,
  allFailure = false,
  singleSource = false,
} = {}) {
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
    if (allFailure) throw new Error('offline');
    if (url === './auto/current_affairs.json') {
      if (newsFailure) throw new Error('news offline');
      return { ok: true, json: async () => ({ items: [news] }) };
    }
    if (url === './auto/current_affairs_signals.json') {
      return { ok: true, json: async () => ({ items: [signal] }) };
    }
    if (url === './auto/current_affairs_events.json') {
      return { ok: !missingV2, status: missingV2 ? 404 : 200,
        json: async () => ({ events: [singleSource ? oneOffEvent : event] }) };
    }
    if (url === './auto/current_affairs_trends.json') {
      return { ok: !missingV2, status: missingV2 ? 404 : 200,
        json: async () => ({ trends: [singleSource ? oneOffTrend : trend] }) };
    }
    throw new Error('unexpected URL ' + url);
  };

  script.runInNewContext({ window, document, fetch, Promise });
  window.NL.open();
  await new Promise(setImmediate);
  assert.equal(opened, 1, 'existing current-affairs entry must remain connected');
  const content = nodes.get('nl-live-radar')?.innerHTML || '';

  assert.deepEqual(calls, [
    './auto/current_affairs.json',
    './auto/current_affairs_signals.json',
    './auto/current_affairs_events.json',
    './auto/current_affairs_trends.json',
  ]);

  if (allFailure) {
    assert.equal(content, '', 'when all feeds fail, preserve the existing page');
    return;
  }

  assert(content.includes('目前 3 個國考重點'), 'focused current-affairs heading missing');
  if (missingV2) {
    assert(content.includes('備援資料'), 'missing V2 must fall back to V1');
    assert(content.includes(news.title), 'V1 news card disappeared');
    assert(content.includes('命題訊號：高'), 'V1 signal fallback disappeared');
    assert(content.includes('不代表命題保證'));
    assert(content.includes('社會工作管理 × 國考五科'), 'V1 knowledge tree disappeared');
  } else {
    assert(content.includes('少量精選・證據分級'), 'focused evidence-grading badge missing');
    assert(!content.includes('命題趨勢雷達'), 'student view should no longer present itself as a trend dashboard');
    const expectedEvent = singleSource ? oneOffEvent : event;
    assert(content.includes(expectedEvent.title), 'event card disappeared');
    assert(content.includes('nlr-preview'), 'compact preview missing');
    assert(content.includes('nlr-deep'), 'full analysis disclosure missing');
    if (!singleSource) {
      assert(content.includes('nlr-study-quick'), 'practice entry should be visible');
      assert(content.indexOf('nlr-study-quick') < content.indexOf('nlr-deep'), 'practice precedes deep analysis');
    }
    if (singleSource) {
      for (const value of [
        '單次觀察', '尚不足以形成趨勢', '來源依據',
        '目前只有單一來源或單次觀察', '事實請以原始來源為準',
      ]) {
        assert(content.includes(value), `missing fail-closed one-off content: ${value}`);
      }
      for (const value of [
        '降溫', '趨勢訊號 5.5/10', '多來源證據', 'SW-113-2-27', '制度或給付已有明確變動',
      ]) {
        assert(!content.includes(value), `one-off event leaked overclaimed content: ${value}`);
      }
    } else {
      for (const value of [
        '升溫', '趨勢訊號 8.4/10', '3 個來源', '2 官方',
        '為什麼值得複習？', '多來源證據', 'SW-115-1-02',
        '同事件跨來源只計一次', '不代表命題保證',
        '社會工作管理 × 國考五科', '品質與風險管理',
        '主要考科', '延伸考科',
        '社會工作直接服務', '兒少保護風險評估',
      ]) {
        assert(content.includes(value), `missing V2 student trend content: ${value}`);
      }
    }
    assert(content.includes('&lt;img') || singleSource);
    assert(!content.includes('<img'), 'V2 dynamic content must be escaped');
    if (newsFailure) {
      assert(content.includes(singleSource ? oneOffEvent.title : event.title), 'V2 should remain usable when V1 news fails');
    }
  }

  window.NL.filter('社會政策與社會立法');
  await new Promise(setImmediate);
  assert.equal(filtered, 1);
  assert(nodes.get('nl-live-radar').innerHTML.includes(
    missingV2 ? '這個科目目前沒有新的高關聯時事' : '這個科目目前沒有新的高關聯事件'
  ));
  window.NL.filter('全部');
  await new Promise(setImmediate);
  assert(nodes.get('nl-live-radar').innerHTML.includes(missingV2 ? news.title : (singleSource ? oneOffEvent.title : event.title)));
  assert.equal(calls.length, 4, 'filter changes should reuse the loaded feeds');
}

(async () => {
  await scenario();
  await scenario({ missingV2: true });
  await scenario({ newsFailure: true });
  await scenario({ singleSource: true });
  await scenario({ allFailure: true });
  console.log('CURRENT AFFAIRS UI V2 SMOKE OK: focused top-3 review, evidence grading, one-off fail-closed, V1 fallback, filtering, escaping');
})().catch(error => { console.error(error); process.exitCode = 1; });

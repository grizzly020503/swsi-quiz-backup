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
const script = new vm.Script(match[1], { filename: 'installed-current-affairs-ui.js' });

const news = {
  id: 'fixture-news', title: '兒少保護制度', source_name: 'Fixture source',
  source_url: 'https://example.test/news', category: '兒少保護',
  subjects: ['社會工作'], exam_tags: ['責任通報'], relevance_score: 8,
  knowledge_root: '社會工作管理',
  management_domains: ['品質與風險管理', '服務輸送與跨網絡'],
  exam_subject_axes: ['社會工作', '社會工作直接服務', '社會工作研究方法'],
  knowledge_topics: ['兒少保護', '責任通報'],
  knowledge_model: 'management-hierarchy-over-five-exam-subjects-v3',
  subject_topics: {
    '社會工作': ['專業倫理與兒童最佳利益'],
    '社會工作直接服務': ['兒少保護風險評估'],
    '社會工作研究方法': ['研究證據判讀'],
  },
  knowledge_paths: ['社會工作管理 > 五科整合 > 社會工作直接服務 > 兒少保護風險評估'],
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
  management_domains: ['品質與風險管理', '服務輸送與跨網絡'],
  exam_subject_axes: ['社會工作', '社會工作直接服務', '社會工作研究方法'],
  knowledge_topics: ['兒少保護', '責任通報'],
  knowledge_model: 'management-hierarchy-over-five-exam-subjects-v3',
  subject_topics: {
    '社會工作': ['專業倫理與兒童最佳利益'],
    '社會工作直接服務': ['兒少保護風險評估'],
    '社會工作研究方法': ['研究證據判讀'],
  },
  knowledge_paths: ['社會工作管理 > 五科整合 > 社會工作直接服務 > 兒少保護風險評估'],
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
  knowledge_root: '社會工作管理',
  management_domains: ['規劃與政策執行', '倫理與權利保障'],
  exam_subject_axes: ['社會工作', '社會政策與社會立法', '社會工作研究方法'],
  knowledge_topics: ['勞動與社會保障'],
  knowledge_model: 'management-hierarchy-over-five-exam-subjects-v3',
  subject_topics: {
    '社會工作': ['勞動權益、社會正義與弱勢支持'],
    '社會政策與社會立法': ['社會保險、就業安全與勞動政策'],
    '社會工作研究方法': ['研究證據判讀'],
  },
  knowledge_paths: ['社會工作管理 > 五科整合 > 社會政策與社會立法 > 社會保險、就業安全與勞動政策'],
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
  trend_state: 'one-off',
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

  if (missingV2) {
    assert(content.includes('V1 備援'), 'missing V2 must fall back to V1');
    assert(content.includes(news.title), 'V1 news card disappeared');
    assert(content.includes('命題訊號：高'), 'V1 signal fallback disappeared');
    assert(content.includes('社會工作管理'), 'V1 knowledge root disappeared');
    assert(content.includes('品質與風險管理'), 'V1 management domain disappeared');
    assert(content.includes('五科怎麼連？'), 'V1 subject-axis disclosure disappeared');
    assert(content.includes('研究方法'), 'V1 research-method axis disappeared');
    assert(content.includes('兒少保護風險評估'), 'V1 subject topic disappeared');
    assert(content.includes('不代表命題保證'));
  } else {
    assert(content.includes('命題趨勢雷達'), 'V2 trend radar heading missing');
    assert(content.includes('事件聚類・證據分級'), 'evidence-grading badge missing');
    const expectedEvent = singleSource ? oneOffEvent : event;
    assert(content.includes(expectedEvent.title), 'event card disappeared');
    assert(content.includes('社會工作管理'), 'V2 knowledge root disappeared');
    assert(content.includes(expectedEvent.management_domains[0]), 'V2 management domain disappeared');
    assert(content.includes('五科怎麼連？'), 'V2 subject-axis disclosure disappeared');
    assert(content.includes('研究方法'), 'V2 research-method axis disappeared');
    assert(content.includes(singleSource ? '社會保險、就業安全與勞動政策' : '兒少保護風險評估'), 'V2 subject topic disappeared');
    if (singleSource) {
      for (const value of [
        '單次觀察', '尚不足以形成趨勢', '來源依據',
        '目前只有單一來源或單次觀察', '事實請以原始來源為準',
      ]) {
        assert(content.includes(value), `missing fail-closed one-off content: ${value}`);
      }
      for (const value of [
        '趨勢訊號 5.5/10', '多來源證據', 'SW-113-2-27', '制度或給付已有明確變動',
      ]) {
        assert(!content.includes(value), `one-off event leaked overclaimed content: ${value}`);
      }
    } else {
      for (const value of [
        '升溫', '趨勢訊號 8.4/10', '3 個來源', '2 官方',
        '為什麼值得複習？', '多來源證據', 'SW-115-1-02',
        '同事件跨來源只計一次', '不代表命題保證',
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
  console.log('CURRENT AFFAIRS UI V2 SMOKE OK: evidence grading, one-off fail-closed, trends, V1 fallback, filtering, escaping');
})().catch(error => { console.error(error); process.exitCode = 1; });

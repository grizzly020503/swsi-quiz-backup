#!/usr/bin/env node
'use strict';

// Exercise auto-curated major-event essays in the legacy history screen.
// Network is mocked. No PII, AI calls, database writes, or production changes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const root = fs.readFileSync('index.html','utf8');
const cdn = fs.readFileSync('cdn/index.html','utf8');
function source(html) {
  const a=html.indexOf('/* ===== 時事庫注入 START'),b=html.indexOf('/* ===== 時事庫注入 END',a);
  assert(a>=0&&b>a,'history module missing');
  return html.slice(a,html.indexOf('*/',b)+2);
}
assert.equal(source(root),source(cdn),'root/CDN history owner drift');
const script = new vm.Script(source(root),{filename:'major-event-history.js'});

async function verify(feed) {
  const attached = [];
  const primary = {style:{}};
  let archive;
  function node(tag) {
    return {
      tag,style:{},className:'',innerHTML:'',scrollTop:0,parentNode:null,children:[],
      appendChild(c){c.parentNode=this;this.children.push(c);},
      removeChild(c){const i=this.children.indexOf(c);assert(i>=0);this.children.splice(i,1);c.parentNode=null;},
      querySelector(selector){
        if(this.className==='nl-ov'&&selector==='.nl-wrap')return primary;
        if(this.className==='nl-history-page'&&selector==='.nl-back')return {focus(){}};
        return null;
      },
    };
  }
  const body=node('body');
  const doc={
    head:node('head'),body,
    documentElement:{getAttribute(){return null;}},
    createElement(tag){let n=node(tag);if(tag==='section')archive=n;return n;},
  };
  let requests=0;
  const fetch=(url,opts)=>{
    requests++;
    assert.equal(url,'./auto/major_social_work_events.json');
    assert.equal(opts.cache,'no-store');
    return Promise.resolve({ok:true,json:async()=>feed});
  };
  const window={};
  script.runInNewContext({document:doc,window,fetch,Promise});
  window.NL.open();
  assert.equal(body.children.length,1);
  assert(!body.children[0].innerHTML.includes('nl-major-card'),'auto event should not clutter main screen');
  window.NL.history();
  await new Promise(setImmediate);
  await new Promise(setImmediate);
  assert.equal(requests,1,'archive should make one GET only');
  assert(archive,'archive screen missing');
  assert(archive.innerHTML.includes('經典案例'),'original history cases lost');
  if(feed.events[0]?.evidence.length>=2){
    assert(archive.innerHTML.includes('自動審核通過的重大事件'));
    assert(archive.innerHTML.includes('自編申論練習 1'));
    assert(archive.innerHTML.includes('自編申論練習 2'));
    assert(archive.innerHTML.includes('非考選部官方題目'));
    assert(!archive.innerHTML.includes('<img src=x'),'untrusted essay prompt injected HTML');
    assert(archive.innerHTML.includes('&lt;img src=x'),'untrusted question text not escaped');
    assert(archive.innerHTML.includes('rel="noopener noreferrer"'));
    window.NL.historyFilter('人類行為');
    assert(!archive.innerHTML.includes('nl-major-card'),'archive subject filter did not hide auto event');
    window.NL.historyFilter('社會工作');
    assert(archive.innerHTML.includes('nl-major-card'),'archive subject filter did not restore auto event');
  } else {
    assert(!archive.innerHTML.includes('nl-major-card'),'unverified major item was admitted');
    assert(archive.innerHTML.includes('近期重大事件資料暫時無法更新'),'bad archive should fail closed');
  }
  window.NL.back();
  assert(!body.children[0].innerHTML.includes('nl-major-card'),'auto cards leaked onto main page');
  window.NL.close();
  assert.equal(body.children.length,0);
}

const major={
  canonical_event_id:'event-major-test',
  title:'政府核定強化社會安全網新制',
  summary:'經跨來源核實的重要社工制度變化',
  subjects:['社會工作'],
  admission_rule:'major-social-work-v1',
  last_seen:'2026-11-07T00:00:00Z',
  evidence:[
    {source_name:'官方',source_url:'https://example.test/official'},
    {source_name:'媒體',source_url:'https://example.test/news'},
  ],
  practice_essays:[
    {type:'practice_only',question:'分析跨網絡服務 <img src=x>',outline:['權益保障','實務合作']},
    {type:'practice_only',question:'請提出社工方案與成效評估',outline:['服務可近性']},
  ],
};
(async()=>{
  await verify({schema_version:1,selection_method:'major-social-work-v1',event_count:1,events:[major]});
  await verify({schema_version:1,selection_method:'major-social-work-v1',event_count:1,events:[{...major,evidence:[major.evidence[0]]}]});
  console.log('MAJOR SOCIAL WORK UI SMOKE PASS: no main-page clutter, async admission, two original questions, escaping, filtering, fallback');
})().catch(e=>{console.error(e);process.exitCode=1;});

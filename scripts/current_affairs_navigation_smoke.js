#!/usr/bin/env node
'use strict';
// SWSI news-to-exam real navigation: exact IDs only, high-confidence gates,
// safe local route, held-source refusal, and no fabricated case-of-the-year claims.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

const marker='<!-- SWSI CURRENT AFFAIRS RADAR V1 -->';
const ui=fs.readFileSync('scripts/install_current_affairs_ui.py','utf8');
const raw=ui.split("BLOCK = r'''")[1]?.split("'''")[0]?.trim();
assert(raw && raw.startsWith(marker),'canonical current-affairs block missing');
for(const file of ['index.html','cdn/index.html']){
  const html=fs.readFileSync(file,'utf8');
  const block=html.slice(html.indexOf(marker),html.indexOf('</script>',html.indexOf(marker))+'</script>'.length);
  assert.equal(block,raw,'installer and '+file+' embedded UI must be byte-identical');
}
const script=new vm.Script(raw.split('<script>')[1].split('</script>')[0]);

async function scenario({held=false}={}){
  const nodes=new Map(), calls=[],selected=[],closed=[];
  let loaderCalls=0,lawName='',theoryName='',essayData=null;
  const status={textContent:''};
  const wrap={
    querySelector(){return null;},
    appendChild(n){nodes.set(n.id,n);}
  };
  const document={
    head:{appendChild(n){nodes.set(n.id,n);}},
    getElementById(id){return nodes.get(id)||null;},
    querySelector(sel){return sel==='.nl-wrap'?wrap:null;},
    createElement(){return {
      id:'',innerHTML:'',handlers:{},
      addEventListener(name,cb){this.handlers[name]=cb;},
      querySelector(sel){return sel==='[data-swsi-news-status]'?status:null;},
      contains(){return true;},
      remove(){nodes.delete(this.id);}
    };}
  };
  const window={
    NL:{open(){},filter(){},close(){closed.push(true);}},
    swsiSourceHeld(){return held;},
    swsiStudyOneEncoded(id){selected.push(decodeURIComponent(id));},
    swsiOpenLawEncoded(id){lawName=decodeURIComponent(id);},
    swsiOpenTheoryEncoded(id){theoryName=decodeURIComponent(id);},
    swsiOpenEssayEncoded(id,subject){essayData=[decodeURIComponent(id),decodeURIComponent(subject)];}
  };
  const strong='SP108-2-22',weak='SP115-1-26';
  const evt={
    canonical_event_id:'test-event',
    title:'少年司法草案仍在審議',
    category:'少年司法與犯罪防治',
    source_count:2,official_source_count:1,subjects:['社會政策與社會立法'],
    last_seen:'2026-11-06T08:00:00Z',
    related_laws:['少年事件處理法'],
    knowledge_topics:['生態系統理論'],
    related_exam_questions:[
      {id:strong,year:'108',subject:'社會政策與社會立法',qno:'22',match_score:5.2},
      {id:weak,year:'115',subject:'社會政策與社會立法',qno:'26',match_score:2.2}
    ]
  };
  const tr={
    canonical_event_id:'test-event',trend_state:'rising',trend_score:7.2,
    source_count:2,observation_count:2,historical_high_confidence_match_count:1,
    related_laws:evt.related_laws,
    related_exam_questions:evt.related_exam_questions
  };
  const fetch=async url=>{
    calls.push(url);
    const results={
      './auto/current_affairs.json':{items:[]},
      './auto/current_affairs_signals.json':{items:[]},
      './auto/current_affairs_events.json':{events:[evt]},
      './auto/current_affairs_trends.json':{trends:[tr]}
    };
    return {ok:true,json:async()=>results[url]};
  };
  const context={
    window,document,fetch,Promise,Set,console,
    LAWS:[{n:'少年事件處理法'}],
    THEORIES:[{n:'生態系統理論'}],
    ESSAYS:[{id:'E-114-1-DS-2',subject:'社會工作直接服務',q:'說明少年司法相關方案',topic:'少年司法',laws:['少年事件處理法']}],
    ALL:[{id:strong,source_exam_code:'108100'},{id:weak,source_exam_code:'115100'}],
    async ensureAllQuestionsLoadedWithUI(){loaderCalls++;}
  };
  vm.createContext(context);script.runInContext(context);
  window.NL.open();await new Promise(setImmediate);
  const box=nodes.get('nl-live-radar');
  assert(box,'current-affairs radar not rendered');
  assert(box.handlers.click,'real click handler not attached');
  assert(box.innerHTML.includes('data-swsi-news-action="question"'),'real question control missing');
  assert(box.innerHTML.includes(strong),'trusted historical question hidden');
  assert(!box.innerHTML.includes(weak),'weak keyword match must not be presented as historical link');
  assert(box.innerHTML.includes('主題相關的舊考題'),'not an event-specific exam disclaimer missing');
  assert(box.innerHTML.includes('data-swsi-news-action="law"'),'canonical law link missing');
  assert(box.innerHTML.includes('data-swsi-news-action="theory"'),'exact theory link missing');
  assert(box.innerHTML.includes('data-swsi-news-action="essay"'),'law-tagged essay link missing');
  assert.equal(calls.length,4,'news entry should reuse four feed snapshots');
  const click=(action,value)=>{
    const button={
      disabled:false,
      getAttribute(k){return k==='data-swsi-news-action'?action:encodeURIComponent(value);}
    };
    return box.handlers.click({target:{closest(){return button;}}});
  };
  click('question',strong);await new Promise(setImmediate);
  assert.equal(loaderCalls,1,'must load exam bank before opening a historical question');
  assert.equal(selected.length,held?0:1,'held-source routing failed');
  if(held){
    assert(status.textContent.includes('核對'),'held question must show human-readable explanation');
  }else{
    assert.equal(selected[0],strong);
    assert.equal(closed.length,1,'must close radar before navigating');
  }
  click('law','少年事件處理法');await new Promise(setImmediate);
  assert.equal(lawName,'少年事件處理法');
  click('theory','生態系統理論');await new Promise(setImmediate);
  assert.equal(theoryName,'生態系統理論');
  click('essay','E-114-1-DS-2');await new Promise(setImmediate);
  assert.deepEqual(essayData,['E-114-1-DS-2','社會工作直接服務']);
  click('question','not-in-published-bank');await new Promise(setImmediate);
  assert.equal(selected.length,held?0:1,'unresolved exam ID must not navigate');
}
(async()=>{
  await scenario();
  await scenario({held:true});
  console.log('CURRENT AFFAIRS REAL LINK SMOKE OK: scored IDs, no vague keyword links, real navigation, held-source block, exact catalog and essays');
})().catch(e=>{console.error(e.stack||e);process.exitCode=1;});

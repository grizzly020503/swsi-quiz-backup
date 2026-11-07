#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const installer=fs.readFileSync('scripts/install_current_affairs_ui.py','utf8');
const start=installer.indexOf('  function reliableQuestions(rows){');
const end=installer.indexOf('  function eventCard(ev){',start);
assert(start>0&&end>start,'maintained event-to-exam link functions missing');
const snippet=installer.slice(start,end);
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const calls=[];
const status={textContent:''};
const env={
  window:{
    NL:{close:()=>calls.push('close')},
    swsiSourceHeld:q=>q.held===true,
    swsiStudyOneEncoded:v=>calls.push(['question',decodeURIComponent(v)]),
    swsiOpenLawEncoded:v=>calls.push(['law',decodeURIComponent(v)]),
    swsiOpenTheoryEncoded:v=>calls.push(['theory',decodeURIComponent(v)]),
    swsiOpenEssayEncoded:(id,subject)=>calls.push(['essay',decodeURIComponent(id),decodeURIComponent(subject)])
  },
  document:{getElementById:id=>id==='nl-live-radar'?{querySelector:()=>status}:null},
  ALL:[{id:'SP108-2-22'}, {id:'SP107-2-23',held:true}],
  ESSAYS:[{id:'E-115-2-SW-1',q:'少年司法問題',topic:'少年司法',subject:'社會工作',laws:['少年事件處理法'],theories:[]}],
  LAWS:[{n:'少年事件處理法'}],THEORIES:[{n:'生態系統理論'}],
  E:esc,encodeURIComponent,decodeURIComponent,Array,Number,Set,
  ensureAllQuestionsLoadedWithUI:async()=>{calls.push('load');},
};
vm.createContext(env);
vm.runInContext(snippet,env,{filename:'maintained-current-affairs-study-links.js'});
const api={reliableQuestions:env.reliableQuestions,studyLinks:env.studyLinks,followStudyLink:env.followStudyLink};
const rows=[
  {id:'SP108-2-22',year:'108',subject:'社政',qno:'22',match_score:5.2},
  {id:'SP108-2-22',year:'108',subject:'社政',qno:'22',match_score:5.2},
  {id:'SP107-2-23',year:'107',subject:'社政',qno:'23',match_score:6.2},
  {id:'SW-115-1-02',match_score:2.2},
  {id:'"><img src=x onerror=alert(1)>',match_score:99},
  {id:'SP115-1-26',match_score:'NaN'}
];
assert.equal(api.reliableQuestions(rows).length,2,'exclude generic keyword matches, untrusted IDs and duplicate IDs');
const html=api.studyLinks(rows,['少年事件處理法'],['生態系統理論']);
assert(html.includes('data-swsi-news-action="question"'),'strong match must offer a question action');
assert(!html.includes('SP115-1-26'),'weak match may never be promoted into a visible question');
assert(html.includes('看相關法規／政策'));
assert(html.includes('看相關理論'));
assert(html.includes('練相關申論'));
assert(html.includes('不代表考題曾考過此新聞事件'),'historical versus current event context warning missing');
const malicious=api.studyLinks([{id:'SP108-2-22',match_score:6,subject:'<script>alert(1)</script>'}],[],[]);
assert(malicious.includes('&lt;script&gt;')&&!malicious.includes('<script>'),'injected metadata must be escaped');
assert.equal(api.studyLinks([{id:'SP115-1-26',match_score:2.2}],[],[]),'','only low-quality matches must not produce a panel');
function button(action,value){
  const attrs={'data-swsi-news-action':action,'data-swsi-news-value':encodeURIComponent(value)};
  const b={disabled:false,getAttribute:key=>attrs[key],closest:selector=>selector==='button[data-swsi-news-action]'?b:null};
  return b;
}
async function click(action,value){
  const b=button(action,value);await api.followStudyLink({target:b},{contains:x=>x===b});assert.equal(b.disabled,false);
}
(async()=>{
  await click('question','SP108-2-22');
  assert.deepEqual(calls.slice(0,3),['load','close',['question','SP108-2-22']]);
  calls.length=0;
  await click('question','SP107-2-23');
  assert.deepEqual(calls,['load'],'held official question cannot be opened');
  assert(status.textContent.includes('核對'));
  calls.length=0;
  await click('question','nonexistent-1');
  assert.deepEqual(calls,['load'],'unknown official question cannot be opened');
  calls.length=0;
  await click('law','少年事件處理法');
  assert.deepEqual(calls,['close',['law','少年事件處理法']]);
  calls.length=0;
  await click('theory','生態系統理論');
  assert.deepEqual(calls,['close',['theory','生態系統理論']]);
  calls.length=0;
  await click('essay','E-115-2-SW-1');
  assert.deepEqual(calls,['close',['essay','E-115-2-SW-1','社會工作']]);
  console.log('CURRENT AFFAIRS TOPIC LINK SMOKE OK: high-confidence matching, safe navigation, source holds, law, theory, essay, escaping');
})().catch(e=>{console.error(e);process.exitCode=1;});

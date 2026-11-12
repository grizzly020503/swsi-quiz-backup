#!/usr/bin/env node
'use strict';
// Exercise actual runtime with immutable official rows; no production writes.
const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium,webkit}=require('playwright');
const base=process.argv[2]||'http://127.0.0.1:4176/';
const origin=new URL(base).origin;
const corpus=['104-1','104-2','107-1','107-2','111-2'].flatMap(stem=>
  JSON.parse(fs.readFileSync('cdn/question-shards/'+stem+'.json')).questions);
const ids=['DS-104-1-22','DS-104-1-27','DS-104-1-29','SP104-2-37','SP107-1-40'];
(async()=>{
for(const type of [chromium,webkit]){
 const browser=await type.launch();
 try{for(const width of [390,1366]){
 const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});
 const page=await context.newPage();page.on('dialog',d=>d.accept());
 await page.route('**/*',r=>{
  const u=new URL(r.request().url());
  if(u.origin===origin)return r.continue();
  if(u.hostname==='wandering-wave-4418.c022050333.workers.dev'&&u.pathname==='/question-shards/manifest.json')return r.fulfill({status:200,contentType:'application/json',body:fs.readFileSync('cdn/question-shards/manifest.json')});
  return r.abort();
 });
 await page.goto(base);
 await page.waitForFunction(()=>typeof view!=='undefined'&&view==='home'&&document.getElementById('tabbar')?.style.display==='flex');
 // Verify that held official text cannot leak into search results, random
 // practice, or a student's *existing* due-review schedule. Old saved review
 // records are preserved, not deleted, so they can reappear after approval.
 const entrances=await page.evaluate(rows=>{
  const normalized=rows.map(normalize);
  ALL=normalized; SUBJECTS=[...new Set(normalized.map(q=>q.subject))];
  window.SWSI_QB.allComplete=true;
  const held=['DS-104-1-22','DS-104-1-27','DS-104-1-29','SP104-2-37','SP107-1-40'];
  const ordinary=normalized.find(q=>q.id==='DS-104-1-01');
  if(!ordinary)throw Error('ordinary control missing');
  const searchLeaks=held.filter(id=>{
   const item=normalized.find(q=>q.id===id);
   const token=String(item?.q||'').match(/[\u4e00-\u9fff]{2,}/)?.[0]?.slice(0,2);
   if(!token)throw Error('missing source search query '+id);
   return searchAll(token).mcq.some(q=>q.id===id);
  });
  const positiveToken=String(ordinary.q).match(/[\u4e00-\u9fff]{2,}/)?.[0]?.slice(0,2);
  const normalSearch=searchAll(positiveToken).mcq.some(q=>q.id===ordinary.id);
  startQuiz(()=>true,0);
  const selectedIds=queue.map(q=>q.id);
  const randomPracticeNoHeld=selectedIds.length===rows.length-held.length&&
    held.every(id=>!selectedIds.includes(id))&&selectedIds.includes(ordinary.id);
  const originalReviewRaw=localStorage.getItem(REVIEW_KEY);
  const state=loadReviewState();state.migratedFromHistory=true;
  state.items[held[0]]={id:held[0],mastered:false,dueAt:0};
  state.items[ordinary.id]={id:ordinary.id,mastered:false,dueAt:0};
  let reviewHeldVisible=false,reviewOrdinaryVisible=false,preserved=false;
  try{
   localStorage.setItem(REVIEW_KEY,JSON.stringify(state));
   const before=localStorage.getItem(REVIEW_KEY);
   const summary=reviewSummary();
   reviewHeldVisible=summary.activeIds.includes(held[0])||summary.dueIds.includes(held[0]);
   reviewOrdinaryVisible=summary.activeIds.includes(ordinary.id)&&summary.dueIds.includes(ordinary.id);
   preserved=localStorage.getItem(REVIEW_KEY)===before;
  }finally{
   if(originalReviewRaw===null)localStorage.removeItem(REVIEW_KEY);
   else localStorage.setItem(REVIEW_KEY,originalReviewRaw);
  }
  return {searchLeaks,normalSearch,randomPracticeNoHeld,
    reviewHeldVisible,reviewOrdinaryVisible,preserved};
 },corpus);
 assert.deepEqual(entrances.searchLeaks,[], 'held official text exposed by search');
 assert(entrances.normalSearch&&entrances.randomPracticeNoHeld,
   'healthy questions must remain searchable/practicable while holds are excluded: '+JSON.stringify(entrances));
 assert(!entrances.reviewHeldVisible&&entrances.reviewOrdinaryVisible&&entrances.preserved,
   'held historical due review not suppressed without deleting saved progress: '+JSON.stringify(entrances));
 console.log(type.name(),width,'held-source search + random practice + due review PASS');
 for(const id of ids){
  const raw=corpus.find(q=>q.id===id);assert(raw,id);
  const result=await page.evaluate(raw=>{
   const before=JSON.stringify(localStorage);
   const q=normalize(raw),original=JSON.stringify(q);
   view='quiz';queue=[q];idx=0;selected=null;answered=false;sessionStats={done:0,correct:0,wrongTopics:[]};
   renderQuiz();pick('B');selected='B';submit(); // stale selected choice cannot bypass submit
   const blocked=!answered&&sessionStats.done===0&&document.querySelectorAll('#app .opt').length===0;
   answered=true;renderQuiz(); // old cached answer must not reveal bad text/analysis
   return {blocked,notice:document.getElementById('app').textContent.includes('暫停作答'),
    staleHidden:!document.getElementById('app').textContent.includes(q.q),
    same:original===JSON.stringify(q),storage:before===JSON.stringify(localStorage),
    overflow:document.documentElement.scrollWidth-innerWidth};
  },raw);
  assert(result.blocked&&result.notice&&result.staleHidden&&result.same&&result.storage&&result.overflow<=3,JSON.stringify(result));
  await page.evaluate(async raw=>{
   ALL=[normalize(raw)];SUBJECTS=[raw.subject];window.SWSI_QB.allComplete=true;
   await MK.open();MK.setMode('exam');MK.setPaper(raw.year+'|'+raw.round);MK.beginExam();
  },raw);
  assert.equal(await page.locator('.mk-ov .mk-opt').count(),0);
  assert((await page.locator('.mk-ov').innerText()).includes('待官方原卷覆核'));
  const storage=await page.evaluate(()=>JSON.stringify(localStorage));
  await page.evaluate(()=>{MK.pick('B');MK.submit();});
  assert.equal((await page.locator('.mk-ov .mk-score .big').innerText()).trim(),'0 / 0');
  assert((await page.locator('.mk-ov').innerText()).includes('已排除計分'));
  assert.equal(await page.evaluate(()=>JSON.stringify(localStorage)),storage);
  await page.evaluate(()=>MK.close());
  console.log(type.name(),width,id,'quiz + stale cache + mock PASS');
 }
 // Owner-approved exact-source Q40 and SP34 must now be visible, answerable
 // and correctly graded; only the other three 104-1 OCR cases are quarantined.
 for(const id of ['R-107-2-40','SP111-2-34']){
  const raw=corpus.find(q=>q.id===id);assert(raw,id);
  const result=await page.evaluate(raw=>{
    const q=normalize(raw);
    view='quiz';queue=[q];idx=0;selected=null;answered=false;
    sessionStats={done:0,correct:0,wrongTopics:[]};
    renderQuiz();
    const a=document.getElementById('app'),initial=a.innerText;
    const safe= !a.querySelector('[data-source-hold]') &&
      a.querySelectorAll('.opt').length===4 && initial.includes(q.q) &&
      !initial.includes('第 12 題答 B 或 C') &&
      !swsiSourceHeld(q) && q.answer===raw.answer;
    pick(q.answer);submit();
    return {safe,done:sessionStats.done,correct:sessionStats.correct,answer:q.answer};
  },raw);
  assert(result.safe&&result.done===1&&result.correct===1,
    'owner-approved official question must be re-enabled safely '+id+' '+JSON.stringify(result));
  console.log(type.name(),width,id,'approved source visible and correctly graded PASS');
 }
 // An ordinary official question remains answerable and scores normally.
 const raw=corpus.find(q=>q.id==='DS-104-1-01');assert(raw);
 const good=await page.evaluate(raw=>{
  const q=normalize(raw);queue=[q];idx=0;selected=null;answered=false;view='quiz';sessionStats={done:0,correct:0,wrongTopics:[]};
  renderQuiz();pick(q.answer);submit();return {done:sessionStats.done,correct:sessionStats.correct};
 },raw);
 assert.deepEqual(good,{done:1,correct:1});
 await context.close();
 }}finally{await browser.close();}
}
console.log('SOURCE HOLD BROWSER QA PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});

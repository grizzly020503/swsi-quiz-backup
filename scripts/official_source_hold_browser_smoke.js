#!/usr/bin/env node
'use strict';
// Exercise actual runtime with immutable official rows; no production writes.
const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium,webkit}=require('playwright');
const base=process.argv[2]||'http://127.0.0.1:4176/';
const origin=new URL(base).origin;
const corpus=JSON.parse(fs.readFileSync('cdn/question-shards/104-1.json')).questions;
const ids=['DS-104-1-22','DS-104-1-27','DS-104-1-29'];
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
 // An ordinary official question remains answerable and scores normally.
 const raw=corpus.find(q=>q.id==='DS-104-1-1');assert(raw);
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

#!/usr/bin/env node
'use strict';
// Real local browser acceptance for original MOEX figures: no live DB/AI/feedback.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
const base=process.argv[2] || 'http://127.0.0.1:4176/';
const origin=new URL(base).origin;
const rows=[
  {id:'DS-113-2-13',file:'113-2.json',width:975,height:859},
  {id:'R-114-2-12',file:'114-2.json',width:641,height:191},
].map(x=>{
  const d=JSON.parse(fs.readFileSync(path.join(__dirname,'../cdn/question-shards',x.file),'utf8'));
  const row=d.questions.find(q=>q.id===x.id);
  assert(row,'official question row missing '+x.id);
  return {...x,row};
});
async function runOne(browser,engine,entry,missing,layout){
  // Prevent WebKit/PWA service worker caches from bypassing the deliberate 404.
  // This test verifies UI fail-closed behavior; PWA caching is tested separately.
  const context=await browser.newContext({viewport:layout.viewport,deviceScaleFactor:layout.mobile?2:1,isMobile:layout.mobile,hasTouch:layout.mobile,serviceWorkers:'block'});
  const page=await context.newPage();
  page.on('dialog',dialog=>dialog.accept());
  const localImage='/official-figures/'+entry.id+'.png';
  let missingRequests=0;
  await page.route('**/*',route=>{
    const url=new URL(route.request().url());
    // Serve the pinned local 24-session manifest to the real boot loader.
    // External Supabase/AI/telemetry calls stay blocked; this test is offline.
    if(url.origin!==origin){
      if(url.hostname==='wandering-wave-4418.c022050333.workers.dev'&&
         url.pathname==='/question-shards/manifest.json'){
        return route.fulfill({status:200,contentType:'application/json',
          body:fs.readFileSync(path.join(__dirname,'../cdn/question-shards/manifest.json'))});
      }
      return route.abort();
    }
    if(missing && url.pathname===localImage){missingRequests++;return route.fulfill({status:404,body:'QA missing image'});}
    return route.continue();
  });
  try{
    await page.goto(base,{waitUntil:'domcontentloaded',timeout:20000});
    await page.waitForFunction(()=>typeof renderQuiz==='function'&&typeof window.MK==='object',{},{timeout:25000});
    // monthly_patch.js boots the site asynchronously and later calls go('home').
    // Do not inject a one-question fixture until that navigation has finished,
    // otherwise the boot callback can erase the quiz during WebKit image loading.
    await page.waitForFunction(()=>typeof view!=='undefined'&&view==='home'&&
      document.getElementById('tabbar')?.style.display==='flex',null,{timeout:25000});
    const initial=await page.evaluate(raw=>{
      const q=normalize(raw);
      view='quiz'; queue=[q]; idx=0;selected=null;answered=false;
      sessionStats={done:0,correct:0,wrongTopics:[]};
      delete SWSI_FIGURE_STATUS[raw.id];
      renderQuiz();
      const gated=document.querySelectorAll('#app .opt').length===0;
      pick('B'); // Must be inert while the original image has not loaded.
      return {gated,picked:selected,hasFigure:!!document.querySelector('#app figure[data-swsi-figure]')};
    },entry.row);
    assert(initial.gated&&initial.picked===null&&initial.hasFigure,
      engine+' '+entry.id+': early answer should be blocked before figure load '+JSON.stringify(initial));
    // WebKit can report image-ready before the DOM re-render finishes.
    // Require the actual figure/image in the document, not only its status flag.
    try{
      await page.waitForFunction(({id,missing,width,height})=>{
        if(SWSI_FIGURE_STATUS[id] !== (missing?'missing':'ready'))return false;
        const fig=document.querySelector('#app figure[data-swsi-figure="'+id+'"]');
        const img=fig&&fig.querySelector('img');
        return !!fig && (missing?!img:!!img&&img.complete&&img.naturalWidth===width&&img.naturalHeight===height);
      },{id:entry.id,missing,width:entry.width,height:entry.height},{timeout:15000});
    }catch(err){
      const diagnostic=await page.evaluate(id=>{
        const fig=document.querySelector('#app figure[data-swsi-figure="'+id+'"]');
        const img=fig?.querySelector('img');
        return {status:SWSI_FIGURE_STATUS[id]||'unset',view:typeof view==='undefined'?'unset':view,
          fig:!!fig,img:!!img,complete:img?.complete,naturalWidth:img?.naturalWidth,
          naturalHeight:img?.naturalHeight,currentSrc:img?.currentSrc,
          appPreview:document.getElementById('app')?.textContent?.slice(0,120)};
      },entry.id);
      throw new Error(engine+' '+entry.id+' figure DOM timeout '+JSON.stringify(diagnostic)+' '+err.message);
    }
    const state=await page.evaluate(({id,width,height,missing})=>{
      const fig=document.querySelector('#app figure[data-swsi-figure="'+id+'"]');
      const img=fig?.querySelector('img');
      const pdf=[...(fig?.querySelectorAll('a')||[])].find(a=>a.href.includes('moex.gov.tw'));
      const app=document.getElementById('app');
      const text=app.textContent;
      const rect=fig?.getBoundingClientRect();
      const imgRect=img?.getBoundingClientRect();
      return {
        hasFigure:!!fig,hasPdf:!!pdf && pdf.href.includes('wHandExamQandA_File.ashx'),
        status:SWSI_FIGURE_STATUS[id],options:app.querySelectorAll('.opt').length,
        blockedText:text.includes('本題不可作答'),
        suppressedWrongSurrogate:!text.includes('62 歲男性與 24 歲女兒'),
        imgOk:missing?!img:(!!img&&img.complete&&img.naturalWidth===width&&img.naturalHeight===height),
        withinViewport:!!rect&&rect.left>=-2&&rect.right<=innerWidth+2&&
          (missing||!!imgRect&&imgRect.width>180&&imgRect.right<=innerWidth+2),
        imageLink:!!img?.closest('a[target="_blank"]'),
        horizontalOverflow:Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-innerWidth,
      };
    },{id:entry.id,width:entry.width,height:entry.height,missing});
    if(missing)assert(missingRequests>=1,engine+' '+entry.id+' deliberate 404 was not intercepted');
    assert(state.hasFigure&&state.hasPdf&&state.imgOk&&state.withinViewport,
      engine+' '+entry.id+' figure/PDF/mobile failure '+JSON.stringify(state));
    assert(state.horizontalOverflow<=3,engine+' '+entry.id+' horizontal overflow '+state.horizontalOverflow);
    assert(state.suppressedWrongSurrogate,engine+' '+entry.id+' false relationship exposed');
    if(missing){
      assert(state.options===0&&state.blockedText,engine+' missing image exposed answer choices');
      const quizBlocked=await page.evaluate(()=>{
        pick('B'); submit();
        return {selected,answered,done:sessionStats.done};
      });
      assert.deepEqual(quizBlocked,{selected:null,answered:false,done:0});
    }else{
      assert(state.options===4&&state.imageLink,engine+' valid image not answerable/zoomable');
      const quizScored=await page.evaluate(()=>{
        pick('B');submit();
        return {selected,answered,done:sessionStats.done,correct:sessionStats.correct};
      });
      assert.deepEqual(quizScored,{selected:'B',answered:true,done:1,correct:1});
    }
    // Real timed mock-exam renderer and scoring, using exactly the same official
    // source row; no invented mock questions and no production network access.
    await page.evaluate(async raw=>{
      ALL=[normalize(raw)]; SUBJECTS=[raw.subject];
      // This hermetic acceptance test supplies the single audited official row;
      // it must not fetch the entire live corpus from the blocked production API.
      if(window.SWSI_QB)window.SWSI_QB.allComplete=true;
      // The unified grading overlay initializes asynchronously; await mounting.
      await window.MK.open();
      if(!document.querySelector('.mk-ov'))throw Error('Mock overlay was not mounted');
      window.MK.setMode('exam');
      window.MK.setPaper(raw.year+'|'+raw.round);
      window.MK.beginExam();
    },entry.row);
    await page.waitForSelector('.mk-ov figure[data-swsi-figure="'+entry.id+'"]',{timeout:10000});
    const mock=await page.evaluate(id=>({
      hasImage:!!document.querySelector('.mk-ov figure[data-swsi-figure="'+id+'"] img'),
      options:document.querySelectorAll('.mk-ov .mk-opt').length,
      hasPdf:!!document.querySelector('.mk-ov figure[data-swsi-figure="'+id+'"] a[href*="moex.gov.tw"]'),
      hasFalseSurrogate:(document.querySelector('.mk-ov')?.textContent||'').includes('62 歲男性與 24 歲女兒'),
    }),entry.id);
    assert(mock.hasPdf&&!mock.hasFalseSurrogate,engine+' mock source/wording mismatch');
    assert(missing?!mock.hasImage&&mock.options===0:mock.hasImage&&mock.options===4,
      engine+' '+entry.id+' mock figure-gate mismatch '+JSON.stringify(mock));
    await page.evaluate(()=>{ window.MK.pick('B'); window.MK.submit(); });
    const score=await page.locator('.mk-ov .mk-score .big').innerText();
    assert.strictEqual(score.trim(),missing?'0 / 0':'1 / 1',
      engine+' '+entry.id+' mock incorrect image-dependent score '+score);
    if(missing)assert((await page.locator('.mk-ov').innerText()).includes('1 題原圖未載入'),
      engine+' missing figure not excluded from result');
    console.log('FIGURE MOBILE '+engine+' '+entry.id+' '+(missing?'MISSING_SAFE':'LOADED_CORRECT')+' quiz+mock PASS');
  }finally{
    await context.close();
  }
}
(async()=>{
  for(const [engine,type] of [['chromium',chromium],['webkit',webkit]]){
    const browser=await type.launch({headless:true});
    try{
      for(const layout of [{name:'mobile',viewport:{width:390,height:844},mobile:true},{name:'desktop',viewport:{width:1366,height:900},mobile:false}]){
        for(const entry of rows){
          await runOne(browser,engine+' '+layout.name,entry,false,layout);
          await runOne(browser,engine+' '+layout.name,entry,true,layout);
        }
      }
    }finally{
      await browser.close();
    }
  }
  console.log('OFFICIAL MOEX FIGURE REAL MOBILE BROWSER QA PASS: 2 engines x 2 layouts x 2 figures x loaded/missing, quiz and mock');
})().catch(err=>{console.error(err&&err.stack||err);process.exitCode=1;});
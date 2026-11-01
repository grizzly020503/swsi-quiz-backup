#!/usr/bin/env node
'use strict';
// No provider calls or real student data; synthetic 1x1 image and mocked replies only.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:4173/';
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/Sc9NxQAAAABJRU5ErkJggg==','base64');
(async function(){
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:390,height:844}});
  try{
    const origin=new URL(base).origin;
    // Exercise the real local question-shard bootstrap without network calls.
    // Aborting every CDN shard made boot fail asynchronously, replacing the OCR
    // editor with a transient "題庫無法載入" screen and causing flaky QA.
    const SHARD_ORIGIN='wandering-wave-4418.c022050333.workers.dev';
    const SHARD_PREFIX='/question-shards/';
    const shardDir=path.resolve(process.cwd(),'cdn/question-shards');
    await page.route('**/*',route=>{
      const url=new URL(route.request().url());
      if(url.hostname===SHARD_ORIGIN&&url.pathname.startsWith(SHARD_PREFIX)){
        const name=decodeURIComponent(url.pathname.slice(SHARD_PREFIX.length));
        if(!name||path.basename(name)!==name)return route.fulfill({status:404,body:'not found'});
        const file=path.join(shardDir,name);
        if(!fs.existsSync(file))return route.fulfill({status:404,body:'not found'});
        return route.fulfill({status:200,contentType:'application/json; charset=utf-8',body:fs.readFileSync(file)});
      }
      return url.origin===origin?route.continue():route.abort();
    });
    await page.goto(base,{waitUntil:'domcontentloaded'});
    // A real student can use navigation only after the CDN manifest and essay
    // bootstrap finish. Calling the quick action before the tab bar becomes
    // visible races boot's final go('home') and falsely resets the test route.
    // This is a concrete readiness condition, not a fixed sleep or test skip.
    await page.locator('#tabbar').waitFor({state:'visible',timeout:20000});
    await page.waitForFunction(()=>{
      const app=document.getElementById('app');
      return app&&app.textContent.trim().length>150&&typeof view!=='undefined'&&view==='home';
    },null,{timeout:20000});
    // Use the canonical quick-essay navigation (same as real mobile students)
    // rather than calling legacy openEssayCard before navigation settles.
    await page.waitForFunction(()=>typeof window.swsiStartEssayNow==='function'&&
      Array.isArray(window.ESSAYS)&&window.ESSAYS.some(e=>e&&e.id&&e.q));
    await page.evaluate(async()=>{await window.swsiStartEssayNow();});
    try {
      await page.locator('.swsi-paper-essay').waitFor({timeout:20000});
    } catch(err) {
      const state=await page.evaluate(()=>({
        app:document.getElementById('app')?.textContent?.slice(0,1100),
        box:!!document.querySelector('#app .wbox'),
        editor:!!document.querySelector('#app textarea.wta'),
        essayCount:window.ESSAYS?.length||0,
        view:typeof view==='undefined'?'unavailable':view,
        opened:typeof openEssay==='undefined'?'unavailable':openEssay,
        paperVersion:window.SWSI_PAPER_ESSAY_VERSION||'missing'
      }));
      throw new Error('paper-first UI not mounted after canonical essay navigation: '+JSON.stringify(state)+'; '+String(err));
    }
    if (process.env.SWSI_HANDWRITING_EVIDENCE_DIR) {
      fs.mkdirSync(process.env.SWSI_HANDWRITING_EVIDENCE_DIR,{recursive:true});
      await page.screenshot({path:path.join(process.env.SWSI_HANDWRITING_EVIDENCE_DIR,'paper-first-mobile-390px.png'),fullPage:true});
    }
    assert.strictEqual(await page.locator('.swsi-paper-mode-paper').getAttribute('aria-pressed'),'true');
    assert.strictEqual(await page.locator('textarea.wta').evaluate(el=>getComputedStyle(el).display),'none');
    await page.evaluate(()=>{
      window.__paperRequests=[];
      window.__paperRequestHeaders=[];
      window.swsiRecordAITelemetry=()=>{};
      window.swsiFetchWithTimeout=async function(url,options){
        const req=JSON.parse(options.body);
        window.__paperRequests.push(req);
        window.__paperRequestHeaders.push(options.headers||{});
        const isPhoto=Array.isArray(req.messages[0].content);
        const answer=isPhoto?'【我讀到的作答】\n一、社會工作要尊重當事人的自決，運用◌了解需求。\n二、還要完成評估、資源連結、執行處遇與後續追蹤。':'一、可補上具體理論。\n二、題目要求要逐項回應。';
        return new Response(JSON.stringify({choices:[{message:{content:answer},finish_reason:(isPhoto&&window.__ocrReturnNoFinish)?undefined:
          ((isPhoto&&window.__ocrReturnTruncated)?'length':'stop')}]}),{status:200,headers:{'Content-Type':'application/json'}});
      };
    });
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'paper.png',mimeType:'image/png',buffer:png});
    try {
      await page.locator('.swsi-paper-review textarea').waitFor({timeout:12000});
    } catch(err) {
      // Diagnostic-only; do not silently downgrade the OCR confirmation gate.
      const snapshot=await page.evaluate(()=>({
        appText:document.querySelector('#app')?.textContent?.slice(-900),
        ocrStatus:document.querySelector('.swsi-paper-body>.swsi-paper-status')?.textContent,
        result:document.querySelector('[id^="airesult_"]')?.textContent?.slice(-1200),
        requests:window.__paperRequests?.map(r=>({model:r.model,isPhoto:Array.isArray(r.messages?.[0]?.content)})),
        publicModel:(typeof GROQ_MODEL==='string'?GROQ_MODEL:'UNAVAILABLE'),
        gradePhotoType:typeof window.gradePhoto,
        photoInputVisible:!!document.querySelector('input[id^="photo_"]'),
        reviewElements:document.querySelectorAll('.swsi-paper-review textarea').length
      }));
      throw new Error('OCR confirmation editor was not displayed: '+JSON.stringify(snapshot)+'; '+String(err));
    }
    if (process.env.SWSI_HANDWRITING_EVIDENCE_DIR) {
      await page.screenshot({path:path.join(process.env.SWSI_HANDWRITING_EVIDENCE_DIR,'ocr-review-before-confirm-390px.png'),fullPage:true});
    }
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),1);
    assert(await page.evaluate(()=>Array.isArray(window.__paperRequests[0].messages[0].content)));
    const photoClientId=await page.evaluate(()=>window.__paperRequestHeaders[0]['X-SWSI-Client-ID']);
    assert.match(photoClientId,/^[A-Za-z0-9_-]{16,128}$/,
      'photo OCR must use the same per-client ID contract as text feedback');
    assert((await page.evaluate(()=>new TextEncoder().encode(JSON.stringify(window.__paperRequests[0])).byteLength)) <= 3800000,
      'OCR request exceeded safe Worker payload limit');
    await page.locator('.swsi-paper-confirm').click();
    assert.match(await page.locator('.swsi-paper-review [role=status]').innerText(),/辨識不清/);
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),1,'unconfirmed OCR cannot trigger grading');
    // OCR providers may emit multiple unreadable-character conventions.
    // Every one must require explicit repair, not trigger a feedback call.
    const originalOCR=await page.locator('.swsi-paper-review textarea').inputValue();
    for(const marker of ['□','�','（看不清）','[無法辨識]','［無法辨識］']){
      await page.locator('.swsi-paper-review textarea').fill(originalOCR.replace('◌',marker));
      await page.locator('.swsi-paper-confirm').click();
      assert.match(await page.locator('.swsi-paper-review [role=status]').innerText(),/辨識不清/);
      assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),1,
        'alternate unreadable marker bypassed OCR confirmation');
    }
    await page.locator('.swsi-paper-review textarea').fill('一、應尊重案主自決並說明社會工作倫理及核心概念，結合理論評估其處境。\n二、提出資源連結、處遇計畫、後續追蹤及實務反思。');
    await page.locator('.swsi-paper-confirm').click();
    await page.waitForFunction(()=>window.__paperRequests.length===2);
    assert.strictEqual(await page.evaluate(()=>typeof window.__paperRequests[1].messages[0].content),'string');
    await page.locator('.swsi-paper-mode-text').click();
    assert.strictEqual(await page.locator('.swsi-paper-mode-text').getAttribute('aria-pressed'),'true');
    assert(await page.locator('textarea.wta').isVisible());
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),2,'switching input must not contact AI');
    // A provider length-limited OCR response cannot become editable 'complete' text,
    // cannot replace an existing confirmed draft, and must never auto-call feedback.
    await page.locator('.swsi-paper-mode-paper').click();
    assert.match(await page.locator('.swsi-paper-review textarea').inputValue(),/應尊重案主自決/,
      'switching between typing and paper must preserve already reviewed OCR text');
    const previousDraft=await page.locator('textarea.wta').inputValue();
    await page.evaluate(()=>{window.__ocrReturnTruncated=true;});
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'long-handwriting.png',mimeType:'image/png',buffer:png});
    await page.waitForFunction(()=>/辨識文字被截斷/.test(document.querySelector('.swsi-paper-body>.swsi-paper-status')?.textContent||''),null,{timeout:15000});
    assert.strictEqual(await page.locator('.swsi-paper-review textarea').count(),0,'truncated OCR must not expose a confirmation editor');
    assert.strictEqual(await page.locator('textarea.wta').inputValue(),previousDraft,'truncated OCR overwrote a verified draft');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),3,'truncated OCR must not trigger a feedback request');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.filter(r=>typeof r.messages[0].content==='string').length),1,'only explicitly confirmed answer may invoke text diagnosis');
    // A response without an explicit successful finish_reason must never
    // be treated as complete OCR, even if it contains plausible transcript text.
    await page.evaluate(()=>{window.__ocrReturnTruncated=false;window.__ocrReturnNoFinish=true;});
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'missing-finish.png',mimeType:'image/png',buffer:png});
    await page.waitForFunction(()=>/辨識沒有完整結束/.test(document.querySelector('.swsi-paper-body>.swsi-paper-status')?.textContent||''),null,{timeout:15000});
    assert.strictEqual(await page.locator('.swsi-paper-review textarea').count(),0,'missing OCR finish_reason exposed a confirmation editor');
    assert.strictEqual(await page.locator('textarea.wta').inputValue(),previousDraft,'unconfirmed OCR overwrote saved draft');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),4,'missing OCR finish_reason caused unsolicited feedback');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.filter(r=>typeof r.messages[0].content==='string').length),1,'only manually confirmed text can be diagnosed');
    await page.evaluate(()=>{window.__ocrReturnNoFinish=false;});
    // A huge encoded body must be blocked BEFORE reaching the AI service.
    // Reject by encoded request bytes, not by JPEG's binary size estimate.
    const sentBeforeOversize=await page.evaluate(()=>window.__paperRequests.length);
    await page.evaluate(()=>{
      window.__originalShrink=window.shrinkImage;
      window.__resizeLimits=[];
      window.shrinkImage=async function(_file,maxDim){
        window.__resizeLimits.push(maxDim);
        return 'data:image/jpeg;base64,'+'A'.repeat(4000000);
      };
    });
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'oversize-paper.png',mimeType:'image/png',buffer:png});
    await page.waitForFunction(()=>/超過整份上傳容量上限/.test(document.querySelector('.swsi-paper-body>.swsi-paper-status')?.textContent||''),null,{timeout:20000});
    assert.deepStrictEqual(await page.evaluate(()=>window.__resizeLimits),[1800,1600,1400],
      'image size reduction must be bounded to legibility floor');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),sentBeforeOversize,
      'oversize photographs must not spend AI quota');
    assert.strictEqual(await page.locator('textarea.wta').inputValue(),previousDraft,'oversize photo must not affect saved answer');
    await page.evaluate(()=>{window.shrinkImage=window.__originalShrink;});
    // >25 MiB original file should fail before browser decoding or provider call.
    const giant=Buffer.alloc(25*1024*1024+1,0);
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'too-large-original.jpg',mimeType:'image/jpeg',buffer:giant});
    await page.waitForFunction(()=>/每張 25 MB/.test(document.querySelector('.swsi-paper-body>.swsi-paper-status')?.textContent||''),null,{timeout:12000});
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),sentBeforeOversize,
      'original-file size failure must not make AI calls');
    // Switching away must cancel an in-flight OCR session permanently,
    // even if the student switches back before the old provider reply arrives.
    const draftBeforeStale=await page.locator('textarea.wta').inputValue();
    const requestsBeforeStale=await page.evaluate(()=>window.__paperRequests.length);
    await page.evaluate(()=>{
      window.__staleOCRResolve=null;
      window.swsiFetchWithTimeout=async function(_url,opts){
        const payload=JSON.parse(opts.body);
        window.__paperRequests.push(payload);
        return await new Promise(resolve=>{
          window.__staleOCRResolve=()=>resolve(new Response(JSON.stringify({
            choices:[{message:{content:'【我讀到的作答】\\n一、舊照片內容不得回填。\\n二、舊資料不得覆蓋新草稿。'},finish_reason:'stop'}]
          }),{status:200,headers:{'Content-Type':'application/json'}}));
        });
      };
    });
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'stale-ocr.png',mimeType:'image/png',buffer:png});
    await page.waitForFunction(()=>typeof window.__staleOCRResolve==='function');
    await page.locator('.swsi-paper-mode-text').click();
    await page.locator('.swsi-paper-mode-paper').click();
    await page.evaluate(()=>window.__staleOCRResolve());
    await page.waitForTimeout(100);
    assert.strictEqual(await page.locator('.swsi-paper-review textarea').count(),0,
      'an OCR reply from a cancelled mode switch must not reappear');
    assert.strictEqual(await page.locator('textarea.wta').inputValue(),draftBeforeStale,
      'cancelled OCR must never overwrite confirmed draft');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),requestsBeforeStale+1,
      'cancelled OCR must not trigger AI diagnosis');
    console.log('HANDWRITTEN ESSAY OCR CONFIRM QA OK: photo OCR, correction, explicit diagnosis, typed fallback, truncation NO-GO');
  }finally{await browser.close();}
})().catch(err=>{console.error(err);process.exitCode=1;});

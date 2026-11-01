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
      window.__nativeFetch=window.fetch.bind(window);
      window.fetch=async function(url,options){
        if(!String(url).includes('/api/ai'))return window.__nativeFetch(url,options);
        const req=JSON.parse(options.body);
        window.__paperRequests.push(req);
        window.__paperRequestHeaders.push(Object.fromEntries(new Headers(options.headers||{}).entries()));
        const isPhoto=Array.isArray(req.messages[0].content);
        if(!isPhoto&&window.__textHoldOnce){
          window.__textHoldOnce=false;
          return new Promise(resolve=>{
            window.__resolveHeldFeedback=()=>resolve(new Response(
              JSON.stringify({error:{code:'UPSTREAM_UNAVAILABLE',message:'AI 服務暫時不可用'}}),
              {status:503,headers:{'Content-Type':'application/json'}}));
          });
        }
        if(!isPhoto&&window.__textFailureOnce){
          window.__textFailureOnce=false;
          return new Response(JSON.stringify({error:{code:'UPSTREAM_UNAVAILABLE',message:'AI 服務暫時不可用'}}),{status:503,headers:{'Content-Type':'application/json'}});
        }
        // Model-access failures and model-supplied grading text are not valid OCR.
        if(isPhoto&&window.__ocrRejectOnce){
          window.__ocrRejectOnce=false;
          return new Response(JSON.stringify({error:{code:'FORBIDDEN',message:'OCR 測試存取被拒絕'}}),
            {status:403,headers:{'Content-Type':'application/json'}});
        }
        if(isPhoto&&window.__ocrInjectedFeedbackOnce){
          window.__ocrInjectedFeedbackOnce=false;
          return new Response(JSON.stringify({choices:[{message:{
            content:'【我讀到的作答】\\n一、這是模擬辨識稿。\\n【練習回饋】不得隱藏批改文字。'
          },finish_reason:'stop'}]}),{status:200,headers:{'Content-Type':'application/json'}});
        }
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
    const photoClientId=await page.evaluate(()=>window.__paperRequestHeaders[0]['x-swsi-client-id']);
    assert.match(photoClientId,/^[A-Za-z0-9_-]{16,128}$/,
      'real SWSI transport wrapper must set a valid photo OCR client ID');
    assert((await page.evaluate(()=>new TextEncoder().encode(JSON.stringify(window.__paperRequests[0])).byteLength)) <= 3800000,
      'OCR request exceeded safe Worker payload limit');
    // Unconfirmed OCR is kept only in browser memory, not localStorage.
    // Navigating to the list or another question must not discard the text
    // within the current tab, submit grading, or leak it into another essay.
    const essayId=(await page.locator('#app textarea.wta').getAttribute('id')).slice(3);
    const unconfirmedOCR=await page.locator('.swsi-paper-review textarea').inputValue();
    const draftBeforeNav=await page.locator('textarea.wta').inputValue();
    // Invalid selections are rejected *before* replacing the existing OCR
    // session, so a student who mis-selects four photos keeps corrections.
    const rejectedBaseline=await page.evaluate(()=>window.__paperRequests.length);
    await page.locator('input[type=file][id^="photo_"]').setInputFiles(
      Array.from({length:4},(_,i)=>({name:'invalid-'+i+'.png',mimeType:'image/png',buffer:png}))
    );
    await page.waitForFunction(()=>/一次只允許 1–3 張/.test(
      document.querySelector('.swsi-paper-body>.swsi-paper-status')?.textContent||''),null,{timeout:12000});
    assert.strictEqual(await page.locator('.swsi-paper-review textarea').inputValue(),unconfirmedOCR,
      'invalid photo count must preserve the unconfirmed OCR review');
    assert.strictEqual(await page.locator('textarea.wta').inputValue(),draftBeforeNav,
      'invalid photo count must not alter the typed draft');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),rejectedBaseline,
      'invalid photo count must not spend AI quota');
    const requestsBeforeNav=await page.evaluate(()=>window.__paperRequests.length);
    await page.evaluate(()=>closeEssay());
    await page.locator('.swsi-paper-essay').waitFor({state:'detached'});
    const otherEssayId=await page.evaluate(id=>window.ESSAYS.find(e=>e&&e.id&&e.id!==id)?.id||'',essayId);
    if(otherEssayId){
      await page.evaluate(id=>toggleEssay(id),otherEssayId);
      await page.locator('.swsi-paper-essay').waitFor({timeout:12000});
      assert.strictEqual(await page.locator('.swsi-paper-review textarea').count(),0,
        'unconfirmed OCR text must not leak across essay questions');
      await page.evaluate(()=>closeEssay());
    }
    await page.evaluate(id=>toggleEssay(id),essayId);
    await page.locator('.swsi-paper-review textarea').waitFor({timeout:12000});
    assert.strictEqual(await page.locator('.swsi-paper-review textarea').inputValue(),unconfirmedOCR,
      'unconfirmed OCR must survive same-tab essay navigation');
    assert.strictEqual(await page.locator('textarea.wta').inputValue(),draftBeforeNav,
      'unconfirmed OCR must not overwrite the student draft on navigation');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),requestsBeforeNav,
      'navigating questions must not consume AI quota');
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
    await page.waitForFunction(()=>/回饋已完成/.test(document.querySelector('.swsi-paper-review [role=status]')?.textContent||''),null,{timeout:15000});
    assert.strictEqual(await page.evaluate(()=>typeof window.__paperRequests[1].messages[0].content),'string');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequestHeaders[0]['x-swsi-client-id']),
      await page.evaluate(()=>window.__paperRequestHeaders[1]['x-swsi-client-id']),
      'OCR and confirmed text-feedback request must use the same real transport client ID');
    await page.locator('.swsi-paper-mode-text').click();
    assert.strictEqual(await page.locator('.swsi-paper-mode-text').getAttribute('aria-pressed'),'true');
    assert(await page.locator('textarea.wta').isVisible());
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),2,'switching input must not contact AI');
    // A provider length-limited OCR response cannot become editable 'complete' text,
    // cannot replace an existing confirmed draft, and must never auto-call feedback.
    await page.locator('.swsi-paper-mode-paper').click();
    assert.match(await page.locator('.swsi-paper-review textarea').inputValue(),/應尊重案主自決/,
      'switching between typing and paper must preserve already reviewed OCR text');
    assert(await page.locator('.swsi-paper-confirm').isDisabled(),
      'switching back to a confirmed OCR answer must not re-enable a duplicate feedback call');
    await page.locator('.swsi-paper-confirm').evaluate(button=>button.click());
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),2,
      're-entering paper mode must not silently consume a second text feedback call');
    const reviewed=await page.locator('.swsi-paper-review textarea').inputValue();
    await page.locator('.swsi-paper-review textarea').fill(reviewed+'\n（待修訂）');
    assert(await page.locator('.swsi-paper-confirm').isEnabled(),
      'a genuinely edited transcription must be eligible for new confirmation');
    await page.locator('.swsi-paper-review textarea').fill(reviewed);
    assert(await page.locator('.swsi-paper-confirm').isDisabled(),
      'restoring already-confirmed transcription must disable duplicate submission');
    const previousDraft=await page.locator('textarea.wta').inputValue();
    await page.evaluate(()=>{window.__ocrReturnTruncated=true;});
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'long-handwriting.png',mimeType:'image/png',buffer:png});
    await page.waitForFunction(()=>/辨識文字被截斷/.test(document.querySelector('.swsi-paper-body>.swsi-paper-status')?.textContent||''),null,{timeout:15000});
    assert.strictEqual(await page.locator('.swsi-paper-review textarea').inputValue(),reviewed,'truncated replacement must retain the prior confirmed transcript');
    assert(await page.locator('.swsi-paper-confirm').isDisabled(),'truncation must not unlock already confirmed text');
    assert.strictEqual(await page.locator('textarea.wta').inputValue(),previousDraft,'truncated OCR overwrote a verified draft');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),3,'truncated OCR must not trigger a feedback request');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.filter(r=>typeof r.messages[0].content==='string').length),1,'only explicitly confirmed answer may invoke text diagnosis');
    // A response without an explicit successful finish_reason must never
    // be treated as complete OCR, even if it contains plausible transcript text.
    await page.evaluate(()=>{window.__ocrReturnTruncated=false;window.__ocrReturnNoFinish=true;});
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'missing-finish.png',mimeType:'image/png',buffer:png});
    await page.waitForFunction(()=>/辨識沒有完整結束/.test(document.querySelector('.swsi-paper-body>.swsi-paper-status')?.textContent||''),null,{timeout:15000});
    assert.strictEqual(await page.locator('.swsi-paper-review textarea').inputValue(),reviewed,'missing finish_reason must retain the prior confirmed transcript');
    assert(await page.locator('.swsi-paper-confirm').isDisabled(),'incomplete OCR must not unlock already confirmed text');
    assert.strictEqual(await page.locator('textarea.wta').inputValue(),previousDraft,'unconfirmed OCR overwrote saved draft');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),4,'missing OCR finish_reason caused unsolicited feedback');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.filter(r=>typeof r.messages[0].content==='string').length),1,'only manually confirmed text can be diagnosed');
    await page.evaluate(()=>{window.__ocrReturnNoFinish=false;});
    // A denied private-model path (403) must fail closed: no confirmed OCR,
    // no grading, no draft overwrite, and the upload button must recover.
    const denyBaseline=await page.evaluate(()=>window.__paperRequests.length);
    await page.evaluate(()=>{window.__ocrRejectOnce=true;});
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'provider-denied.png',mimeType:'image/png',buffer:png});
    await page.waitForFunction(()=>document.querySelector('[id^="aiphoto_"]')?.disabled===false &&
      !/正在辨識文字/.test(document.querySelector('.swsi-paper-body>.swsi-paper-status')?.textContent||''),null,{timeout:15000});
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),denyBaseline+1,
      'provider denial must not retry or send text feedback');
    assert.strictEqual(await page.locator('.swsi-paper-review textarea').inputValue(),reviewed,
      'provider denial must keep only the previous confirmed transcript');
    assert(await page.locator('.swsi-paper-confirm').isDisabled(),'denial must not unlock previous confirmed text');
    assert.strictEqual(await page.locator('textarea.wta').inputValue(),previousDraft,
      'provider denial must not overwrite the verified answer');
    // A provider could return a nominally completed OCR response containing a
    // grading section. That is NOT an OCR-only answer and cannot be confirmed.
    const injectedBaseline=await page.evaluate(()=>window.__paperRequests.length);
    await page.evaluate(()=>{window.__ocrInjectedFeedbackOnce=true;});
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'mixed-ocr-feedback.png',mimeType:'image/png',buffer:png});
    await page.waitForFunction(()=>/辨識結果不可靠/.test(document.querySelector('.swsi-paper-body>.swsi-paper-status')?.textContent||''),null,{timeout:15000});
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),injectedBaseline+1,
      'provider-generated grading text must not cause an unsolicited feedback call');
    assert.strictEqual(await page.locator('.swsi-paper-review textarea').inputValue(),reviewed,
      'provider-generated grading text must not replace the previous transcript');
    assert(await page.locator('.swsi-paper-confirm').isDisabled(),'injected grading must not unlock previous confirmed text');
    assert.strictEqual(await page.locator('textarea.wta').inputValue(),previousDraft,
      'model-injected grading text must not alter the confirmed draft');
    // Real correction work must survive a *valid* replacement photo whose OCR
    // provider later rejects it. This differs from an invalid 4-photo picker.
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'old-ocr-before-failure.png',mimeType:'image/png',buffer:png});
    await page.locator('.swsi-paper-review textarea').waitFor({timeout:12000});
    const preservedOCR='一、這是學生已自行校正的既有手寫辨識稿，請勿因重新拍照失敗而刪除。\\n二、仍有◌需要人工對照原稿，不能自動送去批改。';
    await page.locator('.swsi-paper-review textarea').fill(preservedOCR);
    const preservedTypedDraft=await page.locator('textarea.wta').inputValue();
    const beforeFailedReplacement=await page.evaluate(()=>window.__paperRequests.length);
    const feedbackBeforeReplacement=await page.evaluate(()=>
      window.__paperRequests.filter(r=>typeof r.messages[0].content==='string').length);
    await page.evaluate(()=>{window.__ocrRejectOnce=true;});
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'valid-photo-denied-by-provider.png',mimeType:'image/png',buffer:png});
    await page.waitForFunction(expected=>window.__paperRequests.length===expected+1 &&
      document.querySelector('[id^="aiphoto_"]')?.disabled===false &&
      !!document.querySelector('.swsi-paper-review textarea'),beforeFailedReplacement,{timeout:15000});
    assert.strictEqual(await page.locator('.swsi-paper-review textarea').inputValue(),preservedOCR,
      'HTTP 403 on a valid replacement photo must restore edited unconfirmed OCR');
    assert.strictEqual(await page.locator('textarea.wta').inputValue(),preservedTypedDraft,
      'failed replacement photo must preserve the saved typed answer');
    assert.strictEqual(await page.evaluate(()=>
      window.__paperRequests.filter(r=>typeof r.messages[0].content==='string').length),
      feedbackBeforeReplacement,'OCR replacement failure must not spend feedback quota');
    const beforeTruncatedReplacement=await page.evaluate(()=>window.__paperRequests.length);
    await page.evaluate(()=>{window.__ocrReturnTruncated=true;});
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'valid-photo-truncated-by-provider.png',mimeType:'image/png',buffer:png});
    await page.waitForFunction(()=>/辨識文字被截斷/.test(
      document.querySelector('.swsi-paper-body>.swsi-paper-status')?.textContent||'') &&
      document.querySelector('[id^="aiphoto_"]')?.disabled===false &&
      !!document.querySelector('.swsi-paper-review textarea'),null,{timeout:15000});
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),beforeTruncatedReplacement+1,
      'truncated replacement should consume only its attempted OCR request');
    assert.strictEqual(await page.locator('.swsi-paper-review textarea').inputValue(),preservedOCR,
      'truncated replacement must preserve the previous manually edited OCR');
    assert.strictEqual(await page.locator('textarea.wta').inputValue(),preservedTypedDraft,
      'truncated replacement must not overwrite the student draft');
    await page.evaluate(()=>{window.__ocrReturnTruncated=false;});
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
    // The same confirmed transcription must be retryable when the text-feedback
    // provider returns 503. Failed feedback must not force another paid OCR call.
    const retryBaseline=await page.evaluate(()=>window.__paperRequests.length);
    const photoBeforeRetry=await page.evaluate(()=>window.__paperRequests.filter(x=>Array.isArray(x.messages[0].content)).length);
    await page.evaluate(()=>{window.__textFailureOnce=true;});
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'retry-feedback.png',mimeType:'image/png',buffer:png});
    await page.locator('.swsi-paper-review textarea').waitFor({timeout:12000});
    const retryText='一、政策討論要指出現況與制度限制，說明問題背景及影響。\\n二、提出可行政策與實務分析，兼顧當事人自主、家庭支持及福利資源連結。';
    await page.locator('.swsi-paper-review textarea').fill(retryText);
    page.once('dialog',dialog=>dialog.accept());
    await page.locator('.swsi-paper-confirm').click();
    await page.waitForFunction(()=>document.querySelector('.swsi-paper-review .swsi-paper-confirm')?.disabled===false
      &&/回饋尚未完成/.test(document.querySelector('.swsi-paper-review [role=status]')?.textContent||''),null,{timeout:15000});
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),retryBaseline+2,
      'initial retry case should make exactly one OCR and one failed text-feedback request');
    assert.strictEqual(await page.locator('textarea.wta').inputValue(),retryText,
      'failed text-feedback must preserve the manually confirmed draft');
    await page.locator('.swsi-paper-confirm').click();
    await page.waitForFunction(()=>document.querySelector('.swsi-paper-review .swsi-paper-confirm')?.disabled===true
      &&/回饋已完成/.test(document.querySelector('.swsi-paper-review [role=status]')?.textContent||''),null,{timeout:15000});
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),retryBaseline+3,
      'recovery must use only one additional text-feedback call; no new OCR call');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.filter(x=>Array.isArray(x.messages[0].content)).length),photoBeforeRetry+1,
      'recovery should not upload the photograph a second time');
    const requestsAfterSuccess=await page.evaluate(()=>window.__paperRequests.length);
    await page.locator('.swsi-paper-confirm').evaluate(button=>button.click());
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),requestsAfterSuccess,
      'successful retry must not be repeated from stale confirmation UI');
    // Switching typing/paper while a feedback request is pending re-creates
    // the review button. A 503 must unblock the *new* button, not only the stale one.
    const duringModeBaseline=await page.evaluate(()=>window.__paperRequests.length);
    await page.evaluate(()=>{window.__textHoldOnce=true;window.__resolveHeldFeedback=null;});
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'mode-switch-feedback.png',mimeType:'image/png',buffer:png});
    await page.locator('.swsi-paper-review textarea').waitFor({timeout:12000});
    const newText='一、分析國家政策與社會生活條件，注意家庭選擇與照顧負擔。\\n二、建立社會支持並評估福利措施是否符合需求。';
    await page.locator('.swsi-paper-review textarea').fill(newText);
    page.once('dialog',dialog=>dialog.accept());
    await page.locator('.swsi-paper-confirm').click();
    await page.waitForFunction(()=>typeof window.__resolveHeldFeedback==='function',null,{timeout:12000});
    await page.locator('.swsi-paper-mode-text').click();
    await page.locator('.swsi-paper-mode-paper').click();
    assert(await page.locator('.swsi-paper-confirm').isDisabled(),
      'new review button must remain disabled while feedback is pending');
    await page.evaluate(()=>window.__resolveHeldFeedback());
    await page.waitForFunction(()=>document.querySelector('.swsi-paper-review .swsi-paper-confirm')?.disabled===false
      &&/回饋尚未完成/.test(document.querySelector('.swsi-paper-review [role=status]')?.textContent||''),null,{timeout:15000});
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),duringModeBaseline+2,
      'switching input modes during failed feedback must not duplicate OCR or text calls');
    assert.strictEqual(await page.locator('textarea.wta').inputValue(),newText,
      'failed feedback after mode switch must preserve the confirmed answer');
    await page.locator('.swsi-paper-confirm').click();
    await page.waitForFunction(()=>document.querySelector('.swsi-paper-review .swsi-paper-confirm')?.disabled===true
      &&/已確認/.test(document.querySelector('.swsi-paper-review [role=status]')?.textContent||''),null,{timeout:15000});
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),duringModeBaseline+3,
      'retry should make only one new text request without another photo upload');
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

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
    await page.waitForFunction(()=>typeof window.openEssayCard==='function'&&Array.isArray(window.ESSAYS)&&window.ESSAYS.length>0);
    await page.evaluate(()=>{const e=window.ESSAYS[0];window.openEssayCard(e.id,e.subject);});
    await page.locator('.swsi-paper-essay').waitFor();
    assert.strictEqual(await page.locator('.swsi-paper-mode-paper').getAttribute('aria-pressed'),'true');
    assert.strictEqual(await page.locator('textarea.wta').evaluate(el=>getComputedStyle(el).display),'none');
    await page.evaluate(()=>{
      window.__paperRequests=[];
      window.swsiRecordAITelemetry=()=>{};
      window.swsiFetchWithTimeout=async function(url,options){
        const req=JSON.parse(options.body);
        window.__paperRequests.push(req);
        const isPhoto=Array.isArray(req.messages[0].content);
        const answer=isPhoto?'【我讀到的作答】\n一、社會工作要尊重當事人的自決，運用◌了解需求。\n二、還要完成評估、資源連結、執行處遇與後續追蹤。':'一、可補上具體理論。\n二、題目要求要逐項回應。';
        return new Response(JSON.stringify({choices:[{message:{content:answer},finish_reason:(isPhoto&&window.__ocrReturnTruncated)?'length':'stop'}]}),{status:200,headers:{'Content-Type':'application/json'}});
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
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),1);
    assert(await page.evaluate(()=>Array.isArray(window.__paperRequests[0].messages[0].content)));
    await page.locator('.swsi-paper-confirm').click();
    assert.match(await page.locator('.swsi-paper-review [role=status]').innerText(),/辨識不清/);
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),1,'unconfirmed OCR cannot trigger grading');
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
    const previousDraft=await page.locator('textarea.wta').inputValue();
    await page.evaluate(()=>{window.__ocrReturnTruncated=true;});
    await page.locator('input[type=file][id^="photo_"]').setInputFiles({name:'long-handwriting.png',mimeType:'image/png',buffer:png});
    await page.waitForFunction(()=>/辨識文字被截斷/.test(document.querySelector('.swsi-paper-body>.swsi-paper-status')?.textContent||''),null,{timeout:15000});
    assert.strictEqual(await page.locator('.swsi-paper-review textarea').count(),0,'truncated OCR must not expose a confirmation editor');
    assert.strictEqual(await page.locator('textarea.wta').inputValue(),previousDraft,'truncated OCR overwrote a verified draft');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.length),3,'truncated OCR must not trigger a feedback request');
    assert.strictEqual(await page.evaluate(()=>window.__paperRequests.filter(r=>typeof r.messages[0].content==='string').length),1,'only explicitly confirmed answer may invoke text diagnosis');
    console.log('HANDWRITTEN ESSAY OCR CONFIRM QA OK: photo OCR, correction, explicit diagnosis, typed fallback, truncation NO-GO');
  }finally{await browser.close();}
})().catch(err=>{console.error(err);process.exitCode=1;});

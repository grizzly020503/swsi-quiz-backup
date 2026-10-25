'use strict';
// Real local UI + synthetic transport only; no provider calls or student data.
const assert=require('assert');
const {chromium,webkit}=require('playwright');
const serveLocalQuestionShards=require('./local_question_shards_fixture');
const base=process.argv[2]||'http://127.0.0.1:4173/';
const engine=process.argv[3]||'chromium';
assert(['chromium','webkit'].includes(engine));
const id='社會工作-112-2-申論2';

(async()=>{
  const browser=await ({chromium,webkit})[engine].launch({headless:true});
  try{
    for(const denyGuideAsset of [false,true]){
      const context=await browser.newContext({viewport:{width:390,height:844}});
      await serveLocalQuestionShards(context);
      const page=await context.newPage();
      if(denyGuideAsset)await page.route('**/essay_guides.js*',route=>route.abort());
      await page.goto(base,{waitUntil:'domcontentloaded'});
      await page.locator('.swsi-focus-primary').waitFor();
      await page.locator('#t-essay').click();
      await page.locator('#app .gcard').filter({has:page.getByText('社會工作',{exact:true})}).click();
      await page.locator('[onclick="toggleEssay(\''+id+'\')"]').click();
      await page.locator('.swsi-paper-essay').waitFor();
      const stem=await page.locator('.ebody').innerText();
      assert(stem.includes('Cowger')&&stem.includes('經濟弱勢的女性'),'official Cowger question missing');
      assert(!stem.includes('百分之三十')&&!stem.includes('資源分配的四種標準'),'old substituted question returned');
      assert.strictEqual(await page.evaluate(id=>window.swsiEssayGuideIsVerified(id),id),false);
      await page.locator('.swsi-paper-mode-text').click();
      await page.locator('textarea.wta').fill('先依題目提供的家庭經濟與就業情境評估個人的能力、支持資源及面臨的限制，再與服務對象共同確認就業目標及服務優先順序。');
      await page.evaluate(id=>{
        window.__correctedRequest=null;
        const answer=document.querySelector('textarea.wta').value;
        localStorage.setItem(window.swsiAICacheKey(id),JSON.stringify({answer,feedback:'LEGACY_RESOURCE_ALLOCATION_FEEDBACK',at:Date.now()}));
        window.swsiFetchWithTimeout=async(_url,options)=>{
          window.__correctedRequest=JSON.parse(options.body);
          return {ok:true,status:200,json:async()=>({choices:[{message:{content:'合成傳輸測試，不是模型品質評分。'}}]})};
        };
      },id);
      await page.locator('[id^="aitype_"]').click();
      await page.waitForFunction(()=>window.__correctedRequest!==null);
      const prompt=await page.evaluate(()=>window.__correctedRequest.messages[0].content);
      assert(prompt.includes('Cowger'),'AI handler received old official question');
      assert(!prompt.includes('百分之三十')&&!prompt.includes('資源分配的四種標準'),'old question leaked to AI');
      assert(!prompt.includes('SWSI 已逐題核對的參考架構'),'quarantined guide was treated as verified');
      assert(!(await page.locator('[id^="airesult_"]').innerText()).includes('LEGACY_RESOURCE_ALLOCATION_FEEDBACK'),'legacy feedback survived the official question correction');
      const cacheCheck=await page.evaluate(id=>{
        const answer=document.querySelector('textarea.wta').value;
        const good=window.swsiGetAICache(id,answer);
        const essay=window.ESSAYS.find(e=>e.id===id),q=essay.q;
        essay.q='合成負例：舊題幹不可重用新題的回饋';
        const wrongQuestion=window.swsiGetAICache(id,answer);
        essay.q=q;
        const wrongAnswer=window.swsiGetAICache(id,answer+'新增內容');
        const version=window.SWSI_ESSAY_TRUST_VERSION;
        window.SWSI_ESSAY_TRUST_VERSION='synthetic-different-prompt';
        const wrongPrompt=window.swsiGetAICache(id,answer);
        window.SWSI_ESSAY_TRUST_VERSION=version;
        const verified=window.swsiEssayGuideIsVerified;
        window.swsiEssayGuideIsVerified=()=>true;
        const wrongReference=window.swsiGetAICache(id,answer);
        window.swsiEssayGuideIsVerified=verified;
        const restored=window.swsiGetAICache(id,answer);
        return {schema:good&&good.schema_version,wrongQuestion,wrongAnswer,wrongPrompt,wrongReference,restored:!!restored};
      },id);
      assert.strictEqual(cacheCheck.schema,2,'feedback cache lacks question/model/reference context');
      for(const key of ['wrongQuestion','wrongAnswer','wrongPrompt','wrongReference']){
        assert.strictEqual(cacheCheck[key],null,'feedback cache ignored '+key);
      }
      assert.strictEqual(cacheCheck.restored,true,'unchanged context cache failed');
      await page.locator('[id^="gbtn_"]').click();
      const guide=await page.locator('.guide').innerText();
      assert(guide.includes('參考架構待重新核對'),'guide quarantine notice missing');
      assert(!/Dolgoff|Reamer|倫理原則篩選表/.test(guide),'stale ethics template returned');
      await context.close();
    }
    console.log('OFFICIAL ESSAY CORRECTION BROWSER OK '+engine+': corrected question, stale guide withheld, exact AI payload; normal and denied guide asset');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});

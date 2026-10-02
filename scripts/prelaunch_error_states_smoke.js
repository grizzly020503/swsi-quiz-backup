const assert=require('assert');
const {chromium}=require('playwright');

const base=process.argv[2]||'http://127.0.0.1:4173/';

(async()=>{
  const browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:390,height:844}});
  const page=await context.newPage();
  const pageErrors=[];
  page.on('pageerror',e=>pageErrors.push(String(e&&e.message||e)));

  await page.goto(base,{waitUntil:'commit',timeout:15000});
  await page.waitForSelector('.swsi-focus-primary',{timeout:30000});
  await page.evaluate(()=>{try{localStorage.clear();sessionStorage.clear();}catch(_e){}});
  await page.reload({waitUntil:'commit'});
  await page.waitForSelector('.swsi-focus-primary',{timeout:30000});

  // Public information center: all four sections must open, switch, close, and restore usability.
  assert.strictEqual(await page.evaluate(()=>typeof window.swsiOpenPublicInfo),'function','public information opener missing');
  const infoCases=[
    ['about','關於 SWSI'],
    ['sources','資料來源'],
    ['privacy','隱私'],
    ['terms','使用條款']
  ];
  for(const [key,label] of infoCases){
    await page.evaluate(k=>window.swsiOpenPublicInfo(k),key);
    await page.waitForSelector('#swsi-public-info-backdrop .swsi-public-info-dialog',{timeout:5000});
    const text=await page.locator('#swsi-public-info-backdrop').innerText();
    assert(text.includes(label),`public info ${key} content missing`);
    const box=await page.locator('.swsi-public-info-dialog').boundingBox();
    assert(box&&box.y>=0&&box.y+box.height<=844+2,`public info ${key} escapes mobile viewport`);
    await page.keyboard.press('Escape');
    await page.waitForFunction(()=>!document.getElementById('swsi-public-info-backdrop'));
  }
  assert(!await page.locator('#swsi-public-info-backdrop').count(),'public info backdrop stuck open');

  // Empty review is now owned by the combined Learning Center. It must remain a
  // useful state with a clear next action, not an exception/dead-end.
  await page.evaluate(()=>{try{localStorage.clear();}catch(_e){}});
  await page.locator('#t-review').click();
  await page.waitForSelector('.swsi-myhub',{timeout:10000});
  await page.waitForFunction(()=>{
    const app=document.querySelector('#app');
    return app&&(/還沒有錯題|目前沒有待複習題/.test(app.textContent||''));
  },null,{timeout:10000});
  const emptyReview=await page.locator('#app').innerText();
  assert(/還沒有錯題|目前沒有待複習題/.test(emptyReview),'review empty state missing');
  assert(/快速刷題|完成一組 20 題|開始刷題/.test(emptyReview),'review empty state lacks a next step');
  assert(!/undefined|null|NaN/.test(emptyReview),'review empty state leaked invalid values');
  await page.locator('#t-home').click();
  await page.waitForSelector('.swsi-focus-primary',{timeout:10000});

  // AI network failure: answer stays saved, busy state clears, and the user
  // gets plain-language recovery copy. Enter Essay, choose a subject, then choose a real question.
  await page.locator('#t-essay').click();
  await page.waitForSelector('#app .gcard', { timeout: 30000 });
  await page.locator('#app .gcard').first().click();
  await page.waitForSelector('#app [onclick^="toggleEssay("]', { timeout: 30000 });
  await page.locator('#app [onclick^="toggleEssay("]').first().click();
  await page.waitForSelector('.wta',{timeout:30000});
  let blockedPost='';
  await page.route('**/*',route=>{
    const req=route.request();
    if(req.method()==='POST'){
      blockedPost=req.url();
      return route.abort('failed');
    }
    return route.continue();
  });
  const ta=page.locator('.wta').first();
  await ta.fill('這是一段用來測試 AI 服務暫時中斷時，平台是否仍能保存學生作答並提供清楚錯誤提示的測試內容。學生應該可以稍後再試，而不是卡在批改中的狀態。');
  const aiButton=page.locator('[id^="aitype_"]').first();
  assert(await aiButton.count(),'AI action button missing');
  await aiButton.click();
  await page.waitForFunction(()=>{
    const out=document.querySelector('[id^="airesult_"]');
    return out&&/連線失敗|暫時|稍後再試|網路/.test(out.textContent||'');
  },null,{timeout:15000});
  assert(blockedPost,'AI action did not issue a POST request');
  assert(!(await aiButton.isDisabled()),'AI button stayed disabled after failure');
  assert(/請 AI 看我的作答/.test(await aiButton.innerText()),'AI action label did not return to its normal wording');
  assert((await ta.inputValue()).length>30,'essay answer disappeared after AI failure');
  const aiResult=await page.locator('[id^="airesult_"]').first().innerText();
  assert(/作答仍保存在這台裝置|稍後再試|網路/.test(aiResult),'AI failure lacks recovery guidance');
  await page.unroute('**/*');
  await page.locator('#t-home').click();
  await page.waitForSelector('.swsi-focus-primary',{timeout:10000});

  // Question CDN failure: a failed shard request must not leave a permanent loading/dead screen.
  const cdnHost='wandering-wave-4418.c022050333.workers.dev';
  await page.route(`https://${cdnHost}/question-shards/**`,route=>route.abort('failed'));
  await page.getByRole('button',{name:/開始 10 題/}).click();
  await page.waitForTimeout(3500);
  const afterFailure=await page.locator('#app').innerText();
  const hasQuiz=await page.locator('.qcard').count();
  const recoverable=/載入|網路|稍後|重新|無法|失敗|練題|首頁/.test(afterFailure);
  assert(hasQuiz||recoverable,'question shard failure left no understandable recovery state');
  assert(!/undefined|null|NaN/.test(afterFailure),'question failure leaked invalid values');

  assert.deepStrictEqual(pageErrors,[],`page errors: ${pageErrors.join(' | ')}`);
  console.log('PRELAUNCH ERROR STATES SMOKE OK');
  await browser.close();
})().catch(err=>{console.error(err&&err.stack||err);process.exit(1);});

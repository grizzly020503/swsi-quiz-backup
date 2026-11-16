/* Isolated second-round visual concepts, no production API or bank access. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const out='docs/design/taste-review/round2/evidence';
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch();const report=[];
 for(const theme of ['a','b','c'])for(const width of [390,768,1024,1440]){
  const ctx=await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'});
  await ctx.route('**/*',r=>new URL(r.request().url()).hostname==='127.0.0.1'?r.continue():r.abort());
  const page=await ctx.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:4175/?theme=${theme}`);await page.evaluate(()=>document.fonts.ready);
  assert(await page.evaluate(()=>document.fonts.check('16px StudySans')),'bundled CJK font not loaded');
  async function capture(state){
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${theme}/${width}/${state} overflow`);
   await page.screenshot({path:`${out}/${theme}-${state}-${width}.png`,fullPage:true});
  }
  await capture('home');
  // Every secondary route explains prototype scope, no dead-end placeholder.
  await page.locator('.feature').first().click();await page.locator('#info').waitFor({state:'visible'});
  await page.keyboard.press('Escape');
  await page.locator('main [data-action=quiz]').click();await capture('quiz');
  assert(await page.locator('[data-action=submit]').isDisabled());
  await page.locator('label[for=answer-0]').click();assert(!(await page.locator('[data-action=submit]').isDisabled()));
  await page.locator('[data-action=submit]').click();await capture('answer');
  await page.locator('[data-action=next]').click();
  await page.locator('[data-action=large]').click();
  await page.locator('.qtext').evaluate(el=>el.textContent=el.textContent.repeat(5));
  await page.locator('label[for=answer-1] > span:nth-child(2)').evaluate(el=>el.textContent=el.textContent.repeat(10));
  await capture('long-large');
  await page.locator('label[for=answer-1]').click();await page.locator('[data-action=submit]').click();await page.locator('[data-action=next]').click();
  await page.getByRole('heading',{name:'兩道題，體驗完整流程。'}).waitFor();
  assert.deepEqual(errors,[]);report.push({theme,width,font:'StudySans bundled CJK',overflow:false,interaction:'two answers and completion pass',errors});await ctx.close();
 }
 // Real motion recordings: normal-motion at 390px, deterministic click sequence.
 for(const theme of ['a','b','c']){
  const ctx=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'no-preference',recordVideo:{dir:out,size:{width:390,height:844}}});
  await ctx.route('**/*',r=>new URL(r.request().url()).hostname==='127.0.0.1'?r.continue():r.abort());
  const page=await ctx.newPage();await page.goto(`http://127.0.0.1:4175/?theme=${theme}`);await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(1300);
  await page.locator('main [data-action=quiz]').click();await page.waitForTimeout(800);await page.locator('label[for=answer-0]').click();await page.waitForTimeout(500);await page.locator('[data-action=submit]').click();await page.waitForTimeout(1000);
  const video=page.video();await ctx.close();await video.saveAs(`${out}/${theme}-motion.webm`);
 }
 for(const width of [390,768,1024,1440]){
  const ctx=await browser.newContext({viewport:{width,height:900},reducedMotion:width===390?'no-preference':'reduce',...(width===390?{recordVideo:{dir:out,size:{width:390,height:900}}}:{})});
  await ctx.route('**/*',r=>new URL(r.request().url()).hostname==='127.0.0.1'?r.continue():r.abort());
  const page=await ctx.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:4175/flow.html');await page.evaluate(()=>document.fonts.ready);
  async function shot(state){assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`flow/${width}/${state} overflow`);await page.screenshot({path:`${out}/flow-${state}-${width}.png`,fullPage:true,animations:'disabled'});}
  await shot('home');await page.waitForTimeout(900);await page.locator('[data-action=start]').click();await page.waitForTimeout(700);await shot('quiz');
  assert(await page.locator('[data-action=submit]').isDisabled());
  await page.locator('label[for=o2]').click();await page.waitForTimeout(400);await page.locator('[data-action=submit]').click();await page.waitForTimeout(800);
  assert(await page.evaluate(()=>{const f=document.querySelector('.feedback').getBoundingClientRect(),a=document.querySelector('.actions').getBoundingClientRect();return f.bottom<=a.top+1;}),'feedback obscured by sticky actions');
  await shot('feedback');
  assert(await page.locator('.feedback.wrong').count()===1);
  await page.locator('[data-action=next]').click();await page.waitForTimeout(700);
  await page.locator('label[for=o1]').click();await page.locator('[data-action=submit]').click();await page.waitForTimeout(800);await page.locator('[data-action=next]').click();await page.waitForTimeout(1200);await shot('result');
  assert.equal(await page.locator('.result-stats strong').nth(1).innerText(),'1 / 2');
  await page.locator('main [data-action=home]').click();await page.waitForTimeout(600);
  await page.locator('[data-action=start]').click();await page.waitForTimeout(600);
  await page.locator('[data-action=large]').click();
  await page.locator('.question h1').evaluate(el=>el.textContent=el.textContent.repeat(5));
  await page.locator('label[for=o0] > span:nth-child(2)').evaluate(el=>el.textContent=el.textContent.repeat(10));
  await shot('long-large');
  await page.locator('label[for=o0]').click();
  await page.locator('[data-action=submit]').click();
  assert(await page.locator('.feedback').isVisible());
  await page.locator('[data-action=next]').click();await page.waitForTimeout(600);
  assert.equal(await page.locator('.question h1').innerText(), '在服務過程中，如何讓服務使用者參與目標設定？');


  assert.deepEqual(errors,[]);report.push({design:'continuous-flow',width,errors,result:'1 / 2 correct verified'});
  const video=page.video();await ctx.close();if(video)await video.saveAs(`${out}/flow-motion.webm`);
 }
 fs.writeFileSync(`${out}/results.json`,JSON.stringify(report,null,2));await browser.close();console.log('SECOND ROUND CONCEPTS PASS: 3 designs x 4 widths, font, answer flow, long text and motion videos');
})().catch(e=>{console.error(e);process.exit(1)});

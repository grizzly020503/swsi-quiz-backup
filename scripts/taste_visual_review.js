/* Local-only design acceptance: no production requests, writes or AI quota. */
const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const assert=require('assert');
const base=process.argv[2];
const label=process.argv[3]||'after';
assert(base && new URL(base).hostname==='127.0.0.1','Local HTTP fixture only');
const out=path.resolve('docs/design/taste-review/screenshots');
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||undefined});
 const report=[];
 for(const width of [390,768,1024,1440]){
  const ctx=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block',reducedMotion:'reduce'});
  await ctx.route('**/*',route=>{
   const u=new URL(route.request().url());
   if(u.hostname==='wandering-wave-4418.c022050333.workers.dev'&&u.pathname.startsWith('/question-shards/')){
    const name=path.basename(u.pathname); const p=path.resolve('cdn/question-shards',name);
    return fs.existsSync(p)?route.fulfill({contentType:'application/json',body:fs.readFileSync(p)}):route.abort();
   }
   if(u.origin!==new URL(base).origin)return route.abort();
   return route.continue();
  });
  await ctx.addInitScript(()=>{let seed=17;Math.random=()=>((seed=(seed*16807)%2147483647)-1)/2147483646;});
  const page=await ctx.newPage(); const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.locator('.swsi-v4-start').waitFor();
  await page.screenshot({path:`${out}/${label}-home-${width}.png`,fullPage:true});
  await page.locator('.swsi-v4-start').click();await page.locator('.qcard .opt').first().waitFor();
  await page.screenshot({path:`${out}/${label}-quiz-${width}.png`,fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
  await page.locator('.opt').first().click();
  await page.getByRole('button',{name:'送出答案',exact:true}).click();
  await page.locator('.exp').waitFor();
  await page.screenshot({path:`${out}/${label}-answer-${width}.png`,fullPage:true});
  for (const [name,action] of [
   ['review',()=>go('review')],['learning',()=>swsiOpenLearningCenter()],
   ['essay',()=>go('essay')],['resources',()=>go('topics')],['simulation',()=>MK.open()]
  ]) {
   await page.evaluate(action);
   await page.waitForTimeout(250);
   await page.screenshot({path:`${out}/${label}-${name}-${width}.png`,fullPage:true});
  }
  report.push({width,overflow,errors});
  assert(!overflow,`horizontal overflow at ${width}`);
  assert.deepStrictEqual(errors,[],`browser errors at ${width}`);
  await ctx.close();
 }
 await browser.close();fs.writeFileSync(`docs/design/taste-review/${label}-visual.json`,JSON.stringify(report,null,2));
 console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(e);process.exit(1)});

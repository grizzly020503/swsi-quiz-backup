const assert=require('assert');
const fs=require('fs');
const path=require('path');
const {chromium}=require('playwright');

const base=process.argv[2]||'http://127.0.0.1:4173/';
const QUESTION_CDN_HOST='wandering-wave-4418.c022050333.workers.dev';
const QUESTION_CDN_PREFIX='/question-shards/';
const LOCAL_SHARD_DIR=path.resolve(process.cwd(),'cdn/question-shards');
const DELAY_MS=2500;

const sleep=ms=>new Promise(r=>setTimeout(r,ms));

(async()=>{
  const browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:390,height:844}});
  const page=await context.newPage();
  const pageErrors=[];
  page.on('pageerror',e=>pageErrors.push(String(e&&e.message||e)));

  await page.route('**/*',async route=>{
    const req=route.request();
    const u=new URL(req.url());
    if(u.hostname===QUESTION_CDN_HOST&&u.pathname.startsWith(QUESTION_CDN_PREFIX)){
      const rel=decodeURIComponent(u.pathname.slice(QUESTION_CDN_PREFIX.length));
      if(!rel||rel!==path.basename(rel))return route.fulfill({status:404,body:'not found'});
      const file=path.join(LOCAL_SHARD_DIR,rel);
      if(!fs.existsSync(file))return route.fulfill({status:404,body:'not found'});
      await sleep(DELAY_MS);
      return route.fulfill({status:200,contentType:'application/json; charset=utf-8',body:fs.readFileSync(file)});
    }
    return route.continue();
  });

  const started=Date.now();
  await page.goto(base,{waitUntil:'commit',timeout:15000});

  // While question data is intentionally delayed, the user must see a meaningful
  // loading state rather than an empty/blank app shell.
  await page.waitForSelector('#app',{timeout:5000});
  const early=await page.locator('#app').innerText();
  assert(/載入題庫中|載入/.test(early),'slow-network: meaningful loading state missing');
  assert((await page.locator('body').innerText()).trim().length>0,'slow-network: page rendered blank during load');

  await page.waitForSelector('.swsi-focus-primary',{timeout:45000});
  assert(Date.now()-started>=1500,'slow-network: shard delay was not exercised');
  assert((await page.locator('.swsi-focus-primary').count())>0,'slow-network: home did not recover after delayed shards');

  // A reload under the same delayed network must also recover instead of sticking
  // forever on the initial loading shell.
  await page.reload({waitUntil:'commit',timeout:15000});
  await page.waitForSelector('#app',{timeout:5000});
  assert((await page.locator('body').innerText()).trim().length>0,'slow-network reload: blank body');
  await page.waitForSelector('.swsi-focus-primary',{timeout:45000});

  assert.deepStrictEqual(pageErrors,[],'slow-network page errors: '+pageErrors.join(' | '));
  console.log('PRELAUNCH SLOW NETWORK SMOKE OK');
  await browser.close();
})().catch(err=>{console.error(err&&err.stack||err);process.exit(1);});

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
  let seenShardRequests=0;
  let delayedShardRequests=0;
  let activeDelayedShardRequests=0;
  let delayedShardName='';
  let firstDelayMs=0;
  page.on('pageerror',e=>pageErrors.push(String(e&&e.message||e)));

  await page.route('**/*',async route=>{
    const u=new URL(route.request().url());
    if(u.hostname===QUESTION_CDN_HOST&&u.pathname.startsWith(QUESTION_CDN_PREFIX)){
      const rel=decodeURIComponent(u.pathname.slice(QUESTION_CDN_PREFIX.length));
      if(!rel||rel!==path.basename(rel))return route.fulfill({status:404,body:'not found'});
      const file=path.join(LOCAL_SHARD_DIR,rel);
      if(!fs.existsSync(file))return route.fulfill({status:404,body:'not found'});
      seenShardRequests++;

      // Model a realistic slow-first-data condition. Delaying every shard would
      // multiply the synthetic latency by the number of shards and no longer
      // represent a normal slow network.
      if(delayedShardRequests===0){
        delayedShardRequests=1;
        activeDelayedShardRequests=1;
        delayedShardName=rel;
        const delayStarted=Date.now();
        await sleep(DELAY_MS);
        firstDelayMs=Date.now()-delayStarted;
        activeDelayedShardRequests=0;
      }

      return route.fulfill({status:200,contentType:'application/json; charset=utf-8',body:fs.readFileSync(file)});
    }
    return route.continue();
  });

  async function waitForDelayedShard(timeout=12000){
    const deadline=Date.now()+timeout;
    while(delayedShardRequests===0&&Date.now()<deadline)await sleep(50);
    assert.strictEqual(delayedShardRequests,1,'slow-network: first shard delay was not exercised exactly once');
  }

  await page.goto(base,{waitUntil:'commit',timeout:15000});
  await page.waitForSelector('#app',{timeout:5000});
  await page.waitForSelector('.swsi-focus-primary',{timeout:45000});

  const earlyApp=(await page.locator('#app').innerText()).trim();
  const earlyBody=(await page.locator('body').innerText()).trim();
  assert(earlyApp.length>0,'slow-network: app shell rendered empty before quiz load');
  assert(earlyBody.length>0,'slow-network: page rendered blank before quiz load');

  // Use the same real user path as the dead-end smoke so question data is
  // definitely requested even when Home itself can render from cached metadata.
  await page.getByRole('button',{name:/直接開始 20 題/}).click();
  await waitForDelayedShard();

  if(activeDelayedShardRequests>0){
    assert((await page.locator('#app').innerText()).trim().length>0,'slow-network: app shell emptied while first shard was delayed');
    assert((await page.locator('body').innerText()).trim().length>0,'slow-network: body went blank while first shard was delayed');
  }

  await page.waitForSelector('.qcard .opt',{timeout:45000});
  assert(seenShardRequests>0,'slow-network: no question shard request was observed');
  assert(firstDelayMs>=2000,'slow-network: first shard did not experience the intended delay');
  console.log(`SLOW NETWORK FIRST SHARD OK: ${delayedShardName} ${firstDelayMs}ms; total shard requests=${seenShardRequests}`);

  await page.getByRole('button',{name:/結束這次練習/}).click();
  await page.waitForSelector('.swsi-focus-primary',{timeout:30000});

  // Reload may reuse browser/service-worker caches. It only needs to remain
  // visible and recover to Home; a second network fetch is not required.
  await page.reload({waitUntil:'commit',timeout:15000});
  await page.waitForSelector('#app',{timeout:5000});
  assert((await page.locator('body').innerText()).trim().length>0,'slow-network reload: blank body');
  await page.waitForSelector('.swsi-focus-primary',{timeout:45000});

  assert.deepStrictEqual(pageErrors,[],'slow-network page errors: '+pageErrors.join(' | '));
  console.log('PRELAUNCH SLOW NETWORK SMOKE OK');
  await browser.close();
})().catch(err=>{console.error(err&&err.stack||err);process.exit(1);});

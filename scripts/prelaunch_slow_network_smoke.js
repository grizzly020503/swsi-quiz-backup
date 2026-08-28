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

      // Keep manifest and any non-exam JSON deterministic but fast. Only real
      // exam shards (e.g. 115-1.json) participate in the slow-network assertion.
      const isExamShard=/^\d{3}-[12]\.json$/.test(rel);
      if(isExamShard){
        seenShardRequests++;
        if(delayedShardRequests===0){
          delayedShardRequests=1;
          activeDelayedShardRequests=1;
          delayedShardName=rel;
          const delayStarted=Date.now();
          await sleep(DELAY_MS);
          firstDelayMs=Date.now()-delayStarted;
          activeDelayedShardRequests=0;
        }
      }

      return route.fulfill({status:200,contentType:'application/json; charset=utf-8',body:fs.readFileSync(file)});
    }
    return route.continue();
  });

  async function waitForDelayedShard(timeout=12000){
    const deadline=Date.now()+timeout;
    while(delayedShardRequests===0&&Date.now()<deadline)await sleep(50);
    assert.strictEqual(delayedShardRequests,1,'slow-network: exam shard delay was not exercised exactly once');
  }

  await page.goto(base,{waitUntil:'commit',timeout:15000});
  await page.waitForSelector('#app',{timeout:5000});
  await page.waitForSelector('.swsi-focus-primary',{timeout:45000});

  const earlyApp=(await page.locator('#app').innerText()).trim();
  const earlyBody=(await page.locator('body').innerText()).trim();
  assert(earlyApp.length>0,'slow-network: app shell rendered empty before quiz load');
  assert(earlyBody.length>0,'slow-network: page rendered blank before quiz load');

  // Exercise one explicit exam session instead of the broad smart scope. This
  // isolates a realistic slow first shard without multiplying the synthetic
  // 2.5s delay across many exam sessions.
  await page.getByRole('button',{name:/自訂範圍/}).click();
  const scope=page.getByLabel('刷題範圍');
  await scope.waitFor({state:'visible',timeout:10000});
  await scope.selectOption('specific');

  const yearSelect=page.getByLabel('考試年度');
  await yearSelect.waitFor({state:'visible',timeout:10000});
  const year=await yearSelect.locator('option').first().getAttribute('value');
  assert(/^\d{3}$/.test(String(year||'')),'slow-network: no valid exam year available');
  await yearSelect.selectOption(String(year));

  const roundSelect=page.getByLabel('考試考次');
  await roundSelect.waitFor({state:'visible',timeout:10000});
  await roundSelect.selectOption('1');

  await page.getByRole('button',{name:/開始這組題目/}).click();
  await waitForDelayedShard();

  // startFocusedQuiz intentionally renders a loading shell while its one shard
  // is delayed; it must stay visible rather than becoming blank.
  if(activeDelayedShardRequests>0){
    assert((await page.locator('#app').innerText()).trim().length>0,'slow-network: app shell emptied while exam shard was delayed');
    assert((await page.locator('body').innerText()).trim().length>0,'slow-network: body went blank while exam shard was delayed');
  }

  await page.waitForSelector('.qcard .opt',{timeout:30000});
  assert(seenShardRequests>=1,'slow-network: no exam shard request was observed');
  assert(firstDelayMs>=2000,'slow-network: exam shard did not experience the intended delay');
  console.log(`SLOW NETWORK EXAM SHARD OK: ${delayedShardName} ${firstDelayMs}ms; exam shard requests=${seenShardRequests}`);

  await page.getByRole('button',{name:/結束這次練習/}).click();
  await page.waitForSelector('.swsi-focus-primary',{timeout:30000});

  // Reload may legitimately reuse browser/service-worker caches. It only needs
  // to remain visible and recover to Home; a second network fetch is not required.
  await page.reload({waitUntil:'commit',timeout:15000});
  await page.waitForSelector('#app',{timeout:5000});
  assert((await page.locator('body').innerText()).trim().length>0,'slow-network reload: blank body');
  await page.waitForSelector('.swsi-focus-primary',{timeout:45000});

  assert.deepStrictEqual(pageErrors,[],'slow-network page errors: '+pageErrors.join(' | '));
  console.log('PRELAUNCH SLOW NETWORK SMOKE OK');
  await browser.close();
})().catch(err=>{console.error(err&&err.stack||err);process.exit(1);});

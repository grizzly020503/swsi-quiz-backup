const assert=require('assert');
const fs=require('fs');
const {chromium}=require('playwright');

const base=process.argv[2]||'http://127.0.0.1:4173/';
const axeSource=fs.readFileSync(require.resolve('axe-core/axe.min.js'),'utf8');

async function dismissOnboarding(page){
  try{
    const onboarding=page.locator('#swsi-onboarding-backdrop');
    if(await onboarding.count()){
      const skip=onboarding.getByRole('button',{name:/跳過|開始使用|知道了|關閉/}).last();
      if(await skip.count())await skip.click();
    }
  }catch(_e){}
}

async function injectAndRun(page,label){
  await page.addScriptTag({content:axeSource});
  const result=await page.evaluate(async()=>{
    return await window.axe.run(document,{
      runOnly:{
        type:'tag',
        values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']
      },
      resultTypes:['violations','incomplete']
    });
  });

  const blocking=(result.violations||[]).filter(v=>v.impact==='critical'||v.impact==='serious');
  if(blocking.length){
    const detail=blocking.map(v=>({
      id:v.id,
      impact:v.impact,
      help:v.help,
      helpUrl:v.helpUrl,
      nodes:v.nodes.slice(0,5).map(n=>({
        target:n.target,
        html:n.html,
        failureSummary:n.failureSummary
      }))
    }));
    console.error('AXE BLOCKING VIOLATIONS '+label+'\n'+JSON.stringify(detail,null,2));
  }

  const moderate=(result.violations||[]).filter(v=>v.impact==='moderate'||v.impact==='minor');
  console.log(
    `AXE ${label}: violations=${result.violations.length} blocking=${blocking.length} moderate/minor=${moderate.length} incomplete=${(result.incomplete||[]).length}`
  );
  return blocking.length;
}

(async()=>{
  const browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:390,height:844}});
  const page=await context.newPage();
  const pageErrors=[];
  page.on('pageerror',e=>pageErrors.push(String(e&&e.message||e)));

  await page.goto(base,{waitUntil:'commit',timeout:15000});
  await page.waitForSelector('.swsi-focus-primary',{timeout:30000});
  await dismissOnboarding(page);

  let blockingTotal=0;
  blockingTotal+=await injectAndRun(page,'home');

  assert.strictEqual(await page.evaluate(()=>typeof window.swsiOpenPublicInfo),'function','public info opener missing');
  await page.evaluate(()=>window.swsiOpenPublicInfo('about'));
  await page.waitForSelector('.swsi-public-info-dialog',{timeout:5000});
  blockingTotal+=await injectAndRun(page,'public-info');
  await page.keyboard.press('Escape');
  await page.waitForFunction(()=>!document.getElementById('swsi-public-info-backdrop'));

  assert.strictEqual(await page.evaluate(()=>typeof window.swsiOpenReport),'function','feedback opener missing');
  await page.evaluate(()=>window.swsiOpenReport());
  await page.waitForSelector('.swsi-report-dialog',{timeout:5000});
  blockingTotal+=await injectAndRun(page,'feedback-dialog');
  await page.keyboard.press('Escape');
  await page.waitForFunction(()=>!document.getElementById('swsi-report-backdrop'));

  assert.strictEqual(await page.evaluate(()=>typeof window.swsiOpenExamDate),'function','exam date opener missing');
  await page.evaluate(()=>window.swsiOpenExamDate());
  await page.waitForSelector('.swsi-exam-dialog',{timeout:5000});
  blockingTotal+=await injectAndRun(page,'exam-date-dialog');

  assert.strictEqual(blockingTotal,0,`axe found ${blockingTotal} critical/serious WCAG violation group(s) across tested UI states`);
  assert.deepStrictEqual(pageErrors,[],`page errors: ${pageErrors.join(' | ')}`);
  await context.close();
  await browser.close();
  console.log('PRELAUNCH AXE ACCESSIBILITY GATE OK');
})().catch(err=>{console.error(err&&err.stack||err);process.exit(1);});

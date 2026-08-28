const assert=require('assert');
const {chromium}=require('playwright');

const base=process.argv[2]||'http://127.0.0.1:4173/';

function hasUsableName(el){
  const aria=(el.getAttribute('aria-label')||'').trim();
  const title=(el.getAttribute('title')||'').trim();
  const text=(el.textContent||'').trim();
  return !!(aria||title||text);
}

(async()=>{
  const browser=await chromium.launch({headless:true});

  async function runViewport(width,height,label,opts={}){
    const context=await browser.newContext({viewport:{width,height}});
    const page=await context.newPage();
    const pageErrors=[];
    page.on('pageerror',e=>pageErrors.push(String(e&&e.message||e)));

    await page.goto(base,{waitUntil:'commit',timeout:15000});
    await page.waitForSelector('.swsi-focus-primary',{timeout:30000});
    try{
      const onboarding=page.locator('#swsi-onboarding-backdrop');
      if(await onboarding.count()){
        const skip=onboarding.getByRole('button',{name:/跳過|開始使用|知道了|關閉/}).last();
        if(await skip.count())await skip.click();
      }
    }catch(_e){}

    if(opts.maxFont){
      const controls=page.locator('.fontctl button');
      assert((await controls.count())>=3,`${label}: font controls missing`);
      await controls.last().click();
      await page.waitForFunction(()=>document.documentElement.getAttribute('data-fs')==='2');
    }

    const metrics=await page.evaluate(()=>({
      innerWidth:window.innerWidth,
      scrollWidth:document.documentElement.scrollWidth,
      bodyWidth:document.body.scrollWidth,
      tabbar:document.querySelector('.tabbar')?.getBoundingClientRect()||null,
      primary:[...document.querySelectorAll('.swsi-focus-primary button,.swsi-focus-primary')].map(el=>({
        tag:el.tagName,
        rect:el.getBoundingClientRect().toJSON?el.getBoundingClientRect().toJSON():{width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height},
        text:(el.textContent||'').trim()
      }))
    }));
    assert(metrics.scrollWidth<=metrics.innerWidth+3,`${label}: document horizontally overflows (${metrics.scrollWidth}>${metrics.innerWidth})`);
    assert(metrics.bodyWidth<=metrics.innerWidth+3,`${label}: body horizontally overflows (${metrics.bodyWidth}>${metrics.innerWidth})`);
    assert(metrics.tabbar,`${label}: bottom nav missing`);
    assert(metrics.tabbar.left>=-2&&metrics.tabbar.right<=width+2,`${label}: bottom nav escapes viewport horizontally`);
    assert(metrics.tabbar.bottom<=height+2&&metrics.tabbar.bottom>=height-70,`${label}: bottom nav not anchored near viewport bottom`);

    const navButtons=page.locator('.tabbar button');
    assert((await navButtons.count())>=3,`${label}: bottom nav controls missing`);
    for(let i=0;i<await navButtons.count();i++){
      const b=navButtons.nth(i);
      const box=await b.boundingBox();
      const state=await b.evaluate(el=>{const s=getComputedStyle(el);return {id:el.id,text:(el.textContent||'').trim(),display:s.display,visibility:s.visibility,opacity:s.opacity};});
      assert(box&&box.height>=40&&box.width>=40,`${label}: bottom nav touch target too small at ${i}; box=${JSON.stringify(box)} state=${JSON.stringify(state)}`);
      const named=await b.evaluate(hasUsableName);
      assert(named,`${label}: bottom nav control ${i} has no accessible name`);
    }

    const mainActions=page.locator('.swsi-focus-primary button');
    for(let i=0;i<Math.min(await mainActions.count(),4);i++){
      const b=mainActions.nth(i);
      const box=await b.boundingBox();
      if(box)assert(box.height>=40&&box.width>=40,`${label}: main CTA touch target too small at ${i}`);
      assert(await b.evaluate(hasUsableName),`${label}: main CTA ${i} has no accessible name`);
    }

    // Keyboard users must be able to move focus onto a real interactive element.
    await page.keyboard.press('Tab');
    await page.waitForTimeout(50);
    const firstFocus=await page.evaluate(()=>({tag:document.activeElement&&document.activeElement.tagName,name:(document.activeElement&&((document.activeElement.getAttribute('aria-label')||document.activeElement.textContent||'')))||''}));
    assert(firstFocus.tag&&firstFocus.tag!=='BODY',`${label}: Tab did not move focus to an interactive control`);

    // Public info modal must remain within the smallest mobile viewport and close by keyboard.
    assert.strictEqual(await page.evaluate(()=>typeof window.swsiOpenPublicInfo),'function',`${label}: public info opener missing`);
    await page.evaluate(()=>window.swsiOpenPublicInfo('about'));
    await page.waitForSelector('.swsi-public-info-dialog',{timeout:5000});
    const infoBox=await page.locator('.swsi-public-info-dialog').boundingBox();
    assert(infoBox&&infoBox.x>=-1&&infoBox.x+infoBox.width<=width+1,`${label}: public info modal overflows horizontally`);
    assert(infoBox&&infoBox.y>=-1&&infoBox.y+infoBox.height<=height+2,`${label}: public info modal overflows vertically`);
    await page.keyboard.press('Escape');
    await page.waitForFunction(()=>!document.getElementById('swsi-public-info-backdrop'));

    // Progress / learning center should not horizontally overflow at large app text.
    if(opts.maxFont){
      const progressBtn=page.getByRole('button',{name:/查看完整學習進度/});
      if(await progressBtn.count())await progressBtn.click();
      else if(await page.getByRole('button',{name:'複習',exact:true}).count()){
        await page.getByRole('button',{name:'複習',exact:true}).click();
        const p=page.getByRole('button',{name:/看看我的進度/});
        if(await p.count())await p.click();
      }
      await page.waitForTimeout(250);
      const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-window.innerWidth);
      assert(overflow<=3,`${label}: max-font learning view horizontally overflows by ${overflow}px`);
    }

    assert.deepStrictEqual(pageErrors,[],`${label}: page errors: ${pageErrors.join(' | ')}`);
    await context.close();
  }

  await runViewport(320,568,'small-phone');
  await runViewport(390,844,'max-font-phone',{maxFont:true});
  await runViewport(844,390,'landscape-phone');

  console.log('PRELAUNCH ACCESSIBILITY TOUCH SMOKE OK');
  await browser.close();
})().catch(err=>{console.error(err&&err.stack||err);process.exit(1);});

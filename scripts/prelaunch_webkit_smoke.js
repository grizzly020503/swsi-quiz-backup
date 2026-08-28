const assert=require('assert');
const {webkit}=require('playwright');

const base=process.argv[2]||'http://127.0.0.1:4173/';

(async()=>{
  const browser=await webkit.launch({headless:true});

  async function runViewport(width,height,label,opts={}){
    const context=await browser.newContext({viewport:{width,height}});
    const page=await context.newPage();
    const pageErrors=[];
    page.on('pageerror',e=>pageErrors.push(String(e&&e.message||e)));

    await page.goto(base,{waitUntil:'commit',timeout:20000});
    await page.waitForSelector('.swsi-focus-primary',{timeout:30000});

    try{
      const onboarding=page.locator('#swsi-onboarding-backdrop');
      if(await onboarding.count()){
        const skip=onboarding.getByRole('button',{name:/跳過|開始使用|知道了|關閉/}).last();
        if(await skip.count())await skip.click();
      }
    }catch(_e){}

    const layout=await page.evaluate(()=>({
      innerWidth:window.innerWidth,
      docWidth:document.documentElement.scrollWidth,
      bodyWidth:document.body.scrollWidth,
      tabbar:document.querySelector('.tabbar')?.getBoundingClientRect()||null
    }));
    assert(layout.docWidth<=layout.innerWidth+3,`${label}: document horizontally overflows (${layout.docWidth}>${layout.innerWidth})`);
    assert(layout.bodyWidth<=layout.innerWidth+3,`${label}: body horizontally overflows (${layout.bodyWidth}>${layout.innerWidth})`);
    assert(layout.tabbar,`${label}: bottom navigation missing`);
    assert(layout.tabbar.left>=-2&&layout.tabbar.right<=width+2,`${label}: bottom navigation escapes viewport`);

    const navButtons=page.locator('.tabbar button:visible');
    assert((await navButtons.count())>=3,`${label}: visible bottom navigation controls missing`);
    for(let i=0;i<await navButtons.count();i++){
      const box=await navButtons.nth(i).boundingBox();
      assert(box&&box.width>=40&&box.height>=40,`${label}: bottom navigation target ${i} too small`);
    }

    // Prove that a real bottom-navigation route works in WebKit rather than only rendering.
    const review=page.getByRole('button',{name:'複習',exact:true});
    if(await review.count()){
      await review.click();
      await page.waitForTimeout(150);
      assert(await review.evaluate(el=>el.classList.contains('active')||el.getAttribute('aria-current')==='page'),`${label}: review route did not become active in WebKit`);
      const home=page.getByRole('button',{name:'首頁',exact:true});
      if(await home.count())await home.click();
    }

    assert.strictEqual(await page.evaluate(()=>typeof window.swsiOpenPublicInfo),'function',`${label}: public-info opener missing`);
    await page.evaluate(()=>window.swsiOpenPublicInfo('about'));
    await page.waitForSelector('.swsi-public-info-dialog',{timeout:5000});
    const infoBox=await page.locator('.swsi-public-info-dialog').boundingBox();
    assert(infoBox&&infoBox.x>=-1&&infoBox.x+infoBox.width<=width+1,`${label}: public-info modal overflows horizontally`);
    assert(infoBox&&infoBox.y>=-1&&infoBox.y+infoBox.height<=height+2,`${label}: public-info modal overflows vertically`);
    await page.keyboard.press('Escape');
    await page.waitForFunction(()=>!document.getElementById('swsi-public-info-backdrop'));

    if(opts.maxFont){
      const controls=page.locator('.fontctl button');
      assert((await controls.count())>=3,`${label}: font controls missing`);
      await controls.last().click();
      await page.waitForFunction(()=>document.documentElement.getAttribute('data-fs')==='2');
      await page.waitForTimeout(100);
      const overflow=await page.evaluate(()=>Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-window.innerWidth);
      assert(overflow<=3,`${label}: max-font layout horizontally overflows by ${overflow}px`);
    }

    assert.deepStrictEqual(pageErrors,[],`${label}: WebKit page errors: ${pageErrors.join(' | ')}`);
    await context.close();
  }

  await runViewport(390,844,'webkit-phone',{maxFont:true});
  await runViewport(844,390,'webkit-landscape');

  console.log('PRELAUNCH WEBKIT SMOKE OK');
  await browser.close();
})().catch(err=>{console.error(err&&err.stack||err);process.exit(1);});

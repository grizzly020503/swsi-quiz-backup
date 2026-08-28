const assert=require('assert');
const {chromium}=require('playwright');

const base=process.argv[2]||'http://127.0.0.1:4173/';

(async()=>{
  const browser=await chromium.launch({headless:true});

  async function boot(label,initScript){
    const context=await browser.newContext({viewport:{width:390,height:844}});
    if(initScript)await context.addInitScript(initScript);
    const page=await context.newPage();
    const errors=[];
    page.on('pageerror',e=>errors.push(String(e&&e.message||e)));
    await page.goto(base,{waitUntil:'commit',timeout:20000});
    await page.waitForSelector('.swsi-focus-primary',{timeout:30000});
    assert.strictEqual(await page.locator('.swsi-focus-primary').count(),1,`${label}: home did not become usable`);
    const body=(await page.locator('body').innerText()).trim();
    assert(body.length>20,`${label}: page rendered blank`);
    await context.close();
    return errors;
  }

  // Simulate browsers/privacy modes where Web Storage access throws SecurityError.
  const storageErrors=await boot('localStorage-blocked',()=>{
    const denied=()=>{throw new DOMException('Storage access denied','SecurityError');};
    try{
      Storage.prototype.getItem=denied;
      Storage.prototype.setItem=denied;
      Storage.prototype.removeItem=denied;
      Storage.prototype.clear=denied;
    }catch(_e){}
  });
  assert.deepStrictEqual(storageErrors,[],`localStorage-blocked: page errors: ${storageErrors.join(' | ')}`);

  // Simulate IndexedDB being unavailable/denied without removing the rest of browser storage.
  const idbErrors=await boot('indexedDB-blocked',()=>{
    try{
      const denied=()=>{throw new DOMException('IndexedDB access denied','SecurityError');};
      IDBFactory.prototype.open=denied;
      IDBFactory.prototype.deleteDatabase=denied;
    }catch(_e){}
  });
  assert.deepStrictEqual(idbErrors,[],`indexedDB-blocked: page errors: ${idbErrors.join(' | ')}`);

  // Reload must remain recoverable after a normal first boot.
  const context=await browser.newContext({viewport:{width:390,height:844}});
  const page=await context.newPage();
  const reloadErrors=[];
  page.on('pageerror',e=>reloadErrors.push(String(e&&e.message||e)));
  await page.goto(base,{waitUntil:'commit',timeout:20000});
  await page.waitForSelector('.swsi-focus-primary',{timeout:30000});
  await page.reload({waitUntil:'commit',timeout:20000});
  await page.waitForSelector('.swsi-focus-primary',{timeout:30000});
  assert.deepStrictEqual(reloadErrors,[],`reload: page errors: ${reloadErrors.join(' | ')}`);
  await context.close();

  console.log('PRELAUNCH STORAGE DEGRADATION SMOKE OK');
  await browser.close();
})().catch(err=>{console.error(err&&err.stack||err);process.exit(1);});

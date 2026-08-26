const { chromium } = require('playwright');

const url = process.argv[2] || 'http://127.0.0.1:4173/';

(async()=>{
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage();
  try{
    await page.goto(url, {waitUntil:'domcontentloaded', timeout:30000});
    await page.waitForFunction(() => window.swsiStorageDurabilityVersion === '2026-08-27.history-cap.v1', null, {timeout:15000});

    const result = await page.evaluate(() => {
      localStorage.removeItem('swsi_v2_history');
      localStorage.removeItem('swsi_review_v2');

      const rows=[];
      for(let i=0;i<8050;i++) rows.push({id:'T-'+i,subject:'測試',major:'',mistake:'',correct:i%2===0,ts:i});
      const ok = window.saveHist(rows);
      const stored = JSON.parse(localStorage.getItem('swsi_v2_history') || '[]');
      const capOk = ok === true && stored.length === 8000 && stored[0].id === 'T-50' && stored[stored.length-1].id === 'T-8049';

      const proto = Object.getPrototypeOf(localStorage);
      const originalSetItem = proto.setItem;
      let historyWarn = false;
      let reviewWarn = false;
      try{
        proto.setItem = function(key, value){
          if(key === 'swsi_v2_history') throw new DOMException('quota test','QuotaExceededError');
          return originalSetItem.call(this,key,value);
        };
        window.saveHist([{id:'X',subject:'測試',correct:false,ts:Date.now()}]);
        const el=document.getElementById('swsi-storage-warning');
        historyWarn=!!(el && /學習歷程儲存失敗/.test(el.textContent||'') && el.style.display !== 'none');
      }finally{
        proto.setItem = originalSetItem;
      }

      try{
        proto.setItem = function(key, value){
          if(key === 'swsi_review_v2') throw new DOMException('quota test','QuotaExceededError');
          return originalSetItem.call(this,key,value);
        };
        window.saveReviewState({version:2,migratedFromHistory:true,items:{X:{id:'X'}}});
        const el=document.getElementById('swsi-storage-warning');
        reviewWarn=!!(el && /複習進度儲存失敗/.test(el.textContent||'') && el.style.display !== 'none');
      }finally{
        proto.setItem = originalSetItem;
      }

      return {
        capOk,
        historyWarn,
        reviewWarn,
        version:window.swsiStorageDurabilityVersion,
        historyMaxRecords:window.swsiStorageDurability && window.swsiStorageDurability.historyMaxRecords
      };
    });

    if(!result.capOk) throw new Error('history retention cap contract failed: '+JSON.stringify(result));
    if(!result.historyWarn) throw new Error('history storage failure is not visibly reported: '+JSON.stringify(result));
    if(!result.reviewWarn) throw new Error('review storage failure is not visibly reported: '+JSON.stringify(result));
    if(result.historyMaxRecords !== 8000) throw new Error('unexpected history retention cap: '+JSON.stringify(result));

    console.log('STORAGE DURABILITY SMOKE OK', JSON.stringify(result));
  } finally {
    await browser.close();
  }
})().catch(err=>{ console.error(err); process.exit(1); });

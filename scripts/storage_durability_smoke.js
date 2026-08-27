const { chromium } = require('playwright');

const url = process.argv[2] || 'http://127.0.0.1:4173/';

(async()=>{
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage();
  try{
    await page.goto(url, {waitUntil:'domcontentloaded', timeout:30000});
    await page.waitForFunction(() => window.swsiStorageDurabilityVersion === '2026-08-27.schema-guard.v3', null, {timeout:15000});

    const result = await page.evaluate(() => {
      for(const key of Object.keys(localStorage)){
        if(key === 'swsi_v2_history' || key === 'swsi_review_v2' || key.includes('_corrupt_backup_')){
          localStorage.removeItem(key);
        }
      }

      const rows=[];
      for(let i=0;i<8050;i++) rows.push({id:'T-'+i,subject:'測試',major:'',mistake:'',correct:i%2===0,ts:i});
      const ok = window.saveHist(rows);
      const stored = JSON.parse(localStorage.getItem('swsi_v2_history') || '[]');
      const capOk = ok === true && stored.length === 8000 && stored[0].id === 'T-50' && stored[stored.length-1].id === 'T-8049';

      const preservedHistory=JSON.stringify([{id:'KEEP',subject:'測試',correct:true,ts:1}]);
      localStorage.setItem('swsi_v2_history',preservedHistory);
      const invalidHistorySave=window.saveHist([{id:'BAD',correct:'yes',ts:2}]);
      const invalidHistoryPreserved=localStorage.getItem('swsi_v2_history')===preservedHistory;

      const corruptHistory=JSON.stringify([{id:'BROKEN',correct:'yes',ts:3}]);
      localStorage.setItem('swsi_v2_history',corruptHistory);
      const quarantinedHistory=window.loadHist();
      const historyBackupKey=Object.keys(localStorage).find(key=>key.startsWith('swsi_v2_history_corrupt_backup_'));
      const historyQuarantined=
        Array.isArray(quarantinedHistory)
        &&quarantinedHistory.length===0
        &&!!historyBackupKey
        &&localStorage.getItem(historyBackupKey)===corruptHistory
        &&localStorage.getItem('swsi_v2_history')===null;
      const historyCanResume=window.saveHist([{id:'RESUMED',subject:'測試',correct:false,ts:4}])===true;

      const validReview={version:2,migratedFromHistory:true,items:{KEEP:{id:'KEEP',streak:1,wrongCount:1,correctCount:0,dueAt:1,lastAt:1,lastResult:'wrong',mastered:false,maintenanceStep:0,maintenanceDone:false}}};
      const preservedReview=JSON.stringify(validReview);
      localStorage.setItem('swsi_review_v2',preservedReview);
      const invalidReviewSave=window.saveReviewState({version:2,migratedFromHistory:true,items:{EXPECTED:{id:'DIFFERENT'}}});
      const invalidReviewPreserved=localStorage.getItem('swsi_review_v2')===preservedReview;

      const corruptReview=JSON.stringify({version:2,migratedFromHistory:true,items:{EXPECTED:{id:'DIFFERENT'}}});
      localStorage.setItem('swsi_review_v2',corruptReview);
      const quarantinedReview=window.loadReviewState();
      const reviewBackupKey=Object.keys(localStorage).find(key=>key.startsWith('swsi_review_v2_corrupt_backup_'));
      const reviewQuarantined=
        quarantinedReview.version===2
        &&Object.keys(quarantinedReview.items).length===0
        &&!!reviewBackupKey
        &&localStorage.getItem(reviewBackupKey)===corruptReview
        &&localStorage.getItem('swsi_review_v2')===null;
      const reviewCanResume=window.saveReviewState({version:2,migratedFromHistory:true,items:{}})===true;

      const proto = Object.getPrototypeOf(localStorage);
      const originalSetItem = proto.setItem;
      const backupFailureRaw=JSON.stringify([{id:'UNSAFE',correct:'yes',ts:5}]);
      localStorage.setItem('swsi_v2_history',backupFailureRaw);
      let blockedAfterBackupFailure=false;
      try{
        proto.setItem=function(key,value){
          if(key.startsWith('swsi_v2_history_corrupt_backup_')) throw new DOMException('quota test','QuotaExceededError');
          return originalSetItem.call(this,key,value);
        };
        window.loadHist();
      }finally{
        proto.setItem=originalSetItem;
      }
      blockedAfterBackupFailure=
        window.saveHist([{id:'MUST-NOT-OVERWRITE',subject:'測試',correct:true,ts:6}])===false
        &&localStorage.getItem('swsi_v2_history')===backupFailureRaw;
      localStorage.removeItem('swsi_v2_history');
      window.loadHist();

      let historyWarn = false;
      let reviewWarn = false;
      let recordChainWarn = false;
      try{
        window.swsiStorageDurability.clearWarning();
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
        window.swsiStorageDurability.clearWarning();
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

      try{
        window.swsiStorageDurability.clearWarning();
        localStorage.setItem('swsi_v2_history',JSON.stringify([{id:'REC-BASE',subject:'測試',major:'測試',mistake:'',correct:true,ts:1}]));
        localStorage.removeItem('swsi_review_v2');
        proto.setItem = function(key, value){
          if(key === 'swsi_v2_history') throw new DOMException('quota test','QuotaExceededError');
          return originalSetItem.call(this,key,value);
        };
        window.record({id:'REC-X',subject:'測試',major:'測試',mistake:''},'A',false);
        const el=document.getElementById('swsi-storage-warning');
        const reviewStillSaved=!!localStorage.getItem('swsi_review_v2');
        recordChainWarn=!!(reviewStillSaved && el && /學習歷程儲存失敗/.test(el.textContent||'') && el.style.display !== 'none');
      }finally{
        proto.setItem = originalSetItem;
      }

      return {
        capOk,
        invalidHistorySave,
        invalidHistoryPreserved,
        historyQuarantined,
        historyCanResume,
        invalidReviewSave,
        invalidReviewPreserved,
        reviewQuarantined,
        reviewCanResume,
        blockedAfterBackupFailure,
        historyWarn,
        reviewWarn,
        recordChainWarn,
        version:window.swsiStorageDurabilityVersion,
        historyMaxRecords:window.swsiStorageDurability && window.swsiStorageDurability.historyMaxRecords
      };
    });

    if(!result.capOk) throw new Error('history retention cap contract failed: '+JSON.stringify(result));
    if(result.invalidHistorySave!==false||!result.invalidHistoryPreserved) throw new Error('invalid history write overwrote valid data: '+JSON.stringify(result));
    if(!result.historyQuarantined||!result.historyCanResume) throw new Error('corrupt history quarantine failed: '+JSON.stringify(result));
    if(result.invalidReviewSave!==false||!result.invalidReviewPreserved) throw new Error('invalid review write overwrote valid data: '+JSON.stringify(result));
    if(!result.reviewQuarantined||!result.reviewCanResume) throw new Error('corrupt review-state quarantine failed: '+JSON.stringify(result));
    if(!result.blockedAfterBackupFailure) throw new Error('unbacked corrupt data was overwritten: '+JSON.stringify(result));
    if(!result.historyWarn) throw new Error('history storage failure is not visibly reported: '+JSON.stringify(result));
    if(!result.reviewWarn) throw new Error('review storage failure is not visibly reported: '+JSON.stringify(result));
    if(!result.recordChainWarn) throw new Error('record() hides a history-write failure after review succeeds: '+JSON.stringify(result));
    if(result.historyMaxRecords !== 8000) throw new Error('unexpected history retention cap: '+JSON.stringify(result));

    console.log('STORAGE DURABILITY / SCHEMA SMOKE OK', JSON.stringify(result));
  } finally {
    await browser.close();
  }
})().catch(err=>{ console.error(err); process.exit(1); });


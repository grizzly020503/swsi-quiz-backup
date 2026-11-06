#!/usr/bin/env node
'use strict';
// Deterministic no-network fallback test; no credentials or student records.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const assert=require('node:assert/strict');
const src=fs.readFileSync(path.join(__dirname,'../monthly_patch_parts/00.part'),'utf8');
const start='  const legacyLoadAll = loadAll;',end='  // Manifest replaces ALL as catalog source on the home screen.';
const a=src.indexOf(start),b=src.indexOf(end,a);
assert(a>=0&&b>a&&src.indexOf(start,a+1)<0);
const code=src.slice(a,b);
function scenario({loaded=0,broken=false,offline=false,size=4800,dupe=false,badId,legacyError=false}={}){
  const meta={shards:[{file:'a'},{file:'b'}]};
  let calls=0;
  const ctx={ALL:[],SUBJECTS:[],window:{_usingOfflineBackup:true},
    SWSI_CORE_SUBJECTS:['社會工作'],showLoading(){},swsiText:x=>String(x??''),
    QB:{manifest:null,loadedFiles:new Set(['a','b'].slice(0,loaded)),
      questionOwners:new Map(),allComplete:false,error:null,usingOffline:false},
    loadQuestionManifest:async()=>{
      if(offline)throw Error('manifest offline');
      ctx.QB.manifest=meta;},
    assertCompleteBank:()=>{
      if(broken)throw Error('完整題庫總量或跨 shard ID 驗證失敗');
      return true;},
    loadAll:async()=>{
      calls++;
      if(legacyError)throw Error('legacy storage unavailable');
      ctx.ALL=Array.from({length:size},(_,i)=>({id:'Q'+i}));
      if(dupe)ctx.ALL[1].id=ctx.ALL[0].id;
      if(badId!==undefined)ctx.ALL[0].id=badId;},
    console:{warn(){}}
  };
  vm.runInNewContext(code,ctx);
  return {ctx,count:()=>calls};
}
(async()=>{
  let s=scenario();await s.ctx.loadAll();
  assert.equal(s.count(),0);assert.equal(s.ctx.QB.allComplete,false);
  s=scenario({loaded:2});s.ctx.QB.error=Error('previous failure');
  await s.ctx.loadAll();
  assert.equal(s.count(),0);assert.equal(s.ctx.QB.allComplete,true);
  assert.equal(s.ctx.QB.error,null);
  s=scenario({loaded:2,broken:true});
  s.ctx.QB.allComplete=true;
  await assert.rejects(()=>s.ctx.loadAll(),/完整題庫總量/);
  assert.equal(s.count(),0);assert.equal(s.ctx.QB.allComplete,false);
  s=scenario({loaded:1,offline:true});
  await assert.rejects(()=>s.ctx.loadAll(),/manifest offline/);
  assert.equal(s.count(),0);
  s=scenario({offline:true});await s.ctx.loadAll();
  assert.equal(s.count(),1);assert.equal(s.ctx.QB.allComplete,true);
  for(const opts of [{size:4799},{size:4801},{dupe:true},{badId:''},{badId:'  '},{badId:null}]){
    s=scenario({offline:true,...opts});
    await assert.rejects(()=>s.ctx.loadAll(),/舊版備援題庫/);
    assert.equal(s.ctx.QB.allComplete,false);
    assert(s.ctx.QB.error);
  }
  s=scenario({offline:true,legacyError:true});s.ctx.QB.allComplete=true;
  await assert.rejects(()=>s.ctx.loadAll(),/legacy storage unavailable/);
  assert.equal(s.count(),1);assert.equal(s.ctx.QB.allComplete,false);
  assert.match(s.ctx.QB.error.message,/legacy storage unavailable/);
  console.log('MANIFEST FALLBACK FAIL-CLOSED QA OK');
})().catch(e=>{console.error(e);process.exitCode=1;});

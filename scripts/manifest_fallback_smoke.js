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
function scenario({loaded=0,broken=false,offline=false,size=4800,dupe=false}={}){
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
      calls++;ctx.ALL=Array.from({length:size},(_,i)=>({id:'Q'+i}));
      if(dupe)ctx.ALL[1].id=ctx.ALL[0].id;},
    console:{warn(){}}
  };
  vm.runInNewContext(code,ctx);
  return {ctx,count:()=>calls};
}
(async()=>{
  let s=scenario();await s.ctx.loadAll();
  assert.equal(s.count(),0);assert.equal(s.ctx.QB.allComplete,false);
  s=scenario({loaded:2,broken:true});
  await assert.rejects(()=>s.ctx.loadAll(),/完整題庫總量/);
  assert.equal(s.count(),0);assert.equal(s.ctx.QB.allComplete,false);
  s=scenario({loaded:1,offline:true});
  await assert.rejects(()=>s.ctx.loadAll(),/manifest offline/);
  assert.equal(s.count(),0);
  s=scenario({offline:true});await s.ctx.loadAll();
  assert.equal(s.count(),1);assert.equal(s.ctx.QB.allComplete,true);
  for(const opts of [{size:4799},{size:4801},{dupe:true}]){
    s=scenario({offline:true,...opts});
    await assert.rejects(()=>s.ctx.loadAll(),/舊版備援題庫/);
    assert.equal(s.ctx.QB.allComplete,false);
    assert(s.ctx.QB.error);
  }
  console.log('MANIFEST FALLBACK FAIL-CLOSED QA OK');
})().catch(e=>{console.error(e);process.exitCode=1;});

#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('monthly_patch_parts/80.knowledge-path.part','utf8');
const after=source.split('/* SWSI RELATED LEARNING START 2026-11-07');
assert.equal(after.length,2,'learning runtime marker must be unique');
const beforeEnd=after[1].split('/* SWSI RELATED LEARNING END */');
assert.equal(beforeEnd.length,2,'learning runtime end marker must be unique');
const runtime=after[1].slice(after[1].indexOf('\n')+1,beforeEnd[0].length);
const N=v=>String(v==null?'':v).toLowerCase().replace(/[\s　（）()《》〈〉「」『』【】·・,，.。:：;；/\\_-]+/g,'');
const A=v=>Array.isArray(v)?v:(v?String(v).split(/[、,，;；]/).filter(Boolean):[]);
const q1={id:'q1',topic:'生態系統理論之系統層次定義',keywords:'生態系統理論,微視系統',year:'115'};
const q2={id:'q2',topic:'生態系統理論之系統層次定義',keywords:'生態系統理論',year:'114'};
const q3={id:'q3',topic:'家暴案件服務',law:'家庭暴力防治法',year:'113'};
const distractor={id:'distractor',topic:'統計抽樣',options:{A:'生態系統理論',B:'家庭暴力防治法'},q:'下列何者不是生態系統理論？',year:'112'};
const e1={id:'essay-1',topic:'服務過程分析',theories:['生態系統理論'],laws:[],year:'115',subject:'社會工作'};
const e2={id:'essay-2',topic:'家暴實務',theories:[],laws:['家庭暴力防治法'],year:'114',subject:'社會政策'};
const env={
  window:{}, THEORIES:[{n:'生態系統理論'},{n:'家庭系統理論'}],
  LAWS:[{n:'家庭暴力防治法'}],ALL:[q1,q2,q3,distractor],
  ESSAYS:[e1,e2], N,A, E:encodeURIComponent,
  sn:(v,n)=>String(v||'').slice(0,n),yearNum:v=>Number.parseInt(v||'0',10)||0,
  console:{warn(){}}, Set, document:null
};
vm.createContext(env);
vm.runInContext(runtime+'\nwindow.probe={swsiRelatedTheory,swsiRelatedLaw,swsiRelatedMcqs,swsiRelatedEssays};',env);
const p=env.window.probe;
assert.equal(p.swsiRelatedTheory(q1)?.n,'生態系統理論');
assert.equal(p.swsiRelatedLaw(q3)?.n,'家庭暴力防治法');
assert.equal(p.swsiRelatedTheory(distractor),null,'distractor option or stem must not count as theory proof');
assert.equal(p.swsiRelatedLaw(distractor),null,'distractor option must not count as law proof');
assert.deepEqual(Array.from(p.swsiRelatedMcqs(q1,p.swsiRelatedTheory(q1),null),q=>q.id),['q2']);
assert.deepEqual(Array.from(p.swsiRelatedEssays(q1,p.swsiRelatedTheory(q1),null),q=>q.id),['essay-1']);
assert.deepEqual(Array.from(p.swsiRelatedEssays(q3,null,p.swsiRelatedLaw(q3)),q=>q.id),['essay-2']);
assert.equal(p.swsiRelatedMcqs(distractor,null,null).length,0);
assert.equal(p.swsiRelatedEssays(distractor,null,null).length,0);
assert.equal(p.swsiRelatedTheory(e1)?.n,'生態系統理論','essay to theory reverse link');
assert.equal(p.swsiRelatedLaw(e2)?.n,'家庭暴力防治法','essay to law reverse link');
const owner=fs.readFileSync('monthly_patch_parts/zzzz_product_v1_lock.part','utf8');
assert(owner.includes("window.swsiDecorateLearningConnections();"),'final question owner must call link decorator');
assert(owner.indexOf('collapseExplanation();')<owner.lastIndexOf('window.swsiDecorateLearningConnections();'),'links follow answer expansion');
const build=fs.readFileSync('cdn/monthly_patch.js','utf8');
assert(build.includes('SWSI RELATED LEARNING START 2026-11-07'),'production bundle includes connections');
assert(build.includes("window.swsiDecorateLearningConnections();"),'production bundle wires runtime');
console.log('SWSI RELATED LEARNING SMOKE OK: verified metadata, distractor exclusion, bidirectional links, no duplicate claims');

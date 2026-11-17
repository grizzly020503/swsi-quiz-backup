#!/usr/bin/env node
'use strict';
// Deterministic regressions using maintained source; no network or student data.
const assert=require('assert'),fs=require('fs'),vm=require('vm'),path=require('path');
const root=path.resolve(__dirname,'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
function extract(source,start,end){return source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)));}
const knowledge=read('monthly_patch_parts/80.knowledge-path.part');
const lawContext={};vm.createContext(lawContext);
vm.runInContext(extract(knowledge,'  function N(','  function A(')+extract(knowledge,'  function lawMcqScore(','  function lawMcqs('),lawContext);
const law={n:'社會工作師法',k:['社會工作師','薪資','研究']};
assert.equal(lawContext.lawMcqScore({q:'全國社會工作師之薪資所得研究，研究經費有限，何種資料蒐集方法適當？',law:'社會工作師法',keywords:'社會工作師法'},law),0);
assert.equal(lawContext.lawMcqScore({q:'依《社會工作師法》規定，下列何者正確？'},law),10);
assert.equal(lawContext.lawMcqScore({q:'哪部法律規範社工師資格？',options:{A:'社會工作師法',B:'民法'}},law),10);
assert.equal(lawContext.lawMcqScore({q:'家庭界線與次系統'},law),0);
const all=fs.readdirSync(path.join(root,'cdn/question-shards')).filter(n=>/^\d+-\d+\.json$/.test(n)).flatMap(n=>JSON.parse(read('cdn/question-shards/'+n)).questions||[]);
const matching=all.filter(q=>lawContext.lawMcqScore({q:q.question,options:{A:q.opt_a,B:q.opt_b,C:q.opt_c,D:q.opt_d}},law));
assert(matching.length>0);assert(!matching.some(q=>/薪資所得相關因素/.test(q.question)));
for(const file of ['index.html','cdn/index.html']){
 const src=read(file),history=[],scheduled=[];
 const ctx={loadHist:()=>history,saveHist:()=>{},updateReviewSchedule:(q,ok)=>scheduled.push(ok),Date};vm.createContext(ctx);
 vm.runInContext(extract(src,'function record(item,picked,correct)','/* ===== 間隔複習'),ctx);
 const q={id:'sample',subject:'測試'};ctx.record(q,'A',true);ctx.record(q,null,false);
 assert.deepEqual(history.map(x=>x.answered),[true,false]);assert.deepEqual(scheduled,[true,false]);
 let current,oldSection={pending:true},replaced;
 const oldResult={parentElement:oldSection};current=oldResult;
 const aid={document:{getElementById:()=>current},render(){current={parentElement:{replaceWith(node){replaced=node;current=oldResult;}}};},guideOpen:null,dissectOpen:null};vm.createContext(aid);
 vm.runInContext(extract(src,'function renderEssayAid(id)','function guideHTML('),aid);
 aid.showGuide('essay');assert.strictEqual(replaced,oldSection);assert.equal(aid.guideOpen,'essay');
 // Pending callback still points to the same mounted result, rather than a detached node.
 oldResult.innerHTML='finished feedback';assert.equal(current.innerHTML,'finished feedback');
 aid.toggleDissect('essay');assert.strictEqual(replaced,oldSection);assert.equal(aid.dissectOpen,'essay');
}
const history=[{id:'correct',subject:'已作答科',answered:true,correct:true,ts:Date.now()},...Array.from({length:19},(_,i)=>({id:'blank'+i,subject:'未作答科',answered:false,correct:false,ts:Date.now()})),{id:'old',subject:'舊科',correct:false,ts:1}];
const ctx={app:{innerHTML:''},ALL:[],loadHist:()=>history,reviewSummary:()=>({dueCount:0,activeCount:19,masteredCount:0}),localStorage:{length:0,getItem:()=>null,key:()=>null},document:{getElementById:()=>({}),querySelector:()=>null},renderProgress(){},renderReview(){},view:'none'};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(read('monthly_patch_parts/70.learning-loop.part'),ctx);ctx.renderProgress();
assert(ctx.app.innerHTML.includes('<strong>100%</strong>'));assert(ctx.app.innerHTML.includes('未作答紀錄 19 次'));assert(ctx.app.innerHTML.includes('舊紀錄 1 次'));
assert(!ctx.app.innerHTML.includes('未作答科'));assert(!ctx.app.innerHTML.includes('舊科'));
history.splice(0,1);ctx.renderProgress();assert(ctx.app.innerHTML.includes('還沒有可分析的作答紀錄'));assert(!ctx.app.innerHTML.includes('<strong>0%</strong>'));
console.log(`LEARNING FLOW REGRESSION OK: AI section identity/pending callback, attempt metadata, 19 blanks + legacy exclusion; ${matching.length} explicit-title law candidates across ${all.length} questions.`);

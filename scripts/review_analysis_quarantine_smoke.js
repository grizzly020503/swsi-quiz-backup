#!/usr/bin/env node
'use strict';
// Offline exercise of the actual monthly runtime owner (no network/DB writes).
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const path=require('node:path');
const src=fs.readFileSync(path.join(__dirname,'../monthly_patch_parts/00.part'),'utf8');
function extract(a,b){
  const start=src.indexOf(a),stop=src.indexOf(b,start+a.length);
  assert.ok(start>=0&&stop>start,'runtime anchor not found');
  assert.equal(src.indexOf(a,start+1),-1,'duplicate runtime owner');
  return src.slice(start,stop);
}
const stub={
 // Browser global in the VM; function registration remains production code.
 window:{SWSI_QB:{}},
 normalize:r=>({
   id:r.id,q:r.question,
   options:{A:r.opt_a,B:r.opt_b,C:r.opt_c,D:r.opt_d},
   answer:r.answer,accepted_answers:r.accepted_answers,
   source_exam_code:r.source_exam_code,grading_mode:r.grading_mode,
   exp:{why:r.exp_why,others:r.exp_others,trap:r.exp_trap,raw:r.exp_raw},
   mnemonic:r.mnemonic,extension:r.extension,law:r.law,topic:r.topic,
   mistake:r.mistake,major:r.major,subject:r.subject,year:r.year,round:r.round
 }),
 swsiText:v=>String(v==null?'':v),
 swsiCleanPUA:v=>String(v==null?'':v),
 // This VM isolates explanation masking from the real figure/browser harness.
 // A non-figure row must retain ordinary answer and display behavior.
 swsiOfficialFigureReady:()=>true,
 swsiOfficialFigureMarkup:()=>'',
 swsiOfficialFigureQuestion:q=>String(q&&q.q||''),
 gradingMode:r=>r.grading_mode,
};
stub.QB=stub.window.SWSI_QB;
vm.createContext(stub);
vm.runInContext(extract('  // Official Core stays intact.','  // Clean the current auto-essay payload'),stub);
const raw={
 id:'SP-115-2-037',source_exam_code:'115100',analysis_status:'review',
 question:'OFFICIAL QUESTION',opt_a:'A',opt_b:'B',opt_c:'C',opt_d:'D',
 answer:'B',accepted_answers:['B'],grading_mode:'standard',major:'CATEGORY',
 exp_why:'BAD_AGE_55',exp_others:'BAD_OTHER',exp_trap:'BAD_TRAP',
 exp_raw:'BAD_RAW',mnemonic:'BAD_MNEMONIC',extension:'BAD_EXTENSION',
 law:'BAD_LAW',topic:'BAD_TOPIC',mistake:'BAD_MISTAKE'
};
const normalize=override=>stub.normalize({...raw,...override});
function suppressed(q){
 return ![q.exp.why,q.exp.others,q.exp.trap,q.exp.raw,q.mnemonic,
  q.extension,q.law,q.topic,q.mistake].some(Boolean);
}
let count=0;
for(const status of ['review','pending','analyzing','',null,'unexpected']){
 const q=normalize({analysis_status:status});
 assert.ok(suppressed(q),'unknown/nonready official analysis leaked: '+status);
 assert.equal(q.answer,'B');
 assert.equal(q.q,'OFFICIAL QUESTION');
 assert.equal(q.options.B,'B');
 assert.equal(q.grading_mode,'standard');
 assert.equal(Array.from(q.accepted_answers).join(','),'B');
 count++;
}
const q40=normalize({id:'SP-115-2-040',analysis_status:'ready',answer:'C',accepted_answers:['C']});
assert.ok(suppressed(q40),'known disputed READY item must be quarantined');
assert.equal(q40.analysis_status,'review');
assert.equal(q40.answer,'C');count++;
const ready=normalize({id:'DS-115-2-040',analysis_status:'ready'});
assert.equal(ready.exp.why,'BAD_AGE_55');count++;
const cached=normalize({source_exam_code:'',analysis_status:'review'});
assert.ok(suppressed(cached),'older official offline cache not quarantined');count++;
const practice=normalize({source_exam_code:'',id:'SWSI-LOCAL-001',analysis_status:''});
assert.equal(practice.exp.why,'BAD_AGE_55','nonofficial learning content incorrectly masked');count++;
const multi=normalize({id:'DS-115-2-040',analysis_status:'review',accepted_answers:['B','D']});
assert.ok(suppressed(multi));
assert.equal(Array.from(multi.accepted_answers).join(','),'B,D');count++;
const credit=normalize({id:'SP-115-2-007',analysis_status:'review',answer:'一律給分',
 grading_mode:'all_credit',accepted_answers:null});
assert.ok(suppressed(credit));
assert.equal(credit.answer,'一律給分');
assert.equal(credit.grading_mode,'all_credit');count++;

// Even legacy pre-normalized queue entries must not leak at the quiz renderer.
vm.runInContext(extract('  renderQuiz = function(){','\n  submit = function(){'),stub);
function render(q){
 const app={innerHTML:''};
 Object.assign(stub,{
  queue:[q],idx:0,answered:true,selected:'A',app,
  acceptedAnswers:item=>new Set(item.accepted_answers||[]),
  isCorrectAnswer:()=>false,answerLabel:item=>'官方答案：'+item.answer,
  swsiEsc:v=>String(v??''),swsiEscLines:v=>String(v??''),
  yearTier:()=>'',maxExamYear:()=>115,legalBadge:()=>'',legalNotice:()=>''
 });
 stub.renderQuiz();
 return app.innerHTML;
}
const legacy={...normalize({id:'SP-115-2-037',analysis_status:'ready'}),
 analysis_status:'review',exp:{why:'BAD_AGE_55',others:'BAD_OTHER',trap:'BAD_TRAP'}};
const displayed=render(legacy);
assert.ok(displayed.includes('平台解析待複核，暫不顯示'));
for(const term of ['BAD_AGE_55','BAD_OTHER','BAD_TRAP','BAD_MNEMONIC','BAD_LAW','BAD_MISTAKE','考點：']){
 assert.ok(!displayed.includes(term),'quiz leaked '+term);
}
assert.ok(displayed.includes('官方答案'));count++;
const readyHTML=render(normalize({id:'DS-115-2-040',analysis_status:'ready'}));
assert.ok(readyHTML.includes('BAD_AGE_55'));count++;

// The original mock-exam result view uses its own renderer. Exercise that
// actual snippet without creating a new overlay or changing scoring.
const htmlSrc=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
const m0=htmlSrc.indexOf('    var revHtml=wrong.map(function(w){');
const m1=htmlSrc.indexOf('\n    ov.innerHTML=',m0);
assert.ok(m0>=0 && m1>m0 && htmlSrc.indexOf('    var revHtml=wrong.map(function(w){',m0+1)===-1);
const resultFragment=htmlSrc.slice(m0,m1);
const cdnHtml=fs.readFileSync(path.join(__dirname,'../cdn/index.html'),'utf8');
const c0=cdnHtml.indexOf('    var revHtml=wrong.map(function(w){');
const c1=cdnHtml.indexOf('\n    ov.innerHTML=',c0);
assert.ok(c0>=0 && c1>c0 && cdnHtml.indexOf('    var revHtml=wrong.map(function(w){',c0+1)===-1);
assert.equal(cdnHtml.slice(c0,c1),resultFragment,'CDN mock-exam disclosure gate drifted from canonical HTML');
// Evaluate the actual page helper in the isolated VM, rather than inventing a
// stub that might conceal a broken image-question text gate.
const imageTextHelperStart='function swsiOfficialFigureQuestion(q){';
const imageTextHelperEnd='function swsiOfficialFigureLoaded(id,ok){';
function exactFigureTextHelper(source){
 const a=source.indexOf(imageTextHelperStart), b=source.indexOf(imageTextHelperEnd,a);
 assert.ok(a>=0&&b>a,'original figure text helper missing from student HTML');
 assert.equal(source.indexOf(imageTextHelperStart,a+1),-1,'duplicate image text helper');
 return source.slice(a,b);
}
const imageTextHelper=exactFigureTextHelper(htmlSrc);
assert.equal(imageTextHelper,exactFigureTextHelper(cdnHtml),'root/CDN figure text helper mismatch');
function mockResult(q, mask){
 const context={
  wrong:[{q,picked:'A'}],
  window:mask==null?{}:{SWSI_QB:{shouldMaskAnalysis:mask}},
  E:v=>String(v??''),answerLabel:item=>'官方答案：'+item.answer
 };
 vm.createContext(context);
 vm.runInContext(imageTextHelper,context);
 vm.runInContext(resultFragment,context);
 return context.revHtml;
}
const staleMock={...normalize({id:'SP-115-2-037',analysis_status:'ready'}),
 analysis_status:'review',
 exp:{why:'BAD_AGE_55',others:'BAD_OTHER',trap:'BAD_TRAP',raw:'BAD_RAW'},
 mnemonic:'BAD_MNEMONIC',law:'BAD_LAW'
};
for(const mask of [item=>item.analysis_status!=='ready', null]){
 const out=mockResult(staleMock,mask);
 assert.ok(out.includes('平台解析待複核，暫不顯示'));
 for(const term of ['BAD_AGE_55','BAD_OTHER','BAD_TRAP','BAD_RAW','BAD_MNEMONIC','BAD_LAW']){
  assert.ok(!out.includes(term),'mock review leaked '+term);
 }
 assert.ok(out.includes('官方答案：B'));
 count++;
}
const q40Mock={...staleMock,id:'SP-115-2-040',answer:'C',analysis_status:'ready'};
const q40Text=mockResult(q40Mock,item=>item.id==='SP-115-2-040');
assert.ok(!q40Text.includes('BAD_AGE_55') && q40Text.includes('官方答案：C'));count++;
const normalMock=mockResult(normalize({id:'DS-115-2-040',analysis_status:'ready'}),
 item=>item.analysis_status!=='ready');
assert.ok(normalMock.includes('BAD_AGE_55'));count++;

// Use actual immutable CDN rows, not only synthetic question fixtures. This
// catches a future ID/status/grading drift without modifying MOEX Official Core.
const published=JSON.parse(fs.readFileSync(path.join(__dirname,'../cdn/question-shards/115-2.json'),'utf8'));
assert.equal(published.question_count,200);
assert.equal(published.questions.length,200);
for(const [id,expectedStatus,expectedAnswer] of [
 ['SP-115-2-037','review','B'],
 ['SP-115-2-040','ready','C'],
]){
 const row=published.questions.find(r=>r.id===id);
 assert.ok(row,'missing real CDN row '+id);
 assert.equal(row.analysis_status,expectedStatus,id+' source status changed; re-review gate');
 assert.equal(row.answer,expectedAnswer,'Official Core unexpectedly drifted');
 assert.equal(row.grading_mode,'standard');
 assert.equal(row.source_exam_code,'115100');
 const before=JSON.stringify(row);
 const q=stub.normalize(row);
 assert.ok(suppressed(q),'real CDN question exposed unverified analysis: '+id);
 assert.equal(q.q,row.question);
 assert.equal(q.answer,row.answer);
 assert.equal(q.options.A,row.opt_a);
 assert.equal(q.options.B,row.opt_b);
 assert.equal(q.options.C,row.opt_c);
 assert.equal(q.options.D,row.opt_d);
 assert.equal(q.source_exam_code,row.source_exam_code);
 assert.equal(q.grading_mode,row.grading_mode);
 assert.equal(JSON.stringify(row),before,'normalization mutated original CDN row');
 const quiz=render(q);
 const mock=mockResult(q,item=>stub.window.SWSI_QB.shouldMaskAnalysis(item));
 assert.ok(quiz.includes('平台解析待複核，暫不顯示'));
 assert.ok(mock.includes('平台解析待複核，暫不顯示'));
 assert.ok(quiz.includes('官方答案') && mock.includes('官方答案'));
 assert.ok(!quiz.includes(row.exp_why),'original AI explanation leaked via quiz');
 assert.ok(!mock.includes(row.exp_why),'original AI explanation leaked via mock');
 count++;
}

console.log('REVIEW ANALYSIS QUARANTINE SELFTEST OK: '+count+' regressions');

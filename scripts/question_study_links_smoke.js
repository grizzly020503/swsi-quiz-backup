'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const knowledge=fs.readFileSync('monthly_patch_parts/80.knowledge-path.part','utf8');
const product=fs.readFileSync('monthly_patch_parts/zzzz_product_v1_lock.part','utf8');
const cdn=fs.readFileSync('cdn/monthly_patch.js','utf8');
assert(cdn.includes(knowledge),'Canonical knowledge path must ship verbatim');
assert(cdn.includes(product),'Canonical explanation owner must ship verbatim');
const begin=knowledge.indexOf('  function questionStudyRefs(item){');
const finish=knowledge.indexOf('  window.swsiQuestionStudyRefs=questionStudyRefs;',begin);
assert(begin>=0&&finish>begin,'Missing metadata-only resolver');
const src=knowledge.slice(begin,finish);
assert(!src.includes('q.q'),'Do not infer theory/law from raw official question text');
const N=v=>String(v==null?'':v).toLowerCase().replace(/[\\s　（）()《》〈〉「」『』【】·・,，.。:：;；/\\\\_-]+/g,'');
const A=v=>Array.isArray(v)?v:(v?String(v).split(/[、,，;；]/).filter(Boolean):[]);
const THEORIES=[{n:'生態系統理論'},{n:'增強權能理論'},{n:'心理社會發展理論'}];
const LAWS=[{n:'家庭暴力防治法'},{n:'社會工作師法'}];
const get=new Function('item','THEORIES','LAWS','A','N',src+'\nreturn questionStudyRefs(item);');
let r=get({topic:'生態系統理論',law:'家庭暴力防治法'},THEORIES,LAWS,A,N);
assert.deepEqual(r.theories.map(t=>t.n),['生態系統理論']);
assert.deepEqual(r.laws.map(l=>l.n),['家庭暴力防治法']);
assert.equal(r.term,'生態系統理論');
r=get({topic:'其他',q:'生態系統理論涉及家庭暴力防治法'},THEORIES,LAWS,A,N);
assert.equal(r.theories.length,0,'No text-content theory inference');
assert.equal(r.laws.length,0,'No text-content law inference');
assert.equal(r.term,'','Generic topic must not trigger broad search');
r=get({topic:'政策研究方法',theories:['增強權能理論'],laws:['社會工作師法']},THEORIES,LAWS,A,N);
assert.equal(r.theories[0].n,'增強權能理論');
assert.equal(r.laws[0].n,'社會工作師法');
r=get({topic:'<img src=x onerror=alert(1)>'},THEORIES,LAWS,A,N);
assert.equal(r.theories.length,0);
assert.equal(r.laws.length,0);
assert.equal(get({},THEORIES,LAWS,A,N).term,'');

const a=product.indexOf('  function addQuestionStudyPath(exp,item){');
const b=product.indexOf('  function addQuestionTrust(exp,item){',a);
assert(a>=0&&b>a,'Question explanatory context must own the study links');
const code=product.slice(a,b);
assert(!code.includes('innerHTML'),'All question-derived strings must be textContent');
assert(!code.includes('fetch('),'Question extension must not add per-question network traffic');
assert(product.includes('addQuestionStudyPath(exp,item);'));
assert(product.includes('addQuestionStudyPath(exp,currentItem);'));
class Element{
  constructor(tag){this.tag=tag;this.children=[];this.className='';this.textContent='';this.attrs={};this.events={};}
  setAttribute(k,v){this.attrs[k]=v;}
  appendChild(x){this.children.push(x);return x;}
  insertBefore(x,y){const i=this.children.indexOf(y);assert(i>=0);this.children.splice(i,0,x);return x;}
  addEventListener(type,cb){this.events[type]=cb;}
}
const document={createElement:tag=>new Element(tag)};
const directChild=(parent,sel)=>parent.children.find(e=>e.className===sel.slice(1))||null;
const calls=[];
const window={
  swsiQuestionStudyRefs:item=>get(item,THEORIES,LAWS,A,N),
  swsiOpenTheoryEncoded:x=>calls.push(['theory',decodeURIComponent(x)]),
  swsiOpenLawEncoded:x=>calls.push(['law',decodeURIComponent(x)]),
  swsiKnowledgeSearch:x=>calls.push(['search',x])
};
const render=new Function('exp','item','window','document','directChild','encodeURIComponent',code+'\nreturn addQuestionStudyPath(exp,item);');
const exp=new Element('div');const trust=new Element('details');trust.className='swsi-answer-trust';exp.appendChild(trust);
const item={topic:'生態系統理論',law:'家庭暴力防治法'};
render(exp,item,window,document,directChild,encodeURIComponent);
assert.equal(exp.children.length,2);
const panel=exp.children[0];assert.equal(panel.tag,'details');
assert.equal(panel.className,'swsi-question-study-path');
assert.equal(panel.children[0].tag,'summary','One collapsed default entry');
assert(!panel.attrs.open,'Must remain collapsed by default');
const buttons=panel.children[1].children.filter(x=>x.tag==='button');
assert.equal(buttons.length,3);
for(const button of buttons){assert.equal(typeof button.events.click,'function');button.events.click({stopPropagation(){}});}
assert.deepEqual(calls,[['theory','生態系統理論'],['law','家庭暴力防治法'],['search','生態系統理論']]);
render(exp,item,window,document,directChild,encodeURIComponent);
assert.equal(exp.children.length,2,'No duplicate panels after MutationObserver');
const noTag=new Element('div');
render(noTag,{topic:'未分類',q:'生態系統理論'},window,document,directChild,encodeURIComponent);
assert.equal(noTag.children.length,0,'No fabricated links without metadata');
console.log('QUESTION STUDY LINKS SMOKE OK');

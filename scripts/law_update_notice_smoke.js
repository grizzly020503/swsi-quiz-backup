'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const src=fs.readFileSync('monthly_patch_parts/zzzz_product_v1_lock.part','utf8');
const start=src.indexOf('  function currentOfficialLawHref(value){');
const end=src.indexOf('\n  function addQuestionTrust(exp,item){',start);
assert(start>=0&&end>start,'Law update must remain in the product UI owner');
const snippet=src.slice(start,end);
assert(!snippet.includes('innerHTML'),'Never inject legal notes as HTML');
assert(!snippet.includes('fetch('),'No runtime network needed');
class El{
  constructor(tag){this.tag=tag;this.children=[];this.className='';this.textContent='';this.attrs={};}
  setAttribute(k,v){this.attrs[k]=v;}
  appendChild(c){this.children.push(c);return c;}
  insertBefore(c,b){const i=this.children.indexOf(b);assert(i>=0);this.children.splice(i,0,c);return c;}
}
const document={createElement:tag=>new El(tag)};
const directChild=(exp,sel)=>exp.children.find(x=>x.className===sel.slice(1))||null;
const safeTrustHref=x=>{try{let u=new URL(String(x||''));return u.protocol==='https:'?u.href:'';}catch{return '';}};
const render=new Function('exp','item','document','directChild','safeTrustHref','URL',snippet+'\nreturn addLawUpdateNotice(exp,item);');
const law='https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050071';
function run(item){
  const exp=new El('div'),trust=new El('details');trust.className='swsi-answer-trust';exp.appendChild(trust);
  render(exp,item,document,directChild,safeTrustHref,URL);
  return {exp,notice:directChild(exp,'.swsi-law-update-notice')};
}
{
  const x=run({legal_status:'changed',legal_note:'監測到家庭暴力防治法相關條文異動，需依最新法規重新核對。',legal_source_url:law});
  assert(x.notice&&x.exp.children[0]===x.notice);
  assert.match(x.notice.children[0].textContent,/待核對/);
  assert.match(x.notice.children[1].textContent,/重新核對/);
  assert.equal(x.notice.children.at(-1).href,law);
  assert.equal(x.notice.children.at(-1).rel,'noopener noreferrer');
  render(x.exp,{legal_status:'changed',legal_source_url:law},document,directChild,safeTrustHref,URL);
  assert.equal(x.exp.children.filter(n=>n.className==='swsi-law-update-notice').length,1);
}
{
  const x=run({legal_status:'changed',legal_note:'<img src=x onerror=alert(1)>',legal_source_url:'https://law.moj.gov.tw.evil.test/LawClass/LawAll.aspx?pcode=D0050071'});
  assert.equal(x.notice.children[1].textContent,'<img src=x onerror=alert(1)>');
  assert(!x.notice.children.some(n=>n.tag==='a'));
}
{
  const x=run({legal_status:'changed',legal_source_url:'https://law.moj.gov.tw/LawClass/LawOldVer.aspx?pcode=D0050071'});
  assert.match(x.notice.children[1].textContent,/尚待確認/);
  assert(!x.notice.children.some(n=>n.tag==='a'));
}
for(const status of ['unreviewed','not_applicable','verified_current']){
  assert.equal(run({legal_status:status,legal_note:'監測到修正',legal_source_url:law}).notice,null,status);
}
{
  const x=run({legal_status:'verified_current',legal_note:'【修法摘要已核對】條文已經修正，現行規定請以官方資料為準。',legal_checked_at:'2026-11-07',legal_source_url:law});
  assert(x.notice);
  assert.match(x.notice.children[0].textContent,/已核對/);
  assert.match(x.notice.children[1].textContent,/條文已經修正/);
  assert(!x.notice.children[1].textContent.includes('【修法摘要已核對】'));
}
assert.equal(run({legal_status:'verified_current',legal_note:'【修法摘要已核對】沒有核對日期',legal_source_url:law}).notice,null);
console.log('LAW UPDATE NOTICE SMOKE OK');

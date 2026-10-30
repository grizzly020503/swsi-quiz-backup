'use strict';
// Exercise actual canonical shard bytes and the real quiz renderer/grader.
const assert=require('assert');
const fs=require('fs');
const {chromium,webkit}=require('playwright');
const serveLocalQuestionShards=require('./local_question_shards_fixture');
const proof=JSON.parse(fs.readFileSync('audit/official_mcq_corrections_20261025.json','utf8'));
const additional=JSON.parse(fs.readFileSync('audit/official_mcq_corrections_additional_20261025.json','utf8'));
const projection=JSON.parse(fs.readFileSync('audit/official_combined_base_projection_20261029.json','utf8'));
const shared=['audit/official_105_2_shared_context_20261028.json','audit/official_107_2_shared_context_20261028.json'].flatMap(p=>JSON.parse(fs.readFileSync(p,'utf8')).changes);
const repairs=JSON.parse(fs.readFileSync('audit/official_pdf_stem_repairs_20261029.json','utf8'));
const cases=proof.rows.concat(additional.rows,repairs.rows).map(row=>({...row,quarantine:true})).concat(shared.map(change=>{
  const before=projection.before_rows[change.id];
  assert(before,'missing shared preimage');
  const after={...before};
  for(const [field,delta] of Object.entries(change.fields)){
    assert.strictEqual(before[field],delta.before);
    after[field]=delta.after;
  }
  return {id:change.id,before,after,quarantine:false};
}));
assert.strictEqual(cases.length,42);
assert.strictEqual(new Set(cases.map(row=>row.id)).size,42);
const base=process.argv[2]||'http://127.0.0.1:4173/';
const engine=process.argv[3]||'chromium';
const compact=s=>s.normalize('NFKC').replace(/\s+/g,'');
assert(['chromium','webkit'].includes(engine));
(async()=>{
  const browser=await ({chromium,webkit})[engine].launch({headless:true});
  try{
    for(const viewport of [{width:390,height:844},{width:1365,height:900}]){
      const context=await browser.newContext({viewport});
      await serveLocalQuestionShards(context);
      const page=await context.newPage();
      await page.goto(base,{waitUntil:'domcontentloaded'});
      await page.locator('.swsi-focus-primary').waitFor();
      await page.evaluate(()=>window.ensureAllQuestionsLoaded());
      for(const row of cases){
        await page.evaluate(id=>startQuiz(q=>q.id===id,1),row.id);
        const question=await page.locator('.qtext').innerText();
        assert.strictEqual(compact(question),compact(row.after.question),row.id+': stale question');
        const options=page.locator('.opt');
        assert.strictEqual(await options.count(),4,row.id+': missing options');
        for(const [i,letter] of ['A','B','C','D'].entries()){
          const text=await options.nth(i).innerText();
          assert.strictEqual(compact(text).slice(1),compact(row.after['opt_'+letter.toLowerCase()]),row.id+': stale option '+letter);
        }
        await page.locator('.opt').nth('ABCD'.indexOf(row.after.answer)).click();
        await page.getByRole('button',{name:'送出答案',exact:true}).click();
        await page.locator('.exp').waitFor();
        assert.strictEqual(await page.locator('.opt.correct').count(),1,row.id+': official grading failed');
        if(row.quarantine) assert.strictEqual(await page.locator('.exp-sec').count(),0,row.id+': quarantined old analysis returned');
        if(row.quarantine&&row.before.exp_why){
          assert(!(await page.locator('.exp').innerText()).includes(row.before.exp_why.slice(0,25)),row.id+': old explanation leaked');
        }
      }
      await context.close();
    }
    console.log('CONTROLLED MCQ BROWSER OK '+engine+': '+cases.length+' exact official questions/options, real quiz grading and stale-analysis quarantine on mobile and desktop');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});

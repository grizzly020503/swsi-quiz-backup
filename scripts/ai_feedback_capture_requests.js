#!/usr/bin/env node
'use strict';
// Capture exact request payloads by executing the actual candidate handler.
// Synthetic Golden Set only. No network call, generated feedback, or human rating.
const fs=require('fs');
const vm=require('vm');
const crypto=require('crypto');
const path=require('path');

(async()=>{
  const dataset=JSON.parse(fs.readFileSync('ai_eval/golden_set.json','utf8'));
  const source=fs.readFileSync(dataset.prompt_contract.source,'utf8');
  const records=[];
  for(const fixture of dataset.cases){
    const id=fixture.id;
    const elements={['ta_'+id]:{value:fixture.student_answer},['airesult_'+id]:{innerHTML:''}};
    const window={ESSAYS:[{id,q:fixture.question}],ESSAY_GUIDES:{}};
    if(fixture.reference_status!=='none')window.ESSAY_GUIDES[id]={
      review_status:fixture.reference_status==='verified_but_intentionally_conflicting_fixture'?'verified':'needs_review',
      kao:fixture.reference_text,biaoti:[],kw:[]
    };
    let request;
    window.swsiFetchWithTimeout=async(url,options)=>{
      if(request)throw Error('more than one request per case');
      request=JSON.parse(options.body);
      return {ok:true,status:200,json:async()=>({choices:[]})};
    };
    const context={window,document:{getElementById:id=>elements[id],querySelectorAll:()=>[]},
      AI_PROXY_URL:'https://wandering-wave-4418.c022050333.workers.dev/api/ai',
      GROQ_MODEL:dataset.model_contract.public_model,Date,console};
    vm.createContext(context);
    vm.runInContext(source,context,{filename:dataset.prompt_contract.source,timeout:3000});
    await window.runAIFeedback(id);
    if(!request)throw Error('candidate handler did not create request: '+id);
    const text=request.messages[0].content;
    if(!text.includes(fixture.student_answer)||!text.includes(fixture.question))throw Error('fixture changed: '+id);
    if(fixture.reference_status==='unverified'&&text.includes(fixture.reference_text))throw Error('unverified reference leaked');
    records.push({id,request,human_scores:null,output:null});
  }
  const result={schema_version:1,scope:'request_capture_only_no_model_output',
    golden_set:dataset.name,model:dataset.model_contract.public_model,prompt_version:dataset.prompt_contract.guide_version,
    prompt_source_sha256:crypto.createHash('sha256').update(source).digest('hex'),
    human_review_completed:false,records};
  const destination=process.argv[2];
  if(destination){fs.mkdirSync(path.dirname(destination),{recursive:true});fs.writeFileSync(destination,JSON.stringify(result,null,2)+'\n');}
  console.log('ACTUAL CANDIDATE REQUESTS CAPTURED: '+records.length+'; model outputs=0; human ratings=0; quality HOLD');
})().catch(error=>{console.error(error);process.exit(1);});

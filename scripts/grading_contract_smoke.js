#!/usr/bin/env node
'use strict';

const { chromium } = require('playwright');

(async () => {
  const base = process.argv[2] || 'http://127.0.0.1:4173/';
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', err => errors.push(String(err)));

  await page.goto(base, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForFunction(() => typeof window.isCorrectAnswer === 'function' && window.MK, null, { timeout: 30000 });

  const result = await page.evaluate(() => {
    const standard = { id:'T-STD', answer:'B', accepted_answers:['B'], grading_mode:'standard' };
    const multi = { id:'T-MULTI', answer:'B', accepted_answers:['B','C'], grading_mode:'standard' };
    const allCredit = { id:'T-ALL', answer:'一律給分', accepted_answers:null, grading_mode:'all_credit' };
    const anyAnswer = { id:'T-ANY', answer:'一律給分', accepted_answers:['A','B','C','D'], grading_mode:'any_answer' };
    const missingSpecial = { id:'T-MISSING', answer:'一律給分', accepted_answers:null };
    const ordinaryLegacy = { id:'T-LEGACY', answer:'D', accepted_answers:null };

    const manifest={
      total_questions:4,
      shards:[
        {file:'101-1.json',year:'101',round:'第一次',question_count:2},
        {file:'101-2.json',year:'101',round:'第二次',question_count:2}
      ]
    };
    const bankRows=[
      {id:'A',year:'101',round:'第一次'},
      {id:'B',year:'101',round:'第一次'},
      {id:'C',year:'101',round:'第二次'},
      {id:'D',year:'101',round:'第二次'}
    ];
    const loaded=new Set(['101-1.json','101-2.json']);
    let bankGood=false, bankCollisionBlocked=false, bankManifestMismatchBlocked=false;
    try{bankGood=window.swsiAssertCompleteQuestionBank(bankRows,manifest,loaded).ok===true;}catch(_e){}
    try{window.swsiAssertCompleteQuestionBank(bankRows.slice(0,3),manifest,loaded);}catch(_e){bankCollisionBlocked=true;}
    try{window.swsiAssertCompleteQuestionBank(bankRows,{...manifest,total_questions:5},loaded);}catch(_e){bankManifestMismatchBlocked=true;}

    return {
      contract: window.swsiGradingContractVersion,
      mkContract: window.MK && window.MK.contractVersion,
      standardB: window.isCorrectAnswer(standard,'B'),
      standardC: window.isCorrectAnswer(standard,'C'),
      multiB: window.isCorrectAnswer(multi,'B'),
      multiC: window.isCorrectAnswer(multi,'C'),
      multiA: window.isCorrectAnswer(multi,'A'),
      allBlank: window.isCorrectAnswer(allCredit,null),
      allD: window.isCorrectAnswer(allCredit,'D'),
      anyBlank: window.isCorrectAnswer(anyAnswer,null),
      anyA: window.isCorrectAnswer(anyAnswer,'A'),
      missingMode: window.gradingMode(missingSpecial),
      missingSpecialA: window.isCorrectAnswer(missingSpecial,'A'),
      ordinaryLegacyMode: window.gradingMode(ordinaryLegacy),
      ordinaryLegacyD: window.isCorrectAnswer(ordinaryLegacy,'D'),
      integrityContract: window.swsiShardIntegrityVersion,
      bankIntegrityContract: window.swsiQuestionBankIntegrityVersion,
      bankGood,
      bankCollisionBlocked,
      bankManifestMismatchBlocked
    };
  });

  const expected = {
    contract:'2026-08-26.fail-closed.v1',
    mkContract:'2026-08-26.unified-grading.v1',
    standardB:true,
    standardC:false,
    multiB:true,
    multiC:true,
    multiA:false,
    allBlank:true,
    allD:true,
    anyBlank:false,
    anyA:true,
    missingMode:'invalid',
    missingSpecialA:false,
    ordinaryLegacyMode:'standard',
    ordinaryLegacyD:true,
    integrityContract:'2026-08-26.sha256.v1',
    bankIntegrityContract:'2026-08-27.full-bank.v1',
    bankGood:true,
    bankCollisionBlocked:true,
    bankManifestMismatchBlocked:true
  };

  for (const [key, value] of Object.entries(expected)) {
    if (result[key] !== value) throw new Error(`${key}: expected ${JSON.stringify(value)}, got ${JSON.stringify(result[key])}`);
  }
  if (errors.length) throw new Error('page errors: ' + errors.join(' | '));

  console.log('GRADING CONTRACT SMOKE OK');
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

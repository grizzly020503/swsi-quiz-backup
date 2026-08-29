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
  try {
    await page.waitForFunction(() => typeof window.isCorrectAnswer === 'function' && window.MK, null, { timeout: 30000 });
  } catch (err) {
    const snapshot = await page.evaluate(() => ({
      readyState: document.readyState,
      href: location.href,
      globals: {
        isCorrectAnswer: typeof window.isCorrectAnswer,
        MK: typeof window.MK,
        render: typeof window.render,
        renderHome: typeof window.renderHome,
        init: typeof window.init,
        supabase: typeof window.supabase,
        SG: typeof window.SG,
        NL: typeof window.NL,
        SWSI_QB: typeof window.SWSI_QB,
        bootDeferred: window.__SWSI_BOOT_DEFERRED__,
        studentRestOnly: window.__SWSI_STUDENT_REST_ONLY__
      },
      appText: ((document.getElementById('app') || {}).textContent || '').trim().slice(0, 500),
      scripts: Array.from(document.scripts).map(s => s.src || '[inline]').slice(-12)
    }));
    console.error('GRADING BOOT SNAPSHOT ' + JSON.stringify({ snapshot, pageErrors: errors }, null, 2));
    throw err;
  }

  const result = await page.evaluate(() => {
    const standard = { id:'T-STD', answer:'B', accepted_answers:['B'], grading_mode:'standard' };
    const multi = { id:'T-MULTI', answer:'B', accepted_answers:['B','C'], grading_mode:'standard' };
    const allCredit = { id:'T-ALL', answer:'一律給分', accepted_answers:null, grading_mode:'all_credit' };
    const anyAnswer = { id:'T-ANY', answer:'一律給分', accepted_answers:null, grading_mode:'any_answer' };
    const missingSpecial = { id:'T-MISSING', answer:'一律給分', accepted_answers:null };
    const ordinaryLegacy = { id:'T-LEGACY', answer:'D', accepted_answers:null };
    const inconsistentSpecial = { id:'T-BAD-SPECIAL', answer:'B', accepted_answers:null, grading_mode:'all_credit' };
    const specialWithAccepted = { id:'T-BAD-ACCEPTED', answer:'一律給分', accepted_answers:['A','B','C','D'], grading_mode:'any_answer' };
    const inconsistentStandard = { id:'T-BAD-STANDARD', answer:'一律給分', accepted_answers:null, grading_mode:'standard' };
    const badMulti = { id:'T-BAD-MULTI', answer:'B', accepted_answers:['C','C'], grading_mode:'standard' };
    const mockPerfect = window.swsiEvaluateMockAnswers(
      [standard,multi,allCredit,anyAnswer],
      {0:'B',1:'C',3:'A'}
    );
    const mockAnyBlank = window.swsiEvaluateMockAnswers(
      [standard,multi,allCredit,anyAnswer],
      {0:'B',1:'C'}
    );
    const mockBlocked = window.swsiEvaluateMockAnswers([standard,inconsistentSpecial],{0:'B',1:'B'});
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
      inconsistentSpecialMode: window.gradingMode(inconsistentSpecial),
      inconsistentSpecialAcceptedCount: window.acceptedAnswers(inconsistentSpecial).size,
      specialWithAcceptedMode: window.gradingMode(specialWithAccepted),
      specialWithAcceptedCount: window.acceptedAnswers(specialWithAccepted).size,
      inconsistentStandardMode: window.gradingMode(inconsistentStandard),
      badMultiMode: window.gradingMode(badMulti),
      badMultiAcceptedCount: window.acceptedAnswers(badMulti).size,
      mockPerfect: {blocked:mockPerfect.blocked,total:mockPerfect.total,correct:mockPerfect.correct,answered:mockPerfect.answered,wrong:mockPerfect.wrong.length},
      mockAnyBlank: {blocked:mockAnyBlank.blocked,total:mockAnyBlank.total,correct:mockAnyBlank.correct,answered:mockAnyBlank.answered,wrong:mockAnyBlank.wrong.length},
      mockBlocked: {blocked:mockBlocked.blocked,invalidIds:mockBlocked.invalidIds},
      recordAllBlank: window.swsiShouldRecordMockAnswer('all_credit',null),
      recordAnyBlank: window.swsiShouldRecordMockAnswer('any_answer',null),
      integrityContract: window.swsiShardIntegrityVersion,
      bankIntegrityContract: window.swsiQuestionBankIntegrityVersion,
      bankGood,
      bankCollisionBlocked,
      bankManifestMismatchBlocked
    };
  });

  const expected = {
    contract:'2026-08-26.fail-closed.v2',
    mkContract:'2026-08-26.unified-grading.v2',
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
    inconsistentSpecialMode:'invalid',
    inconsistentSpecialAcceptedCount:0,
    specialWithAcceptedMode:'invalid',
    specialWithAcceptedCount:0,
    inconsistentStandardMode:'invalid',
    badMultiMode:'invalid',
    badMultiAcceptedCount:0,
    mockPerfect:{blocked:false,total:4,correct:4,answered:3,wrong:0},
    mockAnyBlank:{blocked:false,total:4,correct:3,answered:2,wrong:1},
    mockBlocked:{blocked:true,invalidIds:['T-BAD-SPECIAL']},
    recordAllBlank:false,
    recordAnyBlank:true,
    integrityContract:'2026-08-26.sha256.v2',
    bankIntegrityContract:'2026-08-27.full-bank.v1',
    bankGood:true,
    bankCollisionBlocked:true,
    bankManifestMismatchBlocked:true
  };

  for (const [key, value] of Object.entries(expected)) {
    if (JSON.stringify(result[key]) !== JSON.stringify(value)) throw new Error(`${key}: expected ${JSON.stringify(value)}, got ${JSON.stringify(result[key])}`);
  }

  if (errors.length) throw new Error('page errors: ' + errors.join(' | '));

  console.log('GRADING CONTRACT SMOKE OK');
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})().catch(err => {
  console.error(err && err.stack || err);
  process.exit(1);
});

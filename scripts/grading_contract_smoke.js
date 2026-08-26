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
      integrityContract: window.swsiShardIntegrityVersion
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
    integrityContract:'2026-08-26.sha256.v1'
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

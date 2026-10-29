#!/usr/bin/env python3
"""Reject official-stem evidence drift, unrelated edits and stale explanations."""
from copy import deepcopy
import json
import unittest
import official_pdf_stem_repairs as repair
from audit_moex_source_subjects import load_registry


class StemRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof=repair.load_proof()
        cls.report=json.loads((repair.ROOT/'audit/official_mcq_pdf_comparison_20261025.json').read_text())
        cls.observed={r['id']:r for r in cls.report['rows']}
        cls.registry=load_registry()
        cls.transport=json.loads((repair.ROOT/'data/moex_answer_sources.v1.json').read_text())['records']

    def case(self, ident='SW-110-1-33'):
        item=deepcopy(next(r for r in self.proof['rows'] if r['id']==ident))
        return item,deepcopy(self.observed[ident])

    def check(self, item, observed):
        repair.validate_item(item,observed,item['after'],self.registry,self.transport)

    def rehash(self,item):
        item['after_lock_sha256']=repair.row_hash(repair.canonical_row(item['after'],repair.MCQ_FIELDS))
        item['official_transcription']=item['after']['question']

    def test_both_exact_repairs(self):
        self.assertEqual(repair.validated_ids(self.report),repair.REPAIR_IDS)
        for item in self.proof['rows']:
            self.check(item,self.observed[item['id']])

    def test_wrong_question_pdf(self):
        i,o=self.case();i['question_pdf_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'question PDF mismatch'):self.check(i,o)

    def test_wrong_final_answer_pdf(self):
        i,o=self.case();i['answer_pdf_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'answer PDF mismatch'):self.check(i,o)

    def test_wrong_page(self):
        i,o=self.case();i['pdf_page_number']=3
        with self.assertRaisesRegex(ValueError,'page drift'):self.check(i,o)

    def test_false_human_approval(self):
        i,o=self.case();i['human_approval']=True
        with self.assertRaisesRegex(ValueError,'approval/transcription drift'):self.check(i,o)

    def test_unrelated_option_edit(self):
        i,o=self.case();i['after']['opt_a']='②③④';self.rehash(i)
        with self.assertRaisesRegex(ValueError,'unapproved repair field'):self.check(i,o)

    def test_wrong_1950_even_with_rehashed_after(self):
        i,o=self.case();i['after']['question']=i['after']['question'].replace('1950','1960');self.rehash(i)
        with self.assertRaisesRegex(ValueError,'not official extracted text'):self.check(i,o)

    def test_grading_change(self):
        i,o=self.case();i['after']['answer']='A';self.rehash(i)
        with self.assertRaisesRegex(ValueError,'unapproved repair field'):self.check(i,o)

    def test_stale_explanation(self):
        i,o=self.case();i['after']['exp_why']=i['before']['exp_why']
        with self.assertRaisesRegex(ValueError,'stale repair explanation'):self.check(i,o)

    def test_captured_extraction_tamper(self):
        i,o=self.case();o['text_differences']['question']['official_extraction']='wrong'
        with self.assertRaisesRegex(ValueError,'baseline drift'):self.check(i,o)

    def test_incomplete_opening_even_if_extraction_is_tampered_to_match(self):
        i,o=self.case('R-106-2-01');i['after']['question']='在研究過程中，'+i['before']['question'];self.rehash(i)
        o['text_differences']['question']['official_extraction']=i['after']['question']
        i['baseline_differences']=deepcopy(o['text_differences']);i['baseline_comparison_row_sha256']=repair.fingerprint(o)
        with self.assertRaisesRegex(ValueError,'unverified opening clause'):self.check(i,o)


if __name__=='__main__':unittest.main()

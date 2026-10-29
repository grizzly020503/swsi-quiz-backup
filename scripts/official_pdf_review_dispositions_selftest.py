#!/usr/bin/env python3
"""Reject plausible-looking but unsupported PDF review clearances."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
import official_pdf_review_dispositions as review
from audit_moex_source_subjects import load_registry
from official_exam_readonly_guard import canonical_row, row_hash, MCQ_FIELDS


class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = review.ROOT
        cls.proof = json.loads((root / review.PROOF_PATH).read_text())
        cls.report = json.loads((root / 'audit/official_mcq_pdf_comparison_20261025.json').read_text())
        cls.observed = {r['id']:r for r in cls.report['rows']}
        manifest = json.loads((root / 'cdn/question-shards/manifest.json').read_text())
        cls.current = {r['id']:r for e in manifest['shards'] for r in json.loads((root / 'cdn/question-shards' / e['file']).read_text())['questions']}
        cls.registry = load_registry()

    def case(self, ident='R-107-2-08'):
        return deepcopy(self.observed[ident]), deepcopy(next(r for r in self.proof['rows'] if r['id']==ident)), deepcopy(self.current[ident])

    def check(self, observed, item, current):
        review.validate_item(observed, item, current, self.registry)

    def test_exact_five_only(self):
        self.assertEqual(review.validated_ids(self.report), review.DISPOSITION_IDS)
        for item in self.proof['rows']:
            self.check(self.observed[item['id']], item, self.current[item['id']])

    def test_altered_baseline_extraction(self):
        o,i,c = self.case(); o['text_differences']['opt_a']['official_extraction']='僅14'
        with self.assertRaisesRegex(ValueError, 'baseline comparison drift'):
            self.check(o,i,c)

    def test_wrong_official_pdf(self):
        o,i,c = self.case(); i['pdf_sha256']='0'*64
        with self.assertRaisesRegex(ValueError, 'PDF source mismatch'):
            self.check(o,i,c)

    def test_wrong_page(self):
        o,i,c = self.case(); i['pdf_page_number']=1
        with self.assertRaisesRegex(ValueError, 'wrong official page'):
            self.check(o,i,c)

    def test_wrong_circled_option_even_with_rehashed_row(self):
        o,i,c = self.case(); c['opt_a']='僅①③'
        i['current_full_row_sha256']=review.digest(c)
        i['current_core_lock_sha256']=row_hash(canonical_row(c,MCQ_FIELDS))
        i['official_field_transcription']['opt_a']=c['opt_a']
        with self.assertRaisesRegex(ValueError, 'circled glyph mapping'):
            self.check(o,i,c)

    def test_grading_drift_even_with_rehashed_row(self):
        o,i,c = self.case(); c['answer']='A'
        i['current_full_row_sha256']=review.digest(c)
        i['current_core_lock_sha256']=row_hash(canonical_row(c,MCQ_FIELDS))
        with self.assertRaisesRegex(ValueError, 'grading drift'):
            self.check(o,i,c)

    def test_false_human_approval(self):
        o,i,c = self.case(); i['human_approval']=True
        with self.assertRaisesRegex(ValueError, 'false human approval'):
            self.check(o,i,c)

    def test_wrong_context_range_even_with_rehashed_evidence(self):
        o,i,c = self.case('R-105-2-12')
        o['text_differences']['opt_d']['official_extraction']=o['text_differences']['opt_d']['official_extraction'].replace('第 16 題','第 19 題')
        i['baseline_differences']=deepcopy(o['text_differences']); i['baseline_comparison_row_sha256']=review.digest(o)
        with self.assertRaisesRegex(ValueError, 'wrong dependent context range'):
            self.check(o,i,c)

    def test_figure_label_must_not_be_inserted_into_stem(self):
        o,i,c = self.case('DS-113-2-13'); c['question']+='1970結婚'
        i['current_full_row_sha256']=review.digest(c); i['current_core_lock_sha256']=row_hash(canonical_row(c,MCQ_FIELDS)); i['official_field_transcription']['question']=c['question']
        with self.assertRaisesRegex(ValueError, 'unverified figure stem'):
            self.check(o,i,c)


if __name__ == '__main__':
    unittest.main()

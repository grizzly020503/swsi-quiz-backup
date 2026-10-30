#!/usr/bin/env python3
"""Reject lossy circled-glyph substitutions even when local hashes are recomputed."""
from copy import deepcopy
import json
import unittest
import official_pdf_glyph_dispositions as glyph
from audit_moex_source_subjects import load_registry

class GlyphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof=json.loads((glyph.ROOT/glyph.PROOF_PATH).read_text());cls.report=json.loads((glyph.ROOT/'audit/official_mcq_pdf_comparison_20261025.json').read_text())
        cls.observed={r['id']:r for r in cls.report['rows']};cls.current={r['id']:r for name in ('105-2','107-2') for r in json.loads((glyph.ROOT/('cdn/question-shards/'+name+'.json')).read_text())['questions']}
        cls.registry=load_registry();cls.transport=json.loads((glyph.ROOT/'data/moex_answer_sources.v1.json').read_text())['records']
    def case(self):
        i=deepcopy(self.proof['rows'][0]);return i,deepcopy(self.observed[i['id']]),deepcopy(self.current[i['id']])
    def check(self,i,o,c):glyph.validate_item(i,o,c,self.registry,self.transport)
    def test_full_reviewed_scope(self):self.assertEqual(glyph.validated_ids(self.report),glyph.IDS)
    def test_wrong_source(self):
        i,o,c=self.case();i['pdf_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'question PDF mismatch'):self.check(i,o,c)
    def test_wrong_answer_pdf(self):
        i,o,c=self.case();i['answer_pdf_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'answer PDF mismatch'):self.check(i,o,c)
    def test_wrong_page(self):
        i,o,c=self.case();i['pdf_page_number']=1
        with self.assertRaisesRegex(ValueError,'wrong PDF page'):self.check(i,o,c)
    def test_false_human_approval(self):
        i,o,c=self.case();i['human_approval']=True
        with self.assertRaisesRegex(ValueError,'approval/classification'):self.check(i,o,c)
    def test_lossy_parser_must_not_overwrite_choice(self):
        i,o,c=self.case();c['opt_a']='115';i['current_full_row_sha256']=glyph.digest(c);i['current_core_lock_sha256']=glyph.row_hash(glyph.canonical_row(c,glyph.MCQ_FIELDS));i['official_field_transcription']['opt_a']='115'
        with self.assertRaisesRegex(ValueError,'unverified printed glyph'):self.check(i,o,c)
    def test_changed_raw_extraction(self):
        i,o,c=self.case();o['text_differences']['opt_a']['official_extraction']='135'
        with self.assertRaisesRegex(ValueError,'baseline drift'):self.check(i,o,c)
    def test_answer_change_even_with_new_hash(self):
        i,o,c=self.case();c['answer']='A';i['current_full_row_sha256']=glyph.digest(c);i['current_core_lock_sha256']=glyph.row_hash(glyph.canonical_row(c,glyph.MCQ_FIELDS))
        with self.assertRaisesRegex(ValueError,'grading drift'):self.check(i,o,c)

    def followup(self,ident):
        proof=json.loads((glyph.ROOT/glyph.NEW_PROOF_PATH).read_text());i=deepcopy(next(r for r in proof['rows'] if r['id']==ident))
        return i,deepcopy(self.observed[ident]),deepcopy(self.current[ident])
    def test_four_followup_records(self):
        for ident in glyph.FOLLOWUP:
            i,o,c=self.followup(ident);self.check(i,o,c)
    def test_option_without_raw_difference_remains_bound(self):
        i,o,c=self.followup('R-107-2-23');c['opt_c']='僅①③';i['current_full_row_sha256']=glyph.digest(c);i['current_core_lock_sha256']=glyph.row_hash(glyph.canonical_row(c,glyph.MCQ_FIELDS));i['official_field_transcription']['opt_c']=c['opt_c']
        with self.assertRaisesRegex(ValueError,'unverified printed glyph'):self.check(i,o,c)
    def test_revised_answer_M_required(self):
        i,o,c=self.followup('R-107-2-02');i['answer_source_url']=i['answer_source_url'].replace('t=M','t=S')
        with self.assertRaisesRegex(ValueError,'final answer PDF mismatch'):self.check(i,o,c)

if __name__=='__main__':unittest.main()

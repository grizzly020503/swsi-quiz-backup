#!/usr/bin/env python3
"""Bounded, fail-closed rendered-PDF review of R-105-1-38.

The official source has option glyphs visible on PDF page 4-4 that pdftotext
and PyMuPDF native text extraction omit. Do not auto-clear this old P0
comparison, edit source contents, or treat AI visual inspection as independent
human source approval.
"""
import copy
import json
import unicodedata
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'audit/official_r105138_pdf_visual_nochange_candidate_20261031.json'
Q=ROOT/'audit/official_428_review_priority_queue_20261031.json'
SHARD=ROOT/'cdn/question-shards/105-1.json'
ID='R-105-1-38'
FIELDS=('question','opt_a','opt_b','opt_c','opt_d','answer')

def validate(proof, queue, doc):
    assert proof['schema_version']==1
    assert proof['kind']=='RENDERED_OFFICIAL_SOURCE_PARSER_BLINDSPOT'
    assert proof['id']==ID
    assert proof['status']=='AI_VISUAL_VERIFIED_CANDIDATE_HOLD_HUMAN_APPROVAL'
    assert proof['baseline_review_reason']=='missing_field_detail'
    src=proof['source']
    assert src['pdf_filename']=='105030-107-0606.pdf'
    assert src['official_question_pdf_sha256']=='e219347d5b1bbe4ffa539bebf656ce196b72e569437e386fad078b37d7745687'
    assert src['pdf_page']==4 and src['printed_page']=='4-4'
    assert src['answer_filename']=='105030-107-0606-S.pdf'
    assert src['official_answer_pdf_sha256']=='4882b8a01680960d451261219240c061802b9d6173df3c27d8007d3a46930d4'
    assert src['answer_page']==1
    assert proof['normalized_unicode_nfkc_match'] is True
    assert proof['official_answer_unchanged'] is True
    assert proof['official_core_change_required'] is False
    assert proof['source_text_extractor_has_complete_options'] is False
    assert proof['existing_queue_priority']=='P0'
    assert proof['retained_in_428_queue'] is True
    assert proof['independent_human_approval'] is False
    assert proof['cleared_from_release_queue'] is False
    assert proof['production_modified'] is False
    assert proof['backup_modified'] is False
    assert queue['counts']['pending_total']==428
    assert queue['counts']['pending_mcq']==410
    assert len(queue['items'])==428
    item=next(r for r in queue['items'] if r['id']==ID)
    assert item['kind']=='MCQ' and item['priority']=='P0'
    assert item['reason']=='missing_field_detail'
    assert item['status']=='HOLD_HUMAN_REVIEW'
    assert item['source_pdf_sha256']==src['official_question_pdf_sha256']
    assert item['answer_pdf_sha256']==src['official_answer_pdf_sha256']
    assert item['cleared'] is False and item['human_approval'] is False
    assert len(doc['questions'])==200
    original=next(q for q in doc['questions'] if q['id']==ID)
    assert original['answer']=='D' and original['grading_mode']=='standard'
    assert original['accepted_answers'] is None
    for field in FIELDS:
        assert original[field]==proof['stored_question_and_options'][field]
        assert unicodedata.normalize('NFKC', original[field]) == unicodedata.normalize('NFKC', proof['official_page_visual_transcription'][field])
    return original

def main():
    proof=json.loads(P.read_text())
    queue=json.loads(Q.read_text())
    shard=json.loads(SHARD.read_text())
    validate(proof,queue,shard)
    for kind in ('invented-official-answer','false-human-approval','auto-clear','alter-quote','alter-shard','source-sha'):
        p,q,d=copy.deepcopy((proof,queue,shard))
        if kind=='invented-official-answer':p['official_page_visual_transcription']['answer']='A'
        elif kind=='false-human-approval':p['independent_human_approval']=True
        elif kind=='auto-clear':p['cleared_from_release_queue']=True
        elif kind=='alter-quote':p['official_page_visual_transcription']['opt_d']='wrong'
        elif kind=='alter-shard':next(x for x in d['questions'] if x['id']==ID)['opt_d']='tampered'
        elif kind=='source-sha':p['source']['official_question_pdf_sha256']='0'*64
        try:validate(p,q,d)
        except AssertionError:pass
        else:raise AssertionError('R-105-1-38 source visual gate accepted tamper '+kind)
    print('MOEX R-105-1-38 VISUAL SOURCE PROOF PASS: rendered PDF p4, native extraction omitted 4 choices; NFKC visual text matched stored A-D, official answer D unchanged; 6 tamper cases rejected; human review STILL HOLD')

if __name__=='__main__':
    main()

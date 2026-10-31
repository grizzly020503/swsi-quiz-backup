#!/usr/bin/env python3
"""Evidence-only 428 PDF review queue guard. Never certifies source correctness.

The full historical source extraction lives in held PR #447. This guard
checks this ranked triage's coverage/priority/candidate invariants and rejects
accidental claims of human approval or production promotion. It does NOT
lower original official-PDF release gates.
"""
import copy
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'audit/official_428_review_priority_queue_20261031.json'
CROSSWALK=ROOT/'audit/official_eight_p0_pdf_review_crosswalk_20261031.json'
MANIFEST=ROOT/'cdn/question-shards/manifest.json'
BASE_SHA='f1821813830aff4ce811583c142c4a29f35dddf9'
CANDIDATE_IDS={'DS-108-2-23','R-114-1-17','R-111-2-14',
               'R-111-2-15','R-111-2-17','R-111-2-18',
               'R-111-2-29','R-111-2-30'}
BLEED={'R-111-2-12','R-111-2-15','R-111-2-27'}
ENFORCED_COUNTS={'P0':29,'P1':219,'P2':180}

def validate(a,cross,manifest):
    assert a['schema_version']==1 and a['status']=='EVIDENCE_ONLY_NO_CLEAR'
    source=a['source']
    assert source['mcq_blob_sha']==BASE_SHA
    assert source['mcq_ref']==cross['source_baseline']['ref']
    assert source['essay_blob_sha']=='f20444f2cf79bbdf92666ad6e7133d7a6bbfb9f0'
    assert source['candidate_dataset_revision']==manifest['dataset_revision']
    assert source['latest_candidate_pr']==499
    assert source['baseline_release_comparison_is_stale'] is True
    assert source['candidate_is_draft'] is True
    assert manifest['total_questions']==4800 and manifest['shard_count']==24
    assert cross['unresolved_release_count_unchanged']==428
    assert cross['source_baseline']['legacy_evidence_dispositioned']==31
    assert cross['source_baseline']['mcq_held']==441
    assert cross['source_baseline']['essay_held']==18
    assert len(cross['targets'])==8
    assert {x['id'] for x in cross['targets']}==CANDIDATE_IDS
    assert all(x['counted_as_cleared'] is False and x['human_approval'] is False and x['release_approved'] is False for x in cross['targets'])
    assert all(v is False for v in a['guarantees'].values())
    c=a['counts']
    assert c['original_mcq_review']==441
    assert c['already_dispositioned_legacy_mcq']==31
    assert c['pending_mcq']==410 and c['pending_essay']==18
    assert c['pending_total']==428
    assert c['staged_in_pr499']==8 and c['staged_decremented']==0
    assert c['priorities_all']==ENFORCED_COUNTS
    assert c['mcq_priority']=={'P0':27,'P1':203,'P2':180}
    assert c['essay_parser_failures']==2
    assert c['multi_field_mcq']==26
    assert c['fieldless_review_mcq']==1
    assert c['suspected_case_bleed_mcq']==3
    assert set(a['notable']['neighbor_case_bleed'])==BLEED
    assert a['notable']['fieldless_reviews']==['R-105-1-38']
    ids=set(); mcq=[];essays=[]
    for row in a['items']:
        ident=row['id']
        assert ident not in ids;ids.add(ident)
        assert row['status']=='HOLD_HUMAN_REVIEW' and row['cleared'] is False
        assert row['human_approval'] is False
        assert row['priority'] in ENFORCED_COUNTS
        assert len(row['source_pdf_sha256'])==64
        assert row['source_url'].startswith('https://wwwq.moex.gov.tw/')
        if row['kind']=='MCQ':
            mcq.append(row)
            fields=row['displayed_fields']
            assert row['field_count']==len(fields)==len(row['excerpts'])
            assert len(fields)==len(set(fields))
            assert set(fields)<= {'question','opt_a','opt_b','opt_c','opt_d'}
            assert row['option_field_count']==sum(x.startswith('opt_') for x in fields)
            assert row['answer_differs'] is False
            expected='P0' if len(fields)==0 or len(fields)>=3 else 'P1' if row['option_field_count'] else 'P2'
            assert row['priority']==expected
            assert row['extraction_case_bleed_suspected']==(ident in BLEED)
            assert row['staged_in_pr499']==(ident in CANDIDATE_IDS)
        elif row['kind']=='ESSAY':
            essays.append(row)
            assert row['priority']==('P0' if row['reason']=='existing_parser_cannot_extract_exactly_two_essays' else 'P1')
        else:
            raise AssertionError('unexpected review record kind')
    assert len(ids)==428 and len(mcq)==410 and len(essays)==18
    assert Counter(x['priority'] for x in a['items'])==ENFORCED_COUNTS
    assert sum(x['staged_in_pr499'] for x in mcq)==8
    assert {x['id'] for x in mcq if x['staged_in_pr499']}==CANDIDATE_IDS
    assert len({x['id'] for x in mcq if x['field_count']>=3})==26
    assert all(not x.get('staged_in_pr499', False) for x in essays)
    assert all(x['human_approval'] is False and x['release_approved'] is False for x in cross['targets'])

def main():
    a=json.loads(PATH.read_text(encoding='utf-8'))
    cross=json.loads(CROSSWALK.read_text(encoding='utf-8'))
    from official_r105207_ds106134_candidate_smoke import digest
    newer=json.loads((ROOT/'audit/official_r105207_ds106134_source_candidate_20261031.json').read_text())
    raw=MANIFEST.read_bytes()
    assert digest(raw)==newer['new_manifest_sha256']
    manifest=json.loads(newer['old_manifest_raw'])
    validate(a,cross,manifest)
    tests=('auto-clear','fake-human','review-removed','fake-staged-count','manifest-drift','candidate-cleared')
    for kind in tests:
        aa,cc,mm=copy.deepcopy((a,cross,manifest))
        if kind=='auto-clear':aa['guarantees']['auto_clear']=True
        elif kind=='fake-human':aa['items'][0]['human_approval']=True
        elif kind=='review-removed':aa['items'].pop()
        elif kind=='fake-staged-count':aa['counts']['staged_decremented']=8
        elif kind=='manifest-drift':mm['dataset_revision']='0'*20
        else:cc['targets'][0]['counted_as_cleared']=True
        try:validate(aa,cc,mm)
        except AssertionError:pass
        else:raise AssertionError('accepted bad '+kind)
    print('OFFICIAL PDF REVIEW PRIORITY PASS: 428 held (410 MCQ + 18 essay); P0=29, P1=219, P2=180; 8 staged but 0 cleared; 6 tamper cases rejected. Source PDF rerun and human approval STILL REQUIRED.')

if __name__=='__main__':main()

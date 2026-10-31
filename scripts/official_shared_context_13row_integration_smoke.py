#!/usr/bin/env python3
"""Source-bound 13-row transition; reconstruct parent for the earlier genogram gate."""
import copy
import hashlib
import json
from pathlib import Path
from official_exam_readonly_guard import canonical_row, row_hash, MCQ_FIELDS
R=Path(__file__).resolve().parents[1]
P=R/'audit/official_shared_context_release_transition_20261031.json'
SOURCE_HASHES={'105090-107-0606.pdf':'6afea97bde8d58d00358d23bc5a31a0372a47f98d60b99ebc8f04495e3e9d836',
               '107110-107-0606.pdf':'65fc5955c9a6190db3a4792eb0889678d958e856e544ecaa8c22c86cf952468d'}
IDS={f'R-105-2-{n:02d}' for n in (12,13,14,15,16,20,21,22)}|{f'R-107-2-{n:02d}' for n in (4,5,6,7,8)}
ENRICH=('major','topic','keywords','exp_why','exp_others','exp_trap','exp_raw','mnemonic','extension','law','mistake')
def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def validate_transition(proof,rows,lock,manifest_raw):
    assert proof['schema_version']==1 and proof['base_main']=='905dbd8e93972f7d0c078d3ffbd07a2f7624328b'
    assert proof['reuses_candidate_head']=='afefff7a6c8d2d3e28e47c8f6d1437e53d61b754'
    assert proof['independent_human_approval'] is False and proof['whole_platform_release_approved'] is False
    assert proof['analyzer_configuration_changed'] is False and proof['backup_changed'] is False
    assert len(proof['sources'])==2 and {s['pdf']:s['sha256'] for s in proof['sources']}==SOURCE_HASHES
    assert all(s['fresh_download_verified'] and s['source_text_verified'] for s in proof['sources'])
    assert hashlib.sha256(manifest_raw).hexdigest()==proof['manifest_after_sha256']
    prior=proof['manifest_before_raw'].encode();assert hashlib.sha256(prior).hexdigest()==proof['manifest_before_sha256']
    ancestor=json.loads((R/'audit/official_genogram_core_transition_20261031.json').read_text())
    assert proof['manifest_before_sha256']==ancestor['manifest_after_sha256']
    before_m,after_m=json.loads(prior),json.loads(manifest_raw)
    assert after_m['dataset_revision']==proof['dataset_revision_after']
    assert after_m['total_questions']==4800 and len(after_m['shards'])==24
    assert after_m['total_uncompressed_bytes']==sum(x['bytes'] for x in after_m['shards'])
    changed_shards={x['file'] for x,y in zip(before_m['shards'],after_m['shards']) if x!=y}
    assert changed_shards=={'105-2.json','107-2.json'}
    index={r['id']:r for r in rows};assert len(index)==len(rows)==4800
    changes=proof['changed_rows'];assert len(changes)==13 and {c['id'] for c in changes}==IDS
    restored=copy.deepcopy(rows);restored_index={r['id']:r for r in restored};restored_lock=copy.deepcopy(lock)
    source_edits={c['id']:c for name in ('official_105_2_shared_context_20261028.json','official_107_2_shared_context_20261028.json') for c in json.loads((R/'audit'/name).read_text())['changes']}
    for c in changes:
        ident=c['id'];old,new=c['published_before'],c['published_after'];src=source_edits[ident]
        assert c['edits']==src['fields'] and set(c['edits'])<= {'question','opt_d'}
        assert index[ident]==new and old['id']==new['id']==ident
        assert c['before_core_lock_sha256']==src['old_lock_sha256']==row_hash(canonical_row(old,MCQ_FIELDS))
        assert c['after_core_lock_sha256']==src['new_lock_sha256']==row_hash(canonical_row(new,MCQ_FIELDS))==lock['mcq'][ident]
        expected=copy.deepcopy(old)
        for field,edit in c['edits'].items():
            assert old[field]==edit['before'];expected[field]=edit['after']
        for field in ENRICH:expected[field]=None
        expected['analysis_status']='review';assert expected==new
        assert all(old[k]==new[k] for k in ('answer','accepted_answers','grading_mode','source_url','source_exam_code'))
        db_before,db_after=c['database_before'],c['database_after'];expected_db=copy.deepcopy(db_before)
        assert all(db_before[k]==old[k] and db_after[k]==new[k] for k in MCQ_FIELDS+('answer','accepted_answers','grading_mode'))
        for field,edit in c['edits'].items():expected_db[field]=edit['after']
        for field in ENRICH:expected_db[field]=None
        expected_db.update(analysis_status='review',analysis_attempts=0,analysis_error=None,analysis_started_at=None,analysis_completed_at=None,analysis_last_attempt_at=None)
        assert expected_db==db_after
        restored_index[ident].clear();restored_index[ident].update(old);restored_lock['mcq'][ident]=c['before_core_lock_sha256']
    assert digest(sorted([r for r in rows if r['id'] not in IDS],key=lambda r:r['id']))==proof['unchanged_other_rows_sha256']
    assert digest(sorted([[r['id'],r['answer'],r['accepted_answers'],r['grading_mode']] for r in rows]))==proof['grading_tuples_sha256']
    assert digest({k:v for k,v in lock['mcq'].items() if k not in IDS})==proof['unchanged_other_mcq_locks_sha256']
    assert digest(lock['essays'])==proof['unchanged_essay_locks_sha256']
    return restored,restored_lock,prior

def main():
    proof=json.loads(P.read_text());raw=(R/'cdn/question-shards/manifest.json').read_bytes();m=json.loads(raw);rows=[]
    for meta in m['shards']:
        b=(R/'cdn/question-shards'/meta['file']).read_bytes()
        assert hashlib.sha256(b).hexdigest()==meta['sha256'] and len(b)==meta['bytes']
        payload=json.loads(b);assert len(payload['questions'])==meta['question_count'];rows+=payload['questions']
    lock=json.loads((R/'data/official_exam_readonly.lock.json').read_text())
    from official_two_row_p0_candidate_smoke import validate_overlay
    p0_proof=json.loads((R/'audit/official_two_row_p0_candidate_20261031.json').read_text())
    rows,lock,raw=validate_overlay(p0_proof,rows,lock,raw)
    validate_transition(proof,rows,lock,raw)
    for kind in ('target-wording','answer','source-url','unrelated-row','unrelated-lock','source-proof','old-lock','enrichment'):
        p,rs,lk=copy.deepcopy((proof,rows,lock));target=next(r for r in rs if r['id']=='R-105-2-14')
        if kind=='target-wording':target['question']+='tamper'
        elif kind=='answer':target['answer']='A'
        elif kind=='source-url':target['source_url']='https://example.invalid/'
        elif kind=='unrelated-row':next(r for r in rs if r['id'] not in IDS)['question']+='tamper'
        elif kind=='unrelated-lock':lk['mcq'][next(k for k in lk['mcq'] if k not in IDS)]='0'*64
        elif kind=='source-proof':p['sources'][0]['sha256']='0'*64
        elif kind=='old-lock':p['changed_rows'][0]['before_core_lock_sha256']='0'*64
        else:target['analysis_status']='ready'
        try:validate_transition(p,rs,lk,raw)
        except AssertionError:pass
        else:raise AssertionError('accepted unauthorized transition: '+kind)
    print('SHARED CONTEXT TRANSITION OK: 13 source-backed rows, 4787 full rows / 4800 grading tuples / 240 essays preserved; 8 negative cases rejected')
if __name__=='__main__':main()

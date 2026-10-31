#!/usr/bin/env python3
"""Fail-closed source-bound 111-2 shared-context candidate review.

Reverse six source-backed question changes before running released historical
guards. This is a candidate, not human approval and not a production write.
"""
import copy
import hashlib
import json
from pathlib import Path
from official_exam_readonly_guard import canonical_row, row_hash, MCQ_FIELDS

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/'audit/official_111_2_shared_context_six_20261031.json'
PAPER_SHA='14ba09396d90e0ccd8330821e7fa3fbb2f41a57ecfdb807e3bf18be924375153'
IDS={'R-111-2-14','R-111-2-15','R-111-2-17','R-111-2-18','R-111-2-29','R-111-2-30'}
ENRICH=('major','topic','keywords','exp_why','exp_others','exp_trap','exp_raw',
        'mnemonic','extension','law','mistake')

def digest(b):return hashlib.sha256(b).hexdigest()

def validate_overlay(p,rows,lock,manifest_raw):
    assert p['schema_version']==1 and p['scope']=='111_2_RESEARCH_SIX_SHARED_CONTEXT_CANDIDATE'
    assert p['base_main']=='d6a17bd85abfe4c3c71092c666132393cbe7d4a9'
    assert p['paper_sha256']==PAPER_SHA and p['paper_filename']=='111110-105-0406.pdf'
    assert p['official_answers_changed'] is False and p['backup_changed'] is False
    assert p['production_written'] is False and p['human_approval'] is False and p['release_approved'] is False
    assert digest(manifest_raw)==p['after_manifest_sha256']
    orig_manifest_raw=p['baseline_manifest_raw'].encode()
    assert digest(orig_manifest_raw)==p['baseline_manifest_sha256']
    after_manifest=json.loads(manifest_raw);before_manifest=json.loads(orig_manifest_raw)
    assert after_manifest['dataset_revision']==p['dataset_revision_after']
    assert before_manifest['dataset_revision']==p['dataset_revision_before']
    assert len(after_manifest['shards'])==len(before_manifest['shards'])==24
    assert after_manifest['total_questions']==before_manifest['total_questions']==4800
    assert after_manifest['total_uncompressed_bytes']==sum(x['bytes'] for x in after_manifest['shards'])
    before_info={x['file']:x for x in before_manifest['shards']}
    after_info={x['file']:x for x in after_manifest['shards']}
    assert {name for name in after_info if before_info[name]!=after_info[name]}=={'111-2.json'}
    assert len(rows)==len({r['id'] for r in rows})==4800
    assert len(lock['mcq'])==4800 and len(lock['essays'])==240
    assert len(p['changes'])==6 and {x['id'] for x in p['changes']}==IDS
    assert len(p['scenarios'])==3
    assert {s['first_id'] for s in p['scenarios']}=={'R-111-2-13','R-111-2-16','R-111-2-28'}
    assert {id for s in p['scenarios'] for id in s['target_ids']}==IDS

    index={r['id']:r for r in rows}
    # Child PR #501 has exactly three verified source-core changes atop
    # this parent #499 revision. The memory rows were already reversed to
    # #499, but the on-disk files retain #501 bytes. Verify BOTH hashes and
    # the three exact before/after rows instead of skipping raw validation.
    child=json.loads((ROOT/'audit/official_next_three_p0_source_candidate_20261031.json').read_text())
    child_rows={c['id']:c for c in child['changed_rows']}
    assert len(child_rows)==3
    child_shards=child['shards']
    for shard in after_manifest['shards']:
        data=(ROOT/'cdn/question-shards'/shard['file']).read_bytes()
        candidate=child_shards.get('cdn/question-shards/'+shard['file'])
        if candidate is not None:
            assert candidate['old_sha256']==shard['sha256'] and candidate['old_bytes']==shard['bytes']
            assert len(data)==candidate['new_bytes'] and digest(data)==candidate['new_sha256']
        else:
            assert len(data)==shard['bytes'] and digest(data)==shard['sha256']
        for r in json.loads(data)['questions']:
            if r['id'] in child_rows:
                assert r==child_rows[r['id']]['published_after']
                assert index[r['id']]==child_rows[r['id']]['published_before']
            else:
                assert r==index[r['id']]

    previous=copy.deepcopy(rows);previous_index={r['id']:r for r in previous}
    previous_lock=copy.deepcopy(lock)
    for scenario in p['scenarios']:
        lead=index[scenario['first_id']]
        assert lead['question']==scenario['source_question']
        assert scenario['source_question'].startswith(scenario['context'])
        assert scenario['printed_page'] in ('4-2','4-3')
        assert len(scenario['target_ids'])==2
    for fix in p['changes']:
        ident=fix['id'];old=fix['published_before'];new=fix['published_after']
        scenario=next(s for s in p['scenarios'] if ident in s['target_ids'])
        assert fix['lead_id']==scenario['first_id'] and fix['scenario']==scenario['context']
        assert fix['source_pdf_sha256']==PAPER_SHA and fix['printed_page']==scenario['printed_page']
        assert fix['source_url']=='https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?t=Q&code=111110&c=105&s=0406&q=1'
        assert old['id']==new['id']==ident and index[ident]==new
        assert row_hash(canonical_row(old,MCQ_FIELDS))==fix['before_core_lock_sha256']
        assert row_hash(canonical_row(new,MCQ_FIELDS))==fix['after_core_lock_sha256']==lock['mcq'][ident]
        assert new['question']=='情況：'+scenario['context']+'\n\n'+old['question']
        assert all(old[k]==new[k] for k in MCQ_FIELDS if k!='question')
        assert all(old[k]==new[k] for k in ('answer','accepted_answers','grading_mode','source_url','source_exam_code'))
        assert new['analysis_status']=='review'
        assert all(new[k] is None for k in ENRICH)
        expected=copy.deepcopy(old);expected['question']=new['question']
        for k in ENRICH:expected[k]=None
        expected['analysis_status']='review'
        assert expected==new
        previous_index[ident].clear();previous_index[ident].update(old)
        previous_lock['mcq'][ident]=fix['before_core_lock_sha256']

    shard=json.loads((ROOT/'cdn/question-shards/111-2.json').read_text())
    for q in shard['questions']:
        if q['id'] in IDS:
            old_row=next(x['published_before'] for x in p['changes'] if x['id']==q['id'])
            q.clear();q.update(old_row)
    old_bytes=(json.dumps(shard,ensure_ascii=False,separators=(',',':'))+'\n').encode()
    assert digest(old_bytes)==p['baseline_shard_sha256']==before_info['111-2.json']['sha256']
    current_bytes=(ROOT/'cdn/question-shards/111-2.json').read_bytes()
    assert digest(current_bytes)==p['after_shard_sha256']==after_info['111-2.json']['sha256']
    assert all(a['answer']==b['answer'] and a['accepted_answers']==b['accepted_answers']
               and a['grading_mode']==b['grading_mode'] for a,b in zip(rows,previous))
    assert previous_lock['essays']==lock['essays']
    return previous,previous_lock,orig_manifest_raw

def main():
    p=json.loads(FILE.read_text())
    raw=(ROOT/'cdn/question-shards/manifest.json').read_bytes()
    m=json.loads(raw);all_rows=[]
    for info in m['shards']:
        b=(ROOT/'cdn/question-shards'/info['file']).read_bytes()
        assert digest(b)==info['sha256'] and len(b)==info['bytes']
        all_rows.extend(json.loads(b)['questions'])
    lock=json.loads((ROOT/'data/official_exam_readonly.lock.json').read_text())
    from official_combined_nineteen_integrity_smoke import reverse_overlay as reverse_new_eight
    all_rows,lock,raw=reverse_new_eight(all_rows,lock,raw)
    from official_next_three_p0_source_smoke import validate_overlay as reverse_three
    three_proof=json.loads((ROOT/'audit/official_next_three_p0_source_candidate_20261031.json').read_text())
    all_rows,lock,raw=reverse_three(three_proof,all_rows,lock,raw)
    validate_overlay(p,all_rows,lock,raw)
    for kind in ('target','answer','other-row','source-sha','lock','context','manifest'):
        probe,rs,lk=copy.deepcopy((p,all_rows,lock))
        changed=next(r for r in rs if r['id']=='R-111-2-14')
        if kind=='target':changed['question']+='tamper'
        elif kind=='answer':changed['answer']='D'
        elif kind=='other-row':next(r for r in rs if r['id'] not in IDS)['question']+='tamper'
        elif kind=='source-sha':probe['paper_sha256']='0'*64
        elif kind=='lock':lk['mcq'][changed['id']]='0'*64
        elif kind=='context':probe['scenarios'][0]['context']+='fake'
        else:probe['after_manifest_sha256']='0'*64
        try:validate_overlay(probe,rs,lk,raw)
        except AssertionError:pass
        else:raise AssertionError('accepted unauthorized '+kind)
    print('MOEX 111-2 SHARED CONTEXT QA PASS: 6 controlled rows, 4794 others unchanged, 4800 grading tuples, 240 essay locks, 7 negative cases rejected; release HOLD')

if __name__=='__main__':main()

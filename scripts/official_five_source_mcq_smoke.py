#!/usr/bin/env python3
"""Fail-closed five-MOEX-source candidate. No network, DB writes or approvals.

Reconstruct original main for preexisting 13-case and genogram release gates.
Human signoff and production promotion remain separate, mandatory steps.
"""
import copy
import hashlib
import json
from pathlib import Path
from official_exam_readonly_guard import canonical_row, row_hash, MCQ_FIELDS

ROOT=Path(__file__).resolve().parents[1]
PROOF_PATH=ROOT/'audit/official_five_source_corrections_20261031.json'
IDS={'DS-104-1-30','SW-106-1-29','R-106-1-30','SW-108-2-27','DS-108-2-12'}
SHARDS={'104-1.json','106-1.json','108-2.json'}
ENRICH=('major','topic','keywords','exp_why','exp_others','exp_trap',
        'exp_raw','mnemonic','extension','law','mistake')
GRADING=('answer','accepted_answers','grading_mode')
IDENTITY=('id','subject','year','round','qno','source_exam_code','source_url')
SOURCE_PAGES={'DS-104-1-30':3,'SW-106-1-29':3,'R-106-1-30':4,'SW-108-2-27':3,'DS-108-2-12':2}
SOURCE_HASHES={
 'DS-104-1-30':('979233d2cb316565c4eed2b5c5289e89e5d21c0bb2b2076a7443887cd24ffadc','286717203ccd9e7c608ef257bafb942b68538ff949f10a95bbb76aa4b0e260dd','B'),
 'SW-106-1-29':('86a2d3ef50bfbbb3df71cda6fd3215ce39def303e43b22bf9cfaa48e5ecb4951','cfee626fcfca9131e6341b7376b28449f0e132d46577408654893df97e734a07','B'),
 'R-106-1-30':('054c1bc1d7e673a811f1c786bca8e151d506eb99158f67f938f1d490436e7f11','551850b0a48b2f8aeb652953050eb1d927b54404c13cabc4e9e6dcd61d126a6a','C'),
 'SW-108-2-27':('89543185cee74523e23139c31e41440c606919699cb8f2cf0de2285ebc1edfbe','a716564b2ffa64e2c48aa9b174a01afffee8509d033e539cfbc5e37bc6f8d3aa','C'),
 'DS-108-2-12':('78e9473d144f9165622f02ac3e5a004658b0ca7dd516c436f56cfdf4042b3e9b','aa489636b5c0c62a4262b1fe51739e0de0d11bbf7d297d95f2f5220d3c474e79','A')
}

def sha(raw):return hashlib.sha256(raw).hexdigest()

def validate_overlay(proof, rows, lock, manifest_raw):
    assert proof['schema_version']==1 and proof['scope']=='FIVE_PINNED_OFFICIAL_MOEX_SOURCE_CORRECTIONS'
    assert proof['base_main']=='d6a17bd85abfe4c3c71092c666132393cbe7d4a9'
    assert proof['human_approval'] is False and proof['release_approved'] is False
    assert proof['backup_changed'] is False and proof['production_written'] is False
    assert proof['official_answer_change'] is False and proof['grading_changed'] is False
    assert proof['other_rows_changed'] is False and proof['source_question_count']==5
    before_raw=proof['previous_manifest_raw'].encode('utf-8')
    assert sha(before_raw)==proof['previous_manifest_sha256']
    assert sha(manifest_raw)==proof['new_manifest_sha256']
    before_m,after_m=json.loads(before_raw),json.loads(manifest_raw)
    assert before_m['dataset_revision']==proof['before_revision']
    assert after_m['dataset_revision']==proof['after_revision']
    assert len(before_m['shards'])==len(after_m['shards'])==24
    assert before_m['total_questions']==after_m['total_questions']==4800
    assert after_m['total_uncompressed_bytes']==sum(e['bytes'] for e in after_m['shards'])
    pre={x['file']:x for x in before_m['shards']}
    post={x['file']:x for x in after_m['shards']}
    assert set(pre)==set(post)
    assert {name for name in pre if pre[name]!=post[name]}==SHARDS
    assert len(rows)==len({r['id'] for r in rows})==4800
    assert len(lock['mcq'])==4800 and len(lock['essays'])==240
    assert len(proof['rows'])==5 and {x['id'] for x in proof['rows']}==IDS
    index={r['id']:r for r in rows}
    source_map={x['id']:x for x in proof['rows']}
    old_rows=copy.deepcopy(rows);old_index={r['id']:r for r in old_rows}
    old_lock=copy.deepcopy(lock)
    for item in proof['rows']:
        ident=item['id'];before=item['published_before'];after=item['published_after']
        official_q,official_a,official_grade=SOURCE_HASHES[ident]
        assert item['source']['question_pdf_sha256']==official_q
        assert item['source']['official_answer_pdf_sha256']==official_a
        assert item['official_answer']==before['answer']==after['answer']==official_grade
        assert item['source']['question_source_url']==before['source_url']
        assert item['source']['pdf_page_number']==SOURCE_PAGES[ident]
        if ident=='SW-106-1-29':
            assert item['source']['official_correction_pdf_sha256']=='248fe70831bdaa1673f9e01844c03eaf6384203a51009d4458b39a1e7d54fe7f'
            assert item['source']['correction_changed_question_numbers']==[36]
            assert item['source']['target_answer_unchanged_by_correction'] is True
        assert item['file'] in SHARDS and item['file']==('104-1.json' if ident.startswith('DS-104-') else '106-1.json' if '106-1' in ident else '108-2.json')
        assert before['id']==after['id']==ident and index[ident]==after
        assert row_hash(canonical_row(before,MCQ_FIELDS))==item['before_core_lock_sha256']
        assert row_hash(canonical_row(after,MCQ_FIELDS))==item['after_core_lock_sha256']==lock['mcq'][ident]
        assert all(before[k]==after[k] for k in GRADING+IDENTITY)
        assert after['analysis_status']=='review' and all(after[k] is None for k in ENRICH)
        expected=copy.deepcopy(before)
        assert set(item['edits'])<=set(('question','opt_a','opt_b','opt_c','opt_d'))
        for key,value in item['edits'].items():expected[key]=value
        for key in ENRICH:expected[key]=None
        expected['analysis_status']='review'
        assert expected==after
        old_index[ident].clear();old_index[ident].update(before)
        old_lock['mcq'][ident]=item['before_core_lock_sha256']
    for ent in after_m['shards']:
        from official_ten_source_integration_smoke import projected_parent_shard_bytes
        raw=projected_parent_shard_bytes(ent['file'])
        assert sha(raw)==ent['sha256'] and len(raw)==ent['bytes']
        original=json.loads(raw)
        assert len(original['questions'])==ent['question_count']==200
        for row in original['questions']:
            assert row['id'] in index and row==index[row['id']]
        if ent['file'] in SHARDS:
            for row in original['questions']:
                if row['id'] in IDS:
                    before=source_map[row['id']]['published_before']
                    row.clear();row.update(before)
            prev_bytes=(json.dumps(original,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
            assert sha(prev_bytes)==proof['old_shards'][ent['file']]['sha256']==pre[ent['file']]['sha256']
            assert len(prev_bytes)==proof['old_shards'][ent['file']]['bytes']==pre[ent['file']]['bytes']
            assert sha(raw)==proof['new_shards'][ent['file']]['sha256']
        else:
            assert pre[ent['file']]==ent
    assert all(all(a[k]==b[k] for k in GRADING) for a,b in zip(rows,old_rows))
    assert old_lock['essays']==lock['essays']
    return old_rows,old_lock,before_raw

def main():
    proof=json.loads(PROOF_PATH.read_text())
    raw=(ROOT/'cdn/question-shards/manifest.json').read_bytes()
    manifest=json.loads(raw);rows=[]
    for entry in manifest['shards']:
        b=(ROOT/'cdn/question-shards'/entry['file']).read_bytes()
        assert len(b)==entry['bytes'] and sha(b)==entry['sha256']
        rows+=json.loads(b)['questions']
    locks=json.loads((ROOT/'data/official_exam_readonly.lock.json').read_text())
    from official_ten_source_integration_smoke import reverse_current
    rows,locks,raw=reverse_current(rows,locks,raw)
    validate_overlay(proof,rows,locks,raw)
    for kind in ('target-question','wrong-answer','other-row','bad-lock','bad-source','bad-approval','bad-manifest','bad-enrichment','bad-source-page','bad-correction-source'):
        p,r,l=copy.deepcopy((proof,rows,locks))
        t=next(v for v in r if v['id']=='SW-106-1-29')
        if kind=='target-question':t['opt_b']+='fabricated'
        elif kind=='wrong-answer':t['answer']='A'
        elif kind=='other-row':next(v for v in r if v['id'] not in IDS)['question']+='fabricated'
        elif kind=='bad-lock':l['mcq'][t['id']]='0'*64
        elif kind=='bad-source':p['rows'][0]['source']['question_pdf_sha256']='0'*64
        elif kind=='bad-approval':p['human_approval']=True
        elif kind=='bad-manifest':p['new_manifest_sha256']='0'*64
        elif kind=='bad-source-page':p['rows'][0]['source']['pdf_page_number']=1
        elif kind=='bad-correction-source':next(x for x in p['rows'] if x['id']=='SW-106-1-29')['source']['official_correction_pdf_sha256']='0'*64
        else:t['analysis_status']='ready'
        try:validate_overlay(p,r,l,raw)
        except AssertionError:pass
        else:raise AssertionError('Incorrect official-core candidate accepted: '+kind)
    print('OFFICIAL NEXT-FIVE SOURCE QA PASS: 5 original MOEX Q+answer PDFs, 4795 other full rows unchanged, 4800 grading tuples / 240 essay locks unchanged, 10 negatives rejected; NO HUMAN APPROVAL, NO DEPLOY')

if __name__=='__main__':main()

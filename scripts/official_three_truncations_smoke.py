#!/usr/bin/env python3
"""Verify 3 source-SHA-bound MOEX original exam corrections. NO-GO / offline."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT/'audit/official_three_truncations_20261031.json'
IDS = {'SP108-2-09','DS-109-2-26','DS-108-2-38'}
SOURCES = {
 'SP108-2-09':('956025f3383d3d721ae428e3dd8a3a97b0abed4026c5ed71bafc6e8a1171ff03',2,'4-2'),
 'DS-109-2-26':('0351cc6a62bfc1f922ed58cea35cde6b20dde02db4d9768379273ba6baf9798e',4,'4-4'),
 'DS-108-2-38':('78e9473d144f9165622f02ac3e5a004658b0ca7dd516c436f56cfdf4042b3e9b',4,'4-4'),
}
ENRICH=('major','topic','keywords','exp_why','exp_others','exp_trap','exp_raw','mnemonic','extension','law','mistake')
GRADING=('answer','accepted_answers','grading_mode')
IDENTITY=('id','subject','year','round','qno','source_url','source_exam_code')

def digest(blob):
    return hashlib.sha256(blob).hexdigest()

def validate_overlay(proof, rows, lock, manifest_raw):
    assert proof['schema_version']==1
    assert proof['scope']=='THREE_SOURCE_BACKED_P0_TRUNCATIONS_NO_GO'
    assert proof['base_main']=='d6a17bd85abfe4c3c71092c666132393cbe7d4a9'
    assert proof['production_written'] is False and proof['backup_changed'] is False
    assert proof['human_approval'] is False and proof['release_approved'] is False
    assert proof['grading_changed'] is False
    assert len(proof['records'])==3
    assert {r['id'] for r in proof['records']}==IDS
    assert digest(manifest_raw)==proof['after_manifest_sha256']
    older=proof['before_manifest_raw'].encode('utf-8')
    assert digest(older)==proof['before_manifest_sha256']
    newer_m=json.loads(manifest_raw);older_m=json.loads(older)
    assert newer_m['dataset_revision']==proof['after_revision']
    assert older_m['dataset_revision']==proof['before_revision']
    assert newer_m['total_questions']==older_m['total_questions']==4800
    assert len(newer_m['shards'])==len(older_m['shards'])==24
    assert newer_m['total_uncompressed_bytes']==sum(r['bytes'] for r in newer_m['shards'])
    old_m={r['file']:r for r in older_m['shards']}
    new_m={r['file']:r for r in newer_m['shards']}
    assert set(old_m)==set(new_m)
    assert {name for name in old_m if old_m[name]!=new_m[name]}=={'108-2.json','109-2.json'}
    assert len(rows)==len({r['id'] for r in rows})==4800
    assert len(lock['mcq'])==4800 and len(lock['essays'])==240
    index={r['id']:r for r in rows}
    # All 4,800 official-core locks must match the exact current row,
    # not only the three repaired rows. Detect unrelated lock tampering.
    assert all(row_hash(canonical_row(r,MCQ_FIELDS))==lock['mcq'][r['id']] for r in rows)
    for unit in newer_m['shards']:
        raw=(ROOT/'cdn/question-shards'/unit['file']).read_bytes()
        assert digest(raw)==unit['sha256'] and len(raw)==unit['bytes']
        payload=json.loads(raw)
        assert len(payload['questions'])==unit['question_count']
        for item in payload['questions']:
            assert item['id'] in index and item==index[item['id']]
    restored=copy.deepcopy(rows);reverse={r['id']:r for r in restored}
    restored_lock=copy.deepcopy(lock)
    for source in proof['records']:
        ident=source['id']
        pre=source['published_before'];post=source['published_after']
        assert index[ident]==post and pre['id']==post['id']==ident
        assert source['source']['pdf_sha256']==SOURCES[ident][0]
        assert source['source']['pdf_page_number']==SOURCES[ident][1]
        assert source['source']['printed_page']==SOURCES[ident][2]
        assert source['source']['url']==pre['source_url']==post['source_url']
        assert row_hash(canonical_row(pre,MCQ_FIELDS))==source['before_core_sha256']
        assert row_hash(canonical_row(post,MCQ_FIELDS))==source['after_core_sha256']==lock['mcq'][ident]
        assert all(pre[k]==post[k] for k in IDENTITY+GRADING)
        assert post['analysis_status']=='review' and all(post[k] is None for k in ENRICH)
        assert set(source['changed_fields'])==({'question','opt_c'} if ident=='SP108-2-09' else {'question'})
        expected=copy.deepcopy(pre)
        for k in source['changed_fields']:
            assert k in ('question','opt_c') and pre[k]!=post[k]
            expected[k]=post[k]
        for k in ENRICH:
            expected[k]=None
        expected['analysis_status']='review'
        assert expected==post
        if ident=='SP108-2-09':
            assert '敘述何者錯誤' in post['question']
            assert post['opt_c'].endswith('2012 年1 月1 日起施行')
        elif ident=='DS-109-2-26':
            assert '以便充分蒐集資料讓討論內容有代表性' in post['question']
            assert '在所有題目間跳動發表意見' in post['question']
            assert post['answer']=='D' and post['accepted_answers']==['A','D']
        else:
            assert '強調社區組織的「志工化」' in post['question']
        reverse[ident].clear();reverse[ident].update(pre)
        restored_lock['mcq'][ident]=source['before_core_sha256']
    for filename in ('108-2.json','109-2.json'):
        raw=(ROOT/'cdn/question-shards'/filename).read_bytes()
        assert digest(raw)==proof['after_shards'][filename]['sha256']
        assert len(raw)==proof['after_shards'][filename]['bytes']
        payload=json.loads(raw)
        for row in payload['questions']:
            ident=row['id']
            if ident in IDS:
                old=next(x['published_before'] for x in proof['records'] if x['id']==ident)
                row.clear();row.update(old)
        reconstructed=(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
        assert digest(reconstructed)==proof['before_shards'][filename]['sha256']==old_m[filename]['sha256']
        assert len(reconstructed)==proof['before_shards'][filename]['bytes']==old_m[filename]['bytes']
    assert all(all(a[k]==b[k] for k in GRADING) for a,b in zip(rows,restored))
    assert restored_lock['essays']==lock['essays']
    return restored,restored_lock,older

def main():
    proof=json.loads(PROOF.read_text())
    raw=(ROOT/'cdn/question-shards/manifest.json').read_bytes()
    manifest=json.loads(raw)
    rows=[]
    for unit in manifest['shards']:
        blob=(ROOT/'cdn/question-shards'/unit['file']).read_bytes()
        assert digest(blob)==unit['sha256'] and len(blob)==unit['bytes']
        rows+=json.loads(blob)['questions']
    lock=json.loads((ROOT/'data/official_exam_readonly.lock.json').read_text())
    validate_overlay(proof,rows,lock,raw)
    for kind in ('question','option','answer','special-credit','unrelated-row','source-hash','other-lock','manifest'):
        p,rs,lk=copy.deepcopy((proof,rows,lock))
        source=next(r for r in rs if r['id']=='SP108-2-09')
        if kind=='question': source['question']+='tamper'
        elif kind=='option': source['opt_c']+='tamper'
        elif kind=='answer': source['answer']='A'
        elif kind=='special-credit': next(r for r in rs if r['id']=='DS-109-2-26')['accepted_answers']=['D']
        elif kind=='unrelated-row': next(r for r in rs if r['id'] not in IDS)['question']+='tamper'
        elif kind=='source-hash': p['records'][0]['source']['pdf_sha256']='0'*64
        elif kind=='other-lock': lk['mcq'][next(k for k in lk['mcq'] if k not in IDS)]='0'*64
        else: p['after_manifest_sha256']='0'*64
        try:validate_overlay(p,rs,lk,raw)
        except AssertionError:pass
        else:raise AssertionError('unauthorized correction accepted: '+kind)
    print('MOEX 3 TRUNCATIONS QA PASS: source SHA and 3 exact row overlays; 4797 unchanged; 4800 grading tuples, 240 essay locks preserved; 8 negative tamper cases rejected; release HOLD')

if __name__=='__main__':main()

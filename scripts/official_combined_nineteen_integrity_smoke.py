#!/usr/bin/env python3
"""Source-locked 19-row candidate: reverse the eight new rows onto exact #503.
Never grants human approval, clears 428 reviews, writes production or deploys.
"""
import copy
import hashlib
import json
from pathlib import Path
from official_exam_readonly_guard import canonical_row, row_hash, MCQ_FIELDS

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / 'audit/official_combined_nineteen_candidate_20261031.json'
SOURCE_THREE = ROOT / 'audit/official_three_truncations_20261031.json'
SOURCE_FIVE = ROOT / 'audit/official_five_source_corrections_20261031.json'
FIELDS = ('major','topic','keywords','exp_why','exp_others','exp_trap',
          'exp_raw','mnemonic','extension','law','mistake')
SOURCE_SHA = {
    'SP108-2-09':'956025f3383d3d721ae428e3dd8a3a97b0abed4026c5ed71bafc6e8a1171ff03',
    'DS-109-2-26':'0351cc6a62bfc1f922ed58cea35cde6b20dde02db4d9768379273ba6baf9798e',
    'DS-108-2-38':'78e9473d144f9165622f02ac3e5a004658b0ca7dd516c436f56cfdf4042b3e9b',
    'DS-104-1-30':'979233d2cb316565c4eed2b5c5289e89e5d21c0bb2b2076a7443887cd24ffadc',
    'SW-106-1-29':'86a2d3ef50bfbbb3df71cda6fd3215ce39def303e43b22bf9cfaa48e5ecb4951',
    'R-106-1-30':'054c1bc1d7e673a811f1c786bca8e151d506eb99158f67f938f1d490436e7f11',
    'SW-108-2-27':'89543185cee74523e23139c31e41440c606919699cb8f2cf0de2285ebc1edfbe',
    'DS-108-2-12':'78e9473d144f9165622f02ac3e5a004658b0ca7dd516c436f56cfdf4042b3e9b',
}
def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def reverse_overlay(rows, lock, manifest_raw, proof=None):
    p = proof or json.loads(PROOF.read_text())
    assert p['schema_version'] == 1 and p['status'] == 'DRAFT_NO_GO'
    assert p['parent_sha'] == 'ad9d0b711170dfdcb0a72496cf4b8f8da6670a5e'
    assert p['source_prs'] == [503,500,502] and p['distinct_repairs'] == 19
    assert (p['mcq_count'],p['essay_count'],p['unresolved_pdf_reviews']) == (4800,240,428)
    assert all(p[k] is False for k in ('independent_human_approval','production_written','backup_modified','release_approved'))
    original_raw = p['parent_manifest_raw'].encode('utf-8')
    assert sha(original_raw) == p['parent_manifest_sha256']
    assert sha(manifest_raw) == p['new_manifest_sha256']
    current = json.loads(manifest_raw)
    parent = json.loads(original_raw)
    assert current['dataset_revision'] == p['new_revision']
    assert parent['dataset_revision'] == p['parent_revision']
    assert len(parent['shards']) == len(current['shards']) == 24
    assert parent['total_questions'] == current['total_questions'] == 4800
    assert current['total_uncompressed_bytes'] == sum(x['bytes'] for x in current['shards'])
    assert len(rows) == len({r['id'] for r in rows}) == len(lock['mcq']) == 4800
    assert len(lock['essays']) == 240

    three = json.loads(SOURCE_THREE.read_text())
    five = json.loads(SOURCE_FIVE.read_text())
    assert three['human_approval'] is False and five['human_approval'] is False
    assert three['production_written'] is False and five['production_written'] is False
    records = three['records'] + five['rows']
    assert len(records) == len(p['changed_rows']) == 8
    assert {r['id'] for r in records} == set(SOURCE_SHA)
    proof_by_id = {r['id']:r for r in p['changed_rows']}
    index = {r['id']:r for r in rows}
    restored = copy.deepcopy(rows)
    restored_index = {r['id']:r for r in restored}
    old_lock = copy.deepcopy(lock)
    for item in records:
        ident = item['id']
        before, after = item['published_before'], item['published_after']
        old_hash = item.get('before_core_lock_sha256', item.get('before_core_sha256'))
        new_hash = item.get('after_core_lock_sha256', item.get('after_core_sha256'))
        pdf_hash = item['source'].get('question_pdf_sha256', item['source'].get('pdf_sha256'))
        assert pdf_hash == SOURCE_SHA[ident]
        assert index[ident] == after
        assert row_hash(canonical_row(before, MCQ_FIELDS)) == old_hash
        assert row_hash(canonical_row(after, MCQ_FIELDS)) == new_hash == lock['mcq'][ident]
        assert proof_by_id[ident]['old_core_sha256'] == old_hash
        assert proof_by_id[ident]['new_core_sha256'] == new_hash
        year, round_number = before['year'], '1' if before['round']=='第一次' else '2'
        assert proof_by_id[ident]['file'] == f'{year}-{round_number}.json'
        for field in ('id','year','round','qno','answer','accepted_answers','grading_mode','source_url','source_exam_code'):
            assert before[field] == after[field]
        assert after['analysis_status'] == 'review'
        assert all(after[k] is None for k in FIELDS)
        restored_index[ident].clear()
        restored_index[ident].update(before)
        old_lock['mcq'][ident] = old_hash

    pm = {x['file']:x for x in parent['shards']}
    cm = {x['file']:x for x in current['shards']}
    assert set(pm) == set(cm)
    changed_shards = {s for s in pm if pm[s] != cm[s]}
    assert changed_shards == set(p['old_shards']) == set(p['new_shards'])
    assert changed_shards == {'104-1.json','106-1.json','108-2.json','109-2.json'}
    for name, meta in cm.items():
        raw = (ROOT/'cdn/question-shards'/name).read_bytes()
        assert sha(raw) == meta['sha256'] and len(raw) == meta['bytes']
        doc = json.loads(raw)
        assert len(doc['questions']) == meta['question_count'] == 200
        assert all(index[r['id']] == r for r in doc['questions'])
        if name not in changed_shards:
            assert pm[name] == meta
            continue
        assert p['new_shards'][name] == {'sha256':sha(raw),'bytes':len(raw)}
        for q in doc['questions']:
            if q['id'] in SOURCE_SHA:
                old = next(r['published_before'] for r in records if r['id']==q['id'])
                q.clear()
                q.update(old)
        previous = (json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
        assert p['old_shards'][name] == {'sha256':sha(previous),'bytes':len(previous)}
        assert sha(previous) == pm[name]['sha256'] and len(previous) == pm[name]['bytes']
    lock_bytes = (json.dumps(lock,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    old_lock_bytes = (json.dumps(old_lock,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    assert sha(lock_bytes) == p['new_lock_sha256']
    assert sha(old_lock_bytes) == p['parent_lock_sha256']
    assert old_lock['essays'] == lock['essays']
    assert all(all(a[k] == b[k] for k in ('answer','accepted_answers','grading_mode')) for a,b in zip(rows,restored))
    return restored, old_lock, original_raw

def main():
    raw = (ROOT/'cdn/question-shards/manifest.json').read_bytes()
    rows = [q for shard in json.loads(raw)['shards']
            for q in json.loads((ROOT/'cdn/question-shards'/shard['file']).read_bytes())['questions']]
    lock = json.loads((ROOT/'data/official_exam_readonly.lock.json').read_text())
    reverse_overlay(rows,lock,raw)
    proof = json.loads(PROOF.read_text())
    for kind in ('target','grade','special-credit','other-row','lock','manifest','approval'):
        p,rs,lk = copy.deepcopy((proof,rows,lock))
        target = next(r for r in rs if r['id']=='SW-106-1-29')
        if kind == 'target': target['opt_b'] += 'tamper'
        elif kind == 'grade': target['answer'] = 'A'
        elif kind == 'special-credit': next(r for r in rs if r['id']=='DS-109-2-26')['accepted_answers']=['D']
        elif kind == 'other-row': next(r for r in rs if r['id']=='R-105-2-12')['question'] += 'tamper'
        elif kind == 'lock': lk['mcq'][target['id']] = '0'*64
        elif kind == 'manifest': p['new_manifest_sha256'] = '0'*64
        else: p['independent_human_approval'] = True
        try: reverse_overlay(rs,lk,raw,p)
        except AssertionError: pass
        else: raise AssertionError('unauthorized change accepted: '+kind)
    print('COMBINED 19-ROW QA PASS: source-locked eight-row overlay reconstructed exact #503 parent; 4800 grading / 240 essay locks unchanged; 7 tamper cases rejected; release HOLD')
if __name__ == '__main__':
    main()

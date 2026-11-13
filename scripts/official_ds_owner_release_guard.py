#!/usr/bin/env python3
"""Verify three approved source repairs and replay the exact previous release."""
import argparse
import copy
import json
import tempfile
from pathlib import Path
from official_1041_current_rehearsal import project, encode, sha
from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash

ROOT = Path(__file__).resolve().parents[1]
CORES = {
 'DS-104-1-22':'2356a6ccc4ad3c45d9749cbc0e3a04cbdb05dacd94518a26e4eedf022b4fffcb',
 'DS-104-1-27':'f19169cd57390dc9ebaa89fe20b58c883d591830e5327ec51c9b246fd182bd25',
 'DS-104-1-29':'6a94a474f41fbb208852c19647d107afb0ce922553306bc99ecef6276726bedb',
}

def verify(old_verify, selftest=False):
    proof = json.loads((ROOT/'audit/official_ds_owner_release_20261113.json').read_text())
    assert proof['owner_approved'] is True
    assert proof['source_pdf_sha256'] == '979233d2cb316565c4eed2b5c5289e89e5d21c0bb2b2076a7443887cd24ffadc'
    assert set(proof['before_rows']) == set(proof['before_locks']) == set(CORES)
    assert sha(encode(proof['manifest'])) == '18642fe2697f796b5511b95da826e56ed81b84f3e7c594540f1c0fd9c28644be'
    shards = ROOT/'cdn/question-shards'
    current = json.loads((shards/'manifest.json').read_text())
    lock = json.loads((ROOT/'data/official_exam_readonly.lock.json').read_text())
    old_lock = copy.deepcopy(lock);old_lock['mcq'].update(proof['before_locks'])
    old_lock_raw = (json.dumps(old_lock,ensure_ascii=False,indent=2)+'\n').encode()
    assert sha(old_lock_raw) == '8ddd35af0194ab2ca152887c20ac8de56f4541d851c5cbcd8b1e7476c1c037c3'
    candidates = json.loads((ROOT/'audit/official_104_1_direct_service_three_ocr_candidate_20261031.json').read_text())['proposed_changes']
    changes = {c['id']:c for c in candidates}
    expected = copy.deepcopy(proof['manifest'])
    expected.update(dataset_revision='165abd809ec22cf69379',generated_at='2026-11-12T16:40:00Z',total_uncompressed_bytes=7621904)
    found = set()
    with tempfile.TemporaryDirectory(prefix='swsi-ds-predecessor-') as tmp:
        root=Path(tmp);directory=root/'cdn/question-shards';directory.mkdir(parents=True)
        (root/'data').mkdir()
        (root/'audit').symlink_to(ROOT/'audit',target_is_directory=True)
        (root/'cdn/index.html').symlink_to(ROOT/'cdn/index.html')
        for name in ('official_p0_source_successor_20261112.json',):
            assert (root/'audit'/name).exists()
        for old, entry in zip(proof['manifest']['shards'],expected['shards']):
            raw=(shards/old['file']).read_bytes();payload=json.loads(raw)
            assert encode(payload)==raw
            for row in payload['questions']:
                ident=row['id'];assert row_hash(canonical_row(row,MCQ_FIELDS))==lock['mcq'][ident]
                if ident not in CORES:continue
                assert ident not in found;found.add(ident)
                before=proof['before_rows'][ident]
                assert row==project(before,changes[ident]), ('postimage drift',ident)
                assert lock['mcq'][ident]==CORES[ident], ('approved source drift',ident)
                row.clear();row.update(before)
            restored=encode(payload)
            assert sha(restored)==old['sha256'] and len(restored)==old['bytes'],old['file']
            (directory/old['file']).write_bytes(restored)
            entry['sha256'],entry['bytes']=sha(raw),len(raw)
        assert found==set(CORES) and current==expected
        assert sha('\n'.join(e['file']+':'+e['sha256'] for e in current['shards']).encode())[:20]==current['dataset_revision']
        (directory/'manifest.json').write_bytes(encode(proof['manifest']))
        (root/'data/official_exam_readonly.lock.json').write_bytes(old_lock_raw)
        import official_p0_source_successor_guard as previous
        saved=previous.ROOT
        try:
            previous.ROOT=root
            previous.verify(old_verify)
            if selftest:
                import official_p0_source_successor_selftest
                official_p0_source_successor_selftest.main()
        finally:
            previous.ROOT=saved
    print('DS OWNER RELEASE PASS: 3 exact approved repairs; 4797 full rows/4800 grades/240 essays unchanged; exact P0 predecessor replayed')

def verify_transition(rows, live=False):
    proof=json.loads((ROOT/'audit/official_ds_owner_release_20261113.json').read_text())
    assert proof['owner_approved'] is True
    assert len(rows)==3 and {r['id'] for r in rows}==set(CORES)
    if live:
        pre=json.loads((ROOT/'audit/official_ds_full_preimages_20261113.json').read_text())
        before={e['id']:e['row'] for e in pre['rows']}
        after=proof['expected_full_postimages']
        is_before=all(r==before[r['id']] for r in rows)
        is_after=all(r==after[r['id']] for r in rows)
        assert is_before or is_after, 'mixed/unknown production transition'
        return 'EXACT_PRE_RELEASE' if is_before else 'EXACT_RELEASED_POSTIMAGES'
    for row in rows:
        assert row_hash(canonical_row(row,MCQ_FIELDS))==CORES[row['id']]
        assert row['analysis_status']=='pending'
    return 'APPROVED_SOURCE_RELEASE_LOCAL'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--selftest',action='store_true');args=p.parse_args()
    from official_two_source_owner_release_guard import verify_predecessor
    verify(verify_predecessor,args.selftest)

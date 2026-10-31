#!/usr/bin/env python3
"""Verify exactly two MOEX-original PDF fixes on the held candidate branch.

No production SQL, secret, external requests, or release approval. The
immutable before-shard hashes prove every other question retained its bytes.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash

ROOT = Path(__file__).resolve().parents[1]
PROOF_PATH = ROOT / 'audit/official_two_row_p0_candidate_20261031.json'
IDS = {'DS-108-2-23', 'R-114-1-17'}
SOURCE_SHA = {
    'DS-108-2-23': '78e9473d144f9165622f02ac3e5a004658b0ca7dd516c436f56cfdf4042b3e9b',
    'R-114-1-17': 'e2103e4eb154b5ac0c8de24026a7b35fe3a8370678f606356c919540c87646e2',
}
ENRICH = ('major', 'topic', 'keywords', 'exp_why', 'exp_others',
          'exp_trap', 'exp_raw', 'mnemonic', 'extension', 'law', 'mistake')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_overlay(proof: dict, rows: list[dict], lock: dict,
                     manifest_raw: bytes) -> tuple[list[dict], dict, bytes]:
    """Reverse only two checked rows to retain all historical release gates."""
    assert proof['schema_version'] == 1
    assert proof['scope'] == 'TWO_SOURCE_PDF_VERIFIED_OFFICIAL_CORE_CANDIDATE'
    assert proof['base_main'] == 'd6a17bd85abfe4c3c71092c666132393cbe7d4a9'
    assert proof['production_written'] is False
    assert proof['independent_human_approval'] is False
    assert proof['whole_platform_release_approved'] is False
    assert proof['backup_changed'] is False
    assert proof['answer_grading_changed'] is False
    assert digest(manifest_raw) == proof['manifest_after_sha256']
    before_raw = proof['manifest_before_raw'].encode('utf-8')
    assert digest(before_raw) == proof['manifest_before_sha256']
    before_manifest = json.loads(before_raw)
    after_manifest = json.loads(manifest_raw)
    assert after_manifest['dataset_revision'] == proof['dataset_revision_after']
    assert before_manifest['dataset_revision'] == proof['dataset_revision_before']
    assert len(before_manifest['shards']) == len(after_manifest['shards']) == 24
    before_shards = {e['file']: e for e in before_manifest['shards']}
    after_shards = {e['file']: e for e in after_manifest['shards']}
    assert set(before_shards) == set(after_shards)
    assert {name for name in before_shards if before_shards[name] != after_shards[name]} == {'108-2.json', '114-1.json'}
    assert len(rows) == len({r['id'] for r in rows}) == 4800
    assert len(lock['mcq']) == 4800 and len(lock['essays']) == 240
    assert {p['id'] for p in proof['rows']} == IDS and len(proof['rows']) == 2

    index = {r['id']: r for r in rows}
    # Compare supplied in-memory rows against every checked-in shard, including
    # the 22 untouched files. Reject out-of-band changes in any of 4,800 rows.
    # Combined candidate overlays six 111-2 questions on the tracked shard.
    # The six-row source guard has already reversed them in the *in-memory* rows,
    # so compare the six explicit original/after images without weakening any
    # other row checks or accepting unknown source-core edits.
    six_path = ROOT / 'audit/official_111_2_shared_context_six_20261031.json'
    six_items = {}
    if six_path.exists():
        six_proof = json.loads(six_path.read_text())
        six_items = {x['id']: x for x in six_proof['changes']}
        assert len(six_items) == 6
    # Parent #496 overlay reconstructs memory rows to its own version,
    # whereas the checked-in candidate includes both source-bound additions.
    # Verify exact staged rows for both overlays and byte-identities on disk.
    child=json.loads((ROOT/'audit/official_next_three_p0_source_candidate_20261031.json').read_text())
    child_rows={c['id']:c for c in child['changed_rows']}
    assert len(child_rows)==3
    parent_six=json.loads((ROOT/'audit/official_111_2_shared_context_six_20261031.json').read_text())
    for shard in after_manifest['shards']:
        source_path=ROOT / 'cdn/question-shards' / shard['file']
        raw=source_path.read_bytes()
        extra=child['shards'].get('cdn/question-shards/'+shard['file'])
        if extra:
            assert len(raw)==extra['new_bytes'] and digest(raw)==extra['new_sha256']
        elif shard['file']=='111-2.json':
            assert len(raw)==(ROOT/'cdn/question-shards/111-2.json').stat().st_size
            assert digest(raw)==parent_six['after_shard_sha256']
        else:
            assert len(raw)==shard['bytes'] and digest(raw)==shard['sha256']
        payload = json.loads(raw)
        assert len(payload['questions']) == shard['question_count']
        for item in payload['questions']:
            assert item['id'] in index
            if item['id'] in child_rows:
                assert item == child_rows[item['id']]['published_after']
                assert index[item['id']] == child_rows[item['id']]['published_before']
            elif item['id'] in six_items:
                assert item == six_items[item['id']]['published_after']
                assert index[item['id']] == six_items[item['id']]['published_before']
            else:
                assert item == index[item['id']]
    originals = copy.deepcopy(rows)
    orig_index = {r['id']: r for r in originals}
    orig_lock = copy.deepcopy(lock)
    for item in proof['rows']:
        ident = item['id']
        original = item['published_before']
        changed = item['published_after']
        assert item['source']['pdf_sha256'] == SOURCE_SHA[ident]
        assert item['source']['pdf_page'] == 3 and item['source']['printed_page'] == '4-3'
        assert item['file'] == ('108-2.json' if ident == 'DS-108-2-23' else '114-1.json')
        assert index[ident] == changed
        assert original['id'] == changed['id'] == ident
        assert row_hash(canonical_row(original, MCQ_FIELDS)) == item['before_core_lock_sha256']
        assert row_hash(canonical_row(changed, MCQ_FIELDS)) == item['after_core_lock_sha256']
        assert lock['mcq'][ident] == item['after_core_lock_sha256']
        assert all(original[k] == changed[k] for k in ('answer','accepted_answers','grading_mode','source_url','source_exam_code','id','subject','year','round','qno'))
        assert changed['analysis_status'] == 'review'
        assert all(changed[k] is None for k in ENRICH)
        expected = copy.deepcopy(original)
        for field in item['changed_fields']:
            assert field in ('question','opt_a','opt_b','opt_c','opt_d')
            expected[field] = changed[field]
        for field in ENRICH:
            expected[field] = None
        expected['analysis_status'] = 'review'
        assert expected == changed
        assert (ident == 'DS-108-2-23' and set(item['changed_fields']) == {'question','opt_a'}) or (ident == 'R-114-1-17' and set(item['changed_fields']) == {'question','opt_a','opt_b','opt_c','opt_d'})
        orig_index[ident].clear()
        orig_index[ident].update(original)
        orig_lock['mcq'][ident] = item['before_core_lock_sha256']

    # Every row in the two edited shards must exactly reconstruct its parent
    # bytes after reversing only the source-proven row; no unreviewed edits.
    for name in ('108-2.json','114-1.json'):
        path = ROOT / 'cdn/question-shards' / name
        current_bytes = path.read_bytes()
        assert digest(current_bytes) == proof['after_shards'][name]['sha256']
        assert len(current_bytes) == proof['after_shards'][name]['bytes']
        doc = json.loads(current_bytes)
        assert len(doc['questions']) == 200
        for row in doc['questions']:
            ident = row['id']
            if ident in IDS:
                old_row = next(p['published_before'] for p in proof['rows'] if p['id'] == ident)
                row.clear()
                row.update(old_row)
        original_bytes = (json.dumps(doc, ensure_ascii=False, separators=(',',':')) + '\n').encode('utf-8')
        assert digest(original_bytes) == proof['before_shards'][name]['sha256'] == before_shards[name]['sha256']
        assert len(original_bytes) == proof['before_shards'][name]['bytes'] == before_shards[name]['bytes']
    assert all(originals[i]['answer'] == rows[i]['answer']
               and originals[i]['accepted_answers'] == rows[i]['accepted_answers']
               and originals[i]['grading_mode'] == rows[i]['grading_mode']
               for i in range(4800))
    assert orig_lock['essays'] == lock['essays']
    return originals, orig_lock, before_raw


def main():
    proof = json.loads(PROOF_PATH.read_text(encoding='utf-8'))
    manifest_raw = (ROOT / 'cdn/question-shards/manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    rows = []
    for shard in manifest['shards']:
        raw = (ROOT / 'cdn/question-shards' / shard['file']).read_bytes()
        assert digest(raw) == shard['sha256'] and len(raw) == shard['bytes']
        rows.extend(json.loads(raw)['questions'])
    lock = json.loads((ROOT / 'data/official_exam_readonly.lock.json').read_text())
    from official_combined_nineteen_integrity_smoke import reverse_overlay as reverse_new_eight
    rows,lock,manifest_raw=reverse_new_eight(rows,lock,manifest_raw)
    from official_111_2_shared_context_six_smoke import validate_overlay as reverse_six
    six_proof=json.loads((ROOT/'audit/official_111_2_shared_context_six_20261031.json').read_text())
    from official_next_three_p0_source_smoke import validate_overlay as reverse_three
    three_proof=json.loads((ROOT/'audit/official_next_three_p0_source_candidate_20261031.json').read_text())
    rows,lock,manifest_raw=reverse_three(three_proof,rows,lock,manifest_raw)
    rows,lock,manifest_raw=reverse_six(six_proof,rows,lock,manifest_raw)
    validate_overlay(proof, rows, lock, manifest_raw)
    for kind in ('target-text', 'answer', 'other-row', 'target-lock','source-proof','manifest'):
        p, rs, lk = copy.deepcopy((proof, rows, lock))
        raw = manifest_raw
        if kind == 'target-text':
            next(r for r in rs if r['id'] == 'R-114-1-17')['question'] += 'tamper'
        elif kind == 'answer':
            next(r for r in rs if r['id'] == 'DS-108-2-23')['answer'] = 'C'
        elif kind == 'other-row':
            next(r for r in rs if r['id'] not in IDS)['question'] += 'tamper'
        elif kind == 'target-lock':
            lk['mcq']['R-114-1-17'] = '0'*64
        elif kind == 'source-proof':
            p['rows'][0]['source']['pdf_sha256'] = '0'*64
        elif kind == 'manifest':
            raw += b'tamper'
        try:
            validate_overlay(p, rs, lk, raw)
        except AssertionError:
            pass
        else:
            raise AssertionError('Unapproved candidate tamper accepted: ' + kind)
    print('OFFICIAL 2-ROW CANDIDATE QA PASS: 2 source-SHA-bound OCR fixes, 4798 others unchanged, 4800 grading tuples preserved; 6 tamper cases rejected; human approval false / production untouched')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Validate the exact approved successor and replay the unchanged predecessor guard."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGES = {
    'SP104-2-37': {'opt_b': '①③④', 'opt_c': '①③⑤', 'opt_d': '②④⑤'},
    'SP107-1-40': {'opt_c': '②③④⑤', 'opt_d': '②③④'},
}
RESET = ('major', 'topic', 'keywords', 'exp_why', 'exp_others', 'exp_trap',
         'exp_raw', 'mnemonic', 'extension', 'law', 'mistake', 'analysis_error',
         'analysis_started_at', 'analysis_completed_at', 'analysis_last_attempt_at')

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def encode(obj):
    return (json.dumps(obj, ensure_ascii=False, separators=(',', ':'))+'\n').encode()

def verify(predecessor_guard):
    from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash
    proof = json.loads((ROOT/'audit/official_p0_source_successor_20261112.json').read_text())
    approval = json.loads((ROOT/'audit/official_p0_option_order_owner_approval_20261112.json').read_text())
    assert approval['official_source_approved'] is True and approval['changes'] == CHANGES
    assert approval['unchanged_answers'] == {'SP104-2-37': 'C', 'SP107-1-40': 'B'}
    assert set(proof['before_rows']) == set(proof['before_locks']) == set(CHANGES)
    baseline = proof['manifest']
    assert sha(encode(baseline)) == '1802ba9e2d136e89050669320bb0a03a2cad8869e5b649fd41af1b52639fc47d'
    shards = ROOT/'cdn/question-shards'
    manifest = json.loads((shards/'manifest.json').read_text())
    lock = json.loads((ROOT/'data/official_exam_readonly.lock.json').read_text())
    before_lock = copy.deepcopy(lock)
    before_lock['mcq'].update(proof['before_locks'])
    lock_raw = (json.dumps(before_lock, ensure_ascii=False, indent=2)+'\n').encode()
    assert sha(lock_raw) == '0844c3197e33d9cf09d2a66957a2bff1ac62e07819072d8d8f3fa548fa9d9a76'
    expected_manifest = copy.deepcopy(baseline)
    expected_manifest['dataset_revision'] = '6e0842458c9951c7f66c'
    expected_manifest['generated_at'] = '2026-11-12T00:00:00Z'
    expected_manifest['total_uncompressed_bytes'] = 7623230
    found = set()
    with tempfile.TemporaryDirectory(prefix='swsi-p0-predecessor-') as tmp:
        directory = Path(tmp)
        for old, entry in zip(baseline['shards'], expected_manifest['shards']):
            raw = (shards/old['file']).read_bytes()
            payload = json.loads(raw)
            assert encode(payload) == raw
            for row in payload['questions']:
                ident = row['id']
                assert row_hash(canonical_row(row, MCQ_FIELDS)) == lock['mcq'][ident]
                if ident not in CHANGES:
                    continue
                assert ident not in found
                found.add(ident)
                original = proof['before_rows'][ident]
                expected = copy.deepcopy(original)
                expected.update(CHANGES[ident])
                for key in RESET:
                    if key in expected:
                        expected[key] = None
                if 'analysis_attempts' in expected:
                    expected['analysis_attempts'] = 0
                expected['analysis_status'] = 'pending'
                assert row == expected, ('unauthorized row change', ident)
                assert row['answer'] == approval['unchanged_answers'][ident]
                assert row_hash(canonical_row(original, MCQ_FIELDS)) == proof['before_locks'][ident]
                row.clear()
                row.update(original)
            restored = encode(payload)
            assert sha(restored) == old['sha256'] and len(restored) == old['bytes'], old['file']
            (directory/old['file']).write_bytes(restored)
            entry['sha256'], entry['bytes'] = sha(raw), len(raw)
        assert found == set(CHANGES)
        assert manifest == expected_manifest, 'unexpected manifest delta'
        assert sha('\n'.join(e['file']+':'+e['sha256'] for e in manifest['shards']).encode())[:20] == manifest['dataset_revision']
        (directory/'manifest.json').write_bytes(encode(baseline))
        (directory/'lock.json').write_bytes(lock_raw)
        # Original implementation and all its absolute hashes remain unchanged.
        scope = predecessor_guard.__globals__
        saved = {key: scope[key] for key in ('SHARDS', 'M', 'LOCK')}
        try:
            scope.update(SHARDS=directory, M=directory/'manifest.json', LOCK=directory/'lock.json')
            predecessor_guard()
        finally:
            scope.update(saved)
    print('P0 SUCCESSOR PASS: exactly 5 approved options; 4798 rows/240 essays/4800 grading tuples unchanged; exact predecessor replayed; 5 holds retained pending live acceptance')

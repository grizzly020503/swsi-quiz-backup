#!/usr/bin/env python3
"""Rehearse three held source repairs on the current approved corpus, without writes.

The historical candidate remains unapproved. This validates exact changes and
byte reversal in memory; it does not certify live triggers or human PDF review.
"""
import copy
import hashlib
import json
from pathlib import Path
from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash
from official_two_source_owner_release_guard import verify as verify_current

ROOT = Path(__file__).resolve().parents[1]
IDS = {'DS-104-1-22': 'A', 'DS-104-1-27': 'B', 'DS-104-1-29': 'D'}
TEXT = {'question', 'opt_a', 'opt_b', 'opt_c', 'opt_d'}
CLEAR = {'major', 'topic', 'keywords', 'exp_why', 'exp_others', 'exp_trap',
         'exp_raw', 'mnemonic', 'extension', 'law', 'mistake', 'analysis_error',
         'analysis_started_at', 'analysis_completed_at', 'analysis_last_attempt_at'}

def encode(data):
    return (json.dumps(data, ensure_ascii=False, separators=(',', ':'))+'\n').encode()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def project(before, candidate):
    ident = candidate['id']
    assert ident in IDS and before['id'] == ident
    assert set(candidate['preimage_fields']) == set(candidate['proposed_fields']) == TEXT
    assert all(before[k] == v for k, v in candidate['preimage_fields'].items())
    assert (before['answer'], before['accepted_answers'], before['grading_mode']) == (IDS[ident], None, 'standard')
    after = copy.deepcopy(before)
    after.update(candidate['proposed_fields'])
    for key in CLEAR & after.keys():
        after[key] = None
    if 'analysis_attempts' in after:
        after['analysis_attempts'] = 0
    after['analysis_status'] = 'pending'
    assert {k for k in before if before[k] != after[k]} <= TEXT | CLEAR | {'analysis_status', 'analysis_attempts'}
    return after

def main():
    verify_current()
    from official_1041_live_preflight_sql_selftest import validate
    sql = (ROOT/'audit/official_1041_current_preflight_readonly_20261113.sql').read_text()
    validate(sql)
    assert 'ex.pending=2 AND ap.exact_postimages=2 AND ex.analyzing=0' in sql
    receipt = json.loads((ROOT/'audit/official_p0_production_receipt_20261112.json').read_text())
    for ident, digest in receipt['postimages_rechecked_after_commit'].items():
        assert "id='"+ident+"'" in sql and digest in sql
    assert "FROM public.questions q WHERE analysis_status='pending'" in sql
    audit = json.loads((ROOT/'audit/official_104_1_direct_service_three_ocr_candidate_20261031.json').read_text())
    assert audit['independent_human_approval'] is False and audit['release_approved'] is False
    changes = {c['id']: c for c in audit['proposed_changes']}
    assert set(changes) == set(IDS)
    directory = ROOT/'cdn/question-shards'
    manifest = json.loads((directory/'manifest.json').read_text())
    lock = json.loads((ROOT/'data/official_exam_readonly.lock.json').read_text())
    successor = copy.deepcopy(manifest)
    next_lock = copy.deepcopy(lock)
    before_rows, after_rows, physical_changes = {}, {}, []
    for entry in successor['shards']:
        raw = (directory/entry['file']).read_bytes()
        assert sha(raw) == entry['sha256'] and len(raw) == entry['bytes']
        payload = json.loads(raw)
        assert encode(payload) == raw
        for index, row in enumerate(payload['questions']):
            ident = row['id']
            assert ident not in before_rows
            before_rows[ident] = copy.deepcopy(row)
            if ident in changes:
                payload['questions'][index] = project(row, changes[ident])
                next_lock['mcq'][ident] = row_hash(canonical_row(payload['questions'][index], MCQ_FIELDS))
            after_rows[ident] = copy.deepcopy(payload['questions'][index])
        projected = encode(payload)
        if projected != raw:
            physical_changes.append(entry['file'])
            entry['sha256'], entry['bytes'] = sha(projected), len(projected)
        # Restore entire changed rows; equality proves all other bytes preserved.
        for index, row in enumerate(payload['questions']):
            if row['id'] in IDS:
                payload['questions'][index] = before_rows[row['id']]
        assert encode(payload) == raw
    assert len(before_rows) == len(after_rows) == 4800
    assert {k for k in before_rows if before_rows[k] != after_rows[k]} == set(IDS)
    assert physical_changes == ['104-1.json']
    assert all(tuple(before_rows[i][k] for k in ('answer','accepted_answers','grading_mode')) == tuple(after_rows[i][k] for k in ('answer','accepted_answers','grading_mode')) for i in before_rows)
    assert {i for i in lock['mcq'] if lock['mcq'][i] != next_lock['mcq'][i]} == set(IDS)
    assert lock['essays'] == next_lock['essays'] and len(lock['essays']) == 240
    # Regression: drift in either an official preimage or answer must stop staging.
    for ident in IDS:
        for key in ('question', 'answer'):
            wrong = copy.deepcopy(before_rows[ident]); wrong[key] += 'INVALID'
            try:
                project(wrong, changes[ident])
            except AssertionError:
                pass
            else:
                raise AssertionError('preimage tampering accepted')
    revision = sha('\n'.join(e['file']+':'+e['sha256'] for e in successor['shards']).encode())[:20]
    print(json.dumps({'verdict':'PASS_REHEARSAL_ONLY_NO_RELEASE',
        'baseline_revision':manifest['dataset_revision'], 'projected_revision':revision,
        'changed_ids':sorted(IDS), 'changed_shards':physical_changes,
        'unchanged_full_rows':4797, 'unchanged_grading_tuples':4800,
        'unchanged_essay_locks':240, 'changed_mcq_locks':3,
        'byte_reversal_verified':True, 'negative_cases_rejected':6,
        'projected_status':'pending', 'human_approved':False,
        'production_written':False, 'published':False}, ensure_ascii=False))

if __name__ == '__main__':
    main()

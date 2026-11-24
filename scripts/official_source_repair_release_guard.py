#!/usr/bin/env python3
"""Verify the 2026-11-24 owner-approved source repair release.

Thirteen official rows had PDF-extraction defects (stray next-question digits,
truncated options/stems). HBSE-115-2-026 received a MOEX spacing correction in
the 2026-11-23 sync, which also cleared its SWSI explanation; the explanation is
restored because the wording change is whitespace only.

This guard proves that the current shards/lock equal the recorded postimages,
then rebuilds the exact predecessor (main before the 2026-11-23 sync) by
restoring the recorded preimages, and replays the existing 2026-11-13 DS owner
release chain against that predecessor. Answers and grading never change.
"""
import argparse
import copy
import json
import os
import tempfile
from pathlib import Path

from official_1041_current_rehearsal import encode, sha
from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash

ROOT = Path(__file__).resolve().parents[1]
PROOF = 'audit/official_source_repair_release_20261124.json'
SOURCE_IDS = {
    'SW-104-1-03', 'SW-104-1-12', 'SW-104-1-35', 'SW-106-2-09', 'SW-106-2-21', 'SW-106-2-35',
    'SW-107-2-11', 'SW-107-2-21', 'SW-107-2-35', 'SW-105-2-12', 'SP108-2-09', 'DS-108-2-38', 'DS-109-2-26',
}
GRADING = ('answer', 'accepted_answers', 'grading_mode')


def require(test, reason):
    if not test:
        raise SystemExit('SOURCE REPAIR RELEASE GUARD FAILED: ' + reason)


def build_predecessor(root: Path, target: Path) -> None:
    proof = json.loads((root / PROOF).read_text(encoding='utf-8'))
    require(proof['owner_approved'] is True, 'owner approval missing')
    require(set(proof['source_repair_ids']) == SOURCE_IDS, 'approved id set drift')
    rows = proof['rows']
    lock = json.loads((root / 'data/official_exam_readonly.lock.json').read_text(encoding='utf-8'))
    require(set(proof['after_locks']) == SOURCE_IDS | {'HBSE-115-2-026'}, 'lock change set drift')
    for ident, value in proof['after_locks'].items():
        require(lock['mcq'][ident] == value, 'lock postimage drift ' + ident)
    shards = root / 'cdn/question-shards'
    out = target / 'cdn/question-shards'
    out.mkdir(parents=True)
    current_manifest = json.loads((shards / 'manifest.json').read_text(encoding='utf-8'))
    pred_manifest = proof['predecessor_manifest']
    require([s['file'] for s in current_manifest['shards']] == [s['file'] for s in pred_manifest['shards']], 'shard set drift')
    seen = set()
    for entry in pred_manifest['shards']:
        raw = (shards / entry['file']).read_bytes()
        payload = json.loads(raw)
        require(encode(payload) == raw, 'non-canonical shard ' + entry['file'])
        for row in payload['questions']:
            ident = row['id']
            require(row_hash(canonical_row(row, MCQ_FIELDS)) == lock['mcq'][ident], 'lock mismatch ' + ident)
            record = rows.get(ident)
            if record is None:
                continue
            require(record['shard'] == entry['file'], 'shard owner drift ' + ident)
            require(row == record['after'], 'postimage drift ' + ident)
            for key in GRADING:
                require(record['before'].get(key) == row.get(key), 'grading changed ' + ident)
            seen.add(ident)
            row.clear()
            row.update(record['before'])
        restored = encode(payload)
        require(sha(restored) == entry['sha256'] and len(restored) == entry['bytes'], 'predecessor shard mismatch ' + entry['file'])
        (out / entry['file']).write_bytes(restored)
    require(seen == set(rows), 'recorded rows missing from shards')
    (out / 'manifest.json').write_bytes(encode(pred_manifest))
    old_lock = copy.deepcopy(lock)
    old_lock['mcq'].update(proof['before_locks'])
    (target / 'data').mkdir()
    (target / 'data/official_exam_readonly.lock.json').write_text(json.dumps(old_lock, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.symlink(root / 'audit', target / 'audit', target_is_directory=True)
    (target / 'cdn/index.html').write_bytes((root / 'cdn/index.html').read_bytes())


def replay(root: Path, selftest: bool) -> None:
    import official_ds_owner_release_guard as ds
    import official_two_source_owner_release_guard as two
    with tempfile.TemporaryDirectory(prefix='swsi-source-repair-predecessor-') as tmp:
        target = Path(tmp)
        build_predecessor(root, target)
        saved = ds.ROOT
        try:
            ds.ROOT = target
            ds.verify(two.verify_predecessor, selftest)
            if selftest:
                import official_ds_owner_release_selftest
                official_ds_owner_release_selftest.main()
        finally:
            ds.ROOT = saved


def negative_selftest() -> None:
    import shutil
    cases = 0
    with tempfile.TemporaryDirectory(prefix='swsi-source-repair-negative-') as tmp:
        for mutate in ('text', 'answer', 'unrelated'):
            work = Path(tmp) / mutate
            (work / 'cdn').mkdir(parents=True)
            shutil.copytree(ROOT / 'cdn/question-shards', work / 'cdn/question-shards')
            (work / 'data').mkdir()
            shutil.copy(ROOT / 'data/official_exam_readonly.lock.json', work / 'data')
            os.symlink(ROOT / 'audit', work / 'audit', target_is_directory=True)
            path = work / 'cdn/question-shards/104-1.json'
            payload = json.loads(path.read_text(encoding='utf-8'))
            row = next(r for r in payload['questions'] if r['id'] == ('SW-104-1-03' if mutate != 'unrelated' else 'SW-104-1-04'))
            if mutate == 'answer':
                row['answer'] = 'B' if row['answer'] != 'B' else 'C'
            else:
                row['exp_why'] = (row.get('exp_why') or '') + ' tampered'
            path.write_bytes(encode(payload))
            try:
                with tempfile.TemporaryDirectory() as out:
                    build_predecessor(work, Path(out))
            except SystemExit:
                cases += 1
                continue
            raise AssertionError('tamper accepted: ' + mutate)
    print(f'SOURCE REPAIR NEGATIVES PASS: {cases} unauthorized changes rejected')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    replay(ROOT, args.selftest)
    if args.selftest:
        negative_selftest()
    print('SOURCE REPAIR RELEASE PASS: 13 approved source repairs + HBSE-115-2-026 explanation restore; '
          '0 answer/grading changes; exact pre-sync predecessor and DS owner chain replayed')

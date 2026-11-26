#!/usr/bin/env python3
"""Verify the second 2026-11-24 owner-approved source repair release (#447 remainder).

Twenty-nine official rows carried wrong text from PDF extraction: whole
questions taken from a neighbouring item (SP113-1-31..40, SW-109-1-05), option
orders shifted (SP106-2-25, SP106-2-35, SP111-2-37, R-113-2-30), option sets
flattened (DS-115-1-18/22, SW-105-2-25) and smaller defects. Every row was
checked against its official MOEX question PDF (matching SHA-256, text layer
and column layout) by scripts/official_source_repair_pdf_verify.py.

Seven layout-only rows keep their SWSI explanation; the other 22 had
explanations written for the wrong text, so they are cleared to pending.

This guard proves the current shards/lock equal the recorded postimages, then
rebuilds the exact predecessor (main before this release) and replays the
previous release guard (and through it the whole earlier chain) against it.
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
PROOF = 'audit/official_source_repair_release_20261124b.json'
GRADING = ('answer', 'accepted_answers', 'grading_mode')
TEXT = ('question', 'opt_a', 'opt_b', 'opt_c', 'opt_d')
COUNT = 29
KEPT = 7


def require(test, reason):
    if not test:
        raise SystemExit('SOURCE REPAIR B GUARD FAILED: ' + reason)


def build_predecessor(root: Path, target: Path) -> None:
    proof = json.loads((root / PROOF).read_text(encoding='utf-8'))
    require(proof['owner_approved'] is True, 'owner approval missing')
    rows = proof['rows']
    require(len(rows) == COUNT and len(proof['explanation_kept_ids']) == KEPT, 'release size drift')
    require(set(proof['before_locks']) == set(proof['after_locks']) == set(rows), 'lock change set drift')
    lock = json.loads((root / 'data/official_exam_readonly.lock.json').read_text(encoding='utf-8'))
    for ident, value in proof['after_locks'].items():
        require(lock['mcq'][ident] == value, 'lock postimage drift ' + ident)
    shards = root / 'cdn/question-shards'
    out = target / 'cdn/question-shards'
    out.mkdir(parents=True)
    pred_manifest = proof['predecessor_manifest']
    current_manifest = json.loads((shards / 'manifest.json').read_text(encoding='utf-8'))
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
            if ident in proof['explanation_kept_ids']:
                require(row.get('exp_why') and row.get('exp_why') == record['before'].get('exp_why'), 'kept explanation drift ' + ident)
            else:
                require(row.get('exp_why') is None and row.get('analysis_status') == 'pending', 'stale explanation kept ' + ident)
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
    import official_source_repair_release_guard as previous
    with tempfile.TemporaryDirectory(prefix='swsi-source-repair-b-predecessor-') as tmp:
        target = Path(tmp)
        build_predecessor(root, target)
        previous.replay(target, selftest)
        if selftest:
            saved = previous.ROOT
            try:
                previous.ROOT = target
                previous.negative_selftest()
            finally:
                previous.ROOT = saved


def negative_selftest() -> None:
    import shutil
    proof = json.loads((ROOT / PROOF).read_text(encoding='utf-8'))
    regen = sorted(set(proof['rows']) - set(proof['explanation_kept_ids']))[0]
    kept = proof['explanation_kept_ids'][0]
    cases = [
        (regen, lambda r: r.update(answer='Z')),
        (regen, lambda r: r.update(exp_why='stale explanation')),
        (kept, lambda r: r.update(exp_why=None)),
        (regen, lambda r: r.update(opt_a=(r.get('opt_a') or '') + 'x')),
    ]
    rejected = 0
    with tempfile.TemporaryDirectory(prefix='swsi-source-repair-b-negative-') as tmp:
        for n, (ident, mutate) in enumerate(cases):
            work = Path(tmp) / str(n)
            (work / 'cdn').mkdir(parents=True)
            shutil.copytree(ROOT / 'cdn/question-shards', work / 'cdn/question-shards')
            (work / 'data').mkdir()
            shutil.copy(ROOT / 'data/official_exam_readonly.lock.json', work / 'data')
            os.symlink(ROOT / 'audit', work / 'audit', target_is_directory=True)
            (work / 'cdn/index.html').write_bytes((ROOT / 'cdn/index.html').read_bytes())
            path = work / 'cdn/question-shards' / proof['rows'][ident]['shard']
            payload = json.loads(path.read_text(encoding='utf-8'))
            mutate(next(r for r in payload['questions'] if r['id'] == ident))
            path.write_bytes(encode(payload))
            try:
                with tempfile.TemporaryDirectory() as out:
                    build_predecessor(work, Path(out))
            except SystemExit:
                rejected += 1
                continue
            raise AssertionError('tamper accepted: case ' + str(n))
    print(f'SOURCE REPAIR B NEGATIVES PASS: {rejected} unauthorized changes rejected')


LIVE_FIELDS = TEXT + GRADING + ('exp_why', 'analysis_status')


def live_state(rows_live: list) -> str:
    proof = json.loads((ROOT / PROOF).read_text(encoding='utf-8'))
    rows = proof['rows']
    require(sorted(r['id'] for r in rows_live) == sorted(rows), 'live row set mismatch')
    def official(r, ref):
        return all(r.get(k) == ref.get(k) for k in TEXT + GRADING)
    if all(official(r, rows[r['id']]['after']) for r in rows_live):
        for r in rows_live:
            if r['id'] in proof['explanation_kept_ids']:
                require(r.get('exp_why') == rows[r['id']]['after'].get('exp_why'), 'kept explanation lost in production ' + r['id'])
            else:
                # Cleared by the release; the AI job may regenerate it afterwards.
                require(r.get('analysis_status') in ('pending', 'analyzing', 'ready', 'review'), 'unexpected analysis state ' + r['id'])
        return 'LIVE_RELEASED_POSTIMAGES'
    require(all(official(r, rows[r['id']]['before']) for r in rows_live),
            'production differs from both the recorded preimage and the approved postimage')
    return 'LIVE_NOT_YET_APPLIED'


def live_rows() -> list:
    import requests
    from build_question_shards import frontend_config
    proof = json.loads((ROOT / PROOF).read_text(encoding='utf-8'))
    ids = sorted(proof['rows'])
    base, key = frontend_config()
    response = requests.get(
        base + '/rest/v1/questions',
        headers={'apikey': key, 'Authorization': 'Bearer ' + key, 'Accept': 'application/json',
                 'User-Agent': 'SWSI-Source-Repair-GET/1.0'},
        params={'select': ','.join(('id',) + LIVE_FIELDS), 'id': 'in.(' + ','.join(ids) + ')', 'order': 'id.asc', 'limit': str(len(ids))},
        timeout=30,
    )
    response.raise_for_status()
    rows = response.json()
    require(isinstance(rows, list), 'malformed live rows')
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--require-released', action='store_true')
    args = parser.parse_args()
    if args.live:
        state = live_state(live_rows())
        print('SOURCE REPAIR B LIVE STATE:', state)
        require(state == 'LIVE_RELEASED_POSTIMAGES' or not args.require_released, 'production does not yet contain the released rows')
        raise SystemExit(0)
    # A later owner-approved release moved the current corpus; the newest
    # guard rebuilds this release's exact successor state and replays it.
    from legal_status_batch33_release_guard import replay as replay_newest
    replay_newest(ROOT, args.selftest)
    print('SOURCE REPAIR B RELEASE PASS: 29 PDF-verified source repairs (7 explanations kept, 22 regenerated); '
          '0 answer/grading changes; exact predecessor and full earlier release chain replayed')

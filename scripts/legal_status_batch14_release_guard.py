#!/usr/bin/env python3
"""Verify legal-status batch 14 (2026-11-25): per-article review, 性侵害犯罪防治法.

15 MCQ rows were reviewed one by one against the text of 性侵害犯罪防治法 in force
at each exam (MOJ LawOldVer 2011-11-09 and 2015-12-23) and the current text
after the 2023-02-15 full rewrite (in force 2023-02-17, renumbered to 56
articles). 12 rows move to verified_current; SP104-1-29 moves to changed
because current 第18條 lets a person the victim trusts accompany the victim,
SP112-1-36 because current 第11條 dropped the 24-hour triage rule, and
SP113-1-36 because current 第9條 replaced the curriculum list. SW-111-1-28
turns on 精神衛生法 and is moved out. Only legal metadata changes.

The guard proves the current shards equal the recorded postimages, rebuilds
the exact predecessor and replays the batch 13 guard and its whole chain.
"""
import argparse
import datetime as dt
import json
import os
import shutil
import tempfile
from pathlib import Path

from official_1041_current_rehearsal import encode, sha

ROOT = Path(__file__).resolve().parents[1]
PROOF = 'audit/legal_status_batch14_20261125.json'
COUNT = 15
CHANGED = 3
LEGAL_FIELDS = {'legal_status', 'legal_checked_at', 'legal_note', 'legal_source_url'}


def require(test, reason):
    if not test:
        raise SystemExit('LEGAL STATUS BATCH14 GUARD FAILED: ' + reason)


def check_record(ident, record):
    before, after = record['before'], record['after']
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    require(changed and changed <= LEGAL_FIELDS, 'non-legal field changed ' + ident + ' ' + str(sorted(changed - LEGAL_FIELDS)))
    require(before.get('legal_status') == 'unreviewed' and after.get('legal_status') in ('verified_current', 'changed'), 'status transition ' + ident)
    if after.get('legal_status') == 'changed':
        require('考試時' in after.get('legal_note', '') and '現行條文' in after.get('legal_note', ''), 'changed note lacks exam-time/current rule ' + ident)
    require(str(after.get('legal_source_url') or '').startswith('https://law.moj.gov.tw/'), 'non-MOJ source ' + ident)
    require(after.get('analysis_status') != 'pending', 'pending explanation included ' + ident)
    require(record['laws'], 'law evidence missing ' + ident)
    note = after.get('legal_note', '')
    require(note.startswith('考試時點法規核對（逐條人工核對）：') and '法務部全國法規資料庫' in note, 'note lacks review evidence ' + ident)
    for law, articles in record['articles'].items():
        require(law in note and all(('第' + a.split('-')[0] + '條') in note for a in articles), 'note lacks article ' + ident + ' ' + law)

def build_predecessor(root: Path, target: Path) -> None:
    proof = json.loads((root / PROOF).read_text(encoding='utf-8'))
    require(proof['owner_approved'] is True, 'owner approval missing')
    rows = proof['rows']
    require(sorted(rows) == proof['ids'] and len(rows) == COUNT, 'release size drift')
    require(sum(r['after']['legal_status'] == 'changed' for r in rows.values()) == CHANGED, 'changed count drift')
    for ident, record in rows.items():
        check_record(ident, record)
    shards = root / 'cdn/question-shards'
    out = target / 'cdn/question-shards'
    out.mkdir(parents=True)
    pred_manifest = proof['predecessor_manifest']
    seen = set()
    for entry in pred_manifest['shards']:
        raw = (shards / entry['file']).read_bytes()
        payload = json.loads(raw)
        require(encode(payload) == raw, 'non-canonical shard ' + entry['file'])
        for row in payload['questions']:
            record = rows.get(row['id'])
            if record is None:
                continue
            require(record['shard'] == entry['file'], 'shard owner drift ' + row['id'])
            require(row == record['after'], 'postimage drift ' + row['id'])
            seen.add(row['id'])
            row.clear()
            row.update(record['before'])
        restored = encode(payload)
        require(sha(restored) == entry['sha256'] and len(restored) == entry['bytes'], 'predecessor shard mismatch ' + entry['file'])
        (out / entry['file']).write_bytes(restored)
    require(seen == set(rows), 'recorded rows missing from shards')
    (out / 'manifest.json').write_bytes(encode(pred_manifest))
    (target / 'data').mkdir()
    shutil.copy(root / 'data/official_exam_readonly.lock.json', target / 'data/official_exam_readonly.lock.json')
    os.symlink(root / 'audit', target / 'audit', target_is_directory=True)
    shutil.copy(root / 'index.html', target / 'index.html')
    shutil.copy(root / 'cdn/index.html', target / 'cdn/index.html')


def replay(root: Path, selftest: bool) -> None:
    import legal_status_batch13_release_guard as previous
    with tempfile.TemporaryDirectory(prefix='swsi-legal-batch14-predecessor-') as tmp:
        target = Path(tmp)
        (target / 'cdn').mkdir()
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
    proof = json.loads((ROOT / PROOF).read_text(encoding='utf-8'))
    ident = proof['ids'][0]
    cases = [
        lambda r: r.update(exp_why=(r.get('exp_why') or '') + ' tampered'),
        lambda r: r.update(answer='Z'),
        lambda r: r.update(legal_status='unreviewed'),
        lambda r: r.update(legal_source_url='https://example.com/'),
    ]
    rejected = 0
    with tempfile.TemporaryDirectory(prefix='swsi-legal-batch14-negative-') as tmp:
        for n, mutate in enumerate(cases):
            work = Path(tmp) / str(n)
            (work / 'cdn').mkdir(parents=True)
            shutil.copytree(ROOT / 'cdn/question-shards', work / 'cdn/question-shards')
            (work / 'data').mkdir()
            shutil.copy(ROOT / 'data/official_exam_readonly.lock.json', work / 'data')
            os.symlink(ROOT / 'audit', work / 'audit', target_is_directory=True)
            shutil.copy(ROOT / 'index.html', work / 'index.html')
            shutil.copy(ROOT / 'cdn/index.html', work / 'cdn/index.html')
            path = work / 'cdn/question-shards' / proof['rows'][ident]['shard']
            payload = json.loads(path.read_text(encoding='utf-8'))
            mutate(next(r for r in payload['questions'] if r['id'] == ident))
            path.write_bytes(encode(payload))
            try:
                with tempfile.TemporaryDirectory() as out:
                    (Path(out) / 'cdn').mkdir()
                    build_predecessor(work, Path(out))
            except SystemExit:
                rejected += 1
                continue
            raise AssertionError('tamper accepted: case ' + str(n))
    print(f'LEGAL STATUS BATCH14 NEGATIVES PASS: {rejected} unauthorized changes rejected')


LIVE_FIELDS = ('legal_status', 'legal_checked_at', 'legal_note', 'legal_source_url')


def live_state(rows_live: list) -> str:
    proof = json.loads((ROOT / PROOF).read_text(encoding='utf-8'))
    rows = proof['rows']
    require(sorted(r['id'] for r in rows_live) == sorted(rows), 'live row set mismatch')
    def same(r, ref):
        if r.get('legal_status') != ref.get('legal_status') or r.get('legal_note') != ref.get('legal_note') \
                or r.get('legal_source_url') != ref.get('legal_source_url'):
            return False
        a, b = r.get('legal_checked_at'), ref.get('legal_checked_at')
        if a is None or b is None:
            return a is b
        return dt.datetime.fromisoformat(a.replace('Z', '+00:00')) == dt.datetime.fromisoformat(b.replace('Z', '+00:00'))
    if all(same(r, rows[r['id']]['after']) for r in rows_live):
        return 'LIVE_RELEASED_POSTIMAGES'
    require(all(same(r, rows[r['id']]['before']) for r in rows_live),
            'production differs from both the recorded preimage and the approved postimage')
    return 'LIVE_NOT_YET_APPLIED'


def live_rows() -> list:
    import requests
    from build_question_shards import frontend_config
    proof = json.loads((ROOT / PROOF).read_text(encoding='utf-8'))
    base, key = frontend_config()
    response = requests.get(
        base + '/rest/v1/questions',
        headers={'apikey': key, 'Authorization': 'Bearer ' + key, 'Accept': 'application/json',
                 'User-Agent': 'SWSI-Legal-Batch14-GET/1.0'},
        params={'select': ','.join(('id',) + LIVE_FIELDS), 'id': 'in.(' + ','.join(proof['ids']) + ')',
                'order': 'id.asc', 'limit': str(len(proof['ids']))},
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
    args = parser.parse_args()
    if args.live:
        print('LEGAL STATUS BATCH14 LIVE STATE:', live_state(live_rows()))
        raise SystemExit(0)
    # A later owner-approved release moved the current corpus; the newest
    # guard rebuilds this release's exact successor state and replays it.
    from legal_status_batch35_release_guard import replay as replay_newest
    replay_newest(ROOT, args.selftest)
    print('LEGAL STATUS BATCH14 RELEASE PASS: 12 rows verified_current and 3 changed after per-article review; '
          'only legal metadata changed; exact predecessor and full earlier release chain replayed')

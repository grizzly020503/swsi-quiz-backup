#!/usr/bin/env python3
"""Verify legal-status batch 35 (2026-11-26): code of ethics and two administrative rules, 8 rows.

Six rows test the social work code of ethics adopted under 社會工作師法第17條. The
exam-time version (approved 2008-03-28) and the current version (revised
2018-12-15, approved 2019-04-26) were compared from government-hosted copies;
the current code replaced the principle list 尊重、關懷、正義、堅毅、廉潔、守法、專業
and dropped 「嚴禁參與違法之活動」, so SW-104-1-34, SW-104-2-26 and SW-105-2-36 move to
changed and the other three to verified_current. SP106-1-23 rests on
衛生福利部處務規程第8條 and 公益勸募條例第4條; SW-112-1-34 on 全民健康保險法第41條 and the
current NHI rule for family therapy. Only legal metadata changes. Rows citing a
document outside the MOJ database must record its URL and SHA-256.

The guard proves the current shards equal the recorded postimages, rebuilds
the exact predecessor and replays the batch 34 guard and its whole chain.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from official_1041_current_rehearsal import encode, sha

ROOT = Path(__file__).resolve().parents[1]
PROOF = 'audit/legal_status_batch35_20261126.json'
COUNT = 8
CHANGED = 3
LEGAL_FIELDS = {'legal_status', 'legal_checked_at', 'legal_note', 'legal_source_url'}


def require(test, reason):
    if not test:
        raise SystemExit('LEGAL STATUS BATCH35 GUARD FAILED: ' + reason)


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
    docs = record.get('documents') or []
    if '倫理守則' in note or '支付作業要點' in note:
        require(docs, 'document evidence missing ' + ident)
    for doc in docs:
        require(str(doc.get('url') or '').startswith('https://') and re.fullmatch(r'[0-9a-f]{64}', str(doc.get('sha256') or '')),
                'document evidence malformed ' + ident)

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
    import legal_status_batch34_release_guard as previous
    with tempfile.TemporaryDirectory(prefix='swsi-legal-batch35-predecessor-') as tmp:
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
    with tempfile.TemporaryDirectory(prefix='swsi-legal-batch35-negative-') as tmp:
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
    print(f'LEGAL STATUS BATCH35 NEGATIVES PASS: {rejected} unauthorized changes rejected')


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
                 'User-Agent': 'SWSI-Legal-Batch35-GET/1.0'},
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
        print('LEGAL STATUS BATCH35 LIVE STATE:', live_state(live_rows()))
        raise SystemExit(0)
    # A later owner-approved release moved the current corpus; the newest
    # guard rebuilds this release's exact successor state and replays it.
    from legal_status_batch36_release_guard import replay as replay_newest
    replay_newest(ROOT, args.selftest)
    print('LEGAL STATUS BATCH35 RELEASE PASS: 5 rows verified_current and 3 changed after review of the code of ethics (2008 and '
          '2019 versions) and two administrative rules; only legal metadata changed; exact predecessor and full earlier release chain replayed')

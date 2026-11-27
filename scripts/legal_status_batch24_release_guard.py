#!/usr/bin/env python3
"""Verify legal-status batch 24 (2026-11-25): education, justice and health group, 24 rows.

Rows test 刑法, 民法, 少年事件處理法, 家事事件法, 學生輔導法, the dropout reporting
rules, 專科社會工作師分科甄審及接受繼續教育辦法, 性騷擾防治法, 毒品危害防制條例,
病人自主權利法, 長期照顧服務機構法人條例, 性別平等教育法 with 校園性別事件防治準則,
人口販運防制法, 校園霸凌防制準則 and 社區發展工作綱要. Articles amended after the
exam were compared with MOJ LawOldVer. Fifteen rows keep their official
answer (verified_current). Nine rows move to changed: SP104-1-36 (one-year
residence permit), SW-110-2-13 (age of majority eighteen), HBSE-105-1-032
and HBSE-107-2-010 (2024 rewrite of 校園霸凌防制準則), DS-109-2-39,
DS-110-2-39 and SW-106-2-34 (社區發展工作綱要 abolished 2025-07-01), and
SW-109-1-37 and SW-110-1-34 (學生輔導法第11條 in force 2027-01-01).
HBSE-104-2-029 and HBSE-110-2-025 are moved out. Only legal metadata changes.

The guard proves the current shards equal the recorded postimages, rebuilds
the exact predecessor and replays the batch 23 guard and its whole chain.
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
PROOF = 'audit/legal_status_batch24_20261125.json'
COUNT = 24
CHANGED = 9
LEGAL_FIELDS = {'legal_status', 'legal_checked_at', 'legal_note', 'legal_source_url'}


def require(test, reason):
    if not test:
        raise SystemExit('LEGAL STATUS BATCH24 GUARD FAILED: ' + reason)


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
    import legal_status_batch23_release_guard as previous
    with tempfile.TemporaryDirectory(prefix='swsi-legal-batch24-predecessor-') as tmp:
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
    with tempfile.TemporaryDirectory(prefix='swsi-legal-batch24-negative-') as tmp:
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
    print(f'LEGAL STATUS BATCH24 NEGATIVES PASS: {rejected} unauthorized changes rejected')


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
    # The weekly MOJ law watch may flag released rows and a later batch may
    # re-review them; no other change is accepted.
    from legal_live_transitions import released_with_transitions
    transitions = released_with_transitions(PROOF, rows_live, rows, same)
    if transitions:
        return transitions
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
                 'User-Agent': 'SWSI-Legal-Batch24-GET/1.0'},
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
        print('LEGAL STATUS BATCH24 LIVE STATE:', live_state(live_rows()))
        raise SystemExit(0)
    # A later owner-approved release moved the current corpus; the newest
    # guard rebuilds this release's exact successor state and replays it.
    from legal_status_batch36_release_guard import replay as replay_newest
    replay_newest(ROOT, args.selftest)
    print('LEGAL STATUS BATCH24 RELEASE PASS: 15 rows verified_current and 9 changed after per-article review; '
          'only legal metadata changed; exact predecessor and full earlier release chain replayed')

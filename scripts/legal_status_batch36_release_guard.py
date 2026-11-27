#!/usr/bin/env python3
"""Verify legal-status batch 36 (2026-11-27): the last 11 unreviewed questions.

These questions waited for an explanation and the daily automatic label
(public.legal_auto_label_apply) could not decide them. Each cited article was
compared at the exam date and today in the MOJ database (current text and
amendment history, plus the old full-text versions printed earlier by Legal
History Fetch); SP113-1-32 is changed because 最低工資法第18條 now applies the minimum wage
wherever 社會救助法第8條 says 基本工資; SP113-1-31 is social-policy theory and
becomes not_applicable. Only the four legal_* columns change.

Batch 36 is the first prod-first release: it is written to Supabase and the
website shards follow through the weekly automatic publish
(question-shards-publish.yml), which also carries AI explanations and the
automatic labels. Those weekly publishes change shard bytes outside any
guarded release, so the guard chain can no longer be replayed against the
working tree. It is replayed against the shards at CHAIN_ANCHOR instead: the
main commit where every earlier guarded release (official repairs and legal
batches 1-35) is the last change to the shards. The working tree is still
checked: batch rows must carry the recorded legal fields (or a later
recorded change) once the publish has caught up.
"""
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF = 'audit/legal_status_batch36_20261127.json'
COUNT = 11
STATUS = {'verified_current': 9, 'changed': 1, 'not_applicable': 1}
LEGAL_FIELDS = ('legal_status', 'legal_checked_at', 'legal_note', 'legal_source_url')
CHAIN_ANCHOR = '78628323a0bbc94bfc2123e6b58ae5b887bffc3b'
ANCHOR_REVISION = '54410073a28c81b5f9cb'
ANCHOR_FILES = ('cdn/index.html', 'index.html', 'data/official_exam_readonly.lock.json')


def require(test, reason):
    if not test:
        raise SystemExit('LEGAL STATUS BATCH36 GUARD FAILED: ' + reason)


def check_record(ident, record):
    before, after = record['before'], record['after']
    require(set(before) == set(LEGAL_FIELDS) and set(after) == set(LEGAL_FIELDS), 'record must hold exactly the legal fields ' + ident)
    require(before == {'legal_status': 'unreviewed', 'legal_checked_at': None, 'legal_note': None, 'legal_source_url': None},
            'preimage is not an untouched unreviewed row ' + ident)
    status = after['legal_status']
    if status == 'not_applicable':
        require(after['legal_checked_at'] is None and after['legal_note'] is None and after['legal_source_url'] is None,
                'not_applicable keeps the other legal fields empty ' + ident)
        require(not record['laws'] and record.get('reason'), 'not_applicable needs a reason and no law ' + ident)
        return
    require(status in ('verified_current', 'changed'), 'status transition ' + ident)
    note = after['legal_note'] or ''
    require(note.startswith('考試時點法規核對（逐條人工核對）：本題考試日 ' + record['exam_date'] + '。'), 'note header ' + ident)
    require('法務部全國法規資料庫' in note, 'note lacks review evidence ' + ident)
    if status == 'changed':
        require('考試時' in note and '現行條文' in note, 'changed note lacks exam-time/current rule ' + ident)
    else:
        require(note.count('官方答案依現行條文仍正確。') == 1, 'verified note lacks the current-answer statement ' + ident)
    require(str(after['legal_source_url'] or '').startswith('https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode='), 'non-MOJ source ' + ident)
    require(re.fullmatch(r'2026-11-27T\d\d:\d\d:\d\d\+00:00', str(after['legal_checked_at'] or '')), 'checked time ' + ident)
    require(record['laws'], 'law evidence missing ' + ident)
    for law, articles in record['articles'].items():
        require(law in note and all(('第' + a.split('-')[0] + '條') in note for a in articles), 'note lacks article ' + ident + ' ' + law)
    for item in record['evidence']:
        require(item['exam_text'] and item['current_text'], 'article text evidence missing ' + ident)


def load_proof(root: Path = ROOT) -> dict:
    proof = json.loads((root / PROOF).read_text(encoding='utf-8'))
    require(proof['owner_approved'] is True, 'owner approval missing')
    require(proof['chain_anchor'] == {'commit': CHAIN_ANCHOR, 'dataset_revision': ANCHOR_REVISION}, 'chain anchor drift')
    rows = proof['rows']
    require(sorted(rows) == proof['ids'] and len(rows) == COUNT, 'release size drift')
    counts = {}
    for ident, record in rows.items():
        check_record(ident, record)
        counts[record['after']['legal_status']] = counts.get(record['after']['legal_status'], 0) + 1
    require(counts == STATUS, 'status counts drift ' + str(counts))
    earlier = set()
    for path in sorted((root / 'audit').glob('legal_status_batch*_2026*.json')):
        if path.name != Path(PROOF).name:
            earlier |= set(json.loads(path.read_text(encoding='utf-8')).get('ids') or [])
    require(not (earlier & set(rows)), 'row already released by an earlier batch: ' + str(sorted(earlier & set(rows))))
    require(proof['official_text_changes'] == 0, 'official text changed')
    return proof


def git_show(rev: str, path: str) -> bytes:
    done = subprocess.run(['git', '-C', str(ROOT), 'show', rev + ':' + path], capture_output=True)
    if done.returncode != 0:
        subprocess.run(['git', '-C', str(ROOT), 'fetch', '--no-tags', '--depth=1', 'origin', rev], capture_output=True)
        done = subprocess.run(['git', '-C', str(ROOT), 'show', rev + ':' + path], capture_output=True)
    require(done.returncode == 0, 'chain anchor not readable: ' + path + ' ' + done.stderr.decode('utf-8', 'replace')[:200])
    return done.stdout


def materialize_anchor(target: Path) -> Path:
    """The repository state the guard chain was proven against, from git."""
    shards = target / 'cdn/question-shards'
    shards.mkdir(parents=True)
    manifest_raw = git_show(CHAIN_ANCHOR, 'cdn/question-shards/manifest.json')
    manifest = json.loads(manifest_raw)
    require(manifest['dataset_revision'] == ANCHOR_REVISION, 'anchor dataset revision drift')
    (shards / 'manifest.json').write_bytes(manifest_raw)
    for entry in manifest['shards']:
        (shards / entry['file']).write_bytes(git_show(CHAIN_ANCHOR, 'cdn/question-shards/' + entry['file']))
    for rel in ANCHOR_FILES:
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        (target / rel).write_bytes(git_show(CHAIN_ANCHOR, rel))
    (target / 'audit').symlink_to(ROOT / 'audit', target_is_directory=True)
    return target


def anchor_rows(root: Path) -> dict:
    manifest = json.loads((root / 'cdn/question-shards/manifest.json').read_text(encoding='utf-8'))
    rows = {}
    for entry in manifest['shards']:
        payload = json.loads((root / 'cdn/question-shards' / entry['file']).read_text(encoding='utf-8'))
        for row in payload['questions']:
            rows[row['id']] = row
    return rows


def check_shards(root: Path, proof: dict, allow_pending_publish: bool) -> str:
    """Batch rows in a shard tree: recorded preimage (publish not caught up yet)
    or recorded postimage. Anything else fails."""
    rows = anchor_rows(root)
    published = pending = 0
    for ident, record in proof['rows'].items():
        require(ident in rows, 'batch row missing from shards ' + ident)
        legal = {k: rows[ident].get(k) for k in LEGAL_FIELDS}
        if legal == record['after']:
            published += 1
        elif legal == record['before'] and allow_pending_publish:
            pending += 1
        else:
            require(False, 'shard legal fields differ from both recorded images ' + ident)
    return f'{published} published, {pending} awaiting the weekly publish'


def replay(root: Path, selftest: bool) -> None:
    """Prove batch 36 and replay the whole earlier chain from the anchor."""
    import legal_status_batch35_release_guard as previous
    proof = load_proof(ROOT)
    with tempfile.TemporaryDirectory(prefix='swsi-legal-batch36-anchor-') as tmp:
        anchor = materialize_anchor(Path(tmp))
        state = check_shards(anchor, proof, allow_pending_publish=True)
        require(state.startswith('0 published'), 'batch rows already released at the anchor')
        previous.replay(anchor, selftest)
        if selftest:
            saved = previous.ROOT
            try:
                previous.ROOT = anchor
                previous.negative_selftest()
            finally:
                previous.ROOT = saved
    print('LEGAL STATUS BATCH36 WORKING TREE:', check_shards(root, proof, allow_pending_publish=True))


def negative_selftest() -> None:
    proof = load_proof(ROOT)
    ident = next(i for i, r in proof['rows'].items() if r['after']['legal_status'] == 'verified_current')
    na = next(i for i, r in proof['rows'].items() if r['after']['legal_status'] == 'not_applicable')
    cases = [
        lambda p: p['rows'][ident]['after'].update(legal_source_url='https://example.com/'),
        lambda p: p['rows'][ident]['after'].update(legal_note=p['rows'][ident]['after']['legal_note'].replace('第', '')),
        lambda p: p['rows'][ident]['after'].update(legal_status='changed'),
        lambda p: p['rows'][ident]['before'].update(legal_status='verified_current'),
        lambda p: p['rows'][ident]['after'].update(exp_why='tampered'),
        lambda p: p['rows'][na]['after'].update(legal_note='x'),
        lambda p: p.update(chain_anchor={'commit': '0' * 40, 'dataset_revision': ANCHOR_REVISION}),
        lambda p: p.update(official_text_changes=1),
    ]
    rejected = 0
    for n, mutate in enumerate(cases):
        with tempfile.TemporaryDirectory(prefix='swsi-legal-batch36-negative-') as tmp:
            work = Path(tmp)
            (work / 'audit').mkdir()
            for path in (ROOT / 'audit').glob('legal_status_batch*_2026*.json'):
                (work / 'audit' / path.name).symlink_to(path)
            tampered = json.loads(json.dumps(proof))
            mutate(tampered)
            (work / 'audit' / Path(PROOF).name).unlink()
            (work / PROOF).write_text(json.dumps(tampered, ensure_ascii=False), encoding='utf-8')
            try:
                load_proof(work)
            except SystemExit:
                rejected += 1
                continue
            raise AssertionError('tamper accepted: case ' + str(n))
    with tempfile.TemporaryDirectory(prefix='swsi-legal-batch36-shard-negative-') as tmp:
        anchor = materialize_anchor(Path(tmp))
        path = anchor / 'cdn/question-shards' / next(
            e['file'] for e in json.loads((anchor / 'cdn/question-shards/manifest.json').read_text(encoding='utf-8'))['shards']
            if any(r['id'] == ident for r in json.loads((anchor / 'cdn/question-shards' / e['file']).read_text(encoding='utf-8'))['questions']))
        payload = json.loads(path.read_text(encoding='utf-8'))
        next(r for r in payload['questions'] if r['id'] == ident)['legal_note'] = 'unrecorded edit'
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        try:
            check_shards(anchor, proof, allow_pending_publish=True)
        except SystemExit:
            rejected += 1
        else:
            raise AssertionError('unrecorded shard edit accepted')
    print(f'LEGAL STATUS BATCH36 NEGATIVES PASS: {rejected} unauthorized changes rejected')


def live_state(rows_live: list) -> str:
    proof = load_proof(ROOT)
    rows = proof['rows']
    require(sorted(r['id'] for r in rows_live) == sorted(rows), 'live row set mismatch')

    def same(r, ref):
        if any(r.get(k) != ref.get(k) for k in ('legal_status', 'legal_note', 'legal_source_url')):
            return False
        a, b = r.get('legal_checked_at'), ref.get('legal_checked_at')
        if a is None or b is None:
            return a is b
        import datetime as dt
        return dt.datetime.fromisoformat(a.replace('Z', '+00:00')) == dt.datetime.fromisoformat(b.replace('Z', '+00:00'))
    if all(same(r, rows[r['id']]['after']) for r in rows_live):
        return 'LIVE_RELEASED_POSTIMAGES'
    require(all(same(r, rows[r['id']]['before']) for r in rows_live),
            'production differs from both the recorded preimage and the approved postimage')
    return 'LIVE_NOT_YET_APPLIED'


def live_rows() -> list:
    import requests
    from build_question_shards import frontend_config
    proof = load_proof(ROOT)
    base, key = frontend_config()
    response = requests.get(
        base + '/rest/v1/questions',
        headers={'apikey': key, 'Authorization': 'Bearer ' + key, 'Accept': 'application/json',
                 'User-Agent': 'SWSI-Legal-Batch36-GET/1.0'},
        params={'select': ','.join(('id',) + LEGAL_FIELDS), 'id': 'in.(' + ','.join(proof['ids']) + ')',
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
        print('LEGAL STATUS BATCH36 LIVE STATE:', live_state(live_rows()))
        raise SystemExit(0)
    replay(ROOT, args.selftest)
    if args.selftest:
        negative_selftest()
    print('LEGAL STATUS BATCH36 RELEASE PASS: 9 rows verified_current, 1 changed (社會救助法第8條 now reads 最低工資) and 1 '
          'not_applicable after per-article review against the MOJ database; only legal metadata changed; earlier release chain '
          'replayed from the anchor commit')

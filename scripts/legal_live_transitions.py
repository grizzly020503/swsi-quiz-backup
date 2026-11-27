#!/usr/bin/env python3
"""Automatic changes a released legal-status row may go through later.

After a guarded release, the four legal fields of a row may change without a
new guarded release in one way only: the weekly MOJ law watch
(supabase/functions/sync-legal-watch) flags the row as `changed` with one of
its two fixed notes when a law the row cites is amended. A later guarded batch
may also re-review the row; the row then equals that batch's approved
post-image. The release guards accept these two transitions and nothing else.
"""
import argparse
import datetime as dt
import json
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGAL_FIELDS = ('legal_status', 'legal_checked_at', 'legal_note', 'legal_source_url')
_ARTICLE = r'§[0-9]+(?:-[0-9]+)*'
# The two notes sync-legal-watch writes (index.ts, legalNote), nothing else.
MONITOR_NOTE = re.compile(
    '^監測到《(?P<law>[^《》]{2,80})》(?:'
    '條文異動（' + _ARTICLE + '(?:, ' + _ARTICLE + ')*）；本題明確引用受影響條文，需依最新法規重新核對。'
    '|官方修正日期變動，但條文差異無法可靠解析；本題依保守策略重新核對。)$')
# safeOfficialUrl() in sync-legal-watch keeps only these hosts, else NULL.
MONITOR_URL = re.compile(r'^https://(?:law|sendlaw)\.moj\.gov\.tw/\S*$')
PROOF_NAME = re.compile(r'^legal_status_batch(?P<n>[0-9]+)_[0-9]{8}[a-z]?\.json$')


def _instant(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


def same_legal(row: dict, ref: dict) -> bool:
    """The four legal fields are equal; timestamps are compared as instants."""
    if any(row.get(k) != ref.get(k) for k in ('legal_status', 'legal_note', 'legal_source_url')):
        return False
    a, b = row.get('legal_checked_at'), ref.get('legal_checked_at')
    if a is None or b is None:
        return a is None and b is None
    return _instant(a) == _instant(b)


def watched_law_names(root: Path = ROOT) -> set:
    names = json.loads((root / 'data/legal_watch_names.json').read_text(encoding='utf-8'))
    return {(n if isinstance(n, str) else n.get('name') or '').strip() for n in names} - {''}


def is_monitor_flip(row: dict, watched: set) -> bool:
    """The exact state sync-legal-watch writes when a watched law changes."""
    note, url = row.get('legal_note'), row.get('legal_source_url')
    if row.get('legal_status') != 'changed' or row.get('legal_checked_at') is not None:
        return False
    match = MONITOR_NOTE.match(note) if isinstance(note, str) else None
    if not match or match.group('law') not in watched:
        return False
    return url is None or (isinstance(url, str) and bool(MONITOR_URL.match(url)))


def batch_number(proof_path: str) -> int:
    match = PROOF_NAME.match(Path(proof_path).name)
    if not match:
        raise ValueError('not a legal batch proof: ' + str(proof_path))
    return int(match.group('n'))


def later_postimages(proof_path: str, root: Path = ROOT) -> dict:
    """Approved post-images of batches after this one; the newest batch wins."""
    own = batch_number(proof_path)
    found = []
    for path in (root / 'audit').glob('legal_status_batch*_*.json'):
        match = PROOF_NAME.match(path.name)
        if match and int(match.group('n')) > own:
            found.append((int(match.group('n')), path))
    out = {}
    for _, path in sorted(found):
        for ident, record in json.loads(path.read_text(encoding='utf-8'))['rows'].items():
            out[ident] = {k: record['after'].get(k) for k in LEGAL_FIELDS}
    return out


def released_with_transitions(proof_path: str, rows_live: list, rows: dict, same=same_legal, root: Path = ROOT):
    """A state string when every live row is its approved post-image, a later
    batch's approved post-image or the law watch's flag, with at least one of
    the latter two; otherwise None."""
    later = later_postimages(proof_path, root)
    watched = watched_law_names(root)
    flagged = reviewed = 0
    for row in rows_live:
        ident = row['id']
        if same(row, rows[ident]['after']):
            continue
        if ident in later and same(row, later[ident]):
            reviewed += 1
        elif is_monitor_flip(row, watched):
            flagged += 1
        else:
            return None
    if not flagged and not reviewed:
        return None
    return (f'LIVE_RELEASED_WITH_TRANSITIONS ({flagged} flagged by the MOJ law watch, '
            f'{reviewed} re-reviewed in later batches)')


def selftest() -> None:
    watched = watched_law_names()
    law = '社會救助法'
    assert law in watched
    url = 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050078'
    scoped = f'監測到《{law}》條文異動（§8, §17-3）；本題明確引用受影響條文，需依最新法規重新核對。'
    broad = f'監測到《{law}》官方修正日期變動，但條文差異無法可靠解析；本題依保守策略重新核對。'
    flip = {'legal_status': 'changed', 'legal_checked_at': None, 'legal_note': scoped, 'legal_source_url': url}
    accepted = [flip, dict(flip, legal_note=broad), dict(flip, legal_source_url=None),
                dict(flip, legal_source_url='https://sendlaw.moj.gov.tw/x')]
    rejected = [
        dict(flip, legal_status='verified_current'),
        dict(flip, legal_checked_at='2026-11-30T02:35:00+00:00'),
        dict(flip, legal_note=scoped.replace('《社會救助法》', '《不存在的法》')),
        dict(flip, legal_note=scoped.replace('§8, §17-3', '§8,§17-3')),
        dict(flip, legal_note=scoped.replace('§8', '第8條')),
        dict(flip, legal_note=scoped + '另有說明。'),
        dict(flip, legal_note=broad.replace('保守策略', '寬鬆策略')),
        dict(flip, legal_note=None),
        dict(flip, legal_source_url='https://example.com/law'),
        dict(flip, legal_source_url='http://law.moj.gov.tw/LawClass/LawAll.aspx'),
    ]
    assert all(is_monitor_flip(r, watched) for r in accepted)
    assert not any(is_monitor_flip(r, watched) for r in rejected)
    assert same_legal({'legal_checked_at': '2026-11-27T06:00:00Z'}, {'legal_checked_at': '2026-11-27T06:00:00+00:00'})
    assert not same_legal({'legal_checked_at': None}, {'legal_checked_at': '2026-11-27T06:00:00+00:00'})

    with tempfile.TemporaryDirectory(prefix='swsi-legal-transitions-') as tmp:
        root = Path(tmp)
        (root / 'audit').mkdir()
        (root / 'data').mkdir()
        (root / 'data/legal_watch_names.json').write_text(json.dumps([{'name': law}], ensure_ascii=False), encoding='utf-8')
        old = {'legal_status': 'verified_current', 'legal_checked_at': '2026-11-01T00:00:00+00:00',
               'legal_note': 'old', 'legal_source_url': url}
        new = dict(old, legal_note='new', legal_checked_at='2026-12-07T00:00:00+00:00')
        newest = dict(old, legal_note='newest')

        def proof(n, ident, after):
            path = root / 'audit' / f'legal_status_batch{n}_20261201.json'
            path.write_text(json.dumps({'rows': {ident: {'before': {}, 'after': after}}}), encoding='utf-8')
            return str(path.relative_to(root))
        first = proof(5, 'Q1', old)
        proof(40, 'Q1', new)
        proof(41, 'Q1', newest)
        (root / 'audit/legal_status_batch99_notes.json').write_text('{}', encoding='utf-8')
        assert later_postimages(first, root) == {'Q1': newest}
        rows = {'Q1': {'after': old}}
        assert released_with_transitions(first, [dict(newest, id='Q1')], rows, root=root).endswith(
            '(0 flagged by the MOJ law watch, 1 re-reviewed in later batches)')
        assert released_with_transitions(first, [dict(flip, id='Q1')], rows, root=root).startswith(
            'LIVE_RELEASED_WITH_TRANSITIONS (1 flagged')
        assert released_with_transitions(first, [dict(new, id='Q1')], rows, root=root) is None
        assert released_with_transitions(first, [dict(old, id='Q1')], rows, root=root) is None
        assert released_with_transitions(first, [dict(rejected[0], id='Q1')], rows, root=root) is None
    # The accepted notes must stay the ones sync-legal-watch actually writes.
    source = (ROOT / 'supabase/functions/sync-legal-watch/index.ts').read_text(encoding='utf-8')
    for fragment in ('`監測到《${canonicalName}》條文異動（${changedArticleText}）；本題明確引用受影響條文，需依最新法規重新核對。`',
                     '`監測到《${canonicalName}》官方修正日期變動，但條文差異無法可靠解析；本題依保守策略重新核對。`',
                     'const changedArticleText = changedArticles.map((a) => `§${a}`).join(", ");',
                     'legal_status: "changed",', 'legal_checked_at: null,', 'legal_source_url: officialUrl,'):
        assert fragment in source, 'sync-legal-watch no longer writes: ' + fragment

    # Every batch guard's live check: released rows pass, a law-watch flag
    # passes, a forged flag fails.
    import importlib
    guards = sorted((int(p.stem.split('batch')[1].split('_')[0]), p.stem)
                    for p in (ROOT / 'scripts').glob('legal_status_batch*_release_guard.py'))
    assert guards, 'no batch guards found'
    flag = {'legal_status': 'changed', 'legal_checked_at': None, 'legal_source_url': None,
            'legal_note': f'監測到《{law}》條文異動（§3）；本題明確引用受影響條文，需依最新法規重新核對。'}
    for _, name in guards:
        guard = importlib.import_module(name)
        rows = json.loads((ROOT / guard.PROOF).read_text(encoding='utf-8'))['rows']
        released = [dict({k: r['after'].get(k) for k in LEGAL_FIELDS}, id=i) for i, r in rows.items()]
        assert guard.live_state(released) == 'LIVE_RELEASED_POSTIMAGES', name
        assert guard.live_state([{**released[0], **flag}] + released[1:]).startswith(
            'LIVE_RELEASED_WITH_TRANSITIONS (1 flagged'), name
        try:
            guard.live_state([{**released[0], **flag, 'legal_note': f'監測到《{law}》條文異動。'}] + released[1:])
        except SystemExit:
            pass
        else:
            raise AssertionError(name + ' accepted a forged law-watch flag')
    print(f'LEGAL LIVE TRANSITIONS SELFTEST PASS: {len(accepted)} law-watch flags accepted, '
          f'{len(rejected)} look-alikes rejected; later-batch re-reviews resolved newest first; '
          f'notes match sync-legal-watch; live checks of {len(guards)} batch guards verified')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    if not args.selftest:
        parser.error('only --selftest is available; the release guards import this module')
    selftest()

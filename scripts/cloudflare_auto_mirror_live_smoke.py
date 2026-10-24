#!/usr/bin/env python3
"""Read-only Cloudflare auto snapshot parity with the tracked release artifact.

The live site is checked only after main release; PR runs cannot equate
unmerged branch bytes with deployed Cloudflare bytes. No POST, secrets or AI.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://wandering-wave-4418.c022050333.workers.dev'
FILES = ('questions_auto.json', 'essays_auto.json')


def same_snapshot(expected, received, label: str) -> None:
    if not isinstance(expected, list) or not isinstance(received, list):
        raise ValueError(f'{label}: live payload must be a JSON array')
    def by_id(rows):
        if any(not isinstance(x, dict) or not isinstance(x.get('id'), str) or not x['id'] for x in rows):
            raise ValueError(f'{label}: malformed row identity')
        keys = [row['id'] for row in rows]
        if len(set(keys)) != len(keys):
            raise ValueError(f'{label}: duplicate row identity')
        return {row['id']: row for row in rows}
    reference, online = by_id(expected), by_id(received)
    if reference.keys() != online.keys():
        raise ValueError(f'{label}: live question/essay IDs differ from tracked CDN source')
    if reference != online:
        different = sorted(key for key in reference if reference[key] != online[key])
        raise ValueError(f'{label}: live content differs from tracked CDN: {different[:5]}')


def fetch_live(filename: str, nonce: str):
    url = ORIGIN + '/auto/' + filename + '?' + urllib.parse.urlencode(
        {'swsi_auto_release_check': nonce}
    )
    req = urllib.request.Request(url, headers={
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'User-Agent': 'SWSI-Verified-Auto-Release/1.0',
    })
    with urllib.request.urlopen(req, timeout=20) as res:
        if res.status != 200:
            raise ValueError(f'{filename}: HTTP {res.status}')
        content_type = res.headers.get('Content-Type', '')
        if 'json' not in content_type.lower():
            raise ValueError(f'{filename}: unexpected Content-Type {content_type}')
        raw = res.read(2_000_000)
    return json.loads(raw.decode('utf-8'))


def selftest():
    correct = [{
        'id': 'DS-115-2-040', 'answer': 'B',
        'accepted_answers': ['B', 'D'], 'grading_mode': 'standard',
    }]
    same_snapshot(correct, [dict(correct[0])], 'synthetic')
    bad = [dict(correct[0])]
    bad[0].pop('accepted_answers')
    for mutated in (bad, [dict(correct[0], accepted_answers=['B'])], [],
                    [correct[0], correct[0]]):
        try:
            same_snapshot(correct, mutated, 'synthetic')
        except ValueError:
            continue
        raise AssertionError('live stale official grading was not rejected')
    essay = [{'id': 'E-SYNTH', 'analysis_status': 'pending', 'q': 'synthetic'}]
    same_snapshot(essay, [dict(essay[0])], 'synthetic essay')
    try:
        same_snapshot(essay, [{'id': 'E-SYNTH', 'analysis_status': 'ready', 'q': 'synthetic'}],
                      'synthetic essay')
    except ValueError:
        pass
    else:
        raise AssertionError('silent promotion of unreviewed essay status accepted')
    print('LIVE AUTO SNAPSHOT SELFTEST OK: official B/D + essay review-state fail-closed')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--live', action='store_true')
    ap.add_argument('--attempts', type=int, default=24)
    ap.add_argument('--pause', type=float, default=5.0)
    ap.add_argument('--check', default='manual')
    opts = ap.parse_args()
    if opts.selftest:
        selftest()
        return 0
    if not opts.live or opts.attempts < 1 or opts.attempts > 36:
        raise SystemExit('Use --live for explicit read-only hosted verification')
    expected = {
        name: json.loads((ROOT / 'cdn' / 'auto' / name).read_text(encoding='utf-8'))
        for name in FILES
    }
    last = ''
    for i in range(opts.attempts):
        try:
            for name in FILES:
                same_snapshot(
                    expected[name],
                    fetch_live(name, f'{opts.check}-{i + 1}'),
                    name
                )
            print('CLOUDFLARE LIVE AUTO SNAPSHOT PARITY OK: '
                  + ' / '.join(f'{name}={len(expected[name])}' for name in FILES))
            return 0
        except (ValueError, json.JSONDecodeError, urllib.error.URLError,
                UnicodeDecodeError) as error:
            last = f'{type(error).__name__}: {error}'
            print(f'Waiting for Cloudflare auto parity ({i + 1}/{opts.attempts}): {last}')
            if i + 1 < opts.attempts:
                time.sleep(opts.pause)
    raise SystemExit('CLOUDFLARE LIVE AUTO PARITY FAILED: ' + last)


if __name__ == '__main__':
    raise SystemExit(main())

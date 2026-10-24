#!/usr/bin/env python3
"""Check that Cloudflare's auto-essay mirror preserves the official source fields.

SWSI learning metadata and analysis_status are deliberately excluded: a CDN
pending guide must not be promoted to ready just to make the mirror match.
Deterministic, read-only and without network or provider credentials.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_FIELDS = (
    'id', 'subject', 'year', 'round', 'qno', 'q', 'points',
    'source_exam_code', 'source_url',
)


def index(rows: list[dict], label: str) -> dict[str, dict]:
    if not isinstance(rows, list) or not rows:
        raise ValueError(f'{label}: expected a non-empty JSON array')
    result = {}
    for offset, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'].strip():
            raise ValueError(f'{label}: invalid record at index {offset}')
        ident = row['id']
        if ident in result:
            raise ValueError(f'{label}: duplicate ID {ident}')
        result[ident] = row
    return result


def verify(root_rows: list[dict], cdn_rows: list[dict]) -> int:
    canonical = index(root_rows, 'auto/essays_auto.json')
    published = index(cdn_rows, 'cdn/auto/essays_auto.json')
    if canonical.keys() != published.keys():
        missing = sorted(canonical.keys() - published.keys())[:5]
        extra = sorted(published.keys() - canonical.keys())[:5]
        raise ValueError(f'essay mirror ID mismatch: missing={missing}, extra={extra}')
    for ident in sorted(canonical):
        for field in OFFICIAL_FIELDS:
            source, mirror = canonical[ident], published[ident]
            if (field in source) != (field in mirror) or source.get(field) != mirror.get(field):
                raise ValueError(f'{ident}.{field}: official essay/provenance field changed in CDN')
    return len(canonical)


def selftest() -> None:
    official = dict(
        id='E-SYNTH', subject='社會工作', year='115', round='第二次',
        qno='1', q='合成申論題', points=25, source_exam_code='115100',
        source_url='https://wwwq.moex.gov.tw/example', analysis_status='ready',
    )
    # Learning metadata can be ahead in root; never infer CDN review approval.
    assert verify([official], [dict(official, analysis_status='pending', topic='')]) == 1

    def rejected(rows: list[dict]) -> None:
        try:
            verify([official], rows)
        except ValueError:
            return
        raise AssertionError('unsafe CDN official essay drift was accepted')

    rejected([dict(official, q='另一個題幹')])
    rejected([dict(official, points=10)])
    rejected([dict(official, source_url='https://example.invalid')])
    rejected([])
    rejected([official, official])
    print('CDN AUTO ESSAY CORE SELFTEST OK: allowed metadata drift, blocked 5 official mismatches')


def main() -> int:
    args = argparse.ArgumentParser()
    args.add_argument('--selftest', action='store_true')
    args.add_argument('--root', type=Path, default=ROOT)
    ns = args.parse_args()
    if ns.selftest:
        selftest()
    else:
        canonical = json.loads((ns.root / 'auto/essays_auto.json').read_text(encoding='utf-8'))
        mirror = json.loads((ns.root / 'cdn/auto/essays_auto.json').read_text(encoding='utf-8'))
        count = verify(canonical, mirror)
        print(f'CDN AUTO ESSAY OFFICIAL CORE PARITY OK: {count} essays; enrichment excluded')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

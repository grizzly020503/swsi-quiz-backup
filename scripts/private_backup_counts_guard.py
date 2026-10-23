#!/usr/bin/env python3
"""Validate count-only backup/restore coverage, including admin allowlist and both Ops tables.

No DB or network IO. A legacy/missing/ambiguous count must not produce a green
restore proof. Count agreement alone still does not prove complete recovery.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

COUNT_FIELDS = ('auth_users', 'feedback_reports', 'usage_daily_rows',
                'ai_telemetry_client_daily_rows', 'ai_telemetry_5m_rows',
                'storage_buckets', 'storage_objects', 'admin_allowlist_rows',
                'ops_task_runs', 'ops_review_items')


def parse_snapshot(raw: str) -> dict:
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError('duplicate count field')
            out[key] = value
        return out
    if not raw or len(raw) > 16384:
        raise ValueError('missing or oversized count snapshot')
    return json.loads(raw, object_pairs_hook=unique)


def validate_counts(snapshot: object) -> dict:
    if not isinstance(snapshot, dict) or type(snapshot.get('count_schema_version')) is not int or snapshot['count_schema_version'] != 2:
        raise ValueError('count schema v2 required; export a new complete baseline')
    for key in COUNT_FIELDS:
        value = snapshot.get(key)
        if type(value) is not int or value < 0:
            raise ValueError('missing or invalid count: '+key)
    stamp = snapshot.get('captured_at_utc')
    try:
        if not isinstance(stamp, str) or len(stamp) > 64:
            raise ValueError
        parsed = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        raise ValueError('count capture requires a valid UTC timestamp') from None
    return snapshot


def compare_counts(source: object, target: object) -> None:
    source = validate_counts(source)
    target = validate_counts(target)
    mismatch = [key for key in COUNT_FIELDS if source[key] != target[key]]
    if mismatch:
        raise ValueError('restore count mismatch: '+', '.join(mismatch))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--target', type=Path)
    args = parser.parse_args()
    try:
        if args.source.stat().st_size > 16384:
            raise ValueError('oversized source snapshot')
        source = parse_snapshot(args.source.read_text(encoding='utf-8'))
        validate_counts(source)
        if args.target is not None:
            if args.target.stat().st_size > 16384:
                raise ValueError('oversized target snapshot')
            compare_counts(source, parse_snapshot(args.target.read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError):
        print('PRIVATE BACKUP COUNT GUARD REFUSED: missing, invalid or mismatched baseline',file=sys.stderr)
        return 64
    print('PRIVATE BACKUP COUNT BASELINE OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

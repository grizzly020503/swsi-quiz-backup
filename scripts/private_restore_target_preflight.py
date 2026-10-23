#!/usr/bin/env python3
"""Refuse restoring private data to a nonempty or ambiguously classified target.

The caller must separately verify local isolated database identity and consent.
Input contains count-only JSON, not personal records or connection credentials.
"""
from __future__ import annotations
import json
import os
import sys
from private_backup_counts_guard import REQUIRED_COUNTS, OPTIONAL_COUNTS, validate_counts

REQUIRED_EMPTY = tuple(key for key in REQUIRED_COUNTS if key != 'storage_buckets')


def validate(payload: object) -> None:
    values = validate_counts(payload)
    for key in REQUIRED_EMPTY:
        if values[key] != 0:
            raise ValueError('isolated target is not empty: '+key)
    for key in OPTIONAL_COUNTS:
        if values[key+'_present'] and values[key] != 0:
            raise ValueError('isolated target optional relation is not empty: '+key)
        # An absent optional relation is represented as null and false by validate_counts.


def main() -> int:
    try:
        raw = os.environ.get('SWSI_RESTORE_PREFLIGHT','')
        if not raw or len(raw)>16384:
            raise ValueError('missing or oversized count-only preflight')
        validate(json.loads(raw))
    except (ValueError,TypeError,json.JSONDecodeError):
        print('ISOLATED TARGET PREFLIGHT REFUSED: invalid or nonempty count-only snapshot',file=sys.stderr)
        return 64
    print('ISOLATED TARGET PRIVATE TABLE COUNT CHECK OK')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
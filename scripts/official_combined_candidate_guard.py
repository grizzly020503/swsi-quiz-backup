#!/usr/bin/env python3
"""Validate combined bytes before projecting the original 27-correction audit view.

The projection is validation-only: no file is modified and no PDF review cleared.
Pinned evidence is intentionally independent of the current manifest/lock values.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTION_SHA = '345c5a452679bcd63fae4348e0a65e9385cbb6489de52e045673e9cce42d79b9'
REPORT_SHA = '0206839664ae4b56f45d99f946cbeb63013fabda86e362e8b553183ec3a8ab08'


def checked_json(root, path, expected):
    raw = (root / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('combined evidence drift: ' + path)
    return json.loads(raw)


def view(root=ROOT):
    """Return baseline-27 rows/lock/manifest after verifying every combined byte."""
    root = Path(root)
    report = checked_json(root, 'audit/official_combined_data_integration_20261029.json', REPORT_SHA)
    projection = checked_json(root, 'audit/official_combined_base_projection_20261029.json', PROJECTION_SHA)
    for path, expected in report['output_sha256'].items():
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != expected:
            raise ValueError('combined payload drift: ' + path)
    manifest = json.loads((root / 'cdn/question-shards/manifest.json').read_text())
    lock = json.loads((root / 'data/official_exam_readonly.lock.json').read_text())
    rows = {}
    for entry in manifest['shards']:
        raw = (root / 'cdn/question-shards' / entry['file']).read_bytes()
        if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('combined manifest drift')
        for row in json.loads(raw)['questions']:
            if row['id'] in rows:
                raise ValueError('duplicate combined ID')
            rows[row['id']] = row
    if len(rows) != 4800 or len(projection['before_rows']) != 14:
        raise ValueError('combined coverage drift')
    from official_exam_readonly_guard import canonical_row, row_hash, MCQ_FIELDS
    for ident, before in projection['before_rows'].items():
        if any(rows[ident].get(f) != before.get(f) for f in ('answer', 'accepted_answers', 'grading_mode')):
            raise ValueError('combined grading drift: ' + ident)
        if row_hash(canonical_row(before, MCQ_FIELDS)) != projection['base_locks'][ident]:
            raise ValueError('combined preimage drift: ' + ident)
        rows[ident] = deepcopy(before)
        lock['mcq'][ident] = projection['base_locks'][ident]
    return rows, lock, projection['base_manifest']


if __name__ == '__main__':
    view()
    print('COMBINED CANDIDATE OK: exact 41-row dataset/locks/2 figures; 14-row projection bound to pinned evidence; no release approval')

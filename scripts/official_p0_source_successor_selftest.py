#!/usr/bin/env python3
"""Reject grading, unrelated corpus, approval and rollback-evidence tampering."""
import contextlib
import copy
import io
import json
import shutil
import tempfile
from pathlib import Path
import official_p0_source_successor_guard as guard
import official_two_source_owner_release_guard as predecessor


def main():
    guard.verify(predecessor.verify_predecessor)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for folder in ('cdn/question-shards', 'data', 'audit'):
            (root/folder).mkdir(parents=True, exist_ok=True)
        shutil.copytree(guard.ROOT/'cdn/question-shards', root/'cdn/question-shards', dirs_exist_ok=True)
        for name in ('data/official_exam_readonly.lock.json',
                     'audit/official_p0_source_successor_20261112.json',
                     'audit/official_p0_option_order_owner_approval_20261112.json'):
            shutil.copyfile(guard.ROOT/name, root/name)
        original_root = guard.ROOT
        guard.ROOT = root
        cases = [
            ('cdn/question-shards/104-2.json', lambda d: d['questions'][0].update(answer='INVALID')),
            ('cdn/question-shards/manifest.json', lambda d: d.update(dataset_revision='old-cache')),
            ('data/official_exam_readonly.lock.json', lambda d: d['essays'].update({next(iter(d['essays'])):'tampered'})),
            ('audit/official_p0_option_order_owner_approval_20261112.json', lambda d: d.update(official_source_approved=False)),
            ('audit/official_p0_source_successor_20261112.json', lambda d: d['before_rows']['SP104-2-37'].update(answer='D')),
        ]
        try:
            for name, mutate in cases:
                path = root/name
                raw = path.read_bytes()
                data = json.loads(raw)
                mutate(data)
                # Use canonical compact serialization for the shard negative.
                path.write_bytes(guard.encode(data))
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        guard.verify(predecessor.verify_predecessor)
                except (AssertionError, KeyError):
                    pass
                else:
                    raise AssertionError('tamper accepted: '+name)
                finally:
                    path.write_bytes(raw)
        finally:
            guard.ROOT = original_root
    print('P0 SUCCESSOR NEGATIVES PASS: 5 unauthorized changes rejected')

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Reject grading, unrelated corpus, approval and rollback-evidence tampering."""
import contextlib
import copy
import io
import json
import shutil
import tempfile
from pathlib import Path
import official_ds_owner_release_guard as guard
import official_two_source_owner_release_guard as predecessor


def main():
    guard.verify(predecessor.verify_predecessor)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for folder in ('cdn/question-shards', 'data', 'audit'):
            (root/folder).mkdir(parents=True, exist_ok=True)
        shutil.copytree(guard.ROOT/'cdn/question-shards', root/'cdn/question-shards', dirs_exist_ok=True)
        shutil.copytree(guard.ROOT/'audit', root/'audit', dirs_exist_ok=True)
        shutil.copyfile(guard.ROOT/'data/official_exam_readonly.lock.json', root/'data/official_exam_readonly.lock.json')
        shutil.copyfile(guard.ROOT/'cdn/index.html', root/'cdn/index.html')
        original_root = guard.ROOT
        guard.ROOT = root
        cases = [
            ('cdn/question-shards/104-1.json', lambda d: next(r for r in d['questions'] if r['id']=='DS-104-1-22').update(answer='D')),
            ('cdn/question-shards/105-1.json', lambda d: d['questions'][0].update(question='unapproved')),
            ('data/official_exam_readonly.lock.json', lambda d: d['essays'].update({next(iter(d['essays'])):'tampered'})),
            ('audit/official_ds_owner_release_20261113.json', lambda d: d.update(owner_approved=False)),
            ('audit/official_ds_owner_release_20261113.json', lambda d: d['before_rows']['DS-104-1-22'].update(answer='D')),
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
    print('DS RELEASE NEGATIVES PASS: 5 unauthorized changes rejected')

if __name__ == '__main__':
    main()

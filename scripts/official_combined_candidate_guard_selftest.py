#!/usr/bin/env python3
"""Reject artifact and evidence tampering, including recomputed manifests/locks."""
from pathlib import Path
import hashlib
import json
import shutil
import tempfile
import unittest
import official_combined_candidate_guard as guard


class CombinedGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = json.loads((guard.ROOT / 'audit/official_combined_data_integration_20261029.json').read_text())
        for name in list(self.report['output_sha256']) + ['audit/official_combined_data_integration_20261029.json', 'audit/official_combined_base_projection_20261029.json']:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(guard.ROOT / name, target)

    def test_current_combined_view(self):
        rows, lock, manifest = guard.view(self.root)
        self.assertEqual(len(rows), 4800)
        self.assertEqual(len(lock['mcq']), 4800)
        self.assertEqual(manifest['dataset_revision'], '041e28799fd3fd82b7e1')

    def test_unrelated_text_and_recomputed_manifest_rejected(self):
        path = self.root / 'cdn/question-shards/104-1.json'
        doc = json.loads(path.read_text()); doc['questions'][0]['question'] += 'UNAPPROVED'
        path.write_text(json.dumps(doc, ensure_ascii=False))
        mp = self.root / 'cdn/question-shards/manifest.json'; manifest = json.loads(mp.read_text())
        row = next(e for e in manifest['shards'] if e['file'] == path.name)
        row.update(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        mp.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'payload drift'):
            guard.view(self.root)

    def test_grading_and_recomputed_lock_rejected(self):
        path = self.root / 'data/official_exam_readonly.lock.json'
        lock = json.loads(path.read_text()); lock['mcq'][next(iter(lock['mcq']))] = '0' * 64
        path.write_text(json.dumps(lock))
        with self.assertRaisesRegex(ValueError, 'payload drift'):
            guard.view(self.root)

    def test_recomputed_report_rejected(self):
        path = self.root / 'audit/official_combined_data_integration_20261029.json'
        doc = json.loads(path.read_text()); doc['output_sha256']['cdn/question-shards/104-1.json'] = '0' * 64
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, 'evidence drift'):
            guard.view(self.root)

    def test_projection_preimage_rejected(self):
        path = self.root / 'audit/official_combined_base_projection_20261029.json'
        doc = json.loads(path.read_text()); next(iter(doc['before_rows'].values()))['answer'] = 'UNAPPROVED'
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, 'evidence drift'):
            guard.view(self.root)

    def test_wrong_figure_rejected(self):
        path = self.root / 'official-figures/DS-113-2-13.png'
        path.write_bytes(path.read_bytes() + b'WRONG')
        with self.assertRaisesRegex(ValueError, 'payload drift'):
            guard.view(self.root)


if __name__ == '__main__':
    unittest.main()

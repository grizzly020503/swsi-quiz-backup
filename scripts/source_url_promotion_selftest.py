#!/usr/bin/env python3
"""Zero-network tests: precise Official Core preservation and fail-closed source URL staging."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from source_url_promotion_stage import stage, render_session, encode

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'data/source_url_promotion_config.json'

class PromotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
        cls.sample = (ROOT / 'cdn/question-shards/104-1.json').read_bytes()

    def test_all_22_shards_exact_target(self):
        output, report = stage(ROOT, self.cfg)
        self.assertEqual(len(output), 23)
        self.assertEqual(report['changed_source_urls'], 3920)
        self.assertEqual(report['historical_questions'], 4400)
        self.assertEqual(report['other_fields_changed'], 0)
        self.assertFalse(report['production_db_written'])
        self.assertFalse(report['main_shards_written'])

    def test_latest_exam_shard_tampering_is_rejected(self):
        from unittest.mock import patch
        real_read = Path.read_bytes

        def corrupt_latest(path):
            raw = real_read(path)
            if path.name == '115-1.json':
                return raw + b' '\n            return raw

        with patch.object(Path, 'read_bytes', corrupt_latest):
            with self.assertRaisesRegex(ValueError, '115-1.json: manifest SHA256/bytes mismatch'):
                stage(ROOT, self.cfg)

    def test_latest_exam_shard_missing_is_rejected(self):
        from unittest.mock import patch
        real_read = Path.read_bytes

        def missing_latest(path):
            if path.name == '115-2.json':
                raise FileNotFoundError('synthetic missing latest shard')
            return real_read(path)

        with patch.object(Path, 'read_bytes', missing_latest):
            with self.assertRaises(FileNotFoundError):
                stage(ROOT, self.cfg)

    def test_changed_answer_is_rejected(self):
        question_doc = json.loads(self.sample)
        question_doc['questions'][0]['answer'] = 'ZZ'
        with self.assertRaisesRegex(ValueError, 'drifted'):
            render_session(encode(question_doc), '104-1', self.cfg)

    def test_changed_source_url_is_rejected(self):
        question_doc = json.loads(self.sample)
        question_doc['questions'][0]['source_url'] += '&fake=1'
        with self.assertRaisesRegex(ValueError, 'drifted'):
            render_session(encode(question_doc), '104-1', self.cfg)

    def test_wrong_target_official_mapping_rejected(self):
        bad = copy.deepcopy(self.cfg)
        bad['mapping']['104030/0302'] = ['999','9999']
        with self.assertRaisesRegex(ValueError, 'target mismatch'):
            render_session(self.sample, '104-1', bad)

    def test_missing_query_order_exception_rejected(self):
        bad = copy.deepcopy(self.cfg)
        bad['retain_c_first_ids'] = [x for x in bad['retain_c_first_ids'] if x != 'DS-104-1-01']
        with self.assertRaisesRegex(ValueError, 'target mismatch'):
            render_session(self.sample, '104-1', bad)

    def test_false_promotion_status_rejected(self):
        bad = dict(self.cfg)
        bad['status'] = 'DEPLOYED'
        with self.assertRaisesRegex(ValueError, 'unrecognized'):
            stage(ROOT, bad)

    def test_bad_manifest_digest_rejected(self):
        bad = dict(self.cfg)
        bad['expected_manifest_after_git_blob'] = '0'*40
        with self.assertRaisesRegex(ValueError, 'manifest target'):
            stage(ROOT, bad)

if __name__ == '__main__':
    unittest.main()
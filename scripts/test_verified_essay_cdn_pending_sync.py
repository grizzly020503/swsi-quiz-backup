#!/usr/bin/env python3
"""Deterministic synthetic regression tests; never actual human essay grading."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from verified_essay_cdn_pending_sync import (
    approved_shape, collect_official, indexed, staged_rows, verified_moex_url,
)

SUBJECTS = [
    ('社會工作', '0301', 'SW'),
    ('社會工作直接服務', '0302', 'DS'),
    ('社會政策與社會立法', '0303', 'SP'),
    ('人類行為與社會環境', '0304', 'HBSE'),
    ('社會工作研究方法', '0305', 'R'),
]
EXAM = '116100'
TYPE = '專門職業及技術人員高等考試社會工作師'


def exam_payload():
    questions, essays = [], []
    for subject, code, prefix in SUBJECTS:
        url = f'https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=103&code={EXAM}&q=1&s={code}&t=Q'
        for i in range(1, 41):
            questions.append({'id': f'{prefix}-116-2-{i:03d}', 'subject': subject,
                              'year': '116', 'round': '第二次', 'qno': str(i),
                              'source_exam_code': EXAM, 'source_url': url})
        for i in (1, 2):
            essays.append({'id': f'E-116-2-{prefix}-{i}', 'subject': subject,
                           'year': '116', 'round': '第二次', 'qno': str(i),
                           'q': '合成申論題，不是考選部真題', 'points': '20',
                           'source_exam_code': EXAM, 'source_url': url,
                           'analysis_status': 'pending'})
    return {'exam_type': TYPE, 'exam_code': EXAM, 'roc_year': '116',
            'round': '第二次', 'questions': questions, 'essays': essays}


def registry():
    return {'schema_version': 1, 'exam_type': TYPE, 'profiles': [{
        'status': 'approved', 'effective_from': {'roc_year': '104', 'round': '第一次'},
        'effective_to': None,
        'exam_code_suffixes': {'第一次': '030', '第二次': '100'},
        'subjects': [{'name': x, 'code': c, 'prefix': p} for x, c, p in SUBJECTS],
        'mcq': {'expected_total': 200, 'per_subject': 40, 'qno_min': 1, 'qno_max': 40},
        'essay': {'expected_total': 10, 'per_subject': 2, 'qno_min': 1, 'qno_max': 2},
    }]}


class VerifiedFutureEssayTest(unittest.TestCase):
    def setUp(self):
        self.t = TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.base = Path(self.t.name)
        self.inc = self.base / 'incoming'
        self.inc.mkdir()
        self.src = exam_payload()
        self.reg = self.base / 'registry.json'
        self.reg.write_text(json.dumps(registry(), ensure_ascii=False), encoding='utf-8')
        self.write_source()

    def write_source(self):
        (self.inc / f'{EXAM}.json').write_text(json.dumps(self.src, ensure_ascii=False), encoding='utf-8')

    def collect(self):
        return collect_official(self.inc, self.reg)

    def test_complete_approved_116_exam(self):
        self.assertEqual(len(self.collect()), 10)

    def test_missing_mcq_fails_closed(self):
        self.src['questions'].pop()
        self.write_source()
        with self.assertRaisesRegex(ValueError, 'approved total'):
            self.collect()

    def test_bad_subject_distribution_fails_closed(self):
        self.src['essays'][0]['subject'] = SUBJECTS[1][0]
        self.write_source()
        with self.assertRaisesRegex(ValueError, 'number distribution'):
            self.collect()

    def test_wrong_exam_or_source_fails_closed(self):
        for replacement in ['code=115100', 's=0305', 't=M', 'q=2', 'c=999']:
            self.src = exam_payload()
            self.src['essays'][0]['source_url'] = (
                self.src['essays'][0]['source_url'].replace(
                    {'code=115100': 'code=116100', 's=0305': 's=0301',
                     't=M': 't=Q', 'q=2': 'q=1', 'c=999': 'c=103'}[replacement], replacement
                )
            )
            self.write_source()
            with self.subTest(replacement=replacement):
                with self.assertRaisesRegex(ValueError, 'provenance missing'):
                    self.collect()

    def test_unknown_field_fails_closed(self):
        self.src['essays'][0]['private_student'] = 'not publishable'
        self.write_source()
        with self.assertRaisesRegex(ValueError, 'unknown incoming fields'):
            self.collect()

    def test_wrong_id_fails_closed(self):
        self.src['essays'][0]['id'] = 'E-116-2-SP-1'
        self.write_source()
        with self.assertRaisesRegex(ValueError, 'essay ID disagrees'):
            self.collect()

    def test_future_unapproved_scheme_fails_closed(self):
        data = registry()
        data['profiles'][0]['effective_to'] = {'roc_year': '115', 'round': '第二次'}
        self.reg.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'not approved'):
            self.collect()

    def test_pending_only_and_preserve_reviewed(self):
        incoming = self.collect()
        source = deepcopy(self.src['essays'])
        source[0]['analysis_status'] = 'ready'  # root status is NOT publication authority
        cdn = [dict(source[0], analysis_status='pending', topic=None)]
        result, count = staged_rows(incoming, source, cdn)
        self.assertEqual(count, 9)
        self.assertEqual(result[0], cdn[0])
        self.assertTrue(all(x['analysis_status'] == 'pending' for x in result))
        self.assertTrue(all(x['topic'] is None for x in result[1:]))
        again, additions = staged_rows(incoming, source, result)
        self.assertEqual(additions, 0)
        self.assertEqual(again, result)

    def test_existing_official_text_cannot_be_overwritten(self):
        incoming = self.collect()
        old = deepcopy(self.src['essays'][0])
        bad = dict(old, q='不是同一份考選部官方試題')
        with self.assertRaisesRegex(ValueError, 'official source changed'):
            staged_rows(incoming, self.src['essays'], [bad])

    def test_missing_or_duplicate_ids_fails_closed(self):
        incoming = self.collect()
        rows = deepcopy(self.src['essays'])
        with self.assertRaisesRegex(ValueError, 'IDs differ'):
            staged_rows(incoming, rows[:-1], [])
        with self.assertRaisesRegex(ValueError, 'duplicate id'):
            staged_rows(incoming, rows, [rows[0], rows[0]])

    def test_cli_read_only_then_stage_and_repeat(self):
        self.write_source()
        root = self.base / 'root.json'
        cdn = self.base / 'cdn.json'
        canonical = deepcopy(self.src['essays'])
        for item in canonical:
            item['analysis_status'] = 'ready'
            item['topic'] = '未驗證內容'
        existing = [{**self.src['essays'][0], 'analysis_status': 'pending'}]
        root.write_text(json.dumps(canonical, ensure_ascii=False), encoding='utf-8')
        original = json.dumps(existing, ensure_ascii=False).encode('utf-8')
        cdn.write_bytes(original)
        cmd = [sys.executable, str(Path(__file__).with_name('verified_essay_cdn_pending_sync.py')),
               '--incoming', str(self.inc), '--auto', str(root),
               '--cdn', str(cdn), '--registry', str(self.reg)]
        dry = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertEqual(cdn.read_bytes(), original)
        stage = subprocess.run(cmd + ['--stage'], capture_output=True, text=True)
        self.assertEqual(stage.returncode, 0, stage.stderr)
        rows = json.loads(cdn.read_text(encoding='utf-8'))
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0], existing[0])
        self.assertTrue(all(row['analysis_status'] == 'pending' for row in rows))
        staged_bytes = cdn.read_bytes()
        repeat = subprocess.run(cmd + ['--stage'], capture_output=True, text=True)
        self.assertEqual(repeat.returncode, 0, repeat.stderr)
        self.assertEqual(cdn.read_bytes(), staged_bytes)


if __name__ == '__main__':
    unittest.main()

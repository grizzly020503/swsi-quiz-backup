#!/usr/bin/env python3
"""Pure count-only regression; no production rows, DB, filesystem or network."""
import unittest
from private_backup_counts_guard import COUNT_FIELDS, compare_counts, parse_snapshot, validate_counts

class CountGuardTests(unittest.TestCase):
    def setUp(self):
        self.base={'count_schema_version':2,'captured_at_utc':'2026-10-16T12:00:00Z',**{k:0 for k in COUNT_FIELDS}}

    def test_complete_matching_baseline(self):
        self.assertIsNone(compare_counts(self.base,dict(self.base)))

    def test_missing_fields_fail_closed(self):
        for key in COUNT_FIELDS:
            row=dict(self.base);row.pop(key)
            with self.subTest(key=key),self.assertRaises(ValueError):validate_counts(row)

    def test_ambiguous_counts_rejected(self):
        for key in COUNT_FIELDS:
            for value in (False,True,0.0,'0',None,-1):
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):validate_counts({**self.base,key:value})

    def test_each_covered_table_mismatch_rejected(self):
        for key in COUNT_FIELDS:
            with self.subTest(key=key),self.assertRaises(ValueError):compare_counts(self.base,{**self.base,key:1})

    def test_both_ops_tables_require_complete_restore_evidence(self):
        for key in ('ops_task_runs','ops_review_items'):
            self.assertIn(key,COUNT_FIELDS)
            incomplete=dict(self.base);incomplete.pop(key)
            with self.subTest(key=key),self.assertRaises(ValueError):compare_counts(incomplete,self.base)
            with self.subTest(key=key),self.assertRaises(ValueError):compare_counts(self.base,incomplete)
            with self.subTest(key=key),self.assertRaises(ValueError):compare_counts({**self.base,key:1},self.base)

    def test_legacy_or_ambiguous_versions_rejected(self):
        for value in (None,1,'2',True,2.0):
            with self.subTest(value=value),self.assertRaises(ValueError):validate_counts({**self.base,'count_schema_version':value})

    def test_invalid_capture_timestamps_rejected(self):
        for stamp in ('','not-a-date','2026-10-16T12:00:00','2026-10-16T12:00:00+08:00',None):
            with self.subTest(stamp=stamp),self.assertRaises(ValueError):validate_counts({**self.base,'captured_at_utc':stamp})

    def test_duplicate_or_oversized_json_rejected(self):
        for raw in ('{"admin_allowlist_rows":1,"admin_allowlist_rows":0}', 'x'*16385, '', '{'):
            with self.subTest(size=len(raw)),self.assertRaises(ValueError):parse_snapshot(raw)

if __name__=='__main__':unittest.main()

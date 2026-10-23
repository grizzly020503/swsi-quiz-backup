#!/usr/bin/env python3
"""Pure synthetic count-only tests; no DB/network connections or real records."""
import unittest
from private_backup_counts_guard import COUNT_FIELDS, REQUIRED_COUNTS, OPTIONAL_COUNTS,compare_counts,parse_snapshot,validate_counts

class CountGuardTests(unittest.TestCase):
    def setUp(self):
        self.base={'count_schema_version':3,'captured_at_utc':'2026-10-23T02:00:00Z',
                   **{k:0 for k in REQUIRED_COUNTS},
                   **{k:None for k in OPTIONAL_COUNTS},
                   **{k+'_present':False for k in OPTIONAL_COUNTS}}
    def test_complete_missing_ops_is_explicit(self):
        self.assertIsNone(compare_counts(self.base,dict(self.base)))
    def test_present_optional_tables_allow_zero_or_more(self):
        d=dict(self.base);d.update(ops_task_runs=10,ops_task_runs_present=True)
        self.assertIsNone(compare_counts(d,d.copy()))
    def test_missing_required_fields(self):
        for k in (*REQUIRED_COUNTS, *OPTIONAL_COUNTS, *(x+'_present' for x in OPTIONAL_COUNTS)):
            d=dict(self.base);d.pop(k)
            with self.subTest(k=k),self.assertRaises(ValueError):validate_counts(d)
    def test_invalid_required_counts(self):
        for k in REQUIRED_COUNTS:
            for v in (False,True,'0',0.0,None,-1):
                with self.subTest(k=k,v=v),self.assertRaises(ValueError):validate_counts({**self.base,k:v})
    def test_optional_absent_count_never_zero(self):
        for k in OPTIONAL_COUNTS:
            for v in (0,1,'0',False):
                with self.subTest(k=k,v=v),self.assertRaises(ValueError):validate_counts({**self.base,k:v})
    def test_optional_present_requires_int(self):
        for k in OPTIONAL_COUNTS:
            for v in (None,False,True,0.0,'0',-1):
                with self.subTest(k=k,v=v),self.assertRaises(ValueError):validate_counts({**self.base,k+'_present':True,k:v})
    def test_presence_drift_rejected(self):
        for k in OPTIONAL_COUNTS:
            t={**self.base,k+'_present':True,k:0}
            with self.subTest(k=k),self.assertRaises(ValueError):compare_counts(self.base,t)
    def test_row_count_drift_rejected(self):
        for k in COUNT_FIELDS:
            src=dict(self.base);tgt=dict(self.base)
            if k in OPTIONAL_COUNTS:
                src.update({k+'_present':True,k:0});tgt.update({k+'_present':True,k:1})
            else:
                tgt[k]=1
            with self.subTest(k=k),self.assertRaises(ValueError):compare_counts(src,tgt)
    def test_version_2_or_ambiguous_rejected(self):
        for v in (None,1,2,'3',True,3.0):
            with self.subTest(v=v),self.assertRaises(ValueError):validate_counts({**self.base,'count_schema_version':v})
    def test_invalid_timestamps(self):
        for stamp in ('','junk','2026-10-23T01:00:00','2026-10-23T01:00:00+08:00',None):
            with self.subTest(stamp=stamp),self.assertRaises(ValueError):validate_counts({**self.base,'captured_at_utc':stamp})
    def test_duplicate_json_rejected(self):
        for txt in ('{"a":0,"a":0}','x'*16385,'','{'):
            with self.subTest(l=len(txt)),self.assertRaises(ValueError):parse_snapshot(txt)

if __name__=='__main__':unittest.main()
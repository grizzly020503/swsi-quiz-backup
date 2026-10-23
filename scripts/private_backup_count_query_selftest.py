#!/usr/bin/env python3
"""Synthetic tests only; never opens real PostgreSQL or production credentials."""
import sys
import unittest
from unittest import mock
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from private_backup_count_query import build_count_sql, detect_sql, parse_one_json, run_psql, capture

class QueryTests(unittest.TestCase):
    def test_absent(self):
        sql=build_count_sql({'ops_task_runs':'absent','ops_review_items':'absent'})
        self.assertIn("'ops_task_runs', NULL::bigint",sql)
        self.assertIn("'ops_task_runs_present', false",sql)
        self.assertIn("'ops_review_items', NULL::bigint",sql)
        self.assertNotIn('FROM public.swsi_ops_task_runs)',sql)
        self.assertNotIn('FROM public.swsi_ops_review_items)',sql)
    def test_present(self):
        sql=build_count_sql({'ops_task_runs':'table','ops_review_items':'table'})
        self.assertIn('FROM public.swsi_ops_task_runs)',sql)
        self.assertIn('FROM public.swsi_ops_review_items)',sql)
        self.assertIn("'ops_task_runs_present', true",sql)
    def test_mixed(self):
        sql=build_count_sql({'ops_task_runs':'table','ops_review_items':'absent'})
        self.assertIn('FROM public.swsi_ops_task_runs)',sql)
        self.assertNotIn('FROM public.swsi_ops_review_items)',sql)
    def test_unknown_schema_rejected(self):
        for d in ({}, {'ops_task_runs':'table'}, {'ops_task_runs':'view','ops_review_items':'absent'}, {'ops_task_runs':'absent','ops_review_items':False}, {'ops_task_runs':'absent','ops_review_items':'absent','extra':'table'}):
            with self.subTest(d=d),self.assertRaises(ValueError):build_count_sql(d)
    def test_detect_only_fixed_allowlist(self):
        sql=detect_sql()
        self.assertIn("to_regclass('public.swsi_ops_task_runs')",sql)
        self.assertIn("to_regclass('public.swsi_ops_review_items')",sql)
    def test_json_duplicate(self):
        for raw in ('{"x":1,"x":2}', '[]', 'garbage','', 'x'*16385):
            with self.subTest(raw=raw[:12]),self.assertRaises((ValueError,TypeError)):parse_one_json(raw)
    def test_psql_never_logs_credentials(self):
        with mock.patch('subprocess.run') as run:
            run.return_value.returncode=1
            run.return_value.stderr='password=SECRET'
            with self.assertRaisesRegex(RuntimeError, '^read-only count query failed$') as ctx:
                run_psql('postgresql://user:SECRET@127.0.0.1/db','SELECT 1;')
            self.assertNotIn('SECRET',str(ctx.exception))
    def test_psql_refuses_routing_override(self):
        with mock.patch.dict('os.environ', {'PGHOST':'evil'}, clear=True):
            with self.assertRaises(ValueError):run_psql('postgresql://u:p@127.0.0.1/db','SELECT 1')
    def test_psql_sets_read_only(self):
        with mock.patch.dict('os.environ',{},clear=True),mock.patch('subprocess.run') as run:
            run.return_value.returncode=0
            run.return_value.stdout='{"ok":true}'
            self.assertEqual(run_psql('postgresql://u:p@127.0.0.1/db','SELECT 1'),{'ok':True})
            self.assertIn('default_transaction_read_only=on',run.call_args.kwargs['env']['PGOPTIONS'])
            self.assertEqual(run.call_args.kwargs['input'],'SELECT 1')
if __name__=='__main__':unittest.main()
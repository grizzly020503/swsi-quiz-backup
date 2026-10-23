#!/usr/bin/env python3
"""Real PostgreSQL 17 synthetic integration test for schema-aware private counts.

Only runs against a disposable CI service with an explicitly named local fixture
DB and a synthetic password. NEVER connects to Supabase or uses real student data.
"""
from __future__ import annotations
import os
import subprocess
from private_backup_count_query import build_count_sql, detect_sql, parse_one_json
from private_backup_counts_guard import validate_counts, compare_counts
from private_restore_target_preflight import validate as empty_target

TEST_URL = 'postgresql://swsi_fixture:ci-only-synthetic-password@127.0.0.1:5432/swsi_fixture'


def psql(sql: str, *, readonly: bool = False) -> str:
    env=dict(os.environ)
    # psql routing must not inherit unexpected environment overrides.
    for k in tuple(env):
        if k.upper().startswith('PG'):
            del env[k]
    if readonly:
        env['PGOPTIONS']='-c default_transaction_read_only=on'
    p=subprocess.run(['psql','-X','-qAt','--set=ON_ERROR_STOP=1','--dbname',TEST_URL],
                     input=sql,text=True,capture_output=True,env=env,timeout=35)
    if p.returncode:
        raise RuntimeError('synthetic PG17 query failed')
    return p.stdout.strip()


def capture():
    status=parse_one_json(psql(detect_sql(),readonly=True))
    counts=validate_counts(parse_one_json(psql(build_count_sql(status),readonly=True)))
    return status,counts


def main():
    if os.environ.get('SWSI_SYNTHETIC_PG17_CI')!='I_CONFIRM_DISPOSABLE_FIXTURE':
        raise SystemExit('refuses to run outside explicitly marked disposable CI fixture')
    # Names and data are synthetic. Only disposable test DB is targeted.
    psql('''
      CREATE SCHEMA IF NOT EXISTS auth;
      CREATE SCHEMA IF NOT EXISTS storage;
      CREATE TABLE auth.users (id integer);
      CREATE TABLE storage.buckets (id integer);
      CREATE TABLE storage.objects (id integer);
      CREATE TABLE public.swsi_feedback_reports (id integer);
      CREATE TABLE public.swsi_usage_daily (id integer);
      CREATE TABLE public.swsi_ai_telemetry_client_daily (id integer);
      CREATE TABLE public.swsi_ai_telemetry_5m (id integer);
      CREATE TABLE public.swsi_admin_users (id integer);
    ''')
    # No Ops relations: schema v3 must mark absent+null, not zero.
    before_status,before=capture()
    assert before_status=={'ops_task_runs':'absent','ops_review_items':'absent'}
    assert before['ops_task_runs_present'] is False and before['ops_task_runs'] is None
    assert before['ops_review_items_present'] is False and before['ops_review_items'] is None
    empty_target(before)
    print('PG17 ABSENT OPTIONAL RELATIONS PASS')

    psql('CREATE TABLE public.swsi_ops_task_runs (id integer); CREATE TABLE public.swsi_ops_review_items (id integer);')
    status,present_zero=capture()
    assert status=={'ops_task_runs':'table','ops_review_items':'table'}
    assert all(present_zero[k]==0 and present_zero[k+'_present'] is True for k in ('ops_task_runs','ops_review_items'))
    empty_target(present_zero)
    try:
        compare_counts(before,present_zero)
    except ValueError:
        pass
    else:
        raise AssertionError('schema-presence drift accepted')
    print('PG17 PRESENT EMPTY OPTIONAL RELATIONS PASS')

    psql('INSERT INTO public.swsi_ops_task_runs VALUES (101); INSERT INTO public.swsi_admin_users VALUES (7);')
    _,populated=capture()
    assert populated['ops_task_runs']==1 and populated['admin_allowlist_rows']==1
    try:
        empty_target(populated)
    except ValueError:
        pass
    else:
        raise AssertionError('nonempty isolated target accepted')
    print('PG17 NONEMPTY PRIVATE TABLE REJECTED PASS')

    # The new snapshot probe explicitly uses read-only sessions, also at PG layer.
    try:
        psql('INSERT INTO public.swsi_ops_task_runs VALUES (999);',readonly=True)
    except RuntimeError:
        pass
    else:
        raise AssertionError('readonly PostgreSQL query unexpectedly permitted INSERT')
    count=int(psql('SELECT count(*) FROM public.swsi_ops_task_runs;'))
    assert count==1,count
    print('PG17 READONLY SESSION BLOCKS MUTATION PASS')
    print('SWSI PRIVATE BACKUP PG17 SYNTHETIC INTEGRATION OK 4/4')

if __name__=='__main__':
    main()
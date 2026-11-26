#!/usr/bin/env python3
"""Behavioural check of the AI-queue auto-enable trigger on a disposable Postgres.

Builds the minimum of public.questions and the AI queue config in an empty
database, loads the repository's own trigger functions (reset on official
change, auto-enable) and the newest migration that defines
trg_auto_enable_ai_pending, then checks:

* the 2026-11-24 failure: an official text repair that SETs only question /
  opt_* resets the row to pending, and the queue must be re-enabled;
* unrelated updates, rows without an official source, rows that have used
  their 3 attempts and whitespace-only edits must not enable it;
* an INSERT of a pending official row and an explicit status change to
  pending enable it; an already-enabled queue is not re-enabled.

The old trigger definition is checked first and must reproduce the bug, so
the test shows it can tell the two apart. Everything runs in one transaction
that is rolled back. The real enable function needs pg_cron, so a stand-in
records the calls instead.

Refuses to run unless SWSI_DISPOSABLE_PG=I_CONFIRM_DISPOSABLE_FIXTURE and the
target database has no public.questions table. Connection settings come from
the usual PG* environment variables.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / 'supabase/migrations'
PASS = 'AI_QUEUE_AUTO_ENABLE_PG_SELFTEST_PASS'


def psql(sql):
    done = subprocess.run(['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-f', '-'],
                          input=sql, capture_output=True, text=True, timeout=120)
    return done.returncode, done.stdout, done.stderr


def block(path, name, end):
    text = (MIGRATIONS / path).read_text(encoding='utf-8')
    m = re.search(r'create or replace function public\.' + re.escape(name) + r'\(\).*?\n'
                  + re.escape(end) + ';', text, re.S | re.I)
    if not m:
        raise SystemExit('function %s not found in %s' % (name, path))
    return m.group(0)


def newest_trigger_migration():
    found = sorted(p for p in MIGRATIONS.glob('*.sql')
                   if re.search(r'create trigger trg_auto_enable_ai_pending\b',
                                p.read_text(encoding='utf-8'), re.I))
    if not found:
        raise SystemExit('no migration defines trg_auto_enable_ai_pending')
    return found[-1]


def build_sql():
    auto_enable = block('20260825_ai_analysis_automation.sql',
                        'auto_enable_ai_for_pending_question', '$fn$')
    reset = block('20261124120000_reset_ai_ignore_whitespace_only_changes.sql',
                  'reset_ai_analysis_on_official_change', '$function$')
    migration = newest_trigger_migration()
    return '\n'.join([
        'begin;',
        '''create table public.questions (
  id text primary key, source_exam_code text,
  question text, opt_a text, opt_b text, opt_c text, opt_d text,
  answer text, accepted_answers text[], grading_mode text,
  major text, topic text, keywords text,
  exp_why text, exp_others text, exp_trap text, exp_raw text,
  mnemonic text, extension text, law text, mistake text,
  analysis_status text, analysis_attempts integer not null default 0,
  analysis_error text, analysis_started_at timestamptz,
  analysis_completed_at timestamptz, analysis_last_attempt_at timestamptz);''',
        '''create table public.ai_analysis_job_config (
  id boolean primary key default true check (id = true),
  job_key text not null default 'selftest', enabled boolean not null,
  updated_at timestamptz not null default now());
insert into public.ai_analysis_job_config(id, enabled) values (true, false);
create table public.selftest_step (step text not null);
insert into public.selftest_step values ('setup');
create table public.selftest_enable_calls (at_step text not null);''',
        # Stand-in for the real function, which schedules the pg_cron job.
        '''create function public.enable_swsi_ai_analysis() returns void
language plpgsql as $$
begin
  update public.ai_analysis_job_config set enabled = true, updated_at = now() where id = true;
  insert into public.selftest_enable_calls select step from public.selftest_step;
end $$;
create function public.selftest_case(p_step text, p_enabled boolean) returns void
language sql as $$
  update public.selftest_step set step = p_step;
  update public.ai_analysis_job_config set enabled = p_enabled;
$$;
create function public.selftest_calls(p_step text) returns bigint
language sql as $$ select count(*) from public.selftest_enable_calls where at_step = p_step $$;
create function public.selftest_expect(p_label text, p_actual text, p_expected text) returns void
language plpgsql as $$
begin
  if p_actual is distinct from p_expected then
    raise exception 'SELFTEST FAIL %: expected %, got %', p_label, p_expected, p_actual;
  end if;
end $$;''',
        auto_enable,
        "alter function public.auto_enable_ai_for_pending_question() set search_path = '';",
        reset,
        '''create trigger trg_reset_ai_on_official_change
before update of question, opt_a, opt_b, opt_c, opt_d, answer, accepted_answers, grading_mode
on public.questions for each row execute function public.reset_ai_analysis_on_official_change();''',
        # Fixture rows go in before any auto-enable trigger exists.
        '''insert into public.questions
  (id, source_exam_code, question, opt_a, opt_b, opt_c, opt_d, answer, exp_why,
   analysis_status, analysis_attempts) values
  ('Q-OLD', 'EXAM', 'old stem', 'a', 'b', 'c', 'd', 'A', 'old explanation', 'ready', 0),
  ('Q-FIX', 'EXAM', 'old stem', 'a', 'b', 'c', 'd', 'A', 'old explanation', 'ready', 0),
  ('Q-ENABLED', 'EXAM', 'old stem', 'a', 'b', 'c', 'd', 'A', 'old explanation', 'ready', 0),
  ('Q-READY', 'EXAM', 'old stem', 'a', 'b', 'c', 'd', 'A', 'old explanation', 'ready', 0),
  ('Q-WS', 'EXAM', 'old stem', 'a', 'b', 'c', 'd', 'A', 'old explanation', 'ready', 0),
  ('Q-NOSRC', null, 'old stem', 'a', 'b', 'c', 'd', 'A', 'old explanation', 'ready', 0),
  ('Q-EXHAUSTED', 'EXAM', 'old stem', 'a', 'b', 'c', 'd', 'A', null, 'pending', 3),
  ('Q-READY2', 'EXAM', 'old stem', 'a', 'b', 'c', 'd', 'A', 'old explanation', 'ready', 0);''',
        # 1. The definition that was live until 2026-11-26 must show the bug.
        '''create trigger trg_auto_enable_ai_pending
after insert or update of analysis_status on public.questions
for each row execute function public.auto_enable_ai_for_pending_question();
select public.selftest_case('old-trigger-repair', false);
update public.questions set opt_d = 'd repaired' where id = 'Q-OLD';
select public.selftest_expect('old trigger: row reset to pending',
  (select analysis_status from public.questions where id = 'Q-OLD'), 'pending');
select public.selftest_expect('old trigger: explanation cleared',
  (select exp_why from public.questions where id = 'Q-OLD'), null);
select public.selftest_expect('old trigger: queue stays off (the 2026-11-24 bug)',
  public.selftest_calls('old-trigger-repair')::text, '0');''',
        '-- migration under test: ' + migration.name,
        migration.read_text(encoding='utf-8'),
        '''select public.selftest_case('repair', false);
update public.questions set question = 'repaired stem' where id = 'Q-FIX';
select public.selftest_expect('repair: row reset to pending',
  (select analysis_status from public.questions where id = 'Q-FIX'), 'pending');
select public.selftest_expect('repair: queue re-enabled once',
  public.selftest_calls('repair')::text, '1');
select public.selftest_expect('repair: config enabled',
  (select enabled::text from public.ai_analysis_job_config), 'true');

select public.selftest_case('repair-while-enabled', true);
update public.questions set opt_a = 'a repaired' where id = 'Q-ENABLED';
select public.selftest_expect('already enabled: row reset to pending',
  (select analysis_status from public.questions where id = 'Q-ENABLED'), 'pending');
select public.selftest_expect('already enabled: no second enable',
  public.selftest_calls('repair-while-enabled')::text, '0');

select public.selftest_case('unrelated', false);
update public.questions set exp_why = 'edited explanation' where id = 'Q-READY';
select public.selftest_expect('unrelated update: still ready',
  (select analysis_status from public.questions where id = 'Q-READY'), 'ready');
select public.selftest_expect('unrelated update: queue untouched',
  public.selftest_calls('unrelated')::text, '0');

select public.selftest_case('whitespace', false);
update public.questions set question = ' old  stem ' where id = 'Q-WS';
select public.selftest_expect('whitespace-only edit: explanation kept',
  (select analysis_status from public.questions where id = 'Q-WS'), 'ready');
select public.selftest_expect('whitespace-only edit: queue untouched',
  public.selftest_calls('whitespace')::text, '0');

select public.selftest_case('no-source', false);
update public.questions set question = 'changed stem' where id = 'Q-NOSRC';
insert into public.questions (id, source_exam_code, question, analysis_status)
  values ('Q-NOSRC-NEW', null, 'new stem', 'pending');
select public.selftest_expect('no official source: queue untouched',
  public.selftest_calls('no-source')::text, '0');

select public.selftest_case('exhausted', false);
update public.questions set exp_why = 'note' where id = 'Q-EXHAUSTED';
select public.selftest_expect('3 attempts used: queue untouched',
  public.selftest_calls('exhausted')::text, '0');

select public.selftest_case('insert-pending', false);
insert into public.questions (id, source_exam_code, question, analysis_status)
  values ('Q-NEW', 'EXAM', 'new stem', 'pending');
select public.selftest_expect('new pending question: queue enabled',
  public.selftest_calls('insert-pending')::text, '1');

select public.selftest_case('explicit-pending', false);
update public.questions set analysis_status = 'pending' where id = 'Q-READY2';
select public.selftest_expect('explicit status change: queue enabled',
  public.selftest_calls('explicit-pending')::text, '1');''',
        "select '%s';" % PASS,
        'rollback;',
        '',
    ])


def main():
    if os.environ.get('SWSI_DISPOSABLE_PG') != 'I_CONFIRM_DISPOSABLE_FIXTURE':
        raise SystemExit('refusing: set SWSI_DISPOSABLE_PG=I_CONFIRM_DISPOSABLE_FIXTURE '
                         'and point PG* at a disposable database')
    code, out, err = psql("select to_regclass('public.questions') is null;\n")
    if code != 0 or out.strip() != 't':
        raise SystemExit('refusing: public.questions already exists or the database '
                         'is unreachable\n' + err)
    code, out, err = psql(build_sql())
    print(out.strip())
    if code != 0 or PASS not in out.split():
        print(err.strip(), file=sys.stderr)
        raise SystemExit('AI queue auto-enable selftest FAILED')
    print('AI queue auto-enable trigger behaves as intended '
          '(migration: %s)' % newest_trigger_migration().name)


if __name__ == '__main__':
    main()

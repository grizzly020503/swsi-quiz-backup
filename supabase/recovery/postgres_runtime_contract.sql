\set ON_ERROR_STOP on

-- The final policy inventory must match production's public access model.
do $$
declare
  v_policies text[];
begin
  select array_agg(tablename || ':' || policyname order by tablename, policyname)
    into v_policies
  from pg_policies
  where schemaname = 'public';

  if v_policies is distinct from array[
    'essays:public read essays',
    'questions:public read questions',
    'swsi_feedback_reports:swsi_feedback_reports_deny_public'
  ]::text[] then
    raise exception 'unexpected public policy inventory: %', v_policies;
  end if;
end
$$;

-- Sensitive functions must not be executable by student roles.
do $$
begin
  if has_function_privilege('anon', 'public.reset_ai_analysis_on_official_change()', 'EXECUTE') then
    raise exception 'anon can execute official-change reset';
  end if;
  if has_function_privilege('anon', 'public.claim_pending_ai_questions(integer)', 'EXECUTE') then
    raise exception 'anon can claim AI queue';
  end if;
  if has_function_privilege('authenticated', 'public.claim_pending_ai_questions(integer)', 'EXECUTE') then
    raise exception 'authenticated can claim AI queue';
  end if;
  if has_function_privilege(
    'anon',
    'public.submit_swsi_feedback(text,text,text,text,text,text,integer,integer,integer,text,text,text,text,text,text,text,jsonb)',
    'EXECUTE'
  ) then
    raise exception 'anon can execute feedback RPC directly';
  end if;
  if not has_function_privilege('service_role', 'public.reset_ai_analysis_on_official_change()', 'EXECUTE') then
    raise exception 'service_role lost official-change reset execute';
  end if;
  if not has_function_privilege('service_role', 'public.claim_pending_ai_questions(integer)', 'EXECUTE') then
    raise exception 'service_role lost AI queue claim execute';
  end if;
end
$$;

-- The three grading modes must remain mutually consistent.
insert into public.questions(id, answer, accepted_answers, grading_mode)
values
  ('DR-RUNTIME-MULTI', 'B', array['B','C'], 'standard'),
  ('DR-RUNTIME-ALL', '一律給分', null, 'all_credit'),
  ('DR-RUNTIME-ANY', '一律給分', null, 'any_answer');

do $$
begin
  begin
    insert into public.questions(id, answer, accepted_answers, grading_mode)
    values ('DR-RUNTIME-BAD', 'B', null, 'all_credit');
    raise exception 'invalid all_credit row unexpectedly passed';
  exception
    when check_violation then null;
  end;
end
$$;

-- Exercise protected RPCs using synthetic rows only.
set role service_role;
select public.submit_swsi_feedback(
  'site_bug', 'general', null, 'DR synthetic report', 'swsi', null,
  null, null, null, 'Synthetic disaster recovery report', null,
  '/dr', 'https://example.invalid', 'dr', 'dr-agent',
  repeat('a', 64), '{}'::jsonb
);
select public.record_swsi_usage(repeat('b', 64));
select public.record_swsi_ai_telemetry(repeat('c', 64), 'text', 'success', 123);
reset role;

do $$
begin
  if (select count(*) from public.swsi_feedback_reports where context_title='DR synthetic report') <> 1 then
    raise exception 'synthetic feedback RPC failed';
  end if;
  if (select count(*) from public.swsi_usage_daily where client_hash=repeat('b',64)) <> 1 then
    raise exception 'synthetic usage RPC failed';
  end if;
  if (select count(*) from public.swsi_ai_telemetry_5m where mode='text' and outcome='success') <> 1 then
    raise exception 'synthetic AI telemetry RPC failed';
  end if;
end
$$;

-- AI queue fairness: never-attempted rows must run before retries, then the oldest retry.
-- pg_cron/pg_net are intentionally absent in portable DR, so suppress only the two
-- cron-management triggers inside this disposable transaction; rollback restores them.
begin;
alter table public.questions disable trigger trg_auto_enable_ai_pending;
alter table public.questions disable trigger trg_auto_stop_ai_queue;

update public.questions
   set analysis_status = 'review', analysis_started_at = null
 where analysis_status in ('pending', 'analyzing');

insert into public.questions(
  id, subject, qno, answer, grading_mode, source_exam_code,
  analysis_status, analysis_attempts, analysis_last_attempt_at
) values
  ('DR-QUEUE-OLD', '社會工作', '1', 'A', 'standard', 'DR-FAIRNESS', 'pending', 0, now() - interval '20 minutes'),
  ('DR-QUEUE-NEW', '社會工作', '2', 'A', 'standard', 'DR-FAIRNESS', 'pending', 0, now() - interval '5 minutes'),
  ('DR-QUEUE-FRESH', '社會工作', '999', 'A', 'standard', 'DR-FAIRNESS', 'pending', 0, null);

set role service_role;
create temp table dr_first_claim as
select id from public.claim_pending_ai_questions(1);
reset role;

do $$
begin
  if (select array_agg(id order by id) from dr_first_claim) is distinct from array['DR-QUEUE-FRESH']::text[] then
    raise exception 'queue fairness failed: fresh row was not claimed first';
  end if;
  if (select analysis_status from public.questions where id='DR-QUEUE-FRESH') <> 'analyzing' then
    raise exception 'queue fairness failed: fresh row not marked analyzing';
  end if;
  if (select analysis_last_attempt_at from public.questions where id='DR-QUEUE-FRESH') is null then
    raise exception 'queue fairness failed: claim did not persist last-attempt time';
  end if;
end
$$;

update public.questions
   set analysis_status='review', analysis_started_at=null
 where id='DR-QUEUE-FRESH';

set role service_role;
create temp table dr_second_claim as
select id from public.claim_pending_ai_questions(1);
reset role;

do $$
begin
  if (select array_agg(id order by id) from dr_second_claim) is distinct from array['DR-QUEUE-OLD']::text[] then
    raise exception 'queue fairness failed: oldest retry was not claimed next';
  end if;
end
$$;
rollback;

-- Official Core reset must make the next analysis fresh again.
begin;
alter table public.questions disable trigger trg_auto_enable_ai_pending;
alter table public.questions disable trigger trg_auto_stop_ai_queue;

insert into public.questions(
  id, subject, qno, question, answer, grading_mode, source_exam_code,
  analysis_status, analysis_attempts, analysis_last_attempt_at
) values (
  'DR-QUEUE-RESET', '社會工作', '998', '原題', 'A', 'standard', 'DR-FAIRNESS',
  'review', 2, now()
);
update public.questions set question='更正後題目' where id='DR-QUEUE-RESET';
do $$
begin
  if (select analysis_status from public.questions where id='DR-QUEUE-RESET') <> 'pending' then
    raise exception 'official-change reset did not requeue analysis';
  end if;
  if (select analysis_attempts from public.questions where id='DR-QUEUE-RESET') <> 0 then
    raise exception 'official-change reset did not clear attempts';
  end if;
  if (select analysis_last_attempt_at from public.questions where id='DR-QUEUE-RESET') is not null then
    raise exception 'official-change reset did not clear last-attempt time';
  end if;
end
$$;
rollback;

\echo 'SWSI RESTORED RUNTIME DB CONTRACT OK'
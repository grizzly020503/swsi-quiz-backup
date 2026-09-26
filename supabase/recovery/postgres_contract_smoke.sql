\set ON_ERROR_STOP on

-- Final recovery schema inventory: 13 public tables, all RLS-enabled.
do $$
declare
  v_tables integer;
  v_rls integer;
begin
  select count(*) into v_tables
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind = 'r';

  select count(*) into v_rls
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind = 'r' and c.relrowsecurity;

  if v_tables <> 13 then
    raise exception 'expected 13 public tables, got %', v_tables;
  end if;
  if v_rls <> 13 then
    raise exception 'expected RLS on all 13 public tables, got %', v_rls;
  end if;
end
$$;

-- Public students remain read-only on official questions/essays.
do $$
begin
  if not has_table_privilege('anon', 'public.questions', 'SELECT') then
    raise exception 'anon lost SELECT on questions';
  end if;
  if not has_table_privilege('authenticated', 'public.questions', 'SELECT') then
    raise exception 'authenticated lost SELECT on questions';
  end if;
  if has_table_privilege('anon', 'public.questions', 'INSERT')
     or has_table_privilege('anon', 'public.questions', 'UPDATE')
     or has_table_privilege('anon', 'public.questions', 'DELETE') then
    raise exception 'anon unexpectedly has write privilege on questions';
  end if;
  if not has_table_privilege('anon', 'public.essays', 'SELECT') then
    raise exception 'anon lost SELECT on essays';
  end if;
  if has_table_privilege('authenticated', 'public.essays', 'INSERT')
     or has_table_privilege('authenticated', 'public.essays', 'UPDATE')
     or has_table_privilege('authenticated', 'public.essays', 'DELETE') then
    raise exception 'authenticated unexpectedly has write privilege on essays';
  end if;
end
$$;

-- Only the two public-read policies and the explicit feedback deny policy exist.
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

-- Security-definer boundaries stay server-only.
do $$
begin
  if has_function_privilege('anon', 'public.reset_ai_analysis_on_official_change()', 'EXECUTE') then
    raise exception 'anon can execute official-change reset';
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
    raise exception 'service_role cannot execute official-change reset';
  end if;
end
$$;

-- Synthetic standard question proves official-change reset semantics.
insert into public.questions(
  id, subject, year, round, qno, question,
  opt_a, opt_b, opt_c, opt_d, answer,
  major, topic, keywords, exp_why, exp_others, exp_trap, exp_raw,
  mnemonic, extension, law, mistake,
  source_exam_code, source_url, analysis_status,
  accepted_answers, grading_mode
) values (
  'DR-Q1', '社會工作', '115', '1', '1', '原始題幹',
  'A', 'B', 'C', 'D', 'B',
  'old-major', 'old-topic', 'old-keywords', 'old-why', 'old-others', 'old-trap', 'old-raw',
  'old-mnemonic', 'old-extension', '社會工作師法', 'old-mistake',
  'DRTEST', 'https://example.invalid/dr', 'ready',
  array['B'], 'standard'
);

update public.questions
   set question = '官方更正後題幹'
 where id = 'DR-Q1';

do $$
declare
  q public.questions%rowtype;
begin
  select * into q from public.questions where id = 'DR-Q1';
  if q.analysis_status <> 'pending'
     or q.analysis_attempts <> 0
     or q.major is not null
     or q.topic is not null
     or q.exp_why is not null
     or q.mnemonic is not null then
    raise exception 'official-change reset contract failed: %', row_to_json(q);
  end if;
end
$$;

-- Grading-mode constraints accept the three supported official semantics.
insert into public.questions(id, answer, accepted_answers, grading_mode)
values
  ('DR-MULTI', 'B', array['B','C'], 'standard'),
  ('DR-ALL', '一律給分', null, 'all_credit'),
  ('DR-ANY', '一律給分', null, 'any_answer');

do $$
begin
  begin
    insert into public.questions(id, answer, accepted_answers, grading_mode)
    values ('DR-BAD', 'B', null, 'all_credit');
    raise exception 'invalid all_credit row unexpectedly passed';
  exception
    when check_violation then null;
  end;
end
$$;

-- Feedback RPC, anonymous usage, and AI telemetry operate with synthetic data only.
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
  if (select count(*) from public.swsi_feedback_reports) <> 1 then
    raise exception 'synthetic feedback RPC failed';
  end if;
  if (select count(*) from public.swsi_usage_daily) <> 1 then
    raise exception 'synthetic usage RPC failed';
  end if;
  if (select count(*) from public.swsi_ai_telemetry_5m) <> 1 then
    raise exception 'synthetic AI telemetry RPC failed';
  end if;
end
$$;

-- The CI cron shim may store a schedule string but cannot execute or contact HTTP.
do $$
begin
  if (select count(*) from cron.job) > 1 then
    raise exception 'unexpected isolated cron inventory';
  end if;
end
$$;

\echo 'SWSI ISOLATED POSTGRES RESTORE CONTRACT OK'

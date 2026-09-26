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

\echo 'SWSI RESTORED RUNTIME DB CONTRACT OK'

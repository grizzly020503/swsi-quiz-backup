\set ON_ERROR_STOP on

-- Server-only RPC boundaries must stay closed to public roles.
do $$
begin
  if has_function_privilege(
    'anon',
    'public.submit_swsi_feedback(text,text,text,text,text,text,integer,integer,integer,text,text,text,text,text,text,text,jsonb)',
    'EXECUTE'
  ) then
    raise exception 'anon can execute feedback RPC directly';
  end if;
  if has_function_privilege(
    'authenticated',
    'public.claim_pending_ai_questions(integer)',
    'EXECUTE'
  ) then
    raise exception 'authenticated can claim AI queue';
  end if;
  if not has_function_privilege(
    'service_role',
    'public.reset_ai_analysis_on_official_change()',
    'EXECUTE'
  ) then
    raise exception 'service_role cannot execute official-change reset';
  end if;
end
$$;

-- Supported grading modes accept valid synthetic rows and reject an invalid all-credit row.
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

-- Mutable private-data RPC schemas are exercised with synthetic-only rows.
set role service_role;
select public.submit_swsi_feedback(
  'site_bug', 'general', null, 'DR synthetic report', 'swsi', null,
  null, null, null, 'Synthetic disaster recovery report', null,
  '/dr', 'https://example.invalid', 'dr', 'dr-agent',
  repeat('a', 64), '{}'::jsonb
);
select public.record_swsi_usage(repeat('b', 64));
select public.record_swsi_ai_telemetry(
  repeat('c', 64), 'text', 'success', 123
);
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

delete from public.questions
where id in ('DR-MULTI','DR-ALL','DR-ANY');

\echo 'SWSI ISOLATED POSTGRES PRIVATE-DATA CONTRACT OK'

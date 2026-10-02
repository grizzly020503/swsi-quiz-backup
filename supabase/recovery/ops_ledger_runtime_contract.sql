\set ON_ERROR_STOP on

-- #274 durable ops ledger recovery/runtime contract.
-- Runs only in the disposable DR PostgreSQL database.
do $$
begin
  if not exists (
    select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname='swsi_ops_task_runs' and c.relrowsecurity
  ) then
    raise exception 'swsi_ops_task_runs missing RLS';
  end if;
  if not exists (
    select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname='swsi_ops_review_items' and c.relrowsecurity
  ) then
    raise exception 'swsi_ops_review_items missing RLS';
  end if;

  if has_table_privilege('anon','public.swsi_ops_task_runs','SELECT')
     or has_table_privilege('authenticated','public.swsi_ops_task_runs','SELECT')
     or has_table_privilege('anon','public.swsi_ops_review_items','SELECT')
     or has_table_privilege('authenticated','public.swsi_ops_review_items','SELECT') then
    raise exception 'student roles can read ops ledger tables';
  end if;

  if not has_table_privilege('service_role','public.swsi_ops_task_runs','SELECT')
     or not has_table_privilege('service_role','public.swsi_ops_task_runs','INSERT')
     or not has_table_privilege('service_role','public.swsi_ops_task_runs','UPDATE')
     or has_table_privilege('service_role','public.swsi_ops_task_runs','DELETE') then
    raise exception 'service_role task ledger table privileges mismatch';
  end if;

  if not has_table_privilege('service_role','public.swsi_ops_review_items','SELECT')
     or not has_table_privilege('service_role','public.swsi_ops_review_items','INSERT')
     or not has_table_privilege('service_role','public.swsi_ops_review_items','UPDATE')
     or has_table_privilege('service_role','public.swsi_ops_review_items','DELETE') then
    raise exception 'service_role review table privileges mismatch';
  end if;

  if has_function_privilege('anon','public.swsi_ops_claim_task(text,text,text,timestamptz,integer,integer)','EXECUTE')
     or has_function_privilege('authenticated','public.swsi_ops_claim_task(text,text,text,timestamptz,integer,integer)','EXECUTE')
     or has_function_privilege('anon','public.swsi_ops_checkpoint_task(text,text,text,jsonb,bigint,timestamptz,integer,integer)','EXECUTE')
     or has_function_privilege('authenticated','public.swsi_ops_checkpoint_task(text,text,text,jsonb,bigint,timestamptz,integer,integer)','EXECUTE')
     or has_function_privilege('anon','public.swsi_ops_heartbeat_task(text,text,text,timestamptz,integer)','EXECUTE')
     or has_function_privilege('authenticated','public.swsi_ops_heartbeat_task(text,text,text,timestamptz,integer)','EXECUTE')
     or has_function_privilege('anon','public.swsi_ops_complete_task(text,text,text,text,timestamptz,text,text,integer)','EXECUTE')
     or has_function_privilege('authenticated','public.swsi_ops_complete_task(text,text,text,text,timestamptz,text,text,integer)','EXECUTE')
     or has_function_privilege('anon','public.swsi_ops_upsert_review_item(text,text,text,text,timestamptz,jsonb)','EXECUTE')
     or has_function_privilege('authenticated','public.swsi_ops_upsert_review_item(text,text,text,text,timestamptz,jsonb)','EXECUTE')
     or has_function_privilege('anon','public.swsi_ops_touch_review_item(text,timestamptz,text,timestamptz)','EXECUTE')
     or has_function_privilege('authenticated','public.swsi_ops_touch_review_item(text,timestamptz,text,timestamptz)','EXECUTE')
     or has_function_privilege('anon','public.swsi_ops_resolve_review_item(text,text,text,timestamptz)','EXECUTE')
     or has_function_privilege('authenticated','public.swsi_ops_resolve_review_item(text,text,text,timestamptz)','EXECUTE') then
    raise exception 'student role can execute an ops ledger RPC';
  end if;

  if not has_function_privilege('service_role','public.swsi_ops_claim_task(text,text,text,timestamptz,integer,integer)','EXECUTE')
     or not has_function_privilege('service_role','public.swsi_ops_checkpoint_task(text,text,text,jsonb,bigint,timestamptz,integer,integer)','EXECUTE')
     or not has_function_privilege('service_role','public.swsi_ops_heartbeat_task(text,text,text,timestamptz,integer)','EXECUTE')
     or not has_function_privilege('service_role','public.swsi_ops_complete_task(text,text,text,text,timestamptz,text,text,integer)','EXECUTE')
     or not has_function_privilege('service_role','public.swsi_ops_upsert_review_item(text,text,text,text,timestamptz,jsonb)','EXECUTE')
     or not has_function_privilege('service_role','public.swsi_ops_touch_review_item(text,timestamptz,text,timestamptz)','EXECUTE')
     or not has_function_privilege('service_role','public.swsi_ops_resolve_review_item(text,text,text,timestamptz)','EXECUTE') then
    raise exception 'service_role lost an ops ledger RPC';
  end if;
end
$$;

set role service_role;
select * from public.swsi_ops_claim_task(
  'dr-runtime:full-corpus', 'sem1:fixture', 'dr-worker',
  '2026-10-02T11:30:00Z'::timestamptz, 120, 3
);
select public.swsi_ops_checkpoint_task(
  'dr-runtime:full-corpus', 'sem1:fixture', 'dr-worker',
  '{"session":"115-1"}'::jsonb, 1,
  '2026-10-02T11:30:10Z'::timestamptz, 1, 120
);
select public.swsi_ops_complete_task(
  'dr-runtime:full-corpus', 'sem1:fixture', 'dr-worker', 'no_change',
  '2026-10-02T11:30:20Z'::timestamptz, null, null, 60
);
select public.swsi_ops_upsert_review_item(
  'dr-runtime:review:1', 'source_failure', 'historical-law-guardian-queue',
  'fixture|q1', '2026-10-02T11:31:00Z'::timestamptz,
  '{"lane":"source_retry"}'::jsonb
);
select public.swsi_ops_touch_review_item(
  'dr-runtime:review:1', '2026-10-02T11:32:00Z'::timestamptz,
  'temporary source failure', '2026-10-02T12:00:00Z'::timestamptz
);
select public.swsi_ops_resolve_review_item(
  'dr-runtime:review:1', 'resolved', 'source recovered',
  '2026-10-02T11:33:00Z'::timestamptz
);
reset role;

do $$
begin
  if not exists (
    select 1 from public.swsi_ops_task_runs
    where task_id='dr-runtime:full-corpus'
      and idempotency_key='sem1:fixture'
      and status='no_change'
      and processed_count=1
      and checkpoint->>'session'='115-1'
      and last_success_at='2026-10-02T11:30:20Z'::timestamptz
      and worker_id is null
      and lease_expires_at is null
  ) then
    raise exception 'ops task runtime behavior mismatch';
  end if;

  if not exists (
    select 1 from public.swsi_ops_review_items
    where item_id='dr-runtime:review:1'
      and state='resolved'
      and first_seen_at='2026-10-02T11:31:00Z'::timestamptz
      and attempt=1
      and resolved_at='2026-10-02T11:33:00Z'::timestamptz
      and resolution='source recovered'
  ) then
    raise exception 'ops review runtime behavior mismatch';
  end if;
end
$$;

-- A later upsert must not silently reopen or rewrite terminal review history.
set role service_role;
select public.swsi_ops_upsert_review_item(
  'dr-runtime:review:1', 'new_reason_should_not_reopen',
  'historical-law-guardian-queue', 'fixture|q1',
  '2026-10-02T11:34:00Z'::timestamptz,
  '{"later":true}'::jsonb
);
reset role;

do $$
begin
  if not exists (
    select 1 from public.swsi_ops_review_items
    where item_id='dr-runtime:review:1'
      and state='resolved'
      and first_seen_at='2026-10-02T11:31:00Z'::timestamptz
      and resolved_at='2026-10-02T11:33:00Z'::timestamptz
      and resolution='source recovered'
      and reason='source_failure'
  ) then
    raise exception 'terminal review history was reopened or rewritten';
  end if;
end
$$;

-- Conflicting terminal rewrite must fail closed.
set role service_role;
do $$
declare
  v_rejected boolean := false;
begin
  begin
    perform public.swsi_ops_resolve_review_item(
      'dr-runtime:review:1', 'invalid', 'conflicting rewrite',
      '2026-10-02T11:35:00Z'::timestamptz
    );
  exception when others then
    if position('already terminal with different resolution' in sqlerrm) > 0 then
      v_rejected := true;
    else
      raise;
    end if;
  end;
  if not v_rejected then
    raise exception 'conflicting terminal review rewrite was accepted';
  end if;
end
$$;
reset role;

\echo 'SWSI OPS LEDGER RESTORED RUNTIME CONTRACT OK'

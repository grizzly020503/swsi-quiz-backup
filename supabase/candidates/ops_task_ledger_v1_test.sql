-- Deterministic behavior tests for ops_task_ledger_v1.sql candidate.
-- Run in an isolated PostgreSQL/Supabase database after loading the candidate SQL.

begin;

-- Keep candidate tests isolated from any pre-existing rows.
delete from public.swsi_ops_review_items where item_id like 'candidate-test:%';
delete from public.swsi_ops_task_runs where task_id like 'candidate-test:%';

do $$
declare
  v_result text;
  v_run jsonb;
  v_row jsonb;
  v_failed boolean := false;
begin
  select result, run into v_result, v_run
  from public.swsi_ops_claim_task(
    'candidate-test:full-corpus', 'dataset-a', 'w1',
    '2026-10-02T00:00:00Z'::timestamptz, 60, 3
  );
  if v_result <> 'claimed' or (v_run->>'attempt')::int <> 1 then
    raise exception 'first claim failed: % %', v_result, v_run;
  end if;

  select result, run into v_result, v_run
  from public.swsi_ops_claim_task(
    'candidate-test:full-corpus', 'dataset-a', 'w2',
    '2026-10-02T00:00:10Z'::timestamptz, 60, 3
  );
  if v_result <> 'busy' then
    raise exception 'live lease did not block duplicate owner: %', v_result;
  end if;

  v_row := public.swsi_ops_checkpoint_task(
    'candidate-test:full-corpus', 'dataset-a', 'w1',
    '{"session":"110-2"}'::jsonb, 12,
    '2026-10-02T00:00:20Z'::timestamptz, 1, 60
  );
  if (v_row->>'processed_count')::bigint <> 12 then
    raise exception 'checkpoint count not persisted: %', v_row;
  end if;

  v_row := public.swsi_ops_complete_task(
    'candidate-test:full-corpus', 'dataset-a', 'w1', 'failed_retryable',
    '2026-10-02T00:00:30Z'::timestamptz, 'http_503', 'temporary', 30
  );
  if v_row->>'status' <> 'failed_retryable' then
    raise exception 'retryable completion failed: %', v_row;
  end if;

  select result, run into v_result, v_run
  from public.swsi_ops_claim_task(
    'candidate-test:full-corpus', 'dataset-a', 'w2',
    '2026-10-02T00:00:40Z'::timestamptz, 60, 3
  );
  if v_result <> 'retry_not_due' then
    raise exception 'retry window not enforced: %', v_result;
  end if;

  select result, run into v_result, v_run
  from public.swsi_ops_claim_task(
    'candidate-test:full-corpus', 'dataset-a', 'w2',
    '2026-10-02T00:01:01Z'::timestamptz, 60, 3
  );
  if v_result <> 'reclaimed'
     or (v_run->>'attempt')::int <> 2
     or (v_run->>'processed_count')::bigint <> 12
     or v_run->'checkpoint'->>'session' <> '110-2' then
    raise exception 'reclaim/checkpoint preservation failed: % %', v_result, v_run;
  end if;

  begin
    perform public.swsi_ops_checkpoint_task(
      'candidate-test:full-corpus', 'dataset-a', 'w2',
      '{"session":"110-1"}'::jsonb, 11,
      '2026-10-02T00:01:02Z'::timestamptz, 1, 60
    );
  exception when others then
    v_failed := true;
  end;
  if not v_failed then
    raise exception 'processed_count regression was accepted';
  end if;

  v_failed := false;
  begin
    perform public.swsi_ops_checkpoint_task(
      'candidate-test:full-corpus', 'dataset-a', 'w2',
      '{}'::jsonb, 12,
      '2026-10-02T00:01:03Z'::timestamptz, 2, 60
    );
  exception when others then
    v_failed := true;
  end;
  if not v_failed then
    raise exception 'unknown checkpoint version was accepted';
  end if;

  v_row := public.swsi_ops_complete_task(
    'candidate-test:full-corpus', 'dataset-a', 'w2', 'success',
    '2026-10-02T00:01:10Z'::timestamptz, null, null, 60
  );
  if v_row->>'status' <> 'success'
     or v_row->>'last_success_at' <> '2026-10-02T00:01:10+00:00' then
    raise exception 'success completion/last_success failed: %', v_row;
  end if;

  select result, run into v_result, v_run
  from public.swsi_ops_claim_task(
    'candidate-test:full-corpus', 'dataset-a', 'w3',
    '2026-10-02T00:01:20Z'::timestamptz, 60, 3
  );
  if v_result <> 'already_terminal' then
    raise exception 'terminal idempotency failed: %', v_result;
  end if;

  select result, run into v_result, v_run
  from public.swsi_ops_claim_task(
    'candidate-test:lease-expiry', 'weekly-1', 'w1',
    '2026-10-02T01:00:00Z'::timestamptz, 10, 2
  );
  if v_result <> 'claimed' then raise exception 'lease test initial claim failed'; end if;

  select result, run into v_result, v_run
  from public.swsi_ops_claim_task(
    'candidate-test:lease-expiry', 'weekly-1', 'w2',
    '2026-10-02T01:00:11Z'::timestamptz, 10, 2
  );
  if v_result <> 'reclaimed' or (v_run->>'attempt')::int <> 2 then
    raise exception 'expired lease reclaim failed: % %', v_result, v_run;
  end if;

  perform public.swsi_ops_complete_task(
    'candidate-test:lease-expiry', 'weekly-1', 'w2', 'failed_retryable',
    '2026-10-02T01:00:12Z'::timestamptz, 'parse_error', 'temporary', 1
  );

  select result, run into v_result, v_run
  from public.swsi_ops_claim_task(
    'candidate-test:lease-expiry', 'weekly-1', 'w3',
    '2026-10-02T01:00:14Z'::timestamptz, 10, 2
  );
  if v_result <> 'attempt_limit' or v_run->>'status' <> 'failed_terminal' then
    raise exception 'attempt limit failed closed incorrectly: % %', v_result, v_run;
  end if;

  select result, run into v_result, v_run
  from public.swsi_ops_claim_task(
    'candidate-test:no-change', 'tick-1', 'w1',
    '2026-10-02T02:00:00Z'::timestamptz, 30, 1
  );
  perform public.swsi_ops_complete_task(
    'candidate-test:no-change', 'tick-1', 'w1', 'no_change',
    '2026-10-02T02:00:05Z'::timestamptz, null, null, 60
  );
  select to_jsonb(r) into v_run
  from public.swsi_ops_task_runs r
  where r.task_id = 'candidate-test:no-change' and r.idempotency_key = 'tick-1';
  if v_run->>'last_success_at' <> '2026-10-02T02:00:05+00:00' then
    raise exception 'no_change did not count as successful check: %', v_run;
  end if;
end;
$$;

insert into public.swsi_ops_review_items (
  item_id, task_id, reason, source_ref, first_seen_at
) values (
  'candidate-test:review:1', 'candidate-test:full-corpus', 'source_format_changed', 'fixture',
  '2026-10-02T00:00:00Z'::timestamptz
);

update public.swsi_ops_review_items
set attempt = attempt + 1,
    last_attempt_at = '2026-10-02T02:00:00Z'::timestamptz,
    last_error = 'selector_missing',
    next_check_at = '2026-10-02T08:00:00Z'::timestamptz
where item_id = 'candidate-test:review:1';

update public.swsi_ops_review_items
set state = 'resolved',
    resolved_at = '2026-10-02T04:00:00Z'::timestamptz,
    resolution = 'parser updated'
where item_id = 'candidate-test:review:1';

do $$
begin
  if not exists (
    select 1 from public.swsi_ops_review_items
    where item_id = 'candidate-test:review:1'
      and state = 'resolved'
      and attempt = 1
      and resolution = 'parser updated'
  ) then
    raise exception 'review item audit trail failed';
  end if;
end;
$$;

rollback;

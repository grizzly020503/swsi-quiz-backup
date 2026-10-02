-- Formal migration prepared under #274 from the reviewed #269 Phase A-2 candidate.
-- This repository change does NOT apply the migration to production.
-- Contract source: supabase/candidates/ops_task_ledger_v1.sql (PR #273).

create table if not exists public.swsi_ops_task_runs (
  task_id text not null,
  idempotency_key text not null,
  status text not null check (status in (
    'running','failed_retryable','success','no_change','failed_terminal','quarantined'
  )),
  attempt integer not null check (attempt >= 1),
  max_attempts integer not null check (max_attempts >= 1 and attempt <= max_attempts),
  worker_id text,
  started_at timestamptz not null,
  heartbeat_at timestamptz not null,
  lease_expires_at timestamptz,
  completed_at timestamptz,
  last_success_at timestamptz,
  checkpoint_version integer not null default 1 check (checkpoint_version = 1),
  checkpoint jsonb,
  processed_count bigint not null default 0 check (processed_count >= 0),
  error_class text,
  error_message text,
  next_retry_at timestamptz,
  primary key (task_id, idempotency_key),
  check (
    (status = 'running' and worker_id is not null and lease_expires_at is not null and completed_at is null)
    or
    (status <> 'running' and worker_id is null and lease_expires_at is null)
  ),
  check (
    status not in ('success','no_change','failed_terminal','quarantined')
    or completed_at is not null
  ),
  check (status <> 'failed_retryable' or next_retry_at is not null)
);

create index if not exists swsi_ops_task_runs_status_idx
  on public.swsi_ops_task_runs(status, next_retry_at, lease_expires_at);
create index if not exists swsi_ops_task_runs_task_success_idx
  on public.swsi_ops_task_runs(task_id, last_success_at desc nulls last);

alter table public.swsi_ops_task_runs enable row level security;
revoke all on table public.swsi_ops_task_runs from public, anon, authenticated;
grant select, insert, update on table public.swsi_ops_task_runs to service_role;

create table if not exists public.swsi_ops_review_items (
  item_id text primary key,
  task_id text,
  reason text not null,
  source_ref text,
  state text not null default 'open' check (state in ('open','resolved','superseded','invalid')),
  first_seen_at timestamptz not null,
  last_attempt_at timestamptz,
  attempt integer not null default 0 check (attempt >= 0),
  last_error text,
  next_check_at timestamptz,
  resolved_at timestamptz,
  resolution text,
  metadata jsonb not null default '{}'::jsonb,
  check (
    (state = 'open' and resolved_at is null)
    or
    (state <> 'open' and resolved_at is not null and resolution is not null)
  )
);

create index if not exists swsi_ops_review_items_open_age_idx
  on public.swsi_ops_review_items(state, first_seen_at, next_check_at);
create index if not exists swsi_ops_review_items_reason_idx
  on public.swsi_ops_review_items(reason, state);

alter table public.swsi_ops_review_items enable row level security;
revoke all on table public.swsi_ops_review_items from public, anon, authenticated;
grant select, insert, update on table public.swsi_ops_review_items to service_role;

create or replace function public.swsi_ops_claim_task(
  p_task_id text,
  p_idempotency_key text,
  p_worker_id text,
  p_now timestamptz default now(),
  p_lease_seconds integer default 900,
  p_max_attempts integer default 3
)
returns table(result text, run jsonb)
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_row public.swsi_ops_task_runs%rowtype;
  v_inserted integer := 0;
begin
  if nullif(trim(p_task_id), '') is null
     or nullif(trim(p_idempotency_key), '') is null
     or nullif(trim(p_worker_id), '') is null then
    raise exception 'task_id, idempotency_key and worker_id are required';
  end if;
  if p_lease_seconds <= 0 or p_max_attempts <= 0 then
    raise exception 'lease_seconds and max_attempts must be positive';
  end if;

  insert into public.swsi_ops_task_runs (
    task_id, idempotency_key, status, attempt, max_attempts, worker_id,
    started_at, heartbeat_at, lease_expires_at, checkpoint_version, processed_count
  ) values (
    p_task_id, p_idempotency_key, 'running', 1, p_max_attempts, p_worker_id,
    p_now, p_now, p_now + make_interval(secs => p_lease_seconds), 1, 0
  )
  on conflict (task_id, idempotency_key) do nothing;
  get diagnostics v_inserted = row_count;

  select * into v_row
  from public.swsi_ops_task_runs
  where task_id = p_task_id and idempotency_key = p_idempotency_key
  for update;

  if v_inserted = 1 then
    return query select 'claimed'::text, to_jsonb(v_row);
    return;
  end if;

  if v_row.status in ('success','no_change','failed_terminal','quarantined') then
    return query select 'already_terminal'::text, to_jsonb(v_row);
    return;
  end if;

  if v_row.status = 'running' and v_row.lease_expires_at > p_now then
    return query select 'busy'::text, to_jsonb(v_row);
    return;
  end if;

  if v_row.status = 'failed_retryable' and v_row.next_retry_at > p_now then
    return query select 'retry_not_due'::text, to_jsonb(v_row);
    return;
  end if;

  if v_row.attempt >= v_row.max_attempts then
    update public.swsi_ops_task_runs
    set status = 'failed_terminal', completed_at = p_now, worker_id = null,
        lease_expires_at = null, next_retry_at = null,
        error_class = coalesce(error_class, 'attempt_limit'),
        error_message = coalesce(error_message, 'retry limit reached'),
        heartbeat_at = p_now
    where task_id = p_task_id and idempotency_key = p_idempotency_key
    returning * into v_row;
    return query select 'attempt_limit'::text, to_jsonb(v_row);
    return;
  end if;

  update public.swsi_ops_task_runs
  set status = 'running', attempt = attempt + 1, worker_id = p_worker_id,
      heartbeat_at = p_now,
      lease_expires_at = p_now + make_interval(secs => p_lease_seconds),
      completed_at = null, next_retry_at = null
  where task_id = p_task_id and idempotency_key = p_idempotency_key
  returning * into v_row;

  return query select 'reclaimed'::text, to_jsonb(v_row);
end;
$$;

create or replace function public.swsi_ops_checkpoint_task(
  p_task_id text,
  p_idempotency_key text,
  p_worker_id text,
  p_checkpoint jsonb,
  p_processed_count bigint,
  p_now timestamptz default now(),
  p_checkpoint_version integer default 1,
  p_extend_lease_seconds integer default 900
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_row public.swsi_ops_task_runs%rowtype;
begin
  if p_checkpoint_version <> 1 then
    raise exception 'unsupported checkpoint version';
  end if;
  if p_processed_count < 0 or p_extend_lease_seconds <= 0 then
    raise exception 'invalid processed_count or lease extension';
  end if;

  update public.swsi_ops_task_runs
  set checkpoint = p_checkpoint,
      checkpoint_version = p_checkpoint_version,
      processed_count = p_processed_count,
      heartbeat_at = p_now,
      lease_expires_at = p_now + make_interval(secs => p_extend_lease_seconds)
  where task_id = p_task_id
    and idempotency_key = p_idempotency_key
    and status = 'running'
    and worker_id = p_worker_id
    and lease_expires_at > p_now
    and p_processed_count >= processed_count
  returning * into v_row;

  if not found then
    raise exception 'active lease not owned, expired, or processed_count regressed';
  end if;
  return to_jsonb(v_row);
end;
$$;

create or replace function public.swsi_ops_heartbeat_task(
  p_task_id text,
  p_idempotency_key text,
  p_worker_id text,
  p_now timestamptz default now(),
  p_extend_lease_seconds integer default 900
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_row public.swsi_ops_task_runs%rowtype;
begin
  if p_extend_lease_seconds <= 0 then
    raise exception 'lease extension must be positive';
  end if;
  update public.swsi_ops_task_runs
  set heartbeat_at = p_now,
      lease_expires_at = p_now + make_interval(secs => p_extend_lease_seconds)
  where task_id = p_task_id
    and idempotency_key = p_idempotency_key
    and status = 'running'
    and worker_id = p_worker_id
    and lease_expires_at > p_now
  returning * into v_row;
  if not found then
    raise exception 'active lease not owned or expired';
  end if;
  return to_jsonb(v_row);
end;
$$;

create or replace function public.swsi_ops_complete_task(
  p_task_id text,
  p_idempotency_key text,
  p_worker_id text,
  p_outcome text,
  p_now timestamptz default now(),
  p_error_class text default null,
  p_error_message text default null,
  p_retry_after_seconds integer default 60
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_row public.swsi_ops_task_runs%rowtype;
begin
  if p_outcome not in ('success','no_change','failed_retryable','failed_terminal','quarantined') then
    raise exception 'invalid outcome';
  end if;
  if p_outcome = 'failed_retryable' and p_retry_after_seconds <= 0 then
    raise exception 'retry_after_seconds must be positive';
  end if;

  update public.swsi_ops_task_runs
  set status = p_outcome,
      heartbeat_at = p_now,
      worker_id = null,
      lease_expires_at = null,
      error_class = p_error_class,
      error_message = p_error_message,
      completed_at = case when p_outcome = 'failed_retryable' then null else p_now end,
      next_retry_at = case
        when p_outcome = 'failed_retryable' then p_now + make_interval(secs => p_retry_after_seconds)
        else null
      end,
      last_success_at = case
        when p_outcome in ('success','no_change') then p_now
        else last_success_at
      end
  where task_id = p_task_id
    and idempotency_key = p_idempotency_key
    and status = 'running'
    and worker_id = p_worker_id
    and lease_expires_at > p_now
  returning * into v_row;

  if not found then
    raise exception 'active lease not owned or expired';
  end if;
  return to_jsonb(v_row);
end;
$$;

revoke all on function public.swsi_ops_claim_task(text,text,text,timestamptz,integer,integer)
  from public, anon, authenticated;
revoke all on function public.swsi_ops_checkpoint_task(text,text,text,jsonb,bigint,timestamptz,integer,integer)
  from public, anon, authenticated;
revoke all on function public.swsi_ops_heartbeat_task(text,text,text,timestamptz,integer)
  from public, anon, authenticated;
revoke all on function public.swsi_ops_complete_task(text,text,text,text,timestamptz,text,text,integer)
  from public, anon, authenticated;

grant execute on function public.swsi_ops_claim_task(text,text,text,timestamptz,integer,integer) to service_role;
grant execute on function public.swsi_ops_checkpoint_task(text,text,text,jsonb,bigint,timestamptz,integer,integer) to service_role;
grant execute on function public.swsi_ops_heartbeat_task(text,text,text,timestamptz,integer) to service_role;
grant execute on function public.swsi_ops_complete_task(text,text,text,text,timestamptz,text,text,integer) to service_role;

comment on table public.swsi_ops_task_runs is
  'Internal SWSI maintenance task ledger. No anon/authenticated access; service-role backend only.';
comment on table public.swsi_ops_review_items is
  'Internal SWSI maintenance review queue. Unresolved history is retained; no public client access.';

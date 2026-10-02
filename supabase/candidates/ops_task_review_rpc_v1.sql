-- Candidate add-on only. Do not apply directly to production.
-- #269 atomic review-queue RPCs for swsi_ops_review_items.
-- Requires supabase/candidates/ops_task_ledger_v1.sql first.

create or replace function public.swsi_ops_upsert_review_item(
  p_item_id text,
  p_reason text,
  p_task_id text default null,
  p_source_ref text default null,
  p_now timestamptz default now(),
  p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_row public.swsi_ops_review_items%rowtype;
begin
  if nullif(trim(p_item_id), '') is null or nullif(trim(p_reason), '') is null then
    raise exception 'item_id and reason are required';
  end if;

  insert into public.swsi_ops_review_items (
    item_id, task_id, reason, source_ref, state, first_seen_at, metadata
  ) values (
    p_item_id, nullif(trim(p_task_id), ''), p_reason, p_source_ref,
    'open', p_now, coalesce(p_metadata, '{}'::jsonb)
  )
  on conflict (item_id) do nothing;

  select * into v_row
  from public.swsi_ops_review_items
  where item_id = p_item_id
  for update;

  if v_row.state = 'open' then
    update public.swsi_ops_review_items
    set task_id = coalesce(nullif(trim(p_task_id), ''), task_id),
        reason = p_reason,
        source_ref = coalesce(p_source_ref, source_ref),
        metadata = coalesce(metadata, '{}'::jsonb) || coalesce(p_metadata, '{}'::jsonb)
    where item_id = p_item_id
    returning * into v_row;
  end if;

  return to_jsonb(v_row);
end;
$$;

create or replace function public.swsi_ops_touch_review_item(
  p_item_id text,
  p_now timestamptz default now(),
  p_error text default null,
  p_next_check_at timestamptz default null
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_row public.swsi_ops_review_items%rowtype;
begin
  if nullif(trim(p_item_id), '') is null then
    raise exception 'item_id is required';
  end if;

  update public.swsi_ops_review_items
  set attempt = attempt + 1,
      last_attempt_at = p_now,
      last_error = p_error,
      next_check_at = p_next_check_at
  where item_id = p_item_id
    and state = 'open'
  returning * into v_row;

  if not found then
    raise exception 'open review item not found';
  end if;
  return to_jsonb(v_row);
end;
$$;

create or replace function public.swsi_ops_resolve_review_item(
  p_item_id text,
  p_final_state text,
  p_resolution text,
  p_now timestamptz default now()
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_row public.swsi_ops_review_items%rowtype;
begin
  if nullif(trim(p_item_id), '') is null
     or p_final_state not in ('resolved','superseded','invalid')
     or nullif(trim(p_resolution), '') is null then
    raise exception 'item_id, valid terminal state, and resolution are required';
  end if;

  select * into v_row
  from public.swsi_ops_review_items
  where item_id = p_item_id
  for update;

  if not found then
    raise exception 'review item not found';
  end if;

  if v_row.state = 'open' then
    update public.swsi_ops_review_items
    set state = p_final_state,
        resolved_at = p_now,
        resolution = p_resolution,
        next_check_at = null
    where item_id = p_item_id
    returning * into v_row;
    return to_jsonb(v_row);
  end if;

  if v_row.state = p_final_state and v_row.resolution = p_resolution then
    return to_jsonb(v_row);
  end if;

  raise exception 'review item already terminal with different resolution';
end;
$$;

revoke all on function public.swsi_ops_upsert_review_item(text,text,text,text,timestamptz,jsonb)
  from public, anon, authenticated;
revoke all on function public.swsi_ops_touch_review_item(text,timestamptz,text,timestamptz)
  from public, anon, authenticated;
revoke all on function public.swsi_ops_resolve_review_item(text,text,text,timestamptz)
  from public, anon, authenticated;

grant execute on function public.swsi_ops_upsert_review_item(text,text,text,text,timestamptz,jsonb)
  to service_role;
grant execute on function public.swsi_ops_touch_review_item(text,timestamptz,text,timestamptz)
  to service_role;
grant execute on function public.swsi_ops_resolve_review_item(text,text,text,timestamptz)
  to service_role;

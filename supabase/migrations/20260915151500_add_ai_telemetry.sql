begin;

create table if not exists public.swsi_ai_telemetry_client_daily (
  usage_date date not null,
  client_hash text not null,
  event_count integer not null default 0,
  last_seen_at timestamptz not null default now(),
  primary key (usage_date, client_hash),
  constraint swsi_ai_telemetry_client_hash_format check (client_hash ~ '^[0-9a-f]{64}$'),
  constraint swsi_ai_telemetry_client_event_count_range check (event_count between 0 and 100)
);

comment on table public.swsi_ai_telemetry_client_daily is
  'Privacy-minimized anti-abuse counter for AI telemetry. Stores only SHA-256 of the random local browser id and a daily event count; no prompt, answer, image, IP, email, user-agent or device fingerprint.';

create table if not exists public.swsi_ai_telemetry_5m (
  bucket_start timestamptz not null,
  mode text not null,
  outcome text not null,
  request_count integer not null default 0,
  latency_total_ms bigint not null default 0,
  latency_max_ms integer not null default 0,
  primary key (bucket_start, mode, outcome),
  constraint swsi_ai_telemetry_mode check (mode in ('text','photo')),
  constraint swsi_ai_telemetry_outcome check (
    outcome in ('success','rate_limited','service_error','timeout','network_error','client_error')
  ),
  constraint swsi_ai_telemetry_request_count_range check (request_count between 0 and 10000),
  constraint swsi_ai_telemetry_latency_total_range check (latency_total_ms between 0 and 1200000000),
  constraint swsi_ai_telemetry_latency_max_range check (latency_max_ms between 0 and 120000)
);

comment on table public.swsi_ai_telemetry_5m is
  'Aggregate public-AI telemetry in 5-minute buckets. Contains only mode, coarse outcome and latency aggregates. Never stores prompt, answer, image, IP, email, user-agent or client id.';

alter table public.swsi_ai_telemetry_client_daily enable row level security;
alter table public.swsi_ai_telemetry_5m enable row level security;

revoke all on table public.swsi_ai_telemetry_client_daily from anon, authenticated;
revoke all on table public.swsi_ai_telemetry_5m from anon, authenticated;
grant select, insert, update on table public.swsi_ai_telemetry_client_daily to service_role;
grant select, insert, update on table public.swsi_ai_telemetry_5m to service_role;

create or replace function public.record_swsi_ai_telemetry(
  p_client_hash text,
  p_mode text,
  p_outcome text,
  p_latency_ms integer
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_day date := (timezone('Asia/Taipei', now()))::date;
  v_bucket timestamptz :=
    date_trunc('hour', now())
    + floor(extract(minute from now()) / 5) * interval '5 minutes';
  v_rows integer := 0;
  v_latency integer := greatest(0, least(coalesce(p_latency_ms, 0), 120000));
begin
  if p_client_hash is null or p_client_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'INVALID_CLIENT_HASH';
  end if;
  if p_mode not in ('text','photo') then
    raise exception 'INVALID_MODE';
  end if;
  if p_outcome not in ('success','rate_limited','service_error','timeout','network_error','client_error') then
    raise exception 'INVALID_OUTCOME';
  end if;

  insert into public.swsi_ai_telemetry_client_daily (
    usage_date, client_hash, event_count, last_seen_at
  ) values (
    v_day, p_client_hash, 1, now()
  )
  on conflict (usage_date, client_hash) do update
    set event_count = public.swsi_ai_telemetry_client_daily.event_count + 1,
        last_seen_at = now()
  where public.swsi_ai_telemetry_client_daily.event_count < 100;

  get diagnostics v_rows = row_count;
  if v_rows = 0 then
    return false;
  end if;

  insert into public.swsi_ai_telemetry_5m (
    bucket_start, mode, outcome, request_count, latency_total_ms, latency_max_ms
  ) values (
    v_bucket, p_mode, p_outcome, 1, v_latency, v_latency
  )
  on conflict (bucket_start, mode, outcome) do update
    set request_count = least(public.swsi_ai_telemetry_5m.request_count + 1, 10000),
        latency_total_ms = least(public.swsi_ai_telemetry_5m.latency_total_ms + excluded.latency_total_ms, 1200000000),
        latency_max_ms = greatest(public.swsi_ai_telemetry_5m.latency_max_ms, excluded.latency_max_ms);

  return true;
end;
$$;

revoke all on function public.record_swsi_ai_telemetry(text,text,text,integer) from public, anon, authenticated;
grant execute on function public.record_swsi_ai_telemetry(text,text,text,integer) to service_role;

create or replace function public.swsi_ai_telemetry_summary()
returns jsonb
language sql
stable
security definer
set search_path = public, pg_temp
as $$
with recent60 as (
  select
    coalesce(sum(request_count),0)::bigint as requests,
    coalesce(sum(request_count) filter (where outcome='success'),0)::bigint as successes,
    coalesce(sum(request_count) filter (where outcome='rate_limited'),0)::bigint as rate_limited,
    coalesce(sum(request_count) filter (where outcome='service_error'),0)::bigint as service_errors,
    coalesce(sum(request_count) filter (where outcome='timeout'),0)::bigint as timeouts,
    coalesce(sum(request_count) filter (where outcome='network_error'),0)::bigint as network_errors,
    coalesce(sum(request_count) filter (where outcome='client_error'),0)::bigint as client_errors,
    coalesce(sum(latency_total_ms) filter (where outcome='success'),0)::bigint as success_latency_total,
    coalesce(sum(request_count) filter (where outcome='success'),0)::bigint as success_latency_count
  from public.swsi_ai_telemetry_5m
  where bucket_start >= now() - interval '60 minutes'
),
recent24 as (
  select
    coalesce(sum(request_count),0)::bigint as requests,
    coalesce(sum(request_count) filter (where outcome='success'),0)::bigint as successes
  from public.swsi_ai_telemetry_5m
  where bucket_start >= now() - interval '24 hours'
),
lasts as (
  select
    min(bucket_start) as monitoring_since,
    max(bucket_start) as last_event_at,
    max(bucket_start) filter (where outcome='success') as last_success_at
  from public.swsi_ai_telemetry_5m
),
metrics as (
  select
    r.*,
    (r.service_errors + r.timeouts + r.network_errors)::bigint as hard_errors,
    case
      when r.success_latency_count > 0
      then round(r.success_latency_total::numeric / r.success_latency_count)::bigint
      else null
    end as avg_latency_ms
  from recent60 r
)
select jsonb_build_object(
  'enabled', true,
  'window_minutes', 60,
  'status',
    case
      when m.requests >= 3 and m.successes = 0 and m.hard_errors >= 3 then 'down'
      when m.requests >= 4 and m.hard_errors * 2 >= m.requests then 'degraded'
      when m.requests >= 4 and m.rate_limited * 2 >= m.requests then 'busy'
      when m.requests = 0 then 'idle'
      else 'ok'
    end,
  'requests_60m', m.requests,
  'successes_60m', m.successes,
  'rate_limited_60m', m.rate_limited,
  'service_errors_60m', m.service_errors,
  'timeouts_60m', m.timeouts,
  'network_errors_60m', m.network_errors,
  'client_errors_60m', m.client_errors,
  'hard_errors_60m', m.hard_errors,
  'success_rate_pct',
    case when m.requests > 0 then round((m.successes::numeric * 100.0) / m.requests, 1) else null end,
  'avg_latency_ms', m.avg_latency_ms,
  'requests_24h', r24.requests,
  'successes_24h', r24.successes,
  'monitoring_since', (select monitoring_since from lasts),
  'last_event_at', (select last_event_at from lasts),
  'last_success_at', (select last_success_at from lasts)
)
from metrics m cross join recent24 r24;
$$;

revoke all on function public.swsi_ai_telemetry_summary() from public, anon, authenticated;
grant execute on function public.swsi_ai_telemetry_summary() to service_role;

commit;

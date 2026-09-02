begin;

create table if not exists public.swsi_usage_daily (
  usage_date date not null,
  client_hash text not null,
  page_views integer not null default 0,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  primary key (usage_date, client_hash),
  constraint swsi_usage_daily_client_hash_format check (client_hash ~ '^[0-9a-f]{64}$'),
  constraint swsi_usage_daily_page_views_range check (page_views between 0 and 500)
);

comment on table public.swsi_usage_daily is
  'Privacy-minimized SWSI usage counts. Stores only SHA-256 of a random browser ID plus daily page-view totals; no IP, email, name, user-agent or fingerprint.';
comment on column public.swsi_usage_daily.client_hash is
  'SHA-256 of random local browser identifier. Not an account id and not derived from IP or device fingerprint.';

alter table public.swsi_usage_daily enable row level security;
revoke all on table public.swsi_usage_daily from anon, authenticated;
grant select, insert, update on table public.swsi_usage_daily to service_role;

create or replace function public.record_swsi_usage(p_client_hash text)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_day date := (timezone('Asia/Taipei', now()))::date;
begin
  if p_client_hash is null or p_client_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'INVALID_CLIENT_HASH';
  end if;

  insert into public.swsi_usage_daily (
    usage_date, client_hash, page_views, first_seen_at, last_seen_at
  ) values (
    v_day, p_client_hash, 1, now(), now()
  )
  on conflict (usage_date, client_hash) do update
    set page_views = least(public.swsi_usage_daily.page_views + 1, 500),
        last_seen_at = now();
end;
$$;

revoke all on function public.record_swsi_usage(text) from public, anon, authenticated;
grant execute on function public.record_swsi_usage(text) to service_role;

create or replace function public.swsi_usage_summary()
returns jsonb
language sql
stable
security definer
set search_path = public, pg_temp
as $$
with params as (
  select (timezone('Asia/Taipei', now()))::date as today
),
days as (
  select generate_series(
    (select today - 6 from params),
    (select today from params),
    interval '1 day'
  )::date as usage_date
),
daily as (
  select
    d.usage_date,
    count(u.client_hash)::bigint as users,
    coalesce(sum(u.page_views), 0)::bigint as page_views
  from days d
  left join public.swsi_usage_daily u on u.usage_date = d.usage_date
  group by d.usage_date
  order by d.usage_date
),
today_stats as (
  select
    count(*)::bigint as users,
    coalesce(sum(page_views), 0)::bigint as page_views
  from public.swsi_usage_daily
  where usage_date = (select today from params)
),
seven_day as (
  select count(distinct client_hash)::bigint as users
  from public.swsi_usage_daily
  where usage_date between (select today - 6 from params) and (select today from params)
),
all_time as (
  select
    count(distinct client_hash)::bigint as users,
    coalesce(sum(page_views), 0)::bigint as page_views,
    min(usage_date) as since
  from public.swsi_usage_daily
)
select jsonb_build_object(
  'enabled', true,
  'timezone', 'Asia/Taipei',
  'today', (select today::text from params),
  'today_users', (select users from today_stats),
  'today_page_views', (select page_views from today_stats),
  'seven_day_users', (select users from seven_day),
  'total_users', (select users from all_time),
  'total_page_views', (select page_views from all_time),
  'since', (select since::text from all_time),
  'daily_7d', (
    select coalesce(
      jsonb_agg(jsonb_build_object(
        'date', usage_date::text,
        'users', users,
        'page_views', page_views
      ) order by usage_date),
      '[]'::jsonb
    )
    from daily
  )
);
$$;

revoke all on function public.swsi_usage_summary() from public, anon, authenticated;
grant execute on function public.swsi_usage_summary() to service_role;

commit;

-- SWSI dual-site anonymous analytics; preserve all historical Cloudflare rows.
-- Existing per-browser hashes remain unchanged. Netlify starts counting only on activation.
begin;

alter table public.swsi_usage_daily
  add column if not exists site_origin text not null
  default 'https://wandering-wave-4418.c022050333.workers.dev';

alter table public.swsi_usage_daily
  add constraint swsi_usage_daily_allowed_origin
  check (site_origin in (
    'https://wandering-wave-4418.c022050333.workers.dev',
    'https://swsi-quiznetlify.netlify.app'
  ));

alter table public.swsi_usage_daily
  drop constraint swsi_usage_daily_pkey;
alter table public.swsi_usage_daily
  add primary key (usage_date, site_origin, client_hash);

comment on column public.swsi_usage_daily.site_origin is
  'One of two allowlisted SWSI deployed production hosts. Historical records are Cloudflare.';
comment on table public.swsi_usage_daily is
  'Daily anonymous per-site page counts. Only date, official site origin, SHA-256 browser ID, page views and timestamps.';

create or replace function public.record_swsi_usage(
  p_client_hash text, p_site_origin text
) returns void
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
  if p_site_origin not in (
    'https://wandering-wave-4418.c022050333.workers.dev',
    'https://swsi-quiznetlify.netlify.app'
  ) or p_site_origin is null then
    raise exception 'INVALID_SITE_ORIGIN';
  end if;
  insert into public.swsi_usage_daily (
    usage_date, site_origin, client_hash, page_views, first_seen_at, last_seen_at
  ) values (
    v_day, p_site_origin, p_client_hash, 1, now(), now()
  )
  on conflict (usage_date, site_origin, client_hash) do update
    set page_views = least(public.swsi_usage_daily.page_views + 1, 500),
        last_seen_at = now();
end;
$$;

-- Keep the old one-argument RPC working for already-deployed main-site clients.
create or replace function public.record_swsi_usage(p_client_hash text)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  perform public.record_swsi_usage(
    p_client_hash,
    'https://wandering-wave-4418.c022050333.workers.dev'
  );
end;
$$;

revoke all on function public.record_swsi_usage(text,text)
  from public, anon, authenticated;
grant execute on function public.record_swsi_usage(text,text) to service_role;
revoke all on function public.record_swsi_usage(text)
  from public, anon, authenticated;
grant execute on function public.record_swsi_usage(text) to service_role;
alter table public.swsi_usage_daily enable row level security;
revoke all on table public.swsi_usage_daily from anon, authenticated;

create or replace function public.swsi_usage_summary()
returns jsonb
language sql
stable
security definer
set search_path = public, pg_temp
as $$
with params as (
  select (timezone('Asia/Taipei', now()))::date as today
), origins(site_key,site_origin) as (
  values
    ('primary'::text,'https://wandering-wave-4418.c022050333.workers.dev'::text),
    ('backup'::text,'https://swsi-quiznetlify.netlify.app'::text)
), site_stats as (
  select o.site_key,
    count(u.client_hash) filter (where u.usage_date = p.today)::bigint as today_users,
    coalesce(sum(u.page_views) filter (where u.usage_date = p.today),0)::bigint as today_page_views,
    count(distinct u.client_hash) filter (where u.usage_date between p.today - 6 and p.today)::bigint as seven_day_users,
    count(distinct u.client_hash)::bigint as total_users,
    coalesce(sum(u.page_views),0)::bigint as total_page_views,
    min(u.usage_date) as since
  from origins o
  cross join params p
  left join public.swsi_usage_daily u on u.site_origin = o.site_origin
  group by o.site_key
), days as (
  select generate_series(
    (select today - 6 from params),
    (select today from params),
    interval '1 day'
  )::date as usage_date
), daily as (
  select d.usage_date,
    count(u.client_hash)::bigint as users,
    coalesce(sum(u.page_views),0)::bigint as page_views
  from days d
  left join public.swsi_usage_daily u on u.usage_date = d.usage_date
  group by d.usage_date
), today_stats as (
  select count(*)::bigint as users,
    coalesce(sum(page_views),0)::bigint as page_views
  from public.swsi_usage_daily
  where usage_date = (select today from params)
), seven_day as (
  select count(distinct (site_origin,client_hash))::bigint as users
  from public.swsi_usage_daily
  where usage_date between (select today - 6 from params) and (select today from params)
), all_time as (
  select count(distinct (site_origin,client_hash))::bigint as users,
    coalesce(sum(page_views),0)::bigint as page_views,
    min(usage_date) as since
  from public.swsi_usage_daily
)
select jsonb_build_object(
  'enabled',true,
  'timezone','Asia/Taipei',
  'today',(select today::text from params),
  'today_users',(select users from today_stats),
  'today_page_views',(select page_views from today_stats),
  'seven_day_users',(select users from seven_day),
  'total_users',(select users from all_time),
  'total_page_views',(select page_views from all_time),
  'since',(select since::text from all_time),
  'sites',(select jsonb_object_agg(
    site_key,jsonb_build_object(
      'today_users',today_users,
      'today_page_views',today_page_views,
      'seven_day_users',seven_day_users,
      'total_users',total_users,
      'total_page_views',total_page_views,
      'since',since::text
    ) order by site_key
  ) from site_stats),
  'daily_7d',(select coalesce(
    jsonb_agg(jsonb_build_object(
      'date',usage_date::text,
      'users',users,
      'page_views',page_views
    ) order by usage_date),'[]'::jsonb
  ) from daily)
);
$$;

revoke all on function public.swsi_usage_summary()
  from public, anon, authenticated;
grant execute on function public.swsi_usage_summary() to service_role;

commit;

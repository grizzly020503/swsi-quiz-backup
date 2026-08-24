create table if not exists public.current_affairs (
  id text primary key,
  title text not null,
  summary text,
  source_name text not null,
  source_url text not null,
  source_feed text,
  published_at timestamptz,
  region text not null default 'taiwan' check (region in ('taiwan','international')),
  category text not null,
  relevance_score smallint not null default 0 check (relevance_score between 0 and 10),
  exam_tags text[] not null default '{}',
  subjects text[] not null default '{}',
  status text not null default 'candidate' check (status in ('candidate','pinned','archived','ignored')),
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  manual_note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists current_affairs_source_url_uq on public.current_affairs(source_url);
create index if not exists current_affairs_published_idx on public.current_affairs(published_at desc);
create index if not exists current_affairs_score_idx on public.current_affairs(relevance_score desc, published_at desc);
create index if not exists current_affairs_tags_gin on public.current_affairs using gin(exam_tags);

alter table public.current_affairs enable row level security;

create table if not exists public.current_affairs_sync_runs (
  run_id bigint generated always as identity primary key,
  ran_at timestamptz not null default now(),
  fetched_count integer not null default 0,
  accepted_count integer not null default 0,
  note text
);

alter table public.current_affairs_sync_runs enable row level security;

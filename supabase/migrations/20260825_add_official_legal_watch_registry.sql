create table if not exists public.legal_reference_registry (
  canonical_name text primary key,
  question_count integer not null default 0,
  source_type text,
  official_url text,
  official_modified_date text,
  previous_modified_date text,
  last_checked_at timestamptz,
  last_change_detected_at timestamptz,
  watch_status text not null default 'baseline',
  note text,
  updated_at timestamptz not null default now(),
  constraint legal_reference_registry_watch_status_check
    check (watch_status in ('baseline','unchanged','changed','missing'))
);

alter table public.legal_reference_registry enable row level security;

create table if not exists public.legal_watch_hits (
  id bigint generated always as identity primary key,
  question_id text not null references public.questions(id) on delete cascade,
  canonical_name text not null,
  previous_modified_date text,
  new_modified_date text not null,
  official_url text,
  detected_at timestamptz not null default now(),
  resolved_at timestamptz,
  note text
);

alter table public.legal_watch_hits enable row level security;

create unique index if not exists legal_watch_hits_unique_change
  on public.legal_watch_hits(question_id, canonical_name, new_modified_date);

create index if not exists legal_watch_hits_question_idx
  on public.legal_watch_hits(question_id, resolved_at);

create index if not exists legal_reference_registry_status_idx
  on public.legal_reference_registry(watch_status, last_checked_at);

-- Recovered from Supabase migration metadata for isolated disaster recovery.
-- Production migration version/name:
--   20260824154417 add_moex_auto_sync_tables
--
-- This copy is recovery-only. Do not apply it to the existing production DB.

alter table public.questions
  add column if not exists source_exam_code text,
  add column if not exists source_url text,
  add column if not exists analysis_status text not null default 'ready';

create table if not exists public.essays (
  id text primary key,
  subject text not null,
  year text not null,
  round text not null,
  qno text not null,
  q text not null,
  points text,
  topic text,
  major text,
  keywords text[] not null default '{}',
  theories text[] not null default '{}',
  laws text[] not null default '{}',
  difficulty text,
  frequency text,
  qtype text,
  related text[] not null default '{}',
  cluster text,
  cluster_name text,
  source_exam_code text,
  source_url text,
  analysis_status text not null default 'pending',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.essays enable row level security;

drop policy if exists "public read essays" on public.essays;
create policy "public read essays"
on public.essays for select
to public
using (true);

drop policy if exists "authed write essays" on public.essays;
create policy "authed write essays"
on public.essays for all
to authenticated
using (true)
with check (true);

create table if not exists public.moex_sync_runs (
  exam_code text primary key,
  roc_year text not null,
  round text not null,
  status text not null,
  mc_count integer not null default 0,
  essay_count integer not null default 0,
  detected_at timestamptz not null default now(),
  imported_at timestamptz,
  source_page text,
  note text
);

alter table public.moex_sync_runs enable row level security;

-- SWSI Supabase recovery bootstrap baseline
--
-- Purpose:
--   Recreate only the schema objects that predate the repo-owned recovery
--   migrations and therefore cannot currently be rebuilt from migrations alone.
--
-- Source:
--   Read-only production schema introspection on 2026-09-26.
--
-- Safety:
--   Schema only. Contains no production rows, auth identities, secrets, API keys,
--   email addresses, or service-role credentials.
--   Do NOT apply blindly to an existing production project.

create table if not exists public.questions (
  id text primary key,
  subject text,
  year text,
  round text,
  qno text,
  major text,
  topic text,
  keywords text,
  question text,
  opt_a text,
  opt_b text,
  opt_c text,
  opt_d text,
  answer text,
  exp_why text,
  exp_others text,
  exp_trap text,
  exp_raw text,
  mnemonic text,
  extension text,
  law text,
  mistake text,
  source_exam_code text,
  source_url text,
  analysis_status text not null default 'ready'
);

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
  keywords text[] not null default '{}'::text[],
  theories text[] not null default '{}'::text[],
  laws text[] not null default '{}'::text[],
  difficulty text,
  frequency text,
  qtype text,
  related text[] not null default '{}'::text[],
  cluster text,
  cluster_name text,
  source_exam_code text,
  source_url text,
  analysis_status text not null default 'pending',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

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

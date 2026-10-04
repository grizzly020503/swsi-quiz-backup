-- Durable runtime projection of Stage-7/adjudicated historical-law evidence.
--
-- Source only. Adding this migration to the repository does NOT apply it to
-- production. The table intentionally stores only minimized provenance needed
-- for runtime trust; it must never duplicate protected Official Core fields.

create table if not exists public.historical_law_runtime_evidence (
  question_id text not null,
  law_name text not null,
  exam_code text not null check (exam_code ~ '^[0-9]{3}-[12]$'),
  article text not null,
  historical_version_checked boolean not null check (historical_version_checked = true),
  verification_level text not null check (
    verification_level in (
      'machine_verified_historical_v1',
      'evidence_adjudicated_historical_v1'
    )
  ),
  verification_basis text not null,
  selected_version_kind text not null check (selected_version_kind in ('current','oldver')),
  selected_version_date date not null,
  selected_effective_date date,
  selected_effective_date_scope text,
  selected_version_url text not null check (selected_version_url ~ '^https://law\.moj\.gov\.tw/'),
  historical_article_sha256 text not null check (historical_article_sha256 ~ '^[0-9a-f]{64}$'),
  official_history_url text not null check (official_history_url ~ '^https://law\.moj\.gov\.tw/'),
  exam_date_source_url text not null check (exam_date_source_url ~ '^https://wwwc\.moex\.gov\.tw/'),
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  source_registry_sha256 text not null check (source_registry_sha256 ~ '^[0-9a-f]{64}$'),
  synced_at timestamptz not null default now(),
  primary key (question_id, law_name)
);

create index if not exists historical_law_runtime_evidence_exam_idx
  on public.historical_law_runtime_evidence(exam_code, question_id);
create index if not exists historical_law_runtime_evidence_law_idx
  on public.historical_law_runtime_evidence(law_name, question_id);

alter table public.historical_law_runtime_evidence enable row level security;
revoke all on table public.historical_law_runtime_evidence from public, anon, authenticated;
grant select, insert, update on table public.historical_law_runtime_evidence to service_role;

create table if not exists public.historical_law_runtime_evidence_snapshot (
  id boolean primary key default true check (id = true),
  schema_version integer not null default 1 check (schema_version = 1),
  registry_sha256 text not null check (registry_sha256 ~ '^[0-9a-f]{64}$'),
  record_count integer not null check (record_count >= 0),
  historical_version_checked_count integer not null check (historical_version_checked_count >= 0),
  machine_verified_count integer not null check (machine_verified_count >= 0),
  evidence_adjudicated_count integer not null check (evidence_adjudicated_count >= 0),
  sync_status text not null check (sync_status in ('syncing','complete','failed')),
  source text not null default 'github_actions' check (source = 'github_actions'),
  updated_at timestamptz not null default now(),
  constraint historical_law_runtime_snapshot_counts_check check (
    record_count = historical_version_checked_count
    and record_count = machine_verified_count + evidence_adjudicated_count
  )
);

alter table public.historical_law_runtime_evidence_snapshot enable row level security;
revoke all on table public.historical_law_runtime_evidence_snapshot from public, anon, authenticated;
grant select, insert, update on table public.historical_law_runtime_evidence_snapshot to service_role;

comment on table public.historical_law_runtime_evidence is
  'Minimized exam-time law provenance verified by Stage7/adjudication. No Official Core content is stored here.';
comment on table public.historical_law_runtime_evidence_snapshot is
  'Singleton completeness/fingerprint marker for the latest historical-law runtime evidence projection.';

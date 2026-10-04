-- Global health marker for one completed official-law watch batch.
--
-- The per-law legal_reference_registry is not enough to prove that a whole
-- watcher run was healthy: moj_law_watch.py can finish with lookup errors for
-- some names while still producing usable rows for others. Runtime consumers
-- therefore need BOTH:
--   1) this singleton run marker is complete with lookup_error_count = 0; and
--   2) the individual law row was updated in the same checked_at batch.
--
-- Source-only migration. Adding this file does not apply it to production.

create table if not exists public.legal_watch_run_health (
  id boolean primary key default true check (id = true),
  schema_version integer not null default 1 check (schema_version = 1),
  checked_at timestamptz not null,
  baseline boolean not null default false,
  watch_count integer not null check (watch_count >= 0),
  matched_count integer not null check (matched_count >= 0),
  missing_count integer not null check (missing_count >= 0),
  changed_count integer not null check (changed_count >= 0),
  lookup_error_count integer not null check (lookup_error_count >= 0),
  sync_status text not null check (sync_status in ('syncing','complete','failed')),
  source text not null default 'github_actions',
  updated_at timestamptz not null default now(),
  constraint legal_watch_run_health_counts_check
    check (matched_count + missing_count = watch_count),
  constraint legal_watch_run_health_bounds_check
    check (changed_count <= matched_count and lookup_error_count <= watch_count)
);

alter table public.legal_watch_run_health enable row level security;

revoke all on table public.legal_watch_run_health from public, anon, authenticated;
grant select, insert, update on table public.legal_watch_run_health to service_role;

comment on table public.legal_watch_run_health is
  'Singleton global health marker for the latest sync-legal-watch batch. Runtime trust must fail closed unless sync_status=complete, baseline=false, lookup_error_count=0, and the per-law registry row has the same checked_at.';

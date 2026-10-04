-- Tighten runtime privileges for Stage7 historical-law evidence tables.
-- Supabase default table privileges can grant service_role capabilities that
-- these internal evidence projections do not need.

revoke all on table public.historical_law_runtime_evidence
  from public, anon, authenticated, service_role;
grant select, insert, update on table public.historical_law_runtime_evidence
  to service_role;

revoke all on table public.historical_law_runtime_evidence_snapshot
  from public, anon, authenticated, service_role;
grant select, insert, update on table public.historical_law_runtime_evidence_snapshot
  to service_role;

comment on table public.historical_law_runtime_evidence is
  'Minimized exam-time law provenance verified by Stage7/adjudication. No Official Core content is stored here. Only service_role SELECT/INSERT/UPDATE are granted.';
comment on table public.historical_law_runtime_evidence_snapshot is
  'Singleton completeness/fingerprint marker for the latest historical-law runtime evidence projection. Only service_role SELECT/INSERT/UPDATE are granted.';

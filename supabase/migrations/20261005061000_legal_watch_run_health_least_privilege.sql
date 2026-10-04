-- Tighten production and clean-restore privileges for legal_watch_run_health.
-- Supabase default privileges may grant service_role more capabilities than
-- this internal evidence table needs. Keep the runtime contract least-privilege.

revoke all on table public.legal_watch_run_health from public, anon, authenticated, service_role;
grant select, insert, update on table public.legal_watch_run_health to service_role;

comment on table public.legal_watch_run_health is
  'Singleton global health marker for the latest sync-legal-watch batch. Runtime trust must fail closed unless sync_status=complete, baseline=false, lookup_error_count=0, and the per-law registry row has the same checked_at. Only service_role SELECT/INSERT/UPDATE are granted.';

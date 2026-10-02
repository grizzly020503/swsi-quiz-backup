-- Recovery-only ACL alignment verified against production catalog.
--
-- Production read-only verification on 2026-10-02 confirms:
--   anon.rolbypassrls = false
--   authenticated.rolbypassrls = false
--   service_role.rolbypassrls = true
-- The disposable PostgreSQL harness creates portable test roles, so reproduce
-- that Supabase service-role property here before runtime-contract checks.
--
-- The earliest production AI queue migration explicitly revoked EXECUTE on
-- claim_pending_ai_questions(integer) from PUBLIC/anon/authenticated. That
-- migration predates the repo-owned consolidated recovery source, so a clean
-- PostgreSQL rebuild would otherwise inherit PostgreSQL's default PUBLIC
-- EXECUTE privilege on this SECURITY DEFINER function.
--
-- Production is already correct. This file is for isolated/future recovery
-- only and is intentionally outside supabase/migrations/.

alter role service_role bypassrls;

revoke all on function public.claim_pending_ai_questions(integer)
  from public, anon, authenticated;
grant execute on function public.claim_pending_ai_questions(integer)
  to service_role;

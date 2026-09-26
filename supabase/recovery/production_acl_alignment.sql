-- Recovery-only ACL alignment verified against production catalog on 2026-09-26.
--
-- The earliest production AI queue migration explicitly revoked EXECUTE on
-- claim_pending_ai_questions(integer) from PUBLIC/anon/authenticated. That
-- migration predates the repo-owned consolidated recovery source, so a clean
-- PostgreSQL rebuild would otherwise inherit PostgreSQL's default PUBLIC
-- EXECUTE privilege on this SECURITY DEFINER function.
--
-- Production is already correct. This file is for isolated/future recovery
-- only and is intentionally outside supabase/migrations/.

revoke all on function public.claim_pending_ai_questions(integer)
  from public, anon, authenticated;
grant execute on function public.claim_pending_ai_questions(integer)
  to service_role;

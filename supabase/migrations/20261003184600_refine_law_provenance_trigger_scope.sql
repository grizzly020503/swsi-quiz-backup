-- SWSI law metadata provenance guard lifecycle boundary
--
-- Purpose:
--   Trust-state changes (for example verified_current -> unreviewed) must not
--   mutate an already-reviewed law extension merely because the official stem
--   does not spell the law name out. The provenance guard remains responsible
--   for NEW/changed AI enrichment, not for legal-review lifecycle transitions.
--
-- Boundaries:
--   * Function semantics stay fail-closed for ready unverified law writes.
--   * INSERT still runs the guard.
--   * UPDATE of analysis_status/law/question/options still runs the guard.
--   * UPDATE of legal_status alone no longer runs the guard.
--   * No historical row is backfilled by this migration.

set search_path to public;

drop trigger if exists questions_00_sanitize_unverified_law_provenance
  on public.questions;

create trigger questions_00_sanitize_unverified_law_provenance
before insert or update of
  analysis_status,
  law,
  question,
  opt_a,
  opt_b,
  opt_c,
  opt_d
on public.questions
for each row
execute function public.sanitize_unverified_law_provenance();

comment on trigger questions_00_sanitize_unverified_law_provenance on public.questions is
  'Fail-closed AI law provenance guard. Trust-state-only legal_status changes do not mutate law enrichment.';

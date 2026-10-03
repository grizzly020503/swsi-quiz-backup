-- SWSI law metadata provenance guard
--
-- Purpose:
--   Prevent NEW unverified AI explanation writes from persisting inferred or
--   non-canonical law metadata as if it were grounded in the official exam.
--
-- Important boundaries:
--   * Official Core question / options / answers are never modified here.
--   * This migration does NOT backfill or rewrite historical rows.
--   * legal_canonical_names remains an impact/reference index, not proof that a
--     law is the correct answer basis.
--   * verified_current / changed rows are owned by an evidence-backed legal
--     review lifecycle and are not silently stripped by this guard.
--   * For ordinary generated explanations, precision wins over coverage: an
--     unsupported law is dropped while the rest of the ready explanation stays.
--
-- Reuse the existing canonicalizer (including reviewed aliases) instead of
-- creating a second law registry in application code.

create or replace function public.sanitize_unverified_law_provenance()
returns trigger
language plpgsql
set search_path to ''
as $function$
declare
  source_names text[] := '{}'::text[];
  law_names text[] := '{}'::text[];
begin
  -- Only police student-facing ready enrichment. Pending/review rows may retain
  -- draft/debug metadata for diagnosis.
  if lower(coalesce(new.analysis_status, '')) <> 'ready' then
    return new;
  end if;

  if nullif(btrim(coalesce(new.law, '')), '') is null then
    return new;
  end if;

  -- Evidence-backed legal review owns these states. This guard must not erase a
  -- reviewed extension merely because the official stem did not spell it out.
  if lower(coalesce(new.legal_status, '')) in ('verified_current', 'changed') then
    return new;
  end if;

  -- Official-source support is intentionally limited to the immutable question
  -- and option text. AI explanation fields are never accepted as self-evidence.
  source_names := public.extract_legal_canonical_names(
    concat_ws(
      ' ',
      new.question,
      new.opt_a,
      new.opt_b,
      new.opt_c,
      new.opt_d
    )
  );
  law_names := public.extract_legal_canonical_names(new.law);

  -- Fail closed without creating manual-work debt: law is optional enrichment.
  -- If it is not canonical, or any claimed canonical law is absent from the
  -- official question/options, drop the law field and keep the explanation.
  if coalesce(cardinality(law_names), 0) = 0
     or not (law_names <@ source_names) then
    new.law := null;

    -- Keep the reference index consistent even when this trigger was activated
    -- by analysis_status rather than an UPDATE OF law statement.
    new.legal_canonical_names := source_names;
  end if;

  return new;
end;
$function$;

comment on function public.sanitize_unverified_law_provenance() is
  'Fail-closed provenance guard for unverified ready law enrichment. Drops inferred/non-canonical law metadata while preserving Official Core and the rest of the explanation.';

drop trigger if exists questions_00_sanitize_unverified_law_provenance
  on public.questions;

create trigger questions_00_sanitize_unverified_law_provenance
before insert or update of
  analysis_status,
  law,
  legal_status,
  question,
  opt_a,
  opt_b,
  opt_c,
  opt_d
on public.questions
for each row
execute function public.sanitize_unverified_law_provenance();

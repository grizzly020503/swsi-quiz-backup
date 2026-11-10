-- SWSI production preflight: READ-ONLY official-source reset trigger contract.
-- No DML, grants, schema changes, credentials or user data; use on live only
-- as an observation before a future separately authorized release.
WITH seen AS (
  SELECT
    t.tgname, t.tgenabled, pg_get_triggerdef(t.oid, TRUE) AS ddl,
    pg_get_functiondef(t.tgfoid) AS fn
  FROM pg_trigger t
  JOIN pg_class c ON c.oid = t.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relname = 'questions'
    AND NOT t.tgisinternal
    AND t.tgname IN ('trg_reset_ai_on_official_change', 'trg_auto_enable_ai_pending')
),
checks AS (
 SELECT
  (SELECT count(*) FROM seen) = 2 AS two_triggers_exist,
  coalesce((SELECT tgenabled = 'O'
    AND ddl LIKE '%BEFORE UPDATE OF%'
    AND ddl LIKE '%opt_b%'
    AND ddl LIKE '%opt_c%'
    AND ddl LIKE '%opt_d%'
    AND fn LIKE '%new.analysis_status := ''pending''%'
    AND fn LIKE '%new.exp_why := null%'
    AND fn LIKE '%new.analysis_attempts := 0%'
    AND encode(sha256(convert_to(fn,'UTF8')),'hex') = '729a9c8e5158ebe73c65504ce988126d9e6de95d65eff8ed5bec9d6cacac74f0'
    FROM seen WHERE tgname='trg_reset_ai_on_official_change'), FALSE)
     AS canonical_reset_sets_pending,
  coalesce((SELECT tgenabled='O'
    AND ddl LIKE '%AFTER INSERT OR UPDATE OF analysis_status%'
    AND ddl NOT LIKE '%opt_c%'
    FROM seen WHERE tgname='trg_auto_enable_ai_pending'), FALSE)
     AS queue_enable_watches_explicit_status_updates,
  (SELECT enabled FROM public.ai_analysis_job_config WHERE id=TRUE)
    AS current_ai_job_enabled
)
SELECT *, CASE WHEN two_triggers_exist AND canonical_reset_sets_pending
    AND queue_enable_watches_explicit_status_updates
    AND current_ai_job_enabled IS FALSE
    THEN 'PASS_READONLY_TRIGGER_CONTRACT'
    ELSE 'HOLD_TRIGGER_DRIFT'
  END AS source_change_preflight
FROM checks;

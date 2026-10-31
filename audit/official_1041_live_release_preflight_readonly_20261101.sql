-- SWSI / 104-1 Direct Service Q22/Q27/Q29
-- READ-ONLY reusable production preflight (2026-11-01). Single SELECT query.
-- Execute using authorized Supabase database read-only access.
-- Never run a live UPDATE merely to test a trigger or external cron/net call.
-- All expected MD5 values below were read from live pg_catalog on 2026-11-01.
-- This verifies catalog drift and safe-state indicators only: NO HUMAN SIGNOFF,
-- no private-data restore evidence, no official-source text approval.
WITH
expected_trigger(tgname,trigger_md5,function_md5) AS (
  VALUES
    ('questions_00_sanitize_unverified_law_provenance','5dd21c9ef8509c4f7df2917ab61f9662','3c7b947c4c9c543f3f6e5ddeb4b86285'),
    ('questions_sync_legal_canonical_names','acd237201dd5d8604f1fffe361352b68','5dad2f79ae96ed78412d8f953a95ef3b'),
    ('trg_auto_enable_ai_pending','a7daa8fcfd170a2b4509915d05d9b0f1','606942297041402c6bc16cbbab2970ae'),
    ('trg_auto_stop_ai_queue','ab109b1577fd65d9d7033f355f8d65ab','d6df1ff381661c85dc03b049f874d069'),
    ('trg_questions_analysis_completed_at','59f248ee064cf0ed12bd432c42735aec','f50cb2144affb48c09074e9216863426'),
    ('trg_reject_ai_answer_meta_commentary','65752ce043ae32096cef138fdc8e5428','5ee0c1019d8df0e3deeabd88dc27c342'),
    ('trg_reset_ai_on_official_change','4335d9280c175f2e774a5378d3209f56','55921f1fa5733868c01e2047dea9170e')
),
current_trigger AS (
  SELECT t.tgname,t.tgenabled,
         md5(pg_get_triggerdef(t.oid)) AS trigger_md5,
         md5(pg_get_functiondef(p.oid)) AS function_md5
  FROM pg_trigger t
  JOIN pg_class c ON c.oid=t.tgrelid
  JOIN pg_namespace n ON n.oid=c.relnamespace
  JOIN pg_proc p ON p.oid=t.tgfoid
  WHERE n.nspname='public' AND c.relname='questions' AND NOT t.tgisinternal
),
trigger_check AS (
  SELECT count(*)::int AS compared,
         count(*) FILTER (WHERE e.tgname IS NULL OR a.tgname IS NULL
           OR a.tgenabled IS DISTINCT FROM 'O'
           OR a.trigger_md5 IS DISTINCT FROM e.trigger_md5
           OR a.function_md5 IS DISTINCT FROM e.function_md5)::int AS drift
  FROM expected_trigger e FULL OUTER JOIN current_trigger a USING(tgname)
),
expected_dependency(proname,pronargs,function_md5) AS (
  VALUES
    ('enable_swsi_ai_analysis',0,'8d2fa9c8b2eaf42e2898f55a0f3e5c95'),
    ('maybe_stop_swsi_ai_analysis',0,'a60b14078d9e50c93f45680c86594ece'),
    ('extract_legal_canonical_names',1,'e1e535e8c973f60a56c1698ce98fb810')
),
current_dependency AS (
  SELECT p.proname,p.pronargs,
         md5(pg_get_functiondef(p.oid)) AS function_md5
  FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname='public'
    AND p.proname IN ('enable_swsi_ai_analysis',
      'maybe_stop_swsi_ai_analysis','extract_legal_canonical_names')
),
dependency_check AS (
  SELECT count(*)::int AS compared,
         count(*) FILTER (WHERE e.proname IS NULL OR a.proname IS NULL
           OR a.function_md5 IS DISTINCT FROM e.function_md5)::int AS drift
  FROM expected_dependency e FULL OUTER JOIN current_dependency a
  USING(proname,pronargs)
),
exam AS (
  SELECT count(*)::int AS total,
         count(*) FILTER (WHERE analysis_status='pending')::int AS pending,
         count(*) FILTER (WHERE analysis_status='analyzing')::int AS analyzing
  FROM public.questions
),
targets AS (
  SELECT count(*)::int AS total,
         count(*) FILTER (WHERE (id='DS-104-1-22' AND analysis_status='ready')
                         OR (id='DS-104-1-27' AND analysis_status='ready')
                         OR (id='DS-104-1-29' AND analysis_status='review'))::int AS historical_status_matches
  FROM public.questions
  WHERE id IN ('DS-104-1-22','DS-104-1-27','DS-104-1-29')
),
queue AS (
  SELECT (SELECT enabled FROM public.ai_analysis_job_config LIMIT 1) AS enabled,
         count(*)::int AS cron_visible,
         count(*) FILTER (WHERE active AND
           (jobname ILIKE '%ai%' OR jobname ILIKE '%analysis%'))::int
           AS active_ai_named_jobs
  FROM cron.job
  GROUP BY enabled
),
permissions AS (
  SELECT (SELECT relrowsecurity FROM pg_class
          WHERE oid='public.questions'::regclass) AS rls,
         has_table_privilege('anon','public.questions','SELECT') AS anon_select,
         has_table_privilege('authenticated','public.questions','SELECT') AS auth_select,
         has_table_privilege('anon','public.questions','UPDATE') AS anon_update,
         has_table_privilege('authenticated','public.questions','UPDATE') AS auth_update
)
SELECT
  (tc.compared=7 AND tc.drift=0) AS seven_triggers_exact,
  tc.compared AS triggers_compared,
  tc.drift AS trigger_definition_drift,
  (dc.compared=3 AND dc.drift=0) AS three_dependencies_exact,
  dc.drift AS dependency_function_drift,
  ex.total AS mcq_rows,
  ex.pending AS pending_rows,
  ex.analyzing AS analyzing_rows,
  tg.total AS target_rows,
  tg.historical_status_matches AS original_status_matches,
  (q.enabled IS FALSE) AS ai_scheduler_disabled,
  q.active_ai_named_jobs,
  q.cron_visible,
  (p.rls AND p.anon_select AND p.auth_select
    AND NOT p.anon_update AND NOT p.auth_update) AS student_permissions_safe,
  (
    tc.compared=7 AND tc.drift=0
    AND dc.compared=3 AND dc.drift=0
    AND ex.total=4800 AND ex.pending=0 AND ex.analyzing=0
    AND tg.total=3 AND tg.historical_status_matches=3
    AND q.enabled IS FALSE AND q.active_ai_named_jobs=0
    AND p.rls AND p.anon_select AND p.auth_select
    AND NOT p.anon_update AND NOT p.auth_update
  ) AS read_only_technical_preflight_pass,
  FALSE AS independent_human_original_pdf_approval,
  FALSE AS production_faithful_private_restore_proven,
  FALSE AS permission_to_modify_official_core,
  'HOLD_NO_PRODUCTION_DML_OR_DEPLOY'::text AS release_gate
FROM trigger_check tc
CROSS JOIN dependency_check dc
CROSS JOIN exam ex
CROSS JOIN targets tg
CROSS JOIN queue q
CROSS JOIN permissions p;

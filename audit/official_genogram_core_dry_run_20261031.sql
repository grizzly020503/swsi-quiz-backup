-- Source-backed one-row correction. Default is a rollback-only rehearsal.
-- All assertions must pass; no trigger, RLS, grant, cron or analyzer change.
BEGIN ISOLATION LEVEL REPEATABLE READ;
SET LOCAL lock_timeout='3s';
SET LOCAL statement_timeout='15s';
DO $swsi_core_fix$
DECLARE
  expected_before jsonb := $before${"id":"DS-113-2-13","law":"","qno":"13","year":"113","major":"評估與處遇計畫","opt_a":"關係緊密","opt_b":"緊張衝突","opt_c":"疏離脆弱","opt_d":"正向關係","round":"第二次","topic":"家庭評估 > 家系圖關係符號","answer":"B","exp_raw":"","exp_why":"家系圖中,「鋸齒(波浪)線」代表緊張、衝突的關係;(B)。","mistake":"概念混淆","subject":"社會工作直接服務","exp_trap":"家系圖符號:鋸齒/波浪線=衝突;雙線=緊密;虛線=疏離。","keywords":"家系圖, 鋸齒線, 緊張衝突, 關係狀況, 符號","mnemonic":"家系圖:鋸齒線=緊張衝突關係。","question":"有關下圖案母與案主之間的關係狀況，下列何者正確？（圖示：62 歲男性與 24 歲女兒之間以鋸齒線連結）","extension":"家庭評估;家系圖符號。","exp_others":"(A)關係緊密用多條平行線、(C)疏離用虛線、(D)正向關係用實線——皆非「鋸齒線」。","legal_note":null,"source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=103&code=113100&q=1&s=0302&t=Q","grading_mode":"standard","legal_status":"not_applicable","analysis_error":null,"analysis_status":"ready","accepted_answers":null,"legal_checked_at":null,"legal_source_url":null,"source_exam_code":"113100","analysis_attempts":0,"analysis_started_at":null,"analysis_completed_at":null,"legal_canonical_names":[],"analysis_last_attempt_at":null}$before$::jsonb;
  expected_after jsonb := $after${"id":"DS-113-2-13","law":null,"qno":"13","year":"113","major":null,"opt_a":"關係緊密","opt_b":"緊張衝突","opt_c":"疏離脆弱","opt_d":"正向關係","round":"第二次","topic":null,"answer":"B","exp_raw":null,"exp_why":null,"mistake":null,"subject":"社會工作直接服務","exp_trap":null,"keywords":null,"mnemonic":null,"question":"有關下圖案母與案主之間的關係狀況，下列何者正確？","extension":null,"exp_others":null,"legal_note":null,"source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=103&code=113100&q=1&s=0302&t=Q","grading_mode":"standard","legal_status":"not_applicable","analysis_error":null,"analysis_status":"review","accepted_answers":null,"legal_checked_at":null,"legal_source_url":null,"source_exam_code":"113100","analysis_attempts":0,"analysis_started_at":null,"analysis_completed_at":null,"legal_canonical_names":[],"analysis_last_attempt_at":null}$after$::jsonb;
  actual_before jsonb; actual_after jsonb; other_before jsonb; other_after jsonb;
  grading_before jsonb; grading_after jsonb; config_before jsonb; config_after jsonb;
  changed integer;
BEGIN
  SELECT to_jsonb(q) INTO STRICT actual_before FROM public.questions q WHERE id='DS-113-2-13' FOR UPDATE;
  IF actual_before IS DISTINCT FROM expected_before THEN RAISE EXCEPTION 'SWSI controlled correction: preimage mismatch'; END IF;
  IF (SELECT count(*) FROM public.questions) <> 4800 THEN RAISE EXCEPTION 'SWSI corpus count mismatch'; END IF;
  SELECT jsonb_agg(to_jsonb(q) ORDER BY id) INTO other_before FROM public.questions q WHERE id<>'DS-113-2-13';
  SELECT jsonb_agg(jsonb_build_array(id,answer,accepted_answers,grading_mode) ORDER BY id) INTO grading_before FROM public.questions;
  SELECT to_jsonb(c) INTO config_before FROM public.ai_analysis_job_config c WHERE id=true;

  -- UPDATE only question: reset trigger clears stale enrichment but does not fire
  -- UPDATE OF analysis_status automation. Then quarantine before commit; pending
  -- is never visible to another transaction and no trigger is disabled.
  UPDATE public.questions SET question='有關下圖案母與案主之間的關係狀況，下列何者正確？' WHERE id='DS-113-2-13';
  GET DIAGNOSTICS changed=ROW_COUNT;
  IF changed<>1 THEN RAISE EXCEPTION 'SWSI correction affected unexpected rows'; END IF;
  UPDATE public.questions SET analysis_status='review' WHERE id='DS-113-2-13' AND analysis_status='pending';
  GET DIAGNOSTICS changed=ROW_COUNT;
  IF changed<>1 THEN RAISE EXCEPTION 'SWSI correction did not quarantine reset analysis'; END IF;

  SELECT to_jsonb(q) INTO STRICT actual_after FROM public.questions q WHERE id='DS-113-2-13';
  IF actual_after IS DISTINCT FROM expected_after THEN RAISE EXCEPTION 'SWSI correction postimage mismatch'; END IF;
  SELECT jsonb_agg(to_jsonb(q) ORDER BY id) INTO other_after FROM public.questions q WHERE id<>'DS-113-2-13';
  SELECT jsonb_agg(jsonb_build_array(id,answer,accepted_answers,grading_mode) ORDER BY id) INTO grading_after FROM public.questions;
  SELECT to_jsonb(c) INTO config_after FROM public.ai_analysis_job_config c WHERE id=true;
  IF other_before IS DISTINCT FROM other_after THEN RAISE EXCEPTION 'SWSI unrelated row changed'; END IF;
  IF grading_before IS DISTINCT FROM grading_after THEN RAISE EXCEPTION 'SWSI grading changed'; END IF;
  IF config_before IS DISTINCT FROM config_after THEN RAISE EXCEPTION 'SWSI AI configuration changed'; END IF;
  IF EXISTS (SELECT 1 FROM public.questions WHERE analysis_status='pending') THEN RAISE EXCEPTION 'SWSI unexpected pending analysis'; END IF;
END;
$swsi_core_fix$;
ROLLBACK;

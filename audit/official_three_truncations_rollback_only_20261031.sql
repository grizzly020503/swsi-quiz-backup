-- SWSI 2026-10-31 PR #500 3 source-backed MOEX truncated rows ROLLBACK-ONLY.
-- Exact project, exact row source snapshots; do not turn this into COMMIT.
-- 108-2 policy Q9 SHA256 956025f3383d3d721ae428e3dd8a3a97b0abed4026c5ed71bafc6e8a1171ff03
-- 109-2 direct Q26 SHA256 0351cc6a62bfc1f922ed58cea35cde6b20dde02db4d9768379273ba6baf9798e
-- 108-2 direct Q38 SHA256 78e9473d144f9165622f02ac3e5a004658b0ca7dd516c436f56cfdf4042b3e9b
BEGIN ISOLATION LEVEL REPEATABLE READ;
SET LOCAL lock_timeout='3s';
SET LOCAL statement_timeout='30s';
DO $swsi_three_rollback$
DECLARE
  expected_before jsonb:=$before$[{"id":"DS-108-2-38","subject":"社會工作直接服務","year":"108","round":"第二次","qno":"38","major":null,"topic":null,"keywords":null,"question":"2005 年之前，社工人力並未普遍於社區組織中被運用，其原因有哪些? ①「社區發展工作綱要」 ②社區組織無能力聘用專職人力 ③政府支持補助社工專職人力，但社區幹部不接受 ④社區場域派系糾葛抑制社工之專業能力發揮","opt_a":"①②③","opt_b":"②③④","opt_c":"①③④","opt_d":"①②④","answer":"D","exp_why":null,"exp_others":null,"exp_trap":null,"exp_raw":null,"mnemonic":null,"extension":null,"law":null,"mistake":null,"source_exam_code":"108110","source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=108110&q=1&s=0602&t=Q","analysis_status":"review","analysis_attempts":3,"analysis_error":"AI qwen/qwen3.6-27b HTTP 405: ","analysis_started_at":null,"analysis_completed_at":null,"legal_status":"not_applicable","legal_checked_at":null,"legal_note":null,"legal_source_url":null,"legal_canonical_names":["社區發展工作綱要"],"accepted_answers":null,"grading_mode":"standard","analysis_last_attempt_at":null},{"id":"DS-109-2-26","subject":"社會工作直接服務","year":"109","round":"第二次","qno":"26","major":"團體工作","topic":"團體類型 > 焦點團體特色","keywords":"焦點團體, 半結構, 充分討論, 自由方式, 實施特色","question":"有關焦點團體的實施特色，下列敘述何者正確？①焦點團體因為是針對特定主題的討論，成員難免針鋒相對 ②是一種半結構式的團體模式 ③通常成員的人數較多，人數約在 25 人以上 ④會充分討論一個問題後，才到下一個問題 ⑤會採用比較自由的方式","opt_a":"①②","opt_b":"③④","opt_c":"③⑤","opt_d":"②④","answer":"D","exp_why":null,"exp_others":null,"exp_trap":null,"exp_raw":null,"mnemonic":null,"extension":null,"law":"","mistake":"概念混淆","source_exam_code":"109110","source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=109110&q=1&s=0602&t=Q","analysis_status":"review","analysis_attempts":0,"analysis_error":"2026-10-02 multi-answer hold: standard accepted_answers grading is supported end-to-end; keep separate from single-answer HTTP-405 recovery and requeue only as a dedicated multi-answer batch/probe","analysis_started_at":null,"analysis_completed_at":null,"legal_status":"not_applicable","legal_checked_at":null,"legal_note":null,"legal_source_url":null,"legal_canonical_names":[],"accepted_answers":["A","D"],"grading_mode":"standard","analysis_last_attempt_at":null},{"id":"SP108-2-09","subject":"社會政策與社會立法","year":"108","round":"第二次","qno":"9","major":"婦女與性別法規","topic":"CEDAW施行法 > CEDAW國家報告","keywords":"消除對婦女歧視公約, CEDAW, 婦女人權法典, 施行法, 國家報告","question":"對於聯合國在1979 年通過消除對婦女一切形式歧視公約(CEDAW)，並在1981 年正式生 效，下列敘迹何者錯誤？","opt_a":"此公約被稱為婦女人權法典","opt_b":"我國是在2007 年經總統批准並頒發加入書","opt_c":"為明定CEDAW 具有國内法效力，我國在2010 年經行政院送出消除對婦女一切形式歧 視公約","opt_d":"依CEDAW 規定，每5 年提出我國消除對婦女歧視國家報告","answer":"D","exp_why":"(D)是錯的：CEDAW施行法的國家報告是『每4年』提出，不是每5年。","exp_others":"(A)CEDAW被稱為婦女人權法典、(B)我國2007年經總統批准並頒發加入書、(C)我國2010年送出施行法以明定國內法效力(施行法民國100年制定)——大致正確。","exp_trap":"CEDAW(1979通過/1981生效)＝婦女人權法典；國家報告每『4年』。","exp_raw":"","mnemonic":"CEDAW(1979通過/1981生效)＝婦女人權法典；施行法報告每4年。","extension":"CEDAW(1979通過、1981生效)；消除對婦女歧視之實質平等與暫行特別措施。","law":"消除對婦女一切形式歧視公約施行法。","mistake":"法規混淆","source_exam_code":"108110","source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=108110&q=1&s=0604&t=Q","analysis_status":"ready","analysis_attempts":0,"analysis_error":null,"analysis_started_at":null,"analysis_completed_at":null,"legal_status":"unreviewed","legal_checked_at":null,"legal_note":null,"legal_source_url":null,"legal_canonical_names":["消除對婦女一切形式歧視公約施行法"],"accepted_answers":null,"grading_mode":"standard","analysis_last_attempt_at":null}]$before$::jsonb;
  expected_after jsonb:=$after$[{"id":"DS-108-2-38","subject":"社會工作直接服務","year":"108","round":"第二次","qno":"38","major":null,"topic":null,"keywords":null,"question":"2005 年之前，社工人力並未普遍於社區組織中被運用，其原因有哪些? ①「社區發展工作綱要」強調社區組織的「志工化」 ②社區組織無能力聘用專職人力 ③政府支持補助社工專職人力，但社區幹部不接受 ④社區場域派系糾葛抑制社工之專業能力發揮","opt_a":"①②③","opt_b":"②③④","opt_c":"①③④","opt_d":"①②④","answer":"D","exp_why":null,"exp_others":null,"exp_trap":null,"exp_raw":null,"mnemonic":null,"extension":null,"law":null,"mistake":null,"source_exam_code":"108110","source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=108110&q=1&s=0602&t=Q","analysis_status":"review","analysis_attempts":0,"analysis_error":null,"analysis_started_at":null,"analysis_completed_at":null,"legal_status":"not_applicable","legal_checked_at":null,"legal_note":null,"legal_source_url":null,"legal_canonical_names":["社區發展工作綱要"],"accepted_answers":null,"grading_mode":"standard","analysis_last_attempt_at":null},{"id":"DS-109-2-26","subject":"社會工作直接服務","year":"109","round":"第二次","qno":"26","major":null,"topic":null,"keywords":null,"question":"有關焦點團體的實施特色，下列敘述何者正確？①焦點團體因為是針對特定主題的討論，成員間難免針鋒相對 ②是一種半結構式的團體模式 ③通常成員的人數較多，人數約在 25 人以上，以便充分蒐集資料讓討論內容有代表性 ④會充分討論一個問題後，才到下一個問題 ⑤會採用比較自由的方式，在所有題目間跳動發表意見，增加討論的流暢性","opt_a":"①②","opt_b":"③④","opt_c":"③⑤","opt_d":"②④","answer":"D","exp_why":null,"exp_others":null,"exp_trap":null,"exp_raw":null,"mnemonic":null,"extension":null,"law":null,"mistake":null,"source_exam_code":"109110","source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=109110&q=1&s=0602&t=Q","analysis_status":"review","analysis_attempts":0,"analysis_error":null,"analysis_started_at":null,"analysis_completed_at":null,"legal_status":"not_applicable","legal_checked_at":null,"legal_note":null,"legal_source_url":null,"legal_canonical_names":[],"accepted_answers":["A","D"],"grading_mode":"standard","analysis_last_attempt_at":null},{"id":"SP108-2-09","subject":"社會政策與社會立法","year":"108","round":"第二次","qno":"9","major":null,"topic":null,"keywords":null,"question":"對於聯合國在1979 年通過消除對婦女一切形式歧視公約(CEDAW)，並在1981 年正式生效，下列敘述何者錯誤？","opt_a":"此公約被稱為婦女人權法典","opt_b":"我國是在2007 年經總統批准並頒發加入書","opt_c":"為明定CEDAW 具有國內法效力，我國在2010 年經行政院送出消除對婦女一切形式歧視公約施行法草案，經立法院2011 年三讀通過，並自2012 年1 月1 日起施行","opt_d":"依CEDAW 規定，每5 年提出我國消除對婦女歧視國家報告","answer":"D","exp_why":null,"exp_others":null,"exp_trap":null,"exp_raw":null,"mnemonic":null,"extension":null,"law":null,"mistake":null,"source_exam_code":"108110","source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=108110&q=1&s=0604&t=Q","analysis_status":"review","analysis_attempts":0,"analysis_error":null,"analysis_started_at":null,"analysis_completed_at":null,"legal_status":"unreviewed","legal_checked_at":null,"legal_note":null,"legal_source_url":null,"legal_canonical_names":["消除對婦女一切形式歧視公約施行法"],"accepted_answers":null,"grading_mode":"standard","analysis_last_attempt_at":null}]$after$::jsonb;
  item jsonb; observed jsonb; other_before jsonb; other_after jsonb;
  grading_before jsonb; grading_after jsonb; config_before jsonb; config_after jsonb;
  changed integer;
BEGIN
  IF (SELECT COUNT(*) FROM public.questions)<>4800 THEN RAISE EXCEPTION 'P0 corpus count drift';END IF;
  SELECT jsonb_agg(to_jsonb(q) ORDER BY id) INTO other_before FROM public.questions q WHERE id NOT IN ('DS-108-2-38','DS-109-2-26','SP108-2-09');
  SELECT jsonb_agg(jsonb_build_array(id,answer,accepted_answers,grading_mode) ORDER BY id) INTO grading_before FROM public.questions;
  SELECT to_jsonb(c) INTO config_before FROM public.ai_analysis_job_config c WHERE id=true;
  IF config_before->>'enabled'<>'false' THEN RAISE EXCEPTION 'AI queue enabled';END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(expected_before) LOOP
    SELECT to_jsonb(q) INTO STRICT observed FROM public.questions q WHERE id=item->>'id' FOR UPDATE;
    IF observed IS DISTINCT FROM item THEN RAISE EXCEPTION 'P0 exact source row drift: %',item->>'id';END IF;
  END LOOP;
  UPDATE public.questions SET question='2005 年之前，社工人力並未普遍於社區組織中被運用，其原因有哪些? ①「社區發展工作綱要」強調社區組織的「志工化」 ②社區組織無能力聘用專職人力 ③政府支持補助社工專職人力，但社區幹部不接受 ④社區場域派系糾葛抑制社工之專業能力發揮' WHERE id='DS-108-2-38';
  GET DIAGNOSTICS changed=ROW_COUNT;
  IF changed<>1 THEN RAISE EXCEPTION 'P0 update row count DS-108-2-38';END IF;
  UPDATE public.questions SET question='有關焦點團體的實施特色，下列敘述何者正確？①焦點團體因為是針對特定主題的討論，成員間難免針鋒相對 ②是一種半結構式的團體模式 ③通常成員的人數較多，人數約在 25 人以上，以便充分蒐集資料讓討論內容有代表性 ④會充分討論一個問題後，才到下一個問題 ⑤會採用比較自由的方式，在所有題目間跳動發表意見，增加討論的流暢性' WHERE id='DS-109-2-26';
  GET DIAGNOSTICS changed=ROW_COUNT;
  IF changed<>1 THEN RAISE EXCEPTION 'P0 update row count DS-109-2-26';END IF;
  UPDATE public.questions SET question='對於聯合國在1979 年通過消除對婦女一切形式歧視公約(CEDAW)，並在1981 年正式生效，下列敘述何者錯誤？', opt_c='為明定CEDAW 具有國內法效力，我國在2010 年經行政院送出消除對婦女一切形式歧視公約施行法草案，經立法院2011 年三讀通過，並自2012 年1 月1 日起施行' WHERE id='SP108-2-09';
  GET DIAGNOSTICS changed=ROW_COUNT;
  IF changed<>1 THEN RAISE EXCEPTION 'P0 update row count SP108-2-09';END IF;
  UPDATE public.questions SET analysis_status='review'
    WHERE id IN ('DS-108-2-38','DS-109-2-26','SP108-2-09') AND analysis_status='pending';
  GET DIAGNOSTICS changed=ROW_COUNT;
  IF changed<>3 THEN RAISE EXCEPTION 'P0 enrichment quarantine mismatch';END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(expected_after) LOOP
    SELECT to_jsonb(q) INTO STRICT observed FROM public.questions q WHERE id=item->>'id';
    IF observed IS DISTINCT FROM item THEN RAISE EXCEPTION 'P0 exact after row mismatch: %',item->>'id';END IF;
  END LOOP;
  SELECT jsonb_agg(to_jsonb(q) ORDER BY id) INTO other_after FROM public.questions q WHERE id NOT IN ('DS-108-2-38','DS-109-2-26','SP108-2-09');
  SELECT jsonb_agg(jsonb_build_array(id,answer,accepted_answers,grading_mode) ORDER BY id) INTO grading_after FROM public.questions;
  SELECT to_jsonb(c) INTO config_after FROM public.ai_analysis_job_config c WHERE id=true;
  IF other_before IS DISTINCT FROM other_after THEN RAISE EXCEPTION 'P0 unrelated row changed';END IF;
  IF grading_before IS DISTINCT FROM grading_after THEN RAISE EXCEPTION 'P0 grading changed';END IF;
  IF config_before IS DISTINCT FROM config_after THEN RAISE EXCEPTION 'P0 AI config changed';END IF;
  IF EXISTS(SELECT 1 FROM public.questions WHERE analysis_status='pending') THEN RAISE EXCEPTION 'P0 unexpected pending AI queue';END IF;
  RAISE NOTICE 'SWSI three-row ROLLBACK rehearsal OK: 4797 full rows / all 4800 grading tuples preserved';
END;
$swsi_three_rollback$;
ROLLBACK;

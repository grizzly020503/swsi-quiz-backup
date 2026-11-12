-- Exact owner-approved 5-option update. No answer, queue, schema or student-data writes.
-- Run with ROLLBACK for rehearsal; COMMIT only after exact-head release CI.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
LOCK TABLE public.questions IN SHARE ROW EXCLUSIVE MODE;
CREATE TEMP TABLE p0_before ON COMMIT DROP AS SELECT id, to_jsonb(q) AS row FROM public.questions q;
CREATE TEMP TABLE p0_job_before ON COMMIT DROP AS SELECT to_jsonb(c) AS row FROM public.ai_analysis_job_config c;
DO $guard$
BEGIN
  IF (SELECT count(*) FROM p0_before) <> 4800 THEN RAISE EXCEPTION 'corpus count drift'; END IF;
  IF (SELECT enabled FROM public.ai_analysis_job_config WHERE id=true) IS DISTINCT FROM false THEN RAISE EXCEPTION 'AI queue not paused'; END IF;
  IF (SELECT encode(sha256(convert_to(to_jsonb(q)::text,'UTF8')),'hex') FROM public.questions q WHERE id='SP104-2-37') IS DISTINCT FROM '10ed64cb7f1343b45dabb025bf54c281ffb36ec35ccf1128d37f784ddecb7dfb' THEN RAISE EXCEPTION 'preimage drift'; END IF;
  IF (SELECT encode(sha256(convert_to(to_jsonb(q)::text,'UTF8')),'hex') FROM public.questions q WHERE id='SP107-1-40') IS DISTINCT FROM '588af4d0976c6758594e679110f210f4f14dadeebddb9c84a196889e6e7c101f' THEN RAISE EXCEPTION 'preimage drift'; END IF;
  IF (SELECT encode(sha256(convert_to(pg_get_functiondef(t.tgfoid),'UTF8')),'hex') FROM pg_trigger t WHERE tgrelid='public.questions'::regclass AND tgname='trg_reset_ai_on_official_change') IS DISTINCT FROM '729a9c8e5158ebe73c65504ce988126d9e6de95d65eff8ed5bec9d6cacac74f0' THEN RAISE EXCEPTION 'reset trigger drift'; END IF;
END $guard$;
UPDATE public.questions SET opt_b='①③④', opt_c='①③⑤', opt_d='②④⑤' WHERE id='SP104-2-37';
UPDATE public.questions SET opt_c='②③④⑤', opt_d='②③④' WHERE id='SP107-1-40';
DO $assert$
BEGIN
  IF (SELECT to_jsonb(q) FROM public.questions q WHERE id='SP104-2-37') IS DISTINCT FROM $expected${"id":"SP104-2-37","law":null,"qno":"37","year":"104","major":null,"opt_a":"①②③","opt_b":"①③④","opt_c":"①③⑤","opt_d":"②④⑤","round":"第二次","topic":null,"answer":"C","exp_raw":null,"exp_why":null,"mistake":null,"subject":"社會政策與社會立法","exp_trap":null,"keywords":null,"mnemonic":null,"question":"老人照顧機構的發展趨勢，下列組合何者正確？①環境似家化 ②功能單一化 ③規模小型化 ④生活制式化 ⑤環境安全化","extension":null,"exp_others":null,"legal_note":null,"source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=104100&q=1&s=0604&t=Q","grading_mode":"standard","legal_status":"unreviewed","analysis_error":null,"analysis_status":"pending","accepted_answers":null,"legal_checked_at":null,"legal_source_url":null,"source_exam_code":"104100","analysis_attempts":0,"analysis_started_at":null,"analysis_completed_at":null,"legal_canonical_names":[],"analysis_last_attempt_at":null}$expected$::jsonb THEN RAISE EXCEPTION 'unexpected postimage SP104-2-37'; END IF;
  IF (SELECT to_jsonb(q) FROM public.questions q WHERE id='SP107-1-40') IS DISTINCT FROM $expected${"id":"SP107-1-40","law":null,"qno":"40","year":"107","major":null,"opt_a":"①②③④","opt_b":"①③④⑤","opt_c":"②③④⑤","opt_d":"②③④","round":"第一次","topic":null,"answer":"B","exp_raw":null,"exp_why":null,"mistake":null,"subject":"社會政策與社會立法","exp_trap":null,"keywords":null,"mnemonic":null,"question":"下列選項中，那一個組合是屬於兒童及少年福利與權益保障法中之兒少福利機構？①托嬰中心 ②幼兒園 ③早期療育機構 ④安置及教養機構 ⑤心理輔導或家庭諮詢機構","extension":null,"exp_others":null,"legal_note":null,"source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=107030&q=1&s=0604&t=Q","grading_mode":"standard","legal_status":"unreviewed","analysis_error":null,"analysis_status":"pending","accepted_answers":null,"legal_checked_at":null,"legal_source_url":null,"source_exam_code":"107030","analysis_attempts":0,"analysis_started_at":null,"analysis_completed_at":null,"legal_canonical_names":["兒童及少年福利與權益保障法"],"analysis_last_attempt_at":null}$expected$::jsonb THEN RAISE EXCEPTION 'unexpected postimage SP107-1-40'; END IF;
  IF EXISTS (SELECT 1 FROM p0_before b FULL JOIN public.questions q USING(id) WHERE coalesce(b.id,q.id) NOT IN ('SP104-2-37','SP107-1-40') AND b.row IS DISTINCT FROM to_jsonb(q)) THEN RAISE EXCEPTION 'unrelated question changed'; END IF;
  IF EXISTS ((SELECT row FROM p0_job_before EXCEPT SELECT to_jsonb(c) FROM public.ai_analysis_job_config c) UNION ALL (SELECT to_jsonb(c) FROM public.ai_analysis_job_config c EXCEPT SELECT row FROM p0_job_before)) THEN RAISE EXCEPTION 'AI job changed'; END IF;
END $assert$;
SELECT id, opt_a, opt_b, opt_c, opt_d, answer, analysis_status, encode(sha256(convert_to(to_jsonb(q)::text,'UTF8')),'hex') AS postimage_sha256 FROM public.questions q WHERE id IN ('SP104-2-37','SP107-1-40') ORDER BY id;
ROLLBACK;

-- SOURCE PROOF: original MOEX PDF SHA256 exact confirmed, 2026-10-31
-- 105090-107-0606 6afea97bde8d58d00358d23bc5a31a0372a47f98d60b99ebc8f04495e3e9d836
-- 106030-107-0602 9f6d1a64364b25387606e32b8f0a89142ad42fa8e1474c64f712b7e3fad9179c
-- This is ROLLBACK-ONLY rehearsal, NOT production approval.
BEGIN ISOLATION LEVEL REPEATABLE READ;
SET LOCAL lock_timeout='3s';
SET LOCAL statement_timeout='30s';
DO $two_source_p0$
DECLARE
  expected_before jsonb:=$before$[{"id":"DS-106-1-34","subject":"社會工作直接服務","year":"106","round":"第一次","qno":"34","major":"會談與溝通技巧","topic":"自我揭露 > 使用自我","keywords":"使用自我, use of self, 示範真誠, 揭露經驗, 技術","question":"使用自我（use of self）是社會工作直接服務常用的技術，請問下列那一項屬於使用自我 的做法？","opt_a":"深層次的同理心，將覺察到的個案情緒反應出來 心，將覺察到的個案情緒反應出來","opt_b":"示範真誠的行為或適時揭露自己的經驗、想法","opt_c":"透過案主的轉移，處理其和工作者的關係之議題 其和工作者的關係之議題","opt_d":"同理心或設身處地和案主互動，並給予的正向回饋 心或設身處地和案主互動，並給予的正向回饋","answer":"B","exp_why":"(B)使用自我(use of self)：示範真誠的行為、或適時揭露自己的經驗與想法。","exp_others":"(A)是深層同理、(C)是處理轉移、(D)是同理與正向回饋——皆非『使用自我』的核心定義。","exp_trap":"自我表露/使用自我:有意有目的透露自身訊息(口語與非口語);類型＝立即性與個人性;以誠實為基礎且須考量是否有助專業關係與案主利益;含分享與面質意味。","exp_raw":"","mnemonic":"使用自我/自我表露＝有目的透露自身訊息(口語非口語);類型＝立即性與個人性;以誠實為基礎、須利於專業關係與案主利益。","extension":"會談技巧(使用自我)。","law":"","mistake":"概念混淆","source_exam_code":"106030","source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=106030&q=1&s=0602&t=Q","analysis_status":"ready","analysis_attempts":0,"analysis_error":null,"analysis_started_at":null,"analysis_completed_at":null,"legal_status":"not_applicable","legal_checked_at":null,"legal_note":null,"legal_source_url":null,"legal_canonical_names":[],"accepted_answers":null,"grading_mode":"standard","analysis_last_attempt_at":null},{"id":"R-105-2-07","subject":"社會工作研究方法","year":"105","round":"第二次","qno":"7","major":"統計檢定","topic":"統計檢定 > 型 I/II 錯誤","keywords":"型I錯誤, 型II錯誤, 檢定力","question":"型Ⅰ錯誤稱為 ，型Ⅱ錯誤稱為 ，下列敘述何者錯誤？","opt_a":"在不增加 的情況下，我們可以增加樣本數達到降低 的目的","opt_b":"1-稱為檢定力，對立假設為真時，錯誤判斷的機率","opt_c":"是指虛無假設為假，不拒絕虛無假設的機率","opt_d":"是指虛無假設為真，但拒斥虛無假設的機率","answer":"B","exp_why":"用煙霧警報器想：型Ⅰ錯誤＝沒火卻響（誤報）；型Ⅱ錯誤＝有火卻沒響（漏掉）。「檢定力」就是「真的失火時，警報抓得到的本事」——它是抓對的能力、不是出錯的機率，越高越好。(B)把檢定力說成「錯誤判斷的機率」，剛好說反了。","exp_others":"(A)不動α而加大樣本可降低β，正確；(C)β＝有火沒響（虛無為假卻不拒絕）的機率，正確；(D)α＝沒火卻響（虛無為真卻拒絕）的機率，正確。","exp_trap":"檢定力是「好能力」，常被偷換成「錯誤率」。記住1−β＝抓到真效果的本事。","exp_raw":"","mnemonic":"型Ⅰ＝誤報、型Ⅱ＝漏報；檢定力＝真失火時警報抓得到的本事，越大越靈，不是出錯率。","extension":"檢定力四要素（α、效果量、樣本數、變異）→增樣本提升檢定力。","law":"","mistake":"概念混淆","source_exam_code":"105090","source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=105090&q=1&s=0606&t=Q","analysis_status":"ready","analysis_attempts":0,"analysis_error":null,"analysis_started_at":null,"analysis_completed_at":null,"legal_status":"not_applicable","legal_checked_at":null,"legal_note":null,"legal_source_url":null,"legal_canonical_names":[],"accepted_answers":null,"grading_mode":"standard","analysis_last_attempt_at":null}]$before$::jsonb;
  expected_after jsonb:=$after$[{"id":"DS-106-1-34","subject":"社會工作直接服務","year":"106","round":"第一次","qno":"34","major":null,"topic":null,"keywords":null,"question":"使用自我（use of self）是社會工作直接服務常用的技術，請問下列那一項屬於使用自我的做法？","opt_a":"深層次的同理心，將覺察到的個案情緒反應出來","opt_b":"示範真誠的行為或適時揭露自己的經驗、想法","opt_c":"透過案主的轉移，處理其和工作者的關係之議題","opt_d":"同理心或設身處地和案主互動，並給予的正向回饋","answer":"B","exp_why":null,"exp_others":null,"exp_trap":null,"exp_raw":null,"mnemonic":null,"extension":null,"law":null,"mistake":null,"source_exam_code":"106030","source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=106030&q=1&s=0602&t=Q","analysis_status":"review","analysis_attempts":0,"analysis_error":null,"analysis_started_at":null,"analysis_completed_at":null,"legal_status":"not_applicable","legal_checked_at":null,"legal_note":null,"legal_source_url":null,"legal_canonical_names":[],"accepted_answers":null,"grading_mode":"standard","analysis_last_attempt_at":null},{"id":"R-105-2-07","subject":"社會工作研究方法","year":"105","round":"第二次","qno":"7","major":null,"topic":null,"keywords":null,"question":"型Ⅰ錯誤稱為α，型Ⅱ錯誤稱為β，下列敘述何者錯誤？","opt_a":"在不增加α 的情況下，我們可以增加樣本數達到降低β 的目的","opt_b":"1-β 稱為檢定力，對立假設為真時，錯誤判斷的機率","opt_c":"β 是指虛無假設為假，不拒絕虛無假設的機率","opt_d":"α 是指虛無假設為真，但拒斥虛無假設的機率","answer":"B","exp_why":null,"exp_others":null,"exp_trap":null,"exp_raw":null,"mnemonic":null,"extension":null,"law":null,"mistake":null,"source_exam_code":"105090","source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=105090&q=1&s=0606&t=Q","analysis_status":"review","analysis_attempts":0,"analysis_error":null,"analysis_started_at":null,"analysis_completed_at":null,"legal_status":"not_applicable","legal_checked_at":null,"legal_note":null,"legal_source_url":null,"legal_canonical_names":[],"accepted_answers":null,"grading_mode":"standard","analysis_last_attempt_at":null}]$after$::jsonb;
  item jsonb;observed jsonb;others_before jsonb;others_after jsonb;
  grades_before jsonb;grades_after jsonb;ai_before jsonb;ai_after jsonb;changed integer;
BEGIN
  IF (SELECT count(*) FROM public.questions)<>4800 THEN RAISE EXCEPTION 'MOEX source corpus count drift';END IF;
  SELECT jsonb_agg(to_jsonb(q) ORDER BY id) INTO others_before FROM public.questions q WHERE id NOT IN ('DS-106-1-34','R-105-2-07');
  SELECT jsonb_agg(jsonb_build_array(id,answer,accepted_answers,grading_mode) ORDER BY id) INTO grades_before FROM public.questions;
  SELECT to_jsonb(c) INTO ai_before FROM public.ai_analysis_job_config c WHERE id=true;
  IF ai_before->>'enabled'<>'false' THEN RAISE EXCEPTION 'MOEX analyzer enabled unexpectedly'; END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(expected_before) LOOP
    SELECT to_jsonb(q) INTO STRICT observed FROM public.questions q WHERE id=item->>'id' FOR UPDATE;
    IF observed IS DISTINCT FROM item THEN RAISE EXCEPTION 'MOEX preimage differs %',item->>'id'; END IF;
  END LOOP;
  UPDATE public.questions SET question='使用自我（use of self）是社會工作直接服務常用的技術，請問下列那一項屬於使用自我的做法？',opt_a='深層次的同理心，將覺察到的個案情緒反應出來',opt_c='透過案主的轉移，處理其和工作者的關係之議題',opt_d='同理心或設身處地和案主互動，並給予的正向回饋' WHERE id='DS-106-1-34';
  GET DIAGNOSTICS changed=ROW_COUNT; IF changed<>1 THEN RAISE EXCEPTION 'MOEX source P0 update mismatch DS-106-1-34'; END IF;
  UPDATE public.questions SET question='型Ⅰ錯誤稱為α，型Ⅱ錯誤稱為β，下列敘述何者錯誤？',opt_a='在不增加α 的情況下，我們可以增加樣本數達到降低β 的目的',opt_b='1-β 稱為檢定力，對立假設為真時，錯誤判斷的機率',opt_c='β 是指虛無假設為假，不拒絕虛無假設的機率',opt_d='α 是指虛無假設為真，但拒斥虛無假設的機率' WHERE id='R-105-2-07';
  GET DIAGNOSTICS changed=ROW_COUNT; IF changed<>1 THEN RAISE EXCEPTION 'MOEX source P0 update mismatch R-105-2-07'; END IF;
  UPDATE public.questions SET analysis_status='review' WHERE id IN ('DS-106-1-34','R-105-2-07') AND analysis_status='pending';
  GET DIAGNOSTICS changed=ROW_COUNT; IF changed<>2 THEN RAISE EXCEPTION 'MOEX 2-row quarantine failed';END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(expected_after) LOOP
    SELECT to_jsonb(q) INTO STRICT observed FROM public.questions q WHERE id=item->>'id';
    IF observed IS DISTINCT FROM item THEN RAISE EXCEPTION 'MOEX postimage differs %',item->>'id';END IF;
  END LOOP;
  SELECT jsonb_agg(to_jsonb(q) ORDER BY id) INTO others_after FROM public.questions q WHERE id NOT IN ('DS-106-1-34','R-105-2-07');
  SELECT jsonb_agg(jsonb_build_array(id,answer,accepted_answers,grading_mode) ORDER BY id) INTO grades_after FROM public.questions;
  SELECT to_jsonb(c) INTO ai_after FROM public.ai_analysis_job_config c WHERE id=true;
  IF others_before IS DISTINCT FROM others_after THEN RAISE EXCEPTION 'MOEX unrelated rows changed';END IF;
  IF grades_before IS DISTINCT FROM grades_after THEN RAISE EXCEPTION 'MOEX grading tuples changed';END IF;
  IF ai_before IS DISTINCT FROM ai_after THEN RAISE EXCEPTION 'MOEX analyzer configuration changed';END IF;
  IF EXISTS (SELECT 1 FROM public.questions WHERE analysis_status='pending') THEN RAISE EXCEPTION 'MOEX unintended pending';END IF;
  RAISE NOTICE 'Source-backed R105-2-07 and DS106-1-34 exact ROLLBACK rehearsal PASS';
END;
$two_source_p0$;
ROLLBACK;

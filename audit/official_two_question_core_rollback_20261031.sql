-- Rollback-only, exact-production-preimage two question correction rehearsal.
-- No production changes are committed; this file always terminates with ROLLBACK.
-- Do not change to COMMIT without independent release authorization.
BEGIN ISOLATION LEVEL REPEATABLE READ;
SET LOCAL lock_timeout='3s';
SET LOCAL statement_timeout='20s';
DO $swsi_repair$
DECLARE
  before_1 jsonb := $pre1${"id":"R-114-1-17","law":"","qno":"17","year":"114","major":"資料蒐集","opt_a":"日常談話完全沒有目的性，但個別深入訪談具有強烈的目的性","opt_b":"日常談話通常會以友好的打招呼開始，但個別深入訪談會直接開始預定的訪談計畫","opt_c":"個別深入訪談中，通常是由受訪者主導新的話題，訪談者儘可能表現興趣與熱情，鼓勵受","opt_d":"訪者暢所欲言","round":"第一次","topic":"訪問法 > 深度訪談vs日常談話","answer":"A","exp_raw":"","exp_why":"(A)正確：日常談話沒有(研究)目的性，但個別深入訪談具有強烈的目的性——這是兩者最核心的差異。","mistake":"題幹誤讀","subject":"社會工作研究方法","exp_trap":"深入訪談＝有目的的對話(仍需寒暄暖場、訪談者引導)。","keywords":"深度訪談, 日常談話, 目的性, 結構化, 訪談技巧","mnemonic":"深入訪談＝強目的性的對話;仍需暖場、訪談者引導。","question":"下列對於個別深入訪談與日常談話的異同敘述，何者正確？ 個別深入訪談主要是為了滿足訪談者的要求，因此受訪者必須向訪談者提供有用的資料","extension":"訪問法(深入訪談vs日常談話)。","exp_others":"(B)深入訪談也會以寒暄開場建立關係、(C)(D)訪談由『訪談者』引導話題方向(受訪者提供內容)。","legal_note":null,"source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=103&code=114030&q=1&s=0306&t=Q","grading_mode":"standard","legal_status":"not_applicable","analysis_error":null,"analysis_status":"ready","accepted_answers":null,"legal_checked_at":null,"legal_source_url":null,"source_exam_code":"114030","analysis_attempts":0,"analysis_started_at":null,"analysis_completed_at":null,"legal_canonical_names":[],"analysis_last_attempt_at":null}$pre1$::jsonb;
  after_1 jsonb := $post1${"id":"R-114-1-17","law":null,"qno":"17","year":"114","major":null,"opt_a":"個別深入訪談主要是為了滿足訪談者的要求，因此受訪者必須向訪談者提供有用的資料","opt_b":"日常談話完全沒有目的性，但個別深入訪談具有強烈的目的性","opt_c":"日常談話通常會以友好的打招呼開始，但個別深入訪談會直接開始預定的訪談計畫","opt_d":"個別深入訪談中，通常是由受訪者主導新的話題，訪談者儘可能表現興趣與熱情，鼓勵受訪者暢所欲言","round":"第一次","topic":null,"answer":"A","exp_raw":null,"exp_why":null,"mistake":null,"subject":"社會工作研究方法","exp_trap":null,"keywords":null,"mnemonic":null,"question":"下列對於個別深入訪談與日常談話的異同敘述，何者正確？","extension":null,"exp_others":null,"legal_note":null,"source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=103&code=114030&q=1&s=0306&t=Q","grading_mode":"standard","legal_status":"not_applicable","analysis_error":null,"analysis_status":"review","accepted_answers":null,"legal_checked_at":null,"legal_source_url":null,"source_exam_code":"114030","analysis_attempts":0,"analysis_started_at":null,"analysis_completed_at":null,"legal_canonical_names":[],"analysis_last_attempt_at":null}$post1$::jsonb;
  before_2 jsonb := $pre2${"id":"DS-108-2-23","law":"","qno":"23","year":"108","major":"團體工作","opt_a":"②④④⑧","opt_b":"①③⑤⑦","opt_c":"②③⑦⑧","opt_d":"①④⑤⑦","round":"第二次","topic":"團體階段 > 團體開始階段","answer":"B","exp_raw":"","exp_why":"(B)①③⑤⑦：團體開始階段重點＝建立團體規範①、處理成員參與問題③、創造安全與信任關係⑤、發展彈性結構⑦。","mistake":"概念混淆","subject":"社會工作直接服務","exp_trap":"開始階段＝建立規範/促參與/建立安全信任。","keywords":"團體開始階段, 建立規範, 處理參與, 安全信任, 團體一份子","mnemonic":"團體發展階段:計畫期→聚集/開始期(趨避衝突/尋找共同點/依賴工作者)→權力控制/風暴期(衝突/測試工作者;未必發生)→工作親密期→結束期(分離焦慮/否認/賦能告別)。","question":"有關團體工作開始階段的工作重點和工作目標，下列何者正確？①建立團體規範 ②加 強正向動機，降低抗拒 ③處理團體成員參與的問題 ④處理成員之間的衝突與緊張 ⑤ 創造安全與信任關係 ④發展溝通、地位、角色與規範的彈性結構 ⑦協助成員感覺自己 是團體的一份子 ⑧穩定成員的參與及團體的運作","extension":"團體工作(開始階段)。","exp_others":"②降低抗拒/④處理衝突與緊張——偏向中期(權力控制期)的工作。","legal_note":null,"source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=108110&q=1&s=0602&t=Q","grading_mode":"standard","legal_status":"not_applicable","analysis_error":null,"analysis_status":"ready","accepted_answers":null,"legal_checked_at":null,"legal_source_url":null,"source_exam_code":"108110","analysis_attempts":0,"analysis_started_at":null,"analysis_completed_at":null,"legal_canonical_names":[],"analysis_last_attempt_at":null}$pre2$::jsonb;
  after_2 jsonb := $post2${"id":"DS-108-2-23","law":null,"qno":"23","year":"108","major":null,"opt_a":"②④⑥⑧","opt_b":"①③⑤⑦","opt_c":"②③⑦⑧","opt_d":"①④⑤⑦","round":"第二次","topic":null,"answer":"B","exp_raw":null,"exp_why":null,"mistake":null,"subject":"社會工作直接服務","exp_trap":null,"keywords":null,"mnemonic":null,"question":"有關團體工作開始階段的工作重點和工作目標，下列何者正確？①建立團體規範 ②加強正向動機，降低抗拒 ③處理團體成員參與的問題 ④處理成員之間的衝突與緊張 ⑤創造安全與信任關係 ⑥發展溝通、地位、角色與規範的彈性結構 ⑦協助成員感覺自己是團體的一份子 ⑧穩定成員的參與及團體的運作","extension":null,"exp_others":null,"legal_note":null,"source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=108110&q=1&s=0602&t=Q","grading_mode":"standard","legal_status":"not_applicable","analysis_error":null,"analysis_status":"review","accepted_answers":null,"legal_checked_at":null,"legal_source_url":null,"source_exam_code":"108110","analysis_attempts":0,"analysis_started_at":null,"analysis_completed_at":null,"legal_canonical_names":[],"analysis_last_attempt_at":null}$post2$::jsonb;
  observed jsonb;
  other_before jsonb;
  other_after jsonb;
  grades_before jsonb;
  grades_after jsonb;
  changed integer;
BEGIN
  IF (SELECT count(*) FROM public.questions)<>4800 THEN RAISE EXCEPTION 'expected 4800 official questions'; END IF;
  SELECT jsonb_agg(to_jsonb(q) ORDER BY id) INTO other_before FROM public.questions q WHERE id NOT IN ('R-114-1-17','DS-108-2-23');
  SELECT jsonb_agg(jsonb_build_array(id,answer,accepted_answers,grading_mode) ORDER BY id) INTO grades_before FROM public.questions;
  SELECT to_jsonb(q) INTO STRICT observed FROM public.questions q WHERE id='R-114-1-17' FOR UPDATE;
  IF observed IS DISTINCT FROM before_1 THEN RAISE EXCEPTION 'preimage mismatch R-114-1-17'; END IF;
  SELECT to_jsonb(q) INTO STRICT observed FROM public.questions q WHERE id='DS-108-2-23' FOR UPDATE;
  IF observed IS DISTINCT FROM before_2 THEN RAISE EXCEPTION 'preimage mismatch DS-108-2-23'; END IF;
  UPDATE public.questions SET question='下列對於個別深入訪談與日常談話的異同敘述，何者正確？', opt_a='個別深入訪談主要是為了滿足訪談者的要求，因此受訪者必須向訪談者提供有用的資料', opt_b='日常談話完全沒有目的性，但個別深入訪談具有強烈的目的性', opt_c='日常談話通常會以友好的打招呼開始，但個別深入訪談會直接開始預定的訪談計畫', opt_d='個別深入訪談中，通常是由受訪者主導新的話題，訪談者儘可能表現興趣與熱情，鼓勵受訪者暢所欲言' WHERE id='R-114-1-17';
  GET DIAGNOSTICS changed=ROW_COUNT;
  IF changed<>1 THEN RAISE EXCEPTION 'SWSI unexpected row count for R-114-1-17'; END IF;
  UPDATE public.questions SET analysis_status='review' WHERE id='R-114-1-17' AND analysis_status='pending';
  GET DIAGNOSTICS changed=ROW_COUNT;
  IF changed<>1 THEN RAISE EXCEPTION 'SWSI expected quarantine trigger for R-114-1-17'; END IF;
  UPDATE public.questions SET question='有關團體工作開始階段的工作重點和工作目標，下列何者正確？①建立團體規範 ②加強正向動機，降低抗拒 ③處理團體成員參與的問題 ④處理成員之間的衝突與緊張 ⑤創造安全與信任關係 ⑥發展溝通、地位、角色與規範的彈性結構 ⑦協助成員感覺自己是團體的一份子 ⑧穩定成員的參與及團體的運作', opt_a='②④⑥⑧' WHERE id='DS-108-2-23';
  GET DIAGNOSTICS changed=ROW_COUNT;
  IF changed<>1 THEN RAISE EXCEPTION 'SWSI unexpected row count for DS-108-2-23'; END IF;
  UPDATE public.questions SET analysis_status='review' WHERE id='DS-108-2-23' AND analysis_status='pending';
  GET DIAGNOSTICS changed=ROW_COUNT;
  IF changed<>1 THEN RAISE EXCEPTION 'SWSI expected quarantine trigger for DS-108-2-23'; END IF;
  SELECT to_jsonb(q) INTO STRICT observed FROM public.questions q WHERE id='R-114-1-17';
  IF observed IS DISTINCT FROM after_1 THEN RAISE EXCEPTION 'postimage mismatch R-114-1-17'; END IF;
  SELECT to_jsonb(q) INTO STRICT observed FROM public.questions q WHERE id='DS-108-2-23';
  IF observed IS DISTINCT FROM after_2 THEN RAISE EXCEPTION 'postimage mismatch DS-108-2-23'; END IF;
  SELECT jsonb_agg(to_jsonb(q) ORDER BY id) INTO other_after FROM public.questions q WHERE id NOT IN ('R-114-1-17','DS-108-2-23');
  SELECT jsonb_agg(jsonb_build_array(id,answer,accepted_answers,grading_mode) ORDER BY id) INTO grades_after FROM public.questions;
  IF other_before IS DISTINCT FROM other_after THEN RAISE EXCEPTION 'unrelated row changed'; END IF;
  IF grades_before IS DISTINCT FROM grades_after THEN RAISE EXCEPTION 'official grading changed'; END IF;
  IF EXISTS (SELECT 1 FROM public.questions WHERE analysis_status='pending') THEN RAISE EXCEPTION 'pending review records remain'; END IF;
  RAISE NOTICE 'Two source-backed questions match expected postimage; unrelated 4798 and 4800 grading invariant checked';
END;
$swsi_repair$;
ROLLBACK;

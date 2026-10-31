-- PR #496: ROLLBACK-ONLY transaction; never publish by running this script.
-- Source SHA256: DS 78e9473d144f9165622f02ac3e5a004658b0ca7dd516c436f56cfdf4042b3e9b; R e2103e4eb154b5ac0c8de24026a7b35fe3a8370678f606356c919540c87646e2
BEGIN ISOLATION LEVEL REPEATABLE READ;
SET LOCAL lock_timeout='3s';
SET LOCAL statement_timeout='30s';
DO $guard$
DECLARE
  expect_old jsonb:=$old$[{"id":"DS-108-2-23","subject":"社會工作直接服務","year":"108","round":"第二次","qno":"23","major":"團體工作","topic":"團體階段 > 團體開始階段","keywords":"團體開始階段, 建立規範, 處理參與, 安全信任, 團體一份子","question":"有關團體工作開始階段的工作重點和工作目標，下列何者正確？①建立團體規範 ②加 強正向動機，降低抗拒 ③處理團體成員參與的問題 ④處理成員之間的衝突與緊張 ⑤ 創造安全與信任關係 ④發展溝通、地位、角色與規範的彈性結構 ⑦協助成員感覺自己 是團體的一份子 ⑧穩定成員的參與及團體的運作","opt_a":"②④④⑧","opt_b":"①③⑤⑦","opt_c":"②③⑦⑧","opt_d":"①④⑤⑦","answer":"B","exp_why":"(B)①③⑤⑦：團體開始階段重點＝建立團體規範①、處理成員參與問題③、創造安全與信任關係⑤、發展彈性結構⑦。","exp_others":"②降低抗拒/④處理衝突與緊張——偏向中期(權力控制期)的工作。","exp_trap":"開始階段＝建立規範/促參與/建立安全信任。","exp_raw":"","mnemonic":"團體發展階段:計畫期→聚集/開始期(趨避衝突/尋找共同點/依賴工作者)→權力控制/風暴期(衝突/測試工作者;未必發生)→工作親密期→結束期(分離焦慮/否認/賦能告別)。","extension":"團體工作(開始階段)。","law":"","mistake":"概念混淆","source_exam_code":"108110","source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=108110&q=1&s=0602&t=Q","analysis_status":"ready","analysis_attempts":0,"analysis_error":null,"analysis_started_at":null,"analysis_completed_at":null,"legal_status":"not_applicable","legal_checked_at":null,"legal_note":null,"legal_source_url":null,"legal_canonical_names":[],"accepted_answers":null,"grading_mode":"standard","analysis_last_attempt_at":null},{"id":"R-114-1-17","subject":"社會工作研究方法","year":"114","round":"第一次","qno":"17","major":"資料蒐集","topic":"訪問法 > 深度訪談vs日常談話","keywords":"深度訪談, 日常談話, 目的性, 結構化, 訪談技巧","question":"下列對於個別深入訪談與日常談話的異同敘述，何者正確？ 個別深入訪談主要是為了滿足訪談者的要求，因此受訪者必須向訪談者提供有用的資料","opt_a":"日常談話完全沒有目的性，但個別深入訪談具有強烈的目的性","opt_b":"日常談話通常會以友好的打招呼開始，但個別深入訪談會直接開始預定的訪談計畫","opt_c":"個別深入訪談中，通常是由受訪者主導新的話題，訪談者儘可能表現興趣與熱情，鼓勵受","opt_d":"訪者暢所欲言","answer":"A","exp_why":"(A)正確：日常談話沒有(研究)目的性，但個別深入訪談具有強烈的目的性——這是兩者最核心的差異。","exp_others":"(B)深入訪談也會以寒暄開場建立關係、(C)(D)訪談由『訪談者』引導話題方向(受訪者提供內容)。","exp_trap":"深入訪談＝有目的的對話(仍需寒暄暖場、訪談者引導)。","exp_raw":"","mnemonic":"深入訪談＝強目的性的對話;仍需暖場、訪談者引導。","extension":"訪問法(深入訪談vs日常談話)。","law":"","mistake":"題幹誤讀","source_exam_code":"114030","source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=103&code=114030&q=1&s=0306&t=Q","analysis_status":"ready","analysis_attempts":0,"analysis_error":null,"analysis_started_at":null,"analysis_completed_at":null,"legal_status":"not_applicable","legal_checked_at":null,"legal_note":null,"legal_source_url":null,"legal_canonical_names":[],"accepted_answers":null,"grading_mode":"standard","analysis_last_attempt_at":null}]$old$::jsonb;
  expect_new jsonb:=$new$[{"id":"DS-108-2-23","subject":"社會工作直接服務","year":"108","round":"第二次","qno":"23","major":null,"topic":null,"keywords":null,"question":"有關團體工作開始階段的工作重點和工作目標，下列何者正確？①建立團體規範 ②加強正向動機，降低抗拒 ③處理團體成員參與的問題 ④處理成員之間的衝突與緊張 ⑤創造安全與信任關係 ⑥發展溝通、地位、角色與規範的彈性結構 ⑦協助成員感覺自己是團體的一份子 ⑧穩定成員的參與及團體的運作","opt_a":"②④⑥⑧","opt_b":"①③⑤⑦","opt_c":"②③⑦⑧","opt_d":"①④⑤⑦","answer":"B","exp_why":null,"exp_others":null,"exp_trap":null,"exp_raw":null,"mnemonic":null,"extension":null,"law":null,"mistake":null,"source_exam_code":"108110","source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=108110&q=1&s=0602&t=Q","analysis_status":"review","analysis_attempts":0,"analysis_error":null,"analysis_started_at":null,"analysis_completed_at":null,"legal_status":"not_applicable","legal_checked_at":null,"legal_note":null,"legal_source_url":null,"legal_canonical_names":[],"accepted_answers":null,"grading_mode":"standard","analysis_last_attempt_at":null},{"id":"R-114-1-17","subject":"社會工作研究方法","year":"114","round":"第一次","qno":"17","major":null,"topic":null,"keywords":null,"question":"下列對於個別深入訪談與日常談話的異同敘述，何者正確？","opt_a":"個別深入訪談主要是為了滿足訪談者的要求，因此受訪者必須向訪談者提供有用的資料","opt_b":"日常談話完全沒有目的性，但個別深入訪談具有強烈的目的性","opt_c":"日常談話通常會以友好的打招呼開始，但個別深入訪談會直接開始預定的訪談計畫","opt_d":"個別深入訪談中，通常是由受訪者主導新的話題，訪談者儘可能表現興趣與熱情，鼓勵受訪者暢所欲言","answer":"A","exp_why":null,"exp_others":null,"exp_trap":null,"exp_raw":null,"mnemonic":null,"extension":null,"law":null,"mistake":null,"source_exam_code":"114030","source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=103&code=114030&q=1&s=0306&t=Q","analysis_status":"review","analysis_attempts":0,"analysis_error":null,"analysis_started_at":null,"analysis_completed_at":null,"legal_status":"not_applicable","legal_checked_at":null,"legal_note":null,"legal_source_url":null,"legal_canonical_names":[],"accepted_answers":null,"grading_mode":"standard","analysis_last_attempt_at":null}]$new$::jsonb;
  elem jsonb; observed jsonb;other_old jsonb;other_new jsonb;grading_old jsonb;grading_new jsonb;config_old jsonb;config_new jsonb;changed integer;
BEGIN
  IF (SELECT count(*) FROM public.questions)<>4800 THEN RAISE EXCEPTION 'P0 corpus count drift';END IF;
  SELECT jsonb_agg(to_jsonb(q) ORDER BY id) INTO other_old FROM public.questions q WHERE id NOT IN ('DS-108-2-23','R-114-1-17');
  SELECT jsonb_agg(jsonb_build_array(id,answer,accepted_answers,grading_mode) ORDER BY id) INTO grading_old FROM public.questions;
  SELECT to_jsonb(c) INTO config_old FROM public.ai_analysis_job_config c WHERE id=true;
  IF config_old->>'enabled'<>'false' THEN RAISE EXCEPTION 'P0 AI job config unexpectedly enabled';END IF;
  FOR elem IN SELECT value FROM jsonb_array_elements(expect_old) LOOP
    SELECT to_jsonb(q) INTO STRICT observed FROM public.questions q WHERE id=elem->>'id' FOR UPDATE;
    IF observed IS DISTINCT FROM elem THEN RAISE EXCEPTION 'P0 preimage drift: %',elem->>'id';END IF;
  END LOOP;
  UPDATE public.questions SET question='有關團體工作開始階段的工作重點和工作目標，下列何者正確？①建立團體規範 ②加強正向動機，降低抗拒 ③處理團體成員參與的問題 ④處理成員之間的衝突與緊張 ⑤創造安全與信任關係 ⑥發展溝通、地位、角色與規範的彈性結構 ⑦協助成員感覺自己是團體的一份子 ⑧穩定成員的參與及團體的運作',opt_a='②④⑥⑧' WHERE id='DS-108-2-23';
  GET DIAGNOSTICS changed=ROW_COUNT;IF changed<>1 THEN RAISE EXCEPTION 'SWSI P0 row count DS-108-2-23';END IF;
  UPDATE public.questions SET question='下列對於個別深入訪談與日常談話的異同敘述，何者正確？',opt_a='個別深入訪談主要是為了滿足訪談者的要求，因此受訪者必須向訪談者提供有用的資料',opt_b='日常談話完全沒有目的性，但個別深入訪談具有強烈的目的性',opt_c='日常談話通常會以友好的打招呼開始，但個別深入訪談會直接開始預定的訪談計畫',opt_d='個別深入訪談中，通常是由受訪者主導新的話題，訪談者儘可能表現興趣與熱情，鼓勵受訪者暢所欲言' WHERE id='R-114-1-17';
  GET DIAGNOSTICS changed=ROW_COUNT;IF changed<>1 THEN RAISE EXCEPTION 'SWSI P0 row count R-114-1-17';END IF;
  UPDATE public.questions SET analysis_status='review' WHERE id IN ('DS-108-2-23','R-114-1-17') AND analysis_status='pending';
  GET DIAGNOSTICS changed=ROW_COUNT;IF changed<>2 THEN RAISE EXCEPTION 'P0 quarantine failed';END IF;
  FOR elem IN SELECT value FROM jsonb_array_elements(expect_new) LOOP
    SELECT to_jsonb(q) INTO STRICT observed FROM public.questions q WHERE id=elem->>'id';
    IF observed IS DISTINCT FROM elem THEN RAISE EXCEPTION 'P0 postimage drift: %',elem->>'id';END IF;
  END LOOP;
  SELECT jsonb_agg(to_jsonb(q) ORDER BY id) INTO other_new FROM public.questions q WHERE id NOT IN ('DS-108-2-23','R-114-1-17');
  SELECT jsonb_agg(jsonb_build_array(id,answer,accepted_answers,grading_mode) ORDER BY id) INTO grading_new FROM public.questions;
  SELECT to_jsonb(c) INTO config_new FROM public.ai_analysis_job_config c WHERE id=true;
  IF other_old IS DISTINCT FROM other_new THEN RAISE EXCEPTION 'P0 unrelated row changed';END IF;
  IF grading_old IS DISTINCT FROM grading_new THEN RAISE EXCEPTION 'P0 grading changed';END IF;
  IF config_old IS DISTINCT FROM config_new THEN RAISE EXCEPTION 'P0 AI job config changed';END IF;
  IF EXISTS (SELECT 1 FROM public.questions WHERE analysis_status='pending') THEN RAISE EXCEPTION 'P0 unexpected pending';END IF;
  RAISE NOTICE 'SWSI P0 2-row rollback rehearsal PASS; 4798 other rows and 4800 grading tuples exact';
END;
$guard$;
ROLLBACK;

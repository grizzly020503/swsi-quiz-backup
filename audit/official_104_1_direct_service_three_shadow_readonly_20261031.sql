-- SWSI 104-1 DS 3-MCQ exact 37-column shadow rehearsal. SELECT ONLY.
-- No UPDATE/INSERT/DELETE/CREATE, no transaction side-effects, no live changes.
-- Verify original official PDF SHA256 979233d2cb316565c4eed2b5c5289e89e5d21c0bb2b2076a7443887cd24ffadc
-- before independent source approval / publication. THIS DOES NOT APPROVE RELEASE.
WITH candidate AS (
  SELECT x AS c
  FROM jsonb_array_elements('[{"id":"DS-104-1-22","before":{"id":"DS-104-1-22","law":"","qno":"22","year":"104","major":"紀錄與評鑑","opt_a":"「摘要式紀錄」較能具體且深人的呈現團體過程與內容，適用於量化的評鑑，所 花費的時間較多","opt_b":"團體紀錄可以檢視團體目標達成狀態及成員參與狀態等重要面向，是團體成效評 鑑工具之一","opt_c":"紀錄裡的文字內容、相片等，項遵守保密原則及匿名處理","opt_d":"任務性團體的紀錄•需在下次聚會前發給成員檢閱，並於下次會議開始前進行修止","round":"第一次","topic":"團體紀錄 > 摘要式紀錄","answer":"A","exp_raw":"","exp_why":"(A)錯誤：『具體深入呈現團體過程與內容、花時間較多』是『過程式紀錄』的特性，不是摘要式紀錄(摘要式精簡省時)。","mistake":"概念混淆","subject":"社會工作直接服務","exp_trap":"過程式紀錄＝具體深入耗時;摘要式＝精簡。","keywords":"團體紀錄, 摘要式紀錄, 過程紀錄, 保密匿名, 評鑑工具","mnemonic":"紀錄類型:過程式(具體深入呈現互動與深層情緒,耗時,用於督導新進)、摘要式(精簡)、對話式(逐字呈現對話)、管理式(檢查改進服務)、GAAP目標焦點格式＝Goals目標/Activities活動/Assessment評估/Plans計畫。","question":"團體工作紀錄可作為工作者檢視及評鑑團體運作的重要方式之一，下列有關團體紀 錄的敘述何者錯誤","extension":"團體工作(團體紀錄)。","exp_others":"(B)紀錄可檢視目標達成與成員參與、是成效評鑑工具、(C)文字相片須保密匿名、(D)任務性團體紀錄於下次聚會前發給成員檢閱修正——皆正確。","legal_note":null,"source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=110&code=104030&q=1&s=0602&t=Q","grading_mode":"standard","legal_status":"not_applicable","analysis_error":null,"analysis_status":"ready","accepted_answers":null,"legal_checked_at":null,"legal_source_url":null,"source_exam_code":"104030","analysis_attempts":0,"analysis_started_at":null,"analysis_completed_at":null,"legal_canonical_names":[],"analysis_last_attempt_at":null},"after_text":{"question":"團體工作紀錄可作為工作者檢視及評鑑團體運作的重要方式之一，下列有關團體紀錄的敘述何者錯誤？","opt_a":"「摘要式紀錄」較能具體且深入的呈現團體過程與內容，適用於量化的評鑑，所花費的時間較多","opt_b":"團體紀錄可以檢視團體目標達成狀態及成員參與狀態等重要面向，是團體成效評鑑工具之一","opt_c":"紀錄裡的文字內容、相片等，須遵守保密原則及匿名處理","opt_d":"任務性團體的紀錄，需在下次聚會前發給成員檢閱，並於下次會議開始前進行修正"},"expected_grading_mode":"standard","expected_answer":"A","expected_accepted_answers":null},{"id":"DS-104-1-27","before":{"id":"DS-104-1-27","law":"","qno":"27","year":"104","major":"專業關係","opt_a":"反情感轉栘","opt_b":"情感轉栘","opt_c":"反向作用","opt_d":"現實反應","round":"第一次","topic":"情感轉移 > 情感轉移","answer":"B","exp_raw":"","exp_why":"案主把對「重要他人」的情感投射到社工身上(不斷稱讚、言聽計從)——這是情感轉移(transference);(B)。","mistake":"概念混淆","subject":"社會工作直接服務","exp_trap":"情感轉移=「案主」把過去重要關係的情感投射到社工身上。","keywords":"情感轉移, 稱讚, 言聽計從, 專業關係, 案主","mnemonic":"情感轉移=案主把對他人的情感投射到社工(稱讚/依賴)。","question":"當女性社會工作人員與男性案主第二次在機構進行會談時，會談過程中，案主不斷 稱讀社會工作人員，並對社會工作人員的建議言聽計從，此時該社會工作人員應該 合理懷疑這是下面那一種專業關係的反應？","extension":"專業關係;情感轉移。","exp_others":"(A)反情感轉移是社工對案主的投射、(C)反向作用是防衛機轉、(D)現實反應是基於事實的反應——皆不符。","legal_note":null,"source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=110&code=104030&q=1&s=0602&t=Q","grading_mode":"standard","legal_status":"not_applicable","analysis_error":null,"analysis_status":"ready","accepted_answers":null,"legal_checked_at":null,"legal_source_url":null,"source_exam_code":"104030","analysis_attempts":0,"analysis_started_at":null,"analysis_completed_at":null,"legal_canonical_names":[],"analysis_last_attempt_at":null},"after_text":{"question":"當女性社會工作人員與男性案主第二次在機構進行會談時，會談過程中，案主不斷稱讚社會工作人員，並對社會工作人員的建議言聽計從，此時該社會工作人員應該合理懷疑這是下面那一種專業關係的反應？","opt_a":"反情感轉移","opt_b":"情感轉移","opt_c":"反向作用","opt_d":"現實反應"},"expected_grading_mode":"standard","expected_answer":"B","expected_accepted_answers":null},{"id":"DS-104-1-29","before":{"id":"DS-104-1-29","law":null,"qno":"29","year":"104","major":null,"opt_a":"個人價值與專業價值的衝突","opt_b":"不同專業間的價值與介入焦點不一致","opt_c":"不同機構間的代表權利分配的議題","opt_d":"資訊分享程度的保密拿捏的問題","round":"第一次","topic":null,"answer":"D","exp_raw":null,"exp_why":null,"mistake":null,"subject":"社會工作直接服務","exp_trap":null,"keywords":null,"mnemonic":null,"question":"社會工作實務領域常運用「業務聯繫會報」與「個案研討會」等形式,由不同機構或 不同專業工作者, 一起討論個案工作的方法。這種類型的會議，社會工作者需要面對 的倫理議題為何?","extension":null,"exp_others":null,"legal_note":null,"source_url":"https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=110&code=104030&q=1&s=0602&t=Q","grading_mode":"standard","legal_status":"not_applicable","analysis_error":"AI qwen/qwen3.6-27b HTTP 405: ","analysis_status":"review","accepted_answers":null,"legal_checked_at":null,"legal_source_url":null,"source_exam_code":"104030","analysis_attempts":3,"analysis_started_at":null,"analysis_completed_at":null,"legal_canonical_names":[],"analysis_last_attempt_at":null},"after_text":{"question":"社會工作實務領域常運用「業務聯繫會報」與「個案研討會」等形式，由不同機構或不同專業的工作者，一起討論個案工作的方法。這種類型的會議，社會工作者需要面對的倫理議題為何？","opt_a":"個人價值與專業價值的衝突","opt_b":"不同專業間的價值觀與介入焦點不一致","opt_c":"不同機構間的代表權力分配的議題","opt_d":"資訊分享程度與保密拿捏的問題"},"expected_grading_mode":"standard","expected_answer":"D","expected_accepted_answers":null}]'::jsonb) AS x
),
shadow AS (
  SELECT q.id, to_jsonb(q) AS old_record, c.c AS candidate,
         CASE WHEN c.c IS NULL THEN to_jsonb(q)
              ELSE to_jsonb(q) ||
                   (c.c->'after_text') ||
                   jsonb_build_object('analysis_status','review','exp_why',null, 'exp_others',null, 'exp_trap',null, 'exp_raw',null, 'mnemonic',null, 'extension',null, 'law',null, 'mistake',null, 'major',null, 'topic',null, 'keywords',null)
         END AS new_record
  FROM public.questions q
  LEFT JOIN candidate c ON q.id = c.c->>'id'
),
flags AS (
 SELECT id, old_record, new_record, candidate,
        (SELECT count(*) FROM jsonb_object_keys(old_record)) AS col_count,
        CASE WHEN candidate IS NOT NULL
          THEN old_record = candidate->'before'
          ELSE true END AS exact_before,
        CASE WHEN candidate IS NOT NULL
          THEN (SELECT bool_and(new_record->k = candidate->'after_text'->k)
                FROM unnest(ARRAY['question','opt_a','opt_b','opt_c','opt_d']) AS k)
          ELSE true END AS exact_after_text,
        (old_record->'answer' = new_record->'answer' AND
         old_record->'accepted_answers' = new_record->'accepted_answers' AND
         old_record->'grading_mode' = new_record->'grading_mode') AS grading_unchanged,
        (SELECT count(*) FROM jsonb_each(old_record) AS f(k,v)
         WHERE v IS DISTINCT FROM new_record->k
           AND k NOT IN ('question','opt_a','opt_b','opt_c','opt_d','analysis_status','exp_why','exp_others','exp_trap','exp_raw','mnemonic','extension','law','mistake','major','topic','keywords')) AS forbidden_field_changes
 FROM shadow
)
SELECT jsonb_build_object(
 'scenario','SELECT_ONLY; simulated postimages, NOT database transaction or write',
 'status',CASE WHEN count(*)=4800 AND count(*) FILTER(WHERE candidate IS NOT NULL)=3
                 AND bool_and(col_count=37 AND exact_before AND exact_after_text AND grading_unchanged AND forbidden_field_changes=0)
                 AND count(*) FILTER(WHERE candidate IS NULL AND old_record IS DISTINCT FROM new_record)=0
                 AND count(*) FILTER(WHERE candidate IS NOT NULL AND new_record->>'analysis_status'='review')=3
            THEN 'PASS_READONLY_SHADOW_ONLY' ELSE 'BLOCKED' END,
 'live_rows',count(*),
 'affected_rows',count(*) FILTER(WHERE candidate IS NOT NULL),
 'exact_37column_preimage_rows',count(*) FILTER(WHERE candidate IS NOT NULL AND col_count=37 AND exact_before),
 'exact_text_postimage_rows',count(*) FILTER(WHERE candidate IS NOT NULL AND exact_after_text),
 'other_rows_byte_semantics_unchanged',count(*) FILTER(WHERE candidate IS NULL AND old_record=new_record),
 'grade_tuples_unchanged',count(*) FILTER(WHERE grading_unchanged),
 'forbidden_field_changes_total',sum(forbidden_field_changes),
 'would_be_review',count(*) FILTER(WHERE new_record->>'analysis_status'='review'),
 'live_ready',count(*) FILTER(WHERE old_record->>'analysis_status'='ready'),
 'live_review',count(*) FILTER(WHERE old_record->>'analysis_status'='review'),
 'approval_and_deployment','NOT AUTHORIZED: source human approval=false; no DML or main merge',
 'affected_preview',(SELECT jsonb_agg(jsonb_build_object('id',id,'live_status',old_record->>'analysis_status','shadow_status',new_record->>'analysis_status','changed_columns',(SELECT jsonb_agg(k ORDER BY k) FROM jsonb_each(old_record) AS e(k,v) WHERE v IS DISTINCT FROM new_record->k)) ORDER BY id) FROM flags WHERE candidate IS NOT NULL)
) AS evidence
FROM flags;

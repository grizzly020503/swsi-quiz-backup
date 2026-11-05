-- SWSI official MOEX source review: read-only two-row 37-column preimage shadow.
-- ACTUAL LIVE SELECT verified 2026-11-05: corpus=4800, targets=2, strict_matches=2.
-- Source references: R-107-2-40 original MOEX PDF p4-4, SP111-2-34 p6-5.
-- Human original-PDF approval=false; release approval=false. No production DML.
-- This preview changes option text IN MEMORY ONLY, not records.
-- A later release must separately quarantine stale AI analysis, verify all
-- production triggers/pg_cron/pg_net and post-rollback fidelity. NO-GO remains.
WITH proposed(id, expected_sha, expected_unaffected_sha, expected_answer, patch) AS (
  VALUES
   ('R-107-2-40',
    'ec50059ee6d7ef42fb093e19edde8c2058321e6730844f8a64463a01397d6705',
    'b5838df66ee261cf845a0c93f3f08e7e8304c0059286cfd3e8725a93cf943faa',
    'D',
    jsonb_build_object('opt_d','兩個變項間有高度相關，則非常可能有因果關係')),
   ('SP111-2-34',
    'b4ebad61984ab44a8e0949d90d6cf23a8bd2575f00568d93fdd598ca4c79ef7d',
    'd045f3978fb52e7018149c3c7ff81b6efb92c7e86ab1ec0f42bc4a21e7e28f2f',
    'C',
    jsonb_build_object('opt_a','1 至 3 個月','opt_b','2 至 4 個月',
                       'opt_c','3 至 6 個月','opt_d','4 至 6 個月'))
), observed AS (
  SELECT q.id, to_jsonb(q) before_row, proposed.patch,
         proposed.expected_sha, proposed.expected_unaffected_sha,
         proposed.expected_answer
  FROM public.questions q JOIN proposed USING(id)
), validated AS (
  SELECT id, before_row, patch, before_row || patch AS proposed_row,
         (SELECT COUNT(*) FROM jsonb_each(before_row))=37 AS shape_ok,
         encode(sha256(convert_to(before_row::text,'UTF8')),'hex')=expected_sha AS preimage_ok,
         encode(sha256(convert_to(
            (before_row - 'opt_a' - 'opt_b' - 'opt_c' - 'opt_d')::text,'UTF8')),
            'hex')=expected_unaffected_sha AS unaffected_baseline_ok,
         (before_row->>'answer'=expected_answer AND before_row->>'grading_mode'='standard'
          AND before_row->'accepted_answers'='null'::jsonb) AS grading_ok,
         (before_row->>'analysis_status'='ready') AS analysis_pending_quarantine,
         (before_row || patch) <> before_row AS text_change_exists
  FROM observed
)
SELECT
  (SELECT COUNT(*) FROM public.questions) AS full_corpus_count,
  COUNT(*) AS target_count,
  COUNT(*) FILTER(WHERE shape_ok AND preimage_ok AND unaffected_baseline_ok
                  AND grading_ok AND analysis_pending_quarantine
                  AND text_change_exists) AS strict_matches,
  BOOL_AND(
    (proposed_row - 'opt_a' - 'opt_b' - 'opt_c' - 'opt_d') =
    (before_row - 'opt_a' - 'opt_b' - 'opt_c' - 'opt_d')
  ) AS all_non_option_fields_preserved,
  jsonb_agg(jsonb_build_object(
    'id',id,'all_37_columns',shape_ok,'full_preimage_unchanged',preimage_ok,
    'unaffected_fields_unchanged',unaffected_baseline_ok,
    'grading_unchanged',grading_ok,'analysis_requires_quarantine',analysis_pending_quarantine,
    'proposed_source_fields', (SELECT jsonb_agg(k ORDER BY k) FROM jsonb_object_keys(patch) AS k),
    'proposed_sha256',encode(sha256(convert_to(proposed_row::text,'UTF8')),'hex')
  ) ORDER BY id) AS candidate_checks,
  FALSE AS human_original_pdf_approval,
  FALSE AS permission_to_modify_official_core,
  FALSE AS release_approved,
  'NO-GO: SQL SELECT ONLY; HUMAN APPROVAL MISSING; ZERO PRODUCTION WRITES' AS release_status
FROM validated;

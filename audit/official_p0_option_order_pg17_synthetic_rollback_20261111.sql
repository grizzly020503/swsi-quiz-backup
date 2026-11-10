-- SWSI P0 TWO-QUESTION RELEASE: SYNTHETIC POSTGRESQL 17 TRANSACTION TEST ONLY.
-- REQUIRES AN EPHEMERAL CI DATABASE. NEVER RUN AGAINST SUPABASE PRODUCTION.
-- No private rows or credentials. NO official exam records are modified.
-- Exact real production 37-column preimage hashes are protected by a SEPARATE
-- read-only preflight. This test checks synthetic UPDATE guards and ROLLBACK.

CREATE TEMP TABLE swsi_p0_fixture (
  id text PRIMARY KEY,
  subject text, year text, "round" text, qno text,
  major text, topic text, keywords text, question text,
  opt_a text, opt_b text, opt_c text, opt_d text, answer text,
  exp_why text, exp_others text, exp_trap text, exp_raw text,
  mnemonic text, "extension" text, law text, mistake text,
  source_exam_code text, source_url text,
  analysis_status text NOT NULL, analysis_attempts integer NOT NULL DEFAULT 0,
  analysis_error text, analysis_started_at timestamptz,
  analysis_completed_at timestamptz, legal_status text NOT NULL DEFAULT 'unreviewed',
  legal_checked_at timestamptz, legal_note text, legal_source_url text,
  legal_canonical_names text[] NOT NULL DEFAULT ARRAY[]::text[],
  accepted_answers text[], grading_mode text NOT NULL,
  analysis_last_attempt_at timestamptz
);

INSERT INTO swsi_p0_fixture
  (id, subject, year, "round", qno, question,
   opt_a, opt_b, opt_c, opt_d, answer,
   source_exam_code, source_url, analysis_status, grading_mode)
VALUES
  ('SP104-2-37', '社會政策與社會立法', '104', '第二次', '37',
   'SYNTHETIC_FIXTURE_ONLY',
   '①②③', '①③⑤', '②③④', '③④⑤', 'C',
   '104100', 'https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=104100&q=1&s=0604&t=Q',
   'review', 'standard'),
  ('SP107-1-40', '社會政策與社會立法', '107', '第一次', '40',
   'SYNTHETIC_FIXTURE_ONLY',
   '①②③④', '①③④⑤', '①②③⑤', '②③④⑤', 'B',
   '107030', 'https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?c=107&code=107030&q=1&s=0604&t=Q',
   'ready', 'standard');

-- Baseline survives transaction rollback, so exact 37-column rows can
-- be compared after intentionally rolling back the candidate changes.
CREATE TEMP TABLE swsi_p0_before AS SELECT * FROM swsi_p0_fixture;

DO $test$
DECLARE columns_per_row integer; fixture_count integer;
BEGIN
  SELECT count(*) INTO fixture_count FROM swsi_p0_fixture;
  IF fixture_count <> 2 THEN RAISE EXCEPTION 'Expected exactly two synthetic fixtures'; END IF;
  SELECT count(*) INTO columns_per_row
  FROM swsi_p0_fixture f CROSS JOIN LATERAL jsonb_object_keys(to_jsonb(f)) AS key
  WHERE f.id='SP104-2-37';
  IF columns_per_row <> 37 THEN
    RAISE EXCEPTION 'Expected 37-column fixture, got %', columns_per_row;
  END IF;
END $test$;

-- This is a real UPDATE in an isolated disposable PG17 service, never
-- in production. Both rows use exact old-option/answer/grade matching.
BEGIN;
DO $tx$
DECLARE updated_rows integer;
BEGIN
  UPDATE swsi_p0_fixture SET
    opt_b='①③④', opt_c='①③⑤', opt_d='②④⑤', analysis_status='review'
  WHERE id='SP104-2-37' AND
    opt_a='①②③' AND opt_b='①③⑤' AND opt_c='②③④' AND opt_d='③④⑤'
    AND answer='C' AND grading_mode='standard'
    AND accepted_answers IS NULL AND analysis_status='review';
  GET DIAGNOSTICS updated_rows = ROW_COUNT;
  IF updated_rows <> 1 THEN RAISE EXCEPTION '104-2 source preimage drift / wrong affected rows'; END IF;

  UPDATE swsi_p0_fixture SET
    opt_c='②③④⑤', opt_d='②③④', analysis_status='review'
  WHERE id='SP107-1-40' AND
    opt_a='①②③④' AND opt_b='①③④⑤' AND opt_c='①②③⑤' AND opt_d='②③④⑤'
    AND answer='B' AND grading_mode='standard'
    AND accepted_answers IS NULL AND analysis_status='ready';
  GET DIAGNOSTICS updated_rows = ROW_COUNT;
  IF updated_rows <> 1 THEN RAISE EXCEPTION '107-1 source preimage drift / wrong affected rows'; END IF;
END $tx$;

DO $verify$
DECLARE
  diff104 text[];
  diff107 text[];
  modified_count integer;
BEGIN
  SELECT coalesce(array_agg(field.key ORDER BY field.key),ARRAY[]::text[]) INTO diff104
  FROM swsi_p0_fixture f JOIN swsi_p0_before b USING(id)
    CROSS JOIN LATERAL jsonb_each(to_jsonb(f)) AS field(key,value)
  WHERE f.id='SP104-2-37'
    AND field.value IS DISTINCT FROM (to_jsonb(b) -> field.key);
  IF diff104 <> ARRAY['opt_b','opt_c','opt_d']::text[] THEN
    RAISE EXCEPTION '104-2 unexpected full-row changes: %', diff104;
  END IF;

  SELECT coalesce(array_agg(field.key ORDER BY field.key),ARRAY[]::text[]) INTO diff107
  FROM swsi_p0_fixture f JOIN swsi_p0_before b USING(id)
    CROSS JOIN LATERAL jsonb_each(to_jsonb(f)) AS field(key,value)
  WHERE f.id='SP107-1-40'
    AND field.value IS DISTINCT FROM (to_jsonb(b) -> field.key);
  IF diff107 <> ARRAY['analysis_status','opt_c','opt_d']::text[] THEN
    RAISE EXCEPTION '107-1 unexpected full-row changes: %', diff107;
  END IF;

  SELECT count(*) INTO modified_count
  FROM swsi_p0_fixture f JOIN swsi_p0_before b USING (id)
  WHERE to_jsonb(f) IS DISTINCT FROM to_jsonb(b);
  IF modified_count <> 2 THEN RAISE EXCEPTION 'Unexpected number of changed fixtures'; END IF;

  IF EXISTS (
    SELECT 1 FROM swsi_p0_fixture f JOIN swsi_p0_before b USING (id)
    WHERE f.answer IS DISTINCT FROM b.answer
       OR f.grading_mode IS DISTINCT FROM b.grading_mode
       OR f.accepted_answers IS DISTINCT FROM b.accepted_answers
       OR f.source_exam_code IS DISTINCT FROM b.source_exam_code
       OR f.source_url IS DISTINCT FROM b.source_url
       OR f.analysis_status <> 'review'
  ) THEN RAISE EXCEPTION 'Official grading / source or analysis quarantine changed'; END IF;

  IF (SELECT opt_c FROM swsi_p0_fixture WHERE id='SP104-2-37') <> '①③⑤' THEN
    RAISE EXCEPTION 'Correct 104-2 answer text not in C';
  END IF;
END $verify$;
ROLLBACK;

-- FULL ROW (not just options) must match pre-image after rollback.
DO $post_rollback$
DECLARE before_json jsonb; after_json jsonb; fixture_count integer;
BEGIN
  SELECT jsonb_agg(to_jsonb(b) ORDER BY b.id) INTO before_json FROM swsi_p0_before b;
  SELECT jsonb_agg(to_jsonb(f) ORDER BY f.id) INTO after_json FROM swsi_p0_fixture f;
  IF before_json IS DISTINCT FROM after_json THEN
    RAISE EXCEPTION 'ROLLBACK did not restore full 37-column baseline';
  END IF;
  SELECT count(*) INTO fixture_count FROM swsi_p0_fixture;
  IF fixture_count <> 2 THEN RAISE EXCEPTION 'Fixture count changed after rollback'; END IF;
END $post_rollback$;

-- Negative drift control: stale-option update MUST match no rows.
BEGIN;
DO $negative$
DECLARE updated_rows integer;
BEGIN
  UPDATE swsi_p0_fixture SET opt_c='NOT_ALLOWED'
  WHERE id='SP104-2-37' AND opt_b='stale-source-wrong' AND answer='C';
  GET DIAGNOSTICS updated_rows = ROW_COUNT;
  IF updated_rows <> 0 THEN RAISE EXCEPTION 'Stale preimage wrongly accepted'; END IF;
END $negative$;
ROLLBACK;

DO $post_negative$
DECLARE before_json jsonb; after_json jsonb;
BEGIN
  SELECT jsonb_agg(to_jsonb(b) ORDER BY b.id) INTO before_json FROM swsi_p0_before b;
  SELECT jsonb_agg(to_jsonb(f) ORDER BY f.id) INTO after_json FROM swsi_p0_fixture f;
  IF before_json IS DISTINCT FROM after_json THEN
    RAISE EXCEPTION 'Negative-control transaction changed original fixtures';
  END IF;
END $post_negative$;

SELECT 'P0_OPTION_PG17_SYNTHETIC_ROLLBACK_PASS';

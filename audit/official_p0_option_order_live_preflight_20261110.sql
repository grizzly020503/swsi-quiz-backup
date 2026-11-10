-- SWSI 104-2 Q37 / 107-1 Q40 : production preflight / READ ONLY.
-- Verified via SELECT of production public.questions on 2026-11-10.
-- This is not an approval, migration, mutation, promotion or release script.
-- If ANY row changes (including enrichment), status becomes HOLD: re-capture
-- a fresh authorized preimage and re-run independent source review.
-- No transaction, no DML, no privileges, no credentials or private rows.
WITH expected (
    id, full_row_sha256, exam_code, official_answer, baseline_analysis_status,
    a, b, c, d
) AS (
    VALUES
    ('SP104-2-37',
     '10ed64cb7f1343b45dabb025bf54c281ffb36ec35ccf1128d37f784ddecb7dfb',
     '104100', 'C', 'review', '①②③', '①③⑤', '②③④', '③④⑤'),
    ('SP107-1-40',
     '588af4d0976c6758594e679110f210f4f14dadeebddb9c84a196889e6e7c101f',
     '107030', 'B', 'ready', '①②③④', '①③④⑤', '①②③⑤', '②③④⑤')
),
observed AS (
    SELECT
        e.id,
        q.id IS NOT NULL AS found,
        (SELECT count(*) FROM jsonb_object_keys(to_jsonb(q))) AS column_count,
        encode(sha256(convert_to(to_jsonb(q)::text, 'UTF8')), 'hex') AS actual_full_row_sha256,
        e.full_row_sha256 AS expected_full_row_sha256,
        q.source_exam_code = e.exam_code AND q.source_url LIKE
            ('https://wwwq.moex.gov.tw/exam/%code=' || e.exam_code || '%') AS source_matches,
        q.answer = e.official_answer AND q.grading_mode = 'standard'
            AND q.accepted_answers IS NULL AS grading_matches,
        q.analysis_status = e.baseline_analysis_status AS analysis_matches,
        q.opt_a = e.a AND q.opt_b = e.b AND q.opt_c = e.c AND q.opt_d = e.d
            AS option_preimage_matches
    FROM expected AS e
    LEFT JOIN public.questions AS q ON q.id = e.id
)
SELECT
    id, found, column_count, actual_full_row_sha256,
    expected_full_row_sha256, source_matches, grading_matches,
    analysis_matches, option_preimage_matches,
    (SELECT count(*) FROM public.questions) AS total_questions,
    CASE WHEN
        found AND column_count = 37 AND
        actual_full_row_sha256 = expected_full_row_sha256
        AND source_matches AND grading_matches AND analysis_matches
        AND option_preimage_matches
        AND (SELECT count(*) FROM public.questions) = 4800
        THEN 'PASS_READONLY_PREIMAGE'
        ELSE 'HOLD_NO_RELEASE'
    END AS release_preflight
FROM observed
ORDER BY id;

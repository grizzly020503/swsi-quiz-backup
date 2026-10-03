-- Follow-up to 20261003044500_correct_law_citation_metadata.sql.
-- Remove stale article numbers from student-facing exp_trap / mnemonic fields.
-- Official Core and trust states remain untouched. Fail closed on any drift.

DO $$
DECLARE
  matched integer;
BEGIN
  SELECT count(*) INTO matched
  FROM public.questions q
  JOIN (VALUES
    ('SP104-1-28','緊急生活扶助(第7條)＝按當年低收入戶每人每月最低生活費1倍核發、每次最高3個月、同案同事由1次為限、事實發生後6個月內申請。',NULL::text),
    ('SP106-1-17','扶助項目(第3條,7項)＝緊急生活扶助/子女生活津貼/子女教育補助/傷病醫療補助/兒童托育津貼/法律訴訟補助/創業貸款補助。','特殊境遇扶助「7項」:緊急生活/子女生活/子女教育/傷病醫療/兒童托育/法律訴訟/創業貸款(§3)。'),
    ('SP107-1-34','緊急生活扶助(第7條)＝按當年低收入戶每人每月最低生活費1倍核發、每次最高3個月、同案同事由1次為限、事實發生後6個月內申請。','緊急生活扶助:每次最多「3個月」、1倍最低生活費、6個月內申請、1次為限(§7)。'),
    ('SP108-2-34',NULL::text,'緊急生活扶助(第7條)＝按當年低收入戶每人每月最低生活費1倍核發、每次最高3個月、同案同事由1次為限、事實發生後6個月內申請。'),
    ('SP109-2-35','緊急生活扶助(第7條)＝按當年低收入戶每人每月最低生活費1倍核發、每次最高3個月、同案同事由1次為限、事實發生後6個月內申請。','緊急生活扶助:1倍最低生活費、每次最多「3個月」、6個月內申請(§7)。'),
    ('SP110-1-34','扶助項目(第3條,7項)＝緊急生活扶助/子女生活津貼/子女教育補助/傷病醫療補助/兒童托育津貼/法律訴訟補助/創業貸款補助。 災害救助是社會救助法的。','扶助項目(第3條,7項)＝緊急生活扶助/子女生活津貼/子女教育補助/傷病醫療補助/兒童托育津貼/法律訴訟補助/創業貸款補助。'),
    ('SP110-1-37',NULL::text,'國保月投保金額依消費者物價指數累計成長率調整(第13條)。'),
    ('SP111-1-35','扶助項目(第3條,7項)＝緊急生活扶助/子女生活津貼/子女教育補助/傷病醫療補助/兒童托育津貼/法律訴訟補助/創業貸款補助。','特殊境遇扶助7項:緊急生活/子女生活/子女教育/傷病醫療/兒童托育/法律訴訟/創業貸款(§3)。'),
    ('SP111-2-35',NULL::text,'特殊境遇津貼/補助權利不得扣押/讓與/供擔保；專戶存款不得抵銷供擔保強制執行(第15條)。'),
    ('SP114-1-35','緊急生活扶助(第7條)＝按當年低收入戶每人每月最低生活費1倍核發、每次最高3個月、同案同事由1次為限、事實發生後6個月內申請。','緊急生活扶助:1倍最低生活費、每次最多「3個月」、6個月內申請(§7)。')
  ) AS expected(id, exp_trap, mnemonic)
    ON q.id = expected.id
   AND (expected.exp_trap IS NULL OR coalesce(q.exp_trap,'') = expected.exp_trap)
   AND (expected.mnemonic IS NULL OR coalesce(q.mnemonic,'') = expected.mnemonic)
   AND q.analysis_status = 'ready';

  IF matched <> 10 THEN
    RAISE EXCEPTION 'ancillary law citation precondition drift: expected 10 exact rows, got %', matched;
  END IF;
END $$;

-- 特殊境遇家庭扶助條例：扶助項目第2條。
UPDATE public.questions
SET exp_trap = replace(exp_trap, '第3條', '第2條'),
    mnemonic = replace(replace(mnemonic, '第3條', '第2條'), '§3', '§2')
WHERE id IN ('SP106-1-17','SP110-1-34','SP111-1-35');

-- 特殊境遇家庭扶助條例：緊急生活扶助第6條。
UPDATE public.questions
SET exp_trap = replace(exp_trap, '第7條', '第6條'),
    mnemonic = replace(replace(mnemonic, '第7條', '第6條'), '§7', '§6')
WHERE id IN ('SP104-1-28','SP107-1-34','SP108-2-34','SP109-2-35','SP114-1-35');

-- 國民年金法：月投保金額 CPI 調整第11條。
UPDATE public.questions
SET mnemonic = replace(mnemonic, '第13條', '第11條')
WHERE id = 'SP110-1-37';

-- 特殊境遇家庭扶助條例：津貼補助權利保障第13-1條。
UPDATE public.questions
SET mnemonic = replace(mnemonic, '第15條', '第13-1條')
WHERE id = 'SP111-2-35';

DO $$
DECLARE
  clean integer;
BEGIN
  SELECT count(*) INTO clean
  FROM public.questions
  WHERE
    (id = 'SP104-1-28' AND exp_trap LIKE '%第6條%') OR
    (id IN ('SP106-1-17','SP110-1-34','SP111-1-35') AND exp_trap LIKE '%第2條%' AND (mnemonic LIKE '%§2%' OR mnemonic LIKE '%第2條%')) OR
    (id IN ('SP107-1-34','SP109-2-35','SP114-1-35') AND exp_trap LIKE '%第6條%' AND (mnemonic LIKE '%§6%' OR mnemonic LIKE '%第6條%')) OR
    (id = 'SP108-2-34' AND mnemonic LIKE '%第6條%') OR
    (id = 'SP110-1-37' AND mnemonic LIKE '%第11條%') OR
    (id = 'SP111-2-35' AND mnemonic LIKE '%第13-1條%');

  IF clean <> 10 THEN
    RAISE EXCEPTION 'ancillary law citation postcondition failed: expected 10 clean rows, got %', clean;
  END IF;
END $$;

-- Deliberately untouched: question/options/answer/grading, law/exp_why/extension,
-- analysis_status, legal_status and historical verification registries.

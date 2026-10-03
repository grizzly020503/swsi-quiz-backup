-- Correct 12 evidence-confirmed law citation/metadata defects without touching Official Core.
-- Scope: generated enrichment fields only (law / exp_why / extension).
-- Fail closed if any expected production value has drifted since the evidence review.

DO $$
DECLARE
  matched integer;
BEGIN
  SELECT count(*) INTO matched
  FROM public.questions q
  JOIN (VALUES
    ('SP104-1-28','特殊境遇家庭扶助條例(現行)','申請緊急生活扶助，每人每次以補助「3個月」為原則(第7條)。(B)。','特殊境遇家庭扶助條例第7條。'),
    ('SP106-1-17','特殊境遇家庭扶助條例(現行)','(D)不包括：『家庭照顧者津貼』不是特殊境遇家庭扶助項目(第3條)。','特殊境遇家庭扶助條例第3條。'),
    ('SP106-2-24','國民年金法(現行)','(D)不是法定來源：中央主管機關應補助之保險費及應負擔款項，依序由『公益彩券盈餘、調增營業稅徵收率1%所增加之收入、政府預算』籌措；『基金孳息收入』不是該補助款之籌措來源。','國民年金法第36條。'),
    ('SP107-1-23','身心障礙者權利公約施行法第7、9條。','(D)是錯的：CRPD施行法的法規檢視機制為『施行後2年內提出優先檢視清單→不符者3年內完成增修→其餘法規5年內完成』；(D)漏列或誤述了『5年內完成其餘法規』之部分。','CRPD施行法之國內法效力、國家報告與權益推動小組。'),
    ('SP107-1-34','特殊境遇家庭扶助條例(現行)','(D)是錯的：申請緊急生活扶助應於事實發生後「6個月」內申請，不是3個月(第7條)。','特殊境遇家庭扶助條例第7條。'),
    ('SP108-2-34','特殊境遇家庭扶助條例(現行)','申請緊急生活扶助，應於事實發生之後「6個月」內檢具文件提出申請(第7條)。(A)。','特殊境遇家庭扶助條例第7條。'),
    ('SP109-2-35','特殊境遇家庭扶助條例(現行)','申請緊急生活扶助者，按當年度低收入戶每人每月最低生活費用標準1倍核發，每人每次以補助「3個月」為原則(第7條)。(C)。','特殊境遇家庭扶助條例第7條。'),
    ('SP110-1-34','特殊境遇家庭扶助條例(現行)','(D)不是扶助項目：『災害救助』不屬特殊境遇家庭扶助項目(那是社會救助法的範疇)(第3條)。','特殊境遇家庭扶助條例第3條。'),
    ('SP110-1-37','國民年金法(現行)','國民年金保險之月投保金額，於『消費者物價指數』累計成長率達一定比率時，依該成長率調整(第13條)。(C)。','國民年金法第13條。'),
    ('SP111-1-35','特殊境遇家庭扶助條例(現行)','(A)不屬於：『求職交通補助』不是特殊境遇家庭扶助項目(第3條)。','特殊境遇家庭扶助條例第3條。'),
    ('SP111-2-35','特殊境遇家庭扶助條例(現行)','(A)對：依本條例請領之各項津貼或補助之權利，不得作為扣押、讓與或供擔保(第15條)。','特殊境遇家庭扶助條例第15條。'),
    ('SP114-1-35','特殊境遇家庭扶助條例(現行)','(A)對：符合特殊境遇家庭條件者，緊急生活扶助應於事實發生後「6個月」內申請(第7條)。','特殊境遇家庭扶助條例第7條。')
  ) AS expected(id, law, exp_why, extension)
    ON q.id = expected.id
   AND coalesce(q.law,'') = expected.law
   AND coalesce(q.exp_why,'') = expected.exp_why
   AND coalesce(q.extension,'') = expected.extension
   AND q.analysis_status = 'ready';

  IF matched <> 12 THEN
    RAISE EXCEPTION 'law citation correction precondition drift: expected 12 exact rows, got %', matched;
  END IF;
END $$;

-- 特殊境遇家庭扶助條例：扶助項目在第2條。
UPDATE public.questions
SET exp_why = replace(exp_why, '第3條', '第2條'),
    extension = replace(extension, '第3條', '第2條')
WHERE id IN ('SP106-1-17','SP110-1-34','SP111-1-35');

-- 特殊境遇家庭扶助條例：緊急生活扶助在第6條。
UPDATE public.questions
SET exp_why = replace(exp_why, '第7條', '第6條'),
    extension = replace(extension, '第7條', '第6條')
WHERE id IN ('SP104-1-28','SP107-1-34','SP108-2-34','SP109-2-35','SP114-1-35');

-- 特殊境遇家庭扶助條例：津貼／補助權利不得扣押、讓與或供擔保在第13-1條。
UPDATE public.questions
SET exp_why = replace(exp_why, '第15條', '第13-1條'),
    extension = replace(extension, '第15條', '第13-1條')
WHERE id = 'SP111-2-35';

-- 國民年金法：中央主管機關補助保費／負擔款項的財源在第47條。
UPDATE public.questions
SET extension = '國民年金法第47條。'
WHERE id = 'SP106-2-24';

-- 國民年金法：月投保金額依 CPI 累計成長率調整在第11條。
UPDATE public.questions
SET exp_why = replace(exp_why, '第13條', '第11條'),
    extension = '國民年金法第11條。'
WHERE id = 'SP110-1-37';

-- CRPD 施行法：2/3/5 年法規檢視及改進時程在第10條。
UPDATE public.questions
SET law = '身心障礙者權利公約施行法第10條。',
    extension = '身心障礙者權利公約施行法第10條；法規檢視與行政措施改進時程。'
WHERE id = 'SP107-1-23';

DO $$
DECLARE
  corrected integer;
BEGIN
  SELECT count(*) INTO corrected
  FROM public.questions
  WHERE
    (id IN ('SP106-1-17','SP110-1-34','SP111-1-35') AND exp_why LIKE '%第2條%' AND extension LIKE '%第2條%') OR
    (id IN ('SP104-1-28','SP107-1-34','SP108-2-34','SP109-2-35','SP114-1-35') AND exp_why LIKE '%第6條%' AND extension LIKE '%第6條%') OR
    (id = 'SP111-2-35' AND exp_why LIKE '%第13-1條%' AND extension LIKE '%第13-1條%') OR
    (id = 'SP106-2-24' AND extension = '國民年金法第47條。') OR
    (id = 'SP110-1-37' AND exp_why LIKE '%第11條%' AND extension = '國民年金法第11條。') OR
    (id = 'SP107-1-23' AND law = '身心障礙者權利公約施行法第10條。' AND extension LIKE '%第10條%');

  IF corrected <> 12 THEN
    RAISE EXCEPTION 'law citation correction postcondition failed: expected 12 corrected rows, got %', corrected;
  END IF;
END $$;

-- Deliberately untouched: question, options, answer, accepted_answers, grading_mode,
-- analysis_status, legal_status and historical_version_checked registries.

BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='60s';
LOCK TABLE public.questions IN SHARE ROW EXCLUSIVE MODE;
CREATE TEMP TABLE swsi_before ON COMMIT DROP AS SELECT id, to_jsonb(q) AS row FROM public.questions q;
CREATE TEMP TABLE swsi_batch(id text primary key, status text, note text, url text) ON COMMIT DROP;
INSERT INTO swsi_batch VALUES ('SW-104-1-24','verified_current',$swsi$考試時點法規核對（逐條人工核對）：本題考試日 2015-02-07。本題考專科社會工作師分科甄審及接受繼續教育辦法第8條：社會工作師須持有執業於專科社會工作相關領域五年以上之證明文件，始得參加專科社會工作師甄審。考試時適用 2009-07-13 訂定發布之條文；2015-07-16 及 2016-06-07 修正第8條，僅將督導訓練累計期間由二年內改為三年內、繼續教育由一百小時改為一百點，五年以上之規定未變，考試時條文與現行條文就本題規定相同。官方答案依現行條文仍正確。依據：法務部全國法規資料庫現行條文、法規沿革及歷史條文（2026-11-25 查核）。$swsi$,'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050170'),('SW-110-2-02','verified_current',$swsi$考試時點法規核對（逐條人工核對）：本題考試日 2021-08-21。本題考社會工作師接受繼續教育及執業執照更新辦法第2條：社會工作師執業應每六年接受繼續教育，積分合計應達一百二十點以上。本條最後於 2016-06-07 全文修正發布，2023-08-25 僅修正第3條之附表，本題考試日之後本條未再修正，考試時條文與現行條文相同。官方答案依現行條文仍正確。依據：法務部全國法規資料庫現行條文、法規沿革及歷史條文（2026-11-25 查核）。$swsi$,'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050169');
DO $g$ BEGIN
IF (SELECT count(*) FROM swsi_before)<>4800 THEN RAISE EXCEPTION 'count'; END IF;
IF (SELECT count(*) FROM swsi_batch)<>2 THEN RAISE EXCEPTION 'batch size'; END IF;
IF (SELECT count(*) FROM public.questions q JOIN swsi_batch b USING(id) WHERE q.legal_status='unreviewed' AND q.legal_checked_at IS NULL AND q.legal_note IS NULL AND q.legal_source_url IS NULL)<>2 THEN RAISE EXCEPTION 'preimage mismatch'; END IF;
END $g$;
UPDATE public.questions q SET legal_status=b.status, legal_checked_at='2026-11-25T12:00:00+00:00'::timestamptz, legal_note=b.note, legal_source_url=b.url
FROM swsi_batch b WHERE q.id=b.id;
DO $a$ BEGIN
IF (SELECT md5(string_agg(concat_ws(chr(31),q.id,q.legal_status,q.legal_note,q.legal_source_url),chr(30) ORDER BY q.id)) FROM public.questions q JOIN swsi_batch b USING(id) WHERE q.legal_checked_at='2026-11-25T12:00:00+00:00'::timestamptz)<>'3ca1016668380b4f10286399e4088d0d' THEN RAISE EXCEPTION 'postimage mismatch'; END IF;
IF EXISTS (SELECT 1 FROM swsi_before b FULL JOIN public.questions q USING(id) WHERE coalesce(b.id,q.id) NOT IN (SELECT id FROM swsi_batch) AND b.row IS DISTINCT FROM to_jsonb(q)) THEN RAISE EXCEPTION 'unrelated change'; END IF;
IF EXISTS (SELECT 1 FROM swsi_before b JOIN public.questions q USING(id) WHERE b.id IN (SELECT id FROM swsi_batch) AND (b.row - 'legal_status' - 'legal_checked_at' - 'legal_note' - 'legal_source_url') IS DISTINCT FROM (to_jsonb(q) - 'legal_status' - 'legal_checked_at' - 'legal_note' - 'legal_source_url')) THEN RAISE EXCEPTION 'non-legal field changed'; END IF;
END $a$;
SELECT count(*) FILTER (WHERE q.legal_status='verified_current') verified_2, count(*) FILTER (WHERE q.legal_status='changed') changed_0, count(*) total_2 FROM public.questions q JOIN swsi_batch b USING(id);
COMMIT;

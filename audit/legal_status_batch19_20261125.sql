BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='60s';
LOCK TABLE public.questions IN SHARE ROW EXCLUSIVE MODE;
CREATE TEMP TABLE swsi_before ON COMMIT DROP AS SELECT id, to_jsonb(q) AS row FROM public.questions q;
CREATE TEMP TABLE swsi_batch(id text primary key, status text, note text, url text) ON COMMIT DROP;
INSERT INTO swsi_batch VALUES ('SP105-1-12','verified_current',$swsi$考試時點法規核對（逐條人工核對）：本題考公益勸募條例第1條、第5條、第18條、第24條（立法目的；勸募團體限公立學校、行政法人、公益性社團法人及財團法人，學生社團不得逕向大眾勸募；勸募所得應公告及公開徵信；非勸募主體發起勸募之處罰），最後修正公布日：第1條 2006-05-17（制定公布）、第5條 2006-05-17（制定公布）、第18條 2006-05-17（制定公布）、第24條 2006-05-17（制定公布），本題考試日 2016-01-30 之後未再修正，考試時條文與現行條文相同，官方答案依現行條文仍正確。依據：法務部全國法規資料庫現行條文、法規沿革及歷史條文（2026-11-25 查核）。$swsi$,'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050138'),('SP106-1-10','verified_current',$swsi$考試時點法規核對（逐條人工核對）：本題考公益勸募條例第5條（各級政府機關（構）不得發起勸募，但遇重大災害或國際救援時不在此限），最後修正公布日：第5條 2006-05-17（制定公布），本題考試日 2017-02-18 之後未再修正，考試時條文與現行條文相同，官方答案依現行條文仍正確。依據：法務部全國法規資料庫現行條文、法規沿革及歷史條文（2026-11-25 查核）。$swsi$,'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050138'),('SP108-2-39','verified_current',$swsi$考試時點法規核對（逐條人工核對）：本題考公益勸募條例第10條、第11條（負責人或代表人因進行勸募涉犯罪嫌疑須「經提起公訴」始得廢止許可，僅涉犯罪嫌疑不屬之；收據記載不實、違反會務業務財務法令情節重大得廢止，申請文件不實得撤銷），最後修正公布日：第10條 2006-05-17（制定公布）、第11條 2006-05-17（制定公布），本題考試日 2019-07-27 之後未再修正，考試時條文與現行條文相同，官方答案依現行條文仍正確。依據：法務部全國法規資料庫現行條文、法規沿革及歷史條文（2026-11-25 查核）。$swsi$,'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050138'),('SP109-1-39','verified_current',$swsi$考試時點法規核對（逐條人工核對）：本題考公益勸募條例第24條（勸募活動未經許可等，經制止仍不遵從者，處新臺幣四萬元以上二十萬元以下罰鍰），最後修正公布日：第24條 2006-05-17（制定公布），本題考試日 2020-02-15 之後未再修正，考試時條文與現行條文相同，官方答案依現行條文仍正確。依據：法務部全國法規資料庫現行條文、法規沿革及歷史條文（2026-11-25 查核）。$swsi$,'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050138');
DO $g$ BEGIN
IF (SELECT count(*) FROM swsi_before)<>4800 THEN RAISE EXCEPTION 'count'; END IF;
IF (SELECT count(*) FROM swsi_batch)<>4 THEN RAISE EXCEPTION 'batch size'; END IF;
IF (SELECT count(*) FROM public.questions q JOIN swsi_batch b USING(id) WHERE q.legal_status='unreviewed' AND q.legal_checked_at IS NULL AND q.legal_note IS NULL AND q.legal_source_url IS NULL)<>4 THEN RAISE EXCEPTION 'preimage mismatch'; END IF;
END $g$;
UPDATE public.questions q SET legal_status=b.status, legal_checked_at='2026-11-25T12:00:00+00:00'::timestamptz, legal_note=b.note, legal_source_url=b.url
FROM swsi_batch b WHERE q.id=b.id;
DO $a$ BEGIN
IF (SELECT md5(string_agg(concat_ws(chr(31),q.id,q.legal_status,q.legal_note,q.legal_source_url),chr(30) ORDER BY q.id)) FROM public.questions q JOIN swsi_batch b USING(id) WHERE q.legal_checked_at='2026-11-25T12:00:00+00:00'::timestamptz)<>'0d11a530f5d52c45b0ca83d3e9f2663c' THEN RAISE EXCEPTION 'postimage mismatch'; END IF;
IF EXISTS (SELECT 1 FROM swsi_before b FULL JOIN public.questions q USING(id) WHERE coalesce(b.id,q.id) NOT IN (SELECT id FROM swsi_batch) AND b.row IS DISTINCT FROM to_jsonb(q)) THEN RAISE EXCEPTION 'unrelated change'; END IF;
IF EXISTS (SELECT 1 FROM swsi_before b JOIN public.questions q USING(id) WHERE b.id IN (SELECT id FROM swsi_batch) AND (b.row - 'legal_status' - 'legal_checked_at' - 'legal_note' - 'legal_source_url') IS DISTINCT FROM (to_jsonb(q) - 'legal_status' - 'legal_checked_at' - 'legal_note' - 'legal_source_url')) THEN RAISE EXCEPTION 'non-legal field changed'; END IF;
END $a$;
SELECT count(*) FILTER (WHERE q.legal_status='verified_current') verified_4, count(*) FILTER (WHERE q.legal_status='changed') changed_0, count(*) total_4 FROM public.questions q JOIN swsi_batch b USING(id);
COMMIT;

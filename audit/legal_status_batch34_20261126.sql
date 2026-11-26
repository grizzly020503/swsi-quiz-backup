BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='60s';
LOCK TABLE public.questions IN SHARE ROW EXCLUSIVE MODE;
CREATE TEMP TABLE swsi_before ON COMMIT DROP AS SELECT id, to_jsonb(q) AS row FROM public.questions q;
CREATE TEMP TABLE swsi_batch(id text primary key) ON COMMIT DROP;
INSERT INTO swsi_batch VALUES ('SP104-1-14'),('SP104-1-16'),('SP104-1-19'),('SP104-2-07'),('SP104-2-08'),('SP105-1-10'),('SP105-1-30'),('SP106-2-38'),('SP106-2-39'),('SP106-2-40'),('SP107-1-24'),('SP107-1-33'),('SP108-1-05'),('SP108-1-06'),('SP108-1-36'),('SP108-2-06'),('SP108-2-07'),('SP109-1-08'),('SP110-1-05'),('SP111-1-06'),('SP111-1-07'),('SP112-1-03'),('SP112-1-09'),('SP113-2-09'),('SP114-1-07'),('SP115-1-07'),('SP115-1-08'),('SW-106-2-14'),('SW-106-2-17'),('SW-107-1-13'),('SW-107-2-28'),('SW-110-2-33'),('SW-111-2-37'),('SW-113-1-02');
DO $g$ BEGIN
IF (SELECT count(*) FROM swsi_before)<>4800 THEN RAISE EXCEPTION 'count'; END IF;
IF (SELECT count(*) FROM swsi_batch)<>34 THEN RAISE EXCEPTION 'batch size'; END IF;
IF (SELECT count(*) FROM public.questions q JOIN swsi_batch b USING(id) WHERE q.legal_status='unreviewed' AND q.legal_checked_at IS NULL AND q.legal_note IS NULL AND q.legal_source_url IS NULL)<>34 THEN RAISE EXCEPTION 'preimage mismatch'; END IF;
END $g$;
UPDATE public.questions q SET legal_status='not_applicable' FROM swsi_batch b WHERE q.id=b.id;
DO $a$ BEGIN
IF (SELECT md5(string_agg(concat_ws(chr(31),q.id,q.legal_status),chr(30) ORDER BY q.id)) FROM public.questions q JOIN swsi_batch b USING(id)) IS DISTINCT FROM '701d6ecffdf26e214a7e7bde03de152f' THEN RAISE EXCEPTION 'postimage mismatch'; END IF;
IF (SELECT count(*) FROM public.questions q JOIN swsi_batch b USING(id) WHERE q.legal_status='not_applicable' AND q.legal_checked_at IS NULL AND q.legal_note IS NULL AND q.legal_source_url IS NULL)<>34 THEN RAISE EXCEPTION 'postimage count'; END IF;
IF EXISTS (SELECT 1 FROM swsi_before b FULL JOIN public.questions q USING(id) WHERE coalesce(b.id,q.id) NOT IN (SELECT id FROM swsi_batch) AND b.row IS DISTINCT FROM to_jsonb(q)) THEN RAISE EXCEPTION 'unrelated change'; END IF;
IF EXISTS (SELECT 1 FROM swsi_before b JOIN public.questions q USING(id) WHERE b.id IN (SELECT id FROM swsi_batch) AND (b.row - 'legal_status') IS DISTINCT FROM (to_jsonb(q) - 'legal_status')) THEN RAISE EXCEPTION 'non-legal field changed'; END IF;
END $a$;
SELECT count(*) FILTER (WHERE q.legal_status='not_applicable') not_applicable_34, count(*) total_34 FROM public.questions q JOIN swsi_batch b USING(id);
COMMIT;

BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='60s';
LOCK TABLE public.questions IN SHARE ROW EXCLUSIVE MODE;
CREATE TEMP TABLE swsi_before ON COMMIT DROP AS SELECT id, to_jsonb(q) AS row FROM public.questions q;
CREATE TEMP TABLE swsi_batch(id text primary key) ON COMMIT DROP;
INSERT INTO swsi_batch VALUES ('SP105-2-01'),('SP105-2-02'),('SP105-2-03'),('SP105-2-04'),('SP105-2-05'),('SP105-2-06'),('SP105-2-07'),('SP105-2-08'),('SP105-2-09'),('SP105-2-10'),('SP105-2-11'),('SP105-2-15'),('SP105-2-16'),('SP105-2-26'),('SP105-2-29'),('SP105-2-34'),('SP105-2-35'),('SP106-1-13'),('SP106-1-27'),('SP106-1-32'),('SP106-1-33'),('SP106-1-34'),('SP106-1-35'),('SP106-1-36'),('SP106-1-37'),('SP106-1-39'),('SP106-1-40'),('SP106-2-02'),('SP106-2-03'),('SP106-2-04'),('SP106-2-10'),('SP107-1-01'),('SP107-1-03'),('SP107-1-04'),('SP107-1-06'),('SP107-1-07'),('SP107-1-09'),('SP107-1-11'),('SP107-1-12'),('SP107-1-14'),('SP107-1-17'),('SP107-1-35'),('SP107-1-36');
DO $g$ BEGIN
IF (SELECT count(*) FROM swsi_before)<>4800 THEN RAISE EXCEPTION 'count'; END IF;
IF (SELECT count(*) FROM swsi_batch)<>43 THEN RAISE EXCEPTION 'batch size'; END IF;
IF (SELECT count(*) FROM public.questions q JOIN swsi_batch b USING(id) WHERE q.legal_status='unreviewed' AND q.legal_checked_at IS NULL AND q.legal_note IS NULL AND q.legal_source_url IS NULL)<>43 THEN RAISE EXCEPTION 'preimage mismatch'; END IF;
END $g$;
UPDATE public.questions q SET legal_status='not_applicable' FROM swsi_batch b WHERE q.id=b.id;
DO $a$ BEGIN
IF (SELECT md5(string_agg(concat_ws(chr(31),q.id,q.legal_status),chr(30) ORDER BY q.id)) FROM public.questions q JOIN swsi_batch b USING(id)) IS DISTINCT FROM 'c7f63dd6eb0973e6d4077c3ac6be40b1' THEN RAISE EXCEPTION 'postimage mismatch'; END IF;
IF (SELECT count(*) FROM public.questions q JOIN swsi_batch b USING(id) WHERE q.legal_status='not_applicable' AND q.legal_checked_at IS NULL AND q.legal_note IS NULL AND q.legal_source_url IS NULL)<>43 THEN RAISE EXCEPTION 'postimage count'; END IF;
IF EXISTS (SELECT 1 FROM swsi_before b FULL JOIN public.questions q USING(id) WHERE coalesce(b.id,q.id) NOT IN (SELECT id FROM swsi_batch) AND b.row IS DISTINCT FROM to_jsonb(q)) THEN RAISE EXCEPTION 'unrelated change'; END IF;
IF EXISTS (SELECT 1 FROM swsi_before b JOIN public.questions q USING(id) WHERE b.id IN (SELECT id FROM swsi_batch) AND (b.row - 'legal_status') IS DISTINCT FROM (to_jsonb(q) - 'legal_status')) THEN RAISE EXCEPTION 'non-legal field changed'; END IF;
END $a$;
SELECT count(*) FILTER (WHERE q.legal_status='not_applicable') not_applicable_43, count(*) total_43 FROM public.questions q JOIN swsi_batch b USING(id);
COMMIT;

BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='60s';
LOCK TABLE public.questions IN SHARE ROW EXCLUSIVE MODE;
CREATE TEMP TABLE swsi_before ON COMMIT DROP AS SELECT id, to_jsonb(q) AS row FROM public.questions q;
CREATE TEMP TABLE swsi_batch(id text primary key) ON COMMIT DROP;
INSERT INTO swsi_batch VALUES ('SP109-1-01'),('SP109-1-02'),('SP109-1-03'),('SP109-1-04'),('SP109-1-05'),('SP109-1-07'),('SP109-1-09'),('SP109-1-10'),('SP109-1-12'),('SP109-1-13'),('SP109-1-14'),('SP109-1-15'),('SP109-1-16'),('SP109-1-17'),('SP109-1-18'),('SP109-1-20'),('SP109-2-01'),('SP109-2-02'),('SP109-2-03'),('SP109-2-04'),('SP109-2-06'),('SP109-2-07'),('SP109-2-08'),('SP109-2-09'),('SP109-2-10'),('SP109-2-11'),('SP109-2-12'),('SP109-2-13'),('SP109-2-15'),('SP109-2-16'),('SP109-2-18'),('SP109-2-19'),('SP110-1-01'),('SP110-1-03'),('SP110-1-04'),('SP110-1-06'),('SP110-1-08'),('SP110-1-09'),('SP110-1-10'),('SP110-1-11'),('SP110-1-12'),('SP110-1-13'),('SP110-1-14'),('SP110-1-15'),('SP110-1-16'),('SP110-1-17'),('SP110-1-18'),('SP110-1-19'),('SP110-1-23');
DO $g$ BEGIN
IF (SELECT count(*) FROM swsi_before)<>4800 THEN RAISE EXCEPTION 'count'; END IF;
IF (SELECT count(*) FROM swsi_batch)<>49 THEN RAISE EXCEPTION 'batch size'; END IF;
IF (SELECT count(*) FROM public.questions q JOIN swsi_batch b USING(id) WHERE q.legal_status='unreviewed' AND q.legal_checked_at IS NULL AND q.legal_note IS NULL AND q.legal_source_url IS NULL)<>49 THEN RAISE EXCEPTION 'preimage mismatch'; END IF;
END $g$;
UPDATE public.questions q SET legal_status='not_applicable' FROM swsi_batch b WHERE q.id=b.id;
DO $a$ BEGIN
IF (SELECT md5(string_agg(concat_ws(chr(31),q.id,q.legal_status),chr(30) ORDER BY q.id)) FROM public.questions q JOIN swsi_batch b USING(id)) IS DISTINCT FROM 'd47ba79b086ef53bbc030dd03a1b0276' THEN RAISE EXCEPTION 'postimage mismatch'; END IF;
IF (SELECT count(*) FROM public.questions q JOIN swsi_batch b USING(id) WHERE q.legal_status='not_applicable' AND q.legal_checked_at IS NULL AND q.legal_note IS NULL AND q.legal_source_url IS NULL)<>49 THEN RAISE EXCEPTION 'postimage count'; END IF;
IF EXISTS (SELECT 1 FROM swsi_before b FULL JOIN public.questions q USING(id) WHERE coalesce(b.id,q.id) NOT IN (SELECT id FROM swsi_batch) AND b.row IS DISTINCT FROM to_jsonb(q)) THEN RAISE EXCEPTION 'unrelated change'; END IF;
IF EXISTS (SELECT 1 FROM swsi_before b JOIN public.questions q USING(id) WHERE b.id IN (SELECT id FROM swsi_batch) AND (b.row - 'legal_status') IS DISTINCT FROM (to_jsonb(q) - 'legal_status')) THEN RAISE EXCEPTION 'non-legal field changed'; END IF;
END $a$;
SELECT count(*) FILTER (WHERE q.legal_status='not_applicable') not_applicable_49, count(*) total_49 FROM public.questions q JOIN swsi_batch b USING(id);
COMMIT;

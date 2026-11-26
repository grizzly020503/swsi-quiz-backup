BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='60s';
LOCK TABLE public.questions IN SHARE ROW EXCLUSIVE MODE;
CREATE TEMP TABLE swsi_before ON COMMIT DROP AS SELECT id, to_jsonb(q) AS row FROM public.questions q;
CREATE TEMP TABLE swsi_batch(id text primary key) ON COMMIT DROP;
INSERT INTO swsi_batch VALUES ('HBSE-104-2-029'),('SP104-1-01'),('SP104-1-02'),('SP104-1-03'),('SP104-1-04'),('SP104-1-05'),('SP104-1-06'),('SP104-1-07'),('SP104-1-08'),('SP104-1-10'),('SP104-1-11'),('SP104-1-12'),('SP104-1-13'),('SP104-2-01'),('SP104-2-02'),('SP104-2-03'),('SP104-2-04'),('SP104-2-06'),('SP104-2-12'),('SP104-2-13'),('SP104-2-14'),('SP104-2-15'),('SP104-2-16'),('SP104-2-17'),('SP104-2-18'),('SP104-2-19'),('SP104-2-20'),('SP104-2-34'),('SP105-1-11'),('SP105-1-13'),('SP105-1-14'),('SP105-1-15'),('SP105-1-19'),('SP105-1-20'),('SP105-1-22'),('SP105-1-23'),('SP105-1-25'),('SP105-1-26'),('SP105-1-28'),('SP105-1-29'),('SP105-1-34'),('SP105-1-36'),('SP105-1-37'),('SP105-1-38'),('SP105-1-39');
DO $g$ BEGIN
IF (SELECT count(*) FROM swsi_before)<>4800 THEN RAISE EXCEPTION 'count'; END IF;
IF (SELECT count(*) FROM swsi_batch)<>45 THEN RAISE EXCEPTION 'batch size'; END IF;
IF (SELECT count(*) FROM public.questions q JOIN swsi_batch b USING(id) WHERE q.legal_status='unreviewed' AND q.legal_checked_at IS NULL AND q.legal_note IS NULL AND q.legal_source_url IS NULL)<>45 THEN RAISE EXCEPTION 'preimage mismatch'; END IF;
END $g$;
UPDATE public.questions q SET legal_status='not_applicable' FROM swsi_batch b WHERE q.id=b.id;
DO $a$ BEGIN
IF (SELECT md5(string_agg(concat_ws(chr(31),q.id,q.legal_status),chr(30) ORDER BY q.id)) FROM public.questions q JOIN swsi_batch b USING(id)) IS DISTINCT FROM '39d31d021c523ddc246a35c436ac98f3' THEN RAISE EXCEPTION 'postimage mismatch'; END IF;
IF (SELECT count(*) FROM public.questions q JOIN swsi_batch b USING(id) WHERE q.legal_status='not_applicable' AND q.legal_checked_at IS NULL AND q.legal_note IS NULL AND q.legal_source_url IS NULL)<>45 THEN RAISE EXCEPTION 'postimage count'; END IF;
IF EXISTS (SELECT 1 FROM swsi_before b FULL JOIN public.questions q USING(id) WHERE coalesce(b.id,q.id) NOT IN (SELECT id FROM swsi_batch) AND b.row IS DISTINCT FROM to_jsonb(q)) THEN RAISE EXCEPTION 'unrelated change'; END IF;
IF EXISTS (SELECT 1 FROM swsi_before b JOIN public.questions q USING(id) WHERE b.id IN (SELECT id FROM swsi_batch) AND (b.row - 'legal_status') IS DISTINCT FROM (to_jsonb(q) - 'legal_status')) THEN RAISE EXCEPTION 'non-legal field changed'; END IF;
END $a$;
SELECT count(*) FILTER (WHERE q.legal_status='not_applicable') not_applicable_45, count(*) total_45 FROM public.questions q JOIN swsi_batch b USING(id);
COMMIT;

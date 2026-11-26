BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='60s';
LOCK TABLE public.questions IN SHARE ROW EXCLUSIVE MODE;
CREATE TEMP TABLE swsi_before ON COMMIT DROP AS SELECT id, to_jsonb(q) AS row FROM public.questions q;
CREATE TEMP TABLE swsi_batch(id text primary key) ON COMMIT DROP;
INSERT INTO swsi_batch VALUES ('HBSE-108-2-028'),('SP107-2-01'),('SP107-2-02'),('SP107-2-03'),('SP107-2-04'),('SP107-2-11'),('SP107-2-12'),('SP107-2-13'),('SP107-2-14'),('SP107-2-21'),('SP107-2-24'),('SP107-2-25'),('SP107-2-35'),('SP107-2-36'),('SP107-2-37'),('SP107-2-38'),('SP108-1-01'),('SP108-1-02'),('SP108-1-03'),('SP108-1-04'),('SP108-1-07'),('SP108-1-08'),('SP108-1-09'),('SP108-1-10'),('SP108-1-11'),('SP108-1-12'),('SP108-1-13'),('SP108-1-14'),('SP108-1-15'),('SP108-1-16'),('SP108-1-17'),('SP108-1-37'),('SP108-2-01'),('SP108-2-02'),('SP108-2-03'),('SP108-2-04'),('SP108-2-05'),('SP108-2-10'),('SP108-2-11'),('SP108-2-12'),('SP108-2-13'),('SP108-2-14'),('SP108-2-15'),('SP108-2-16'),('SP108-2-17'),('SP108-2-18'),('SP108-2-19'),('SP108-2-37');
DO $g$ BEGIN
IF (SELECT count(*) FROM swsi_before)<>4800 THEN RAISE EXCEPTION 'count'; END IF;
IF (SELECT count(*) FROM swsi_batch)<>48 THEN RAISE EXCEPTION 'batch size'; END IF;
IF (SELECT count(*) FROM public.questions q JOIN swsi_batch b USING(id) WHERE q.legal_status='unreviewed' AND q.legal_checked_at IS NULL AND q.legal_note IS NULL AND q.legal_source_url IS NULL)<>48 THEN RAISE EXCEPTION 'preimage mismatch'; END IF;
END $g$;
UPDATE public.questions q SET legal_status='not_applicable' FROM swsi_batch b WHERE q.id=b.id;
DO $a$ BEGIN
IF (SELECT md5(string_agg(concat_ws(chr(31),q.id,q.legal_status),chr(30) ORDER BY q.id)) FROM public.questions q JOIN swsi_batch b USING(id)) IS DISTINCT FROM 'e3c8f18e81b4c166fac746f70fb120d8' THEN RAISE EXCEPTION 'postimage mismatch'; END IF;
IF (SELECT count(*) FROM public.questions q JOIN swsi_batch b USING(id) WHERE q.legal_status='not_applicable' AND q.legal_checked_at IS NULL AND q.legal_note IS NULL AND q.legal_source_url IS NULL)<>48 THEN RAISE EXCEPTION 'postimage count'; END IF;
IF EXISTS (SELECT 1 FROM swsi_before b FULL JOIN public.questions q USING(id) WHERE coalesce(b.id,q.id) NOT IN (SELECT id FROM swsi_batch) AND b.row IS DISTINCT FROM to_jsonb(q)) THEN RAISE EXCEPTION 'unrelated change'; END IF;
IF EXISTS (SELECT 1 FROM swsi_before b JOIN public.questions q USING(id) WHERE b.id IN (SELECT id FROM swsi_batch) AND (b.row - 'legal_status') IS DISTINCT FROM (to_jsonb(q) - 'legal_status')) THEN RAISE EXCEPTION 'non-legal field changed'; END IF;
END $a$;
SELECT count(*) FILTER (WHERE q.legal_status='not_applicable') not_applicable_48, count(*) total_48 FROM public.questions q JOIN swsi_batch b USING(id);
COMMIT;

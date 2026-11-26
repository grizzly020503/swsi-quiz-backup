-- Re-open the SWSI AI analysis queue whenever a question ends up pending,
-- including when trg_reset_ai_on_official_change (a BEFORE trigger) is what
-- set analysis_status = 'pending'.
--
-- 2026-11-23 14:00 UTC: the queue drained, so trg_auto_stop_ai_queue turned
-- the swsi-ai-analysis cron off (by design).
-- 2026-11-24: official source repair release 20261124b updated only
-- question/opt_* columns. trg_reset_ai_on_official_change cleared the old
-- explanations of 22 questions and set them to pending, but
-- trg_auto_enable_ai_pending was declared AFTER ... UPDATE OF analysis_status.
-- PostgreSQL fires a column-list UPDATE trigger only for columns named in the
-- UPDATE's SET list; values changed by BEFORE triggers do not count. The cron
-- stayed off and the 22 questions waited until it was re-enabled by hand on
-- 2026-11-26.
--
-- The trigger now fires on every INSERT/UPDATE and lets WHEN decide on the
-- final row, which includes values written by BEFORE triggers. WHEN mirrors
-- the queue's own claim rule (pending, official source, fewer than 3
-- attempts), so updates to other rows never call the function. The function
-- body is unchanged; it only enables the cron when it is off.
--
-- Checked by scripts/ai_queue_auto_enable_pg_selftest.py.

drop trigger if exists trg_auto_enable_ai_pending on public.questions;
create trigger trg_auto_enable_ai_pending
after insert or update on public.questions
for each row
when (
  new.analysis_status = 'pending'
  and new.source_exam_code is not null
  and coalesce(new.analysis_attempts, 0) < 3
)
execute function public.auto_enable_ai_for_pending_question();

-- SWSI recovery/source-of-truth alignment for official grading metadata.
--
-- Production already includes grading_mode in the official-change reset trigger.
-- This migration makes the GitHub recovery path match production so a future
-- rebuild does not regress to stale AI analysis when official grading semantics
-- change.

create or replace function public.reset_ai_analysis_on_official_change()
returns trigger
language plpgsql
security definer
set search_path to ''
as $function$
begin
  if new.source_exam_code is not null and (
       new.question is distinct from old.question
    or new.opt_a is distinct from old.opt_a
    or new.opt_b is distinct from old.opt_b
    or new.opt_c is distinct from old.opt_c
    or new.opt_d is distinct from old.opt_d
    or new.answer is distinct from old.answer
    or new.accepted_answers is distinct from old.accepted_answers
    or new.grading_mode is distinct from old.grading_mode
  ) then
    new.major := null;
    new.topic := null;
    new.keywords := null;
    new.exp_why := null;
    new.exp_others := null;
    new.exp_trap := null;
    new.exp_raw := null;
    new.mnemonic := null;
    new.extension := null;
    new.law := null;
    new.mistake := null;
    new.analysis_status := 'pending';
    new.analysis_attempts := 0;
    new.analysis_error := null;
    new.analysis_started_at := null;
    new.analysis_completed_at := null;
  end if;
  return new;
end;
$function$;

drop trigger if exists trg_reset_ai_on_official_change on public.questions;
create trigger trg_reset_ai_on_official_change
before update of question, opt_a, opt_b, opt_c, opt_d, answer, accepted_answers, grading_mode
on public.questions
for each row execute function public.reset_ai_analysis_on_official_change();

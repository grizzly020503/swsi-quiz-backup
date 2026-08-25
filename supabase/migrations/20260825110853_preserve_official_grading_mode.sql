-- Preserve official MOEX unanswered-scoring semantics.
-- Applied to production as migration 20260825110853_preserve_official_grading_mode.

alter table public.questions
  add column if not exists grading_mode text not null default 'standard';

-- 12 questions are true official "一律給分": even an unanswered item receives credit.
update public.questions
set grading_mode = 'all_credit'
where id in (
  'R-104-2-21',
  'SP104-2-25',
  'SW-105-1-16',
  'HBSE-106-2-004',
  'HBSE-106-2-023',
  'DS-107-1-25',
  'SW-107-2-09',
  'HBSE-111-1-018',
  'SW-112-2-34',
  'SW-113-1-29',
  'HBSE-114-2-007',
  'SW-114-2-36'
);

-- 4 questions use MOEX wording "除未作答者不給分外，其餘均給分":
-- any A-D response receives credit, but blank does not.
update public.questions
set grading_mode = 'any_answer'
where id in (
  'SW-105-1-17',
  'SW-106-1-36',
  'HBSE-108-2-039',
  'HBSE-110-2-034'
);

alter table public.questions
  drop constraint if exists questions_grading_mode_valid;
alter table public.questions
  add constraint questions_grading_mode_valid
  check (grading_mode in ('standard','all_credit','any_answer'));

alter table public.questions
  drop constraint if exists questions_grading_mode_consistent;
alter table public.questions
  add constraint questions_grading_mode_consistent
  check (
    (
      grading_mode = 'standard'
      and answer = any(array['A','B','C','D']::text[])
    )
    or
    (
      grading_mode in ('all_credit','any_answer')
      and answer = '一律給分'
      and accepted_answers is null
    )
  );

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

comment on column public.questions.grading_mode is
'Official MOEX scoring semantics: standard = score by answer/accepted_answers; all_credit = official 一律給分 including blank; any_answer = any A-D response scores but unanswered does not.';

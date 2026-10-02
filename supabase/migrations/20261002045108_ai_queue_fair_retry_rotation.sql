-- Prevent transient analyzer failures from deterministically starving later queue rows.
-- Operational metadata only: no Official Core fields are changed.

alter table public.questions
  add column if not exists analysis_last_attempt_at timestamptz;

create or replace function public.claim_pending_ai_questions(p_limit integer default 1)
returns setof public.questions
language plpgsql
security definer
set search_path to 'public'
as $function$
declare
  completed_24h integer;
begin
  select count(*)::integer
    into completed_24h
    from public.questions
   where analysis_completed_at >= now() - interval '24 hours';

  if completed_24h >= 25 then
    return;
  end if;

  return query
  with picked as (
    select q.id
      from public.questions q
     where (
       q.analysis_status = 'pending'
       or (
         q.analysis_status = 'analyzing'
         and q.analysis_started_at < now() - interval '15 minutes'
       )
     )
       and coalesce(q.analysis_attempts, 0) < 3
     order by q.analysis_last_attempt_at nulls first,
              q.source_exam_code nulls last,
              case when q.qno ~ '^\d+$' then q.qno::integer else 999999 end,
              q.subject,
              q.id
     for update skip locked
     limit greatest(1, least(coalesce(p_limit, 1), 1))
  )
  update public.questions q
     set analysis_status = 'analyzing',
         analysis_started_at = now(),
         analysis_last_attempt_at = now(),
         analysis_error = null
    from picked p
   where q.id = p.id
  returning q.*;
end;
$function$;

-- Official Core changes create a fresh analysis job and must clear retry age too.
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
    new.analysis_last_attempt_at := null;
  end if;
  return new;
end;
$function$;

revoke all on function public.claim_pending_ai_questions(integer) from public, anon, authenticated;
grant execute on function public.claim_pending_ai_questions(integer) to service_role;

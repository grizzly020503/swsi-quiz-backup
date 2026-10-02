#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
MANIFEST = ROOT / "supabase" / "recovery" / "recovery_manifest.json"
RECOVERY = ROOT / "scripts" / "supabase_recovery_dry_run.py"
CONTRACT = ROOT / "supabase" / "recovery" / "postgres_runtime_contract.sql"

matches = sorted(MIGRATIONS.glob("*_ai_queue_fair_retry_rotation.sql"))
if len(matches) != 1:
    raise SystemExit(f"expected exactly one generated fairness migration, found {len(matches)}")
migration = matches[0]
rel = migration.relative_to(ROOT).as_posix()

migration.write_text(r'''-- Prevent transient analyzer failures from deterministically starving later queue rows.
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
''', encoding="utf-8")

manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
order = manifest["migration_order"]
if rel in order:
    raise SystemExit(f"migration already registered: {rel}
")
acl = "supabase/recovery/production_acl_alignment.sql"
if acl not in order:
    raise SystemExit("production ACL alignment marker missing")
order.insert(order.index(acl), rel)
if int(manifest["expected"]["question_columns"]) != 36:
    raise SystemExit("question_columns baseline changed; review manually")
manifest["expected"]["question_columns"] = 37
MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

text = RECOVERY.read_text(encoding="utf-8")
needle = '        "analysis_completed_at",\n'
if text.count(needle) != 1:
    raise SystemExit("recovery required-column marker changed")
text = text.replace(needle, needle + '        "analysis_last_attempt_at",\n', 1)
RECOVERY.write_text(text, encoding="utf-8")

contract = CONTRACT.read_text(encoding="utf-8")
marker = "\\echo 'SWSI RESTORED RUNTIME DB CONTRACT OK'"
if contract.count(marker) != 1:
    raise SystemExit("runtime contract end marker changed")
fixture = r'''
-- AI queue fairness: never-attempted rows must run before retries, then the oldest retry.
begin;
update public.questions
   set analysis_status = 'review', analysis_started_at = null
 where analysis_status in ('pending', 'analyzing');

insert into public.questions(
  id, subject, qno, answer, grading_mode, source_exam_code,
  analysis_status, analysis_attempts, analysis_last_attempt_at
) values
  ('DR-QUEUE-OLD', '社會工作', '1', 'A', 'standard', 'DR-FAIRNESS', 'pending', 0, now() - interval '20 minutes'),
  ('DR-QUEUE-NEW', '社會工作', '2', 'A', 'standard', 'DR-FAIRNESS', 'pending', 0, now() - interval '5 minutes'),
  ('DR-QUEUE-FRESH', '社會工作', '999', 'A', 'standard', 'DR-FAIRNESS', 'pending', 0, null);

set role service_role;
create temp table dr_first_claim as
select id from public.claim_pending_ai_questions(1);
reset role;

do $$
begin
  if (select array_agg(id order by id) from dr_first_claim) is distinct from array['DR-QUEUE-FRESH']::text[] then
    raise exception 'queue fairness failed: fresh row was not claimed first';
  end if;
  if (select analysis_status from public.questions where id='DR-QUEUE-FRESH') <> 'analyzing' then
    raise exception 'queue fairness failed: fresh row not marked analyzing';
  end if;
  if (select analysis_last_attempt_at from public.questions where id='DR-QUEUE-FRESH') is null then
    raise exception 'queue fairness failed: claim did not persist last-attempt time';
  end if;
end
$$;

update public.questions
   set analysis_status='review', analysis_started_at=null
 where id='DR-QUEUE-FRESH';

set role service_role;
create temp table dr_second_claim as
select id from public.claim_pending_ai_questions(1);
reset role;

do $$
begin
  if (select array_agg(id order by id) from dr_second_claim) is distinct from array['DR-QUEUE-OLD']::text[] then
    raise exception 'queue fairness failed: oldest retry was not claimed next';
  end if;
end
$$;
rollback;

-- Official Core reset must make the next analysis fresh again.
begin;
insert into public.questions(
  id, subject, qno, question, answer, grading_mode, source_exam_code,
  analysis_status, analysis_attempts, analysis_last_attempt_at
) values (
  'DR-QUEUE-RESET', '社會工作', '998', '原題', 'A', 'standard', 'DR-FAIRNESS',
  'review', 2, now()
);
update public.questions set question='更正後題目' where id='DR-QUEUE-RESET';
do $$
begin
  if (select analysis_status from public.questions where id='DR-QUEUE-RESET') <> 'pending' then
    raise exception 'official-change reset did not requeue analysis';
  end if;
  if (select analysis_attempts from public.questions where id='DR-QUEUE-RESET') <> 0 then
    raise exception 'official-change reset did not clear attempts';
  end if;
  if (select analysis_last_attempt_at from public.questions where id='DR-QUEUE-RESET') is not null then
    raise exception 'official-change reset did not clear last-attempt time';
  end if;
end
$$;
rollback;

'''
contract = contract.replace(marker, fixture + marker, 1)
CONTRACT.write_text(contract, encoding="utf-8")

print(rel)

-- SWSI production QA consolidation
--
-- This file is a GitHub recovery/source-of-truth consolidation for production changes
-- already applied in Supabase on 2026-08-25. Do NOT re-apply to production merely
-- because this file was added to GitHub.
--
-- Consolidates production migrations:
--   20260825082549 balance_ai_question_queue_by_question_number
--   20260825083449 add_official_multi_answer_metadata
--   20260825084501 enforce_multi_answer_consistency_and_analysis_reset
--   20260825085242 add_official_multi_answer_support_data
--   20260825090927 reset_ai_when_accepted_answers_change
--   20260825092357 expand_legal_mapping_to_official_question_text
--   20260825094110 quarantine_all_give_and_reject_ai_answer_meta

-- 1) Balance the AI queue across subjects by question number.
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
       and coalesce(q.analysis_attempts,0) < 3
     order by q.source_exam_code nulls last,
              case when q.qno ~ '^\d+$' then q.qno::integer else 999999 end,
              q.subject,
              q.id
     for update skip locked
     limit greatest(1, least(coalesce(p_limit,1),1))
  )
  update public.questions q
     set analysis_status = 'analyzing',
         analysis_started_at = now(),
         analysis_error = null
    from picked p
   where q.id = p.id
  returning q.*;
end;
$function$;

-- 2) Official multiple-answer metadata.
alter table public.questions
  add column if not exists accepted_answers text[];

alter table public.questions drop constraint if exists questions_accepted_answers_valid;
alter table public.questions add constraint questions_accepted_answers_valid
check (
  accepted_answers is null
  or (
    cardinality(accepted_answers) >= 1
    and cardinality(accepted_answers) <= 4
    and accepted_answers <@ array['A','B','C','D']::text[]
  )
);

alter table public.questions drop constraint if exists questions_answer_within_accepted_answers;
alter table public.questions add constraint questions_answer_within_accepted_answers
check (accepted_answers is null or answer = any(accepted_answers));

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
before update of question, opt_a, opt_b, opt_c, opt_d, answer, accepted_answers
on public.questions
for each row execute function public.reset_ai_analysis_on_official_change();

-- Official MOEX final multiple-answer rows verified by the historical 4,800-question audit.
with official_multi(id, accepted_answers) as (
  values
    ('SW-104-1-14', array['B','C']::text[]),
    ('DS-104-2-36', array['B','D']::text[]),
    ('R-104-2-07', array['B','C']::text[]),
    ('R-104-2-23', array['B','D']::text[]),
    ('HBSE-105-1-036', array['A','C']::text[]),
    ('SW-105-2-20', array['A','B']::text[]),
    ('SP105-2-18', array['B','C']::text[]),
    ('HBSE-107-1-013', array['A','C']::text[]),
    ('SP107-1-16', array['B','C']::text[]),
    ('HBSE-107-2-012', array['A','D']::text[]),
    ('R-107-2-12', array['B','C']::text[]),
    ('HBSE-108-1-011', array['A','B']::text[]),
    ('HBSE-108-1-021', array['A','B']::text[]),
    ('HBSE-108-2-021', array['A','B']::text[]),
    ('R-108-2-21', array['A','B']::text[]),
    ('DS-109-2-26', array['A','D']::text[]),
    ('HBSE-110-2-037', array['C','D']::text[]),
    ('SW-111-2-40', array['C','D']::text[]),
    ('R-111-2-22', array['C','D']::text[]),
    ('HBSE-112-2-007', array['A','C']::text[]),
    ('HBSE-112-2-027', array['B','D']::text[]),
    ('HBSE-113-2-022', array['A','B','D']::text[]),
    ('SW-114-1-12', array['B','C']::text[]),
    ('HBSE-114-2-016', array['C','D']::text[])
)
update public.questions q
   set accepted_answers = m.accepted_answers,
       exp_why = null,
       exp_others = null,
       exp_trap = null,
       exp_raw = null,
       mnemonic = null,
       extension = null,
       law = null,
       mistake = null,
       analysis_status = 'review',
       analysis_attempts = 0,
       analysis_error = '官方多答案題：等待前端 accepted_answers 判題支援後重新解析',
       analysis_started_at = null,
       analysis_completed_at = null
  from official_multi m
 where q.id = m.id;

-- 3) Legal mapping now uses official question/option text plus AI law metadata.
create or replace function public.extract_legal_canonical_names(raw_law text)
returns text[]
language plpgsql
immutable
set search_path to ''
as $function$
declare
  s text := coalesce(raw_law, '');
  out_names text[] := '{}'::text[];
  n text;
  names text[] := array[
    '兒童及少年福利與權益保障法','身心障礙者權益保障法','老人福利法','家庭暴力防治法','社會救助法','長期照顧服務法','社會工作師法','兒童及少年性剝削防制條例','特殊境遇家庭扶助條例','性侵害犯罪防治法','性別平等工作法','國民年金法','志願服務法','公益勸募條例','精神衛生法','兒童及少年未來教育與發展帳戶條例','病人自主權利法','就業保險法','少年事件處理法','消除對婦女一切形式歧視公約施行法','兒童權利公約施行法','兒童權利公約','身心障礙者權利公約施行法','身心障礙者權利公約','全民健康保險法','原住民族工作權保障法','中華民國刑法','中華民國憲法增修條文','人口販運防制法','住宅法','公益彩券發行條例','勞工保險條例','協助積極自立脫離貧窮實施辦法','國民教育法','學生輔導法','家事事件法','專科社會工作師分科甄審及接受繼續教育辦法','性別平等教育法','性騷擾防治法','跟蹤騷擾防制法','毒品危害防制條例','民法','社會工作師接受繼續教育及執業執照更新辦法','社會福利基本法','老年農民福利津貼暫行條例','長期照顧服務機構法人條例','經濟社會文化權利國際公約','全民健康保險醫療服務給付項目及支付標準','國民小學與國民中學未入學或中途輟學學生通報及復學輔導辦法','校園霸凌防制準則','社區發展工作綱要','公民與政治權利國際公約及經濟社會文化權利國際公約施行法'
  ];
begin
  if position('性別工作平等法' in s) > 0 and position('性別平等工作法' in s) = 0 then
    out_names := array_append(out_names, '性別平等工作法');
  end if;

  if position('兩公約施行法' in s) > 0 or position('人權公約施行法' in s) > 0 then
    if not ('公民與政治權利國際公約及經濟社會文化權利國際公約施行法' = any(out_names)) then
      out_names := array_append(out_names, '公民與政治權利國際公約及經濟社會文化權利國際公約施行法');
    end if;
  end if;

  if position('社會工作師執業登記及繼續教育辦法' in s) > 0
     and position('社會工作師接受繼續教育及執業執照更新辦法' in s) = 0 then
    out_names := array_append(out_names, '社會工作師接受繼續教育及執業執照更新辦法');
  end if;

  foreach n in array names loop
    if position(n in s) > 0 and not (n = any(out_names)) then
      out_names := array_append(out_names, n);
    end if;
  end loop;

  return out_names;
end;
$function$;

create or replace function public.sync_question_legal_canonical_names()
returns trigger
language plpgsql
set search_path to 'public'
as $function$
begin
  new.legal_canonical_names := public.extract_legal_canonical_names(
    concat_ws(' ', new.question, new.opt_a, new.opt_b, new.opt_c, new.opt_d, new.law)
  );
  return new;
end;
$function$;

drop trigger if exists questions_sync_legal_canonical_names on public.questions;
create trigger questions_sync_legal_canonical_names
before insert or update of question, opt_a, opt_b, opt_c, opt_d, law
on public.questions
for each row execute function public.sync_question_legal_canonical_names();

update public.questions
set legal_canonical_names = public.extract_legal_canonical_names(
  concat_ws(' ', question, opt_a, opt_b, opt_c, opt_d, law)
);

-- 4) AI analysis quality gate: do not publish answer-meta/editorial commentary.
create or replace function public.reject_ai_answer_meta_commentary()
returns trigger
language plpgsql
set search_path to ''
as $function$
declare
  s text;
begin
  if new.analysis_status = 'ready' then
    s := concat_ws(' ', new.exp_why, new.exp_others, new.exp_trap, new.mnemonic, new.extension, new.law);
    if s ~* '(題庫答案|題庫正解|答案待查|答案有瑕疵|官方答案|本題官方|官方正確|官方全體給分|建議.{0,12}(查|複查).{0,12}答案|已核對答案|選項判定有爭議)' then
      raise exception 'AI analysis contains forbidden answer-meta commentary' using errcode = '23514';
    end if;
  end if;
  return new;
end;
$function$;

drop trigger if exists trg_reject_ai_answer_meta_commentary on public.questions;
create trigger trg_reject_ai_answer_meta_commentary
before insert or update of analysis_status, exp_why, exp_others, exp_trap, mnemonic, extension, law
on public.questions
for each row execute function public.reject_ai_answer_meta_commentary();

-- Legacy answer-meta rows are re-queued. All-give questions stay in review until the
-- analyzer explicitly models A-D as all scoreable without claiming all options are academically correct.
update public.questions
set exp_why = null,
    exp_others = null,
    exp_trap = null,
    exp_raw = null,
    mnemonic = null,
    extension = null,
    law = null,
    mistake = null,
    analysis_status = 'pending',
    analysis_attempts = 0,
    analysis_error = null,
    analysis_started_at = null,
    analysis_completed_at = null
where analysis_status = 'ready'
  and concat_ws(' ', exp_why, exp_others, exp_trap, mnemonic, extension, law)
      ~* '(題庫答案|題庫正解|答案待查|答案有瑕疵|官方答案|本題官方|官方正確|官方全體給分|建議.{0,12}(查|複查).{0,12}答案|已核對答案|選項判定有爭議)'
  and answer <> '一律給分';

update public.questions
set exp_why = null,
    exp_others = null,
    exp_trap = null,
    exp_raw = null,
    mnemonic = null,
    extension = null,
    law = null,
    mistake = null,
    analysis_status = 'review',
    analysis_attempts = 0,
    analysis_error = '一律給分題：等待 analyzer 明確支援 A-D 全部計分後再生成解析',
    analysis_started_at = null,
    analysis_completed_at = null
where answer = '一律給分';

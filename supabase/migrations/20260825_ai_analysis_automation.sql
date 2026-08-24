-- 社工師題庫：免費版 AI 自動分析架構備份
-- 不含任何 API key / service-role key / job key。
-- 目的：新考題進入 questions 後自動排隊；24h 最多完成 25 題；
-- 最後一題完成後自動停用 cron；下次新題/官方更正再自動啟用。

create extension if not exists pgcrypto;
create extension if not exists pg_cron;
create extension if not exists pg_net;

alter table public.questions add column if not exists analysis_attempts integer not null default 0;
alter table public.questions add column if not exists analysis_error text;
alter table public.questions add column if not exists analysis_started_at timestamptz;
alter table public.questions add column if not exists analysis_completed_at timestamptz;

create table if not exists public.ai_analysis_job_config (
  id boolean primary key default true check (id = true),
  job_key text not null,
  enabled boolean not null default true,
  updated_at timestamptz not null default now()
);
alter table public.ai_analysis_job_config enable row level security;

insert into public.ai_analysis_job_config(id,job_key,enabled)
values (true, encode(gen_random_bytes(32),'hex'), true)
on conflict (id) do nothing;

create or replace function public.set_analysis_completed_at()
returns trigger language plpgsql set search_path=public as $fn$
begin
  if new.analysis_status = 'ready' and old.analysis_status is distinct from 'ready' then
    new.analysis_completed_at := now();
  elsif new.analysis_status <> 'ready' then
    new.analysis_completed_at := null;
  end if;
  return new;
end;
$fn$;

drop trigger if exists trg_questions_analysis_completed_at on public.questions;
create trigger trg_questions_analysis_completed_at
before update of analysis_status on public.questions
for each row execute function public.set_analysis_completed_at();

create or replace function public.claim_pending_ai_questions(p_limit integer default 1)
returns setof public.questions
language plpgsql security definer set search_path=public as $fn$
declare completed_24h integer;
begin
  select count(*)::integer into completed_24h
  from public.questions
  where analysis_completed_at >= now() - interval '24 hours';

  -- 免費版硬上限：24 小時最多完成 25 題。
  if completed_24h >= 25 then return; end if;

  return query
  with picked as (
    select q.id
    from public.questions q
    where (
      q.analysis_status='pending'
      or (q.analysis_status='analyzing' and q.analysis_started_at < now()-interval '15 minutes')
    )
      and coalesce(q.analysis_attempts,0) < 3
    order by q.source_exam_code nulls last,
             q.subject,
             case when q.qno ~ '^\d+$' then q.qno::integer else 999999 end,
             q.id
    for update skip locked
    limit greatest(1,least(coalesce(p_limit,1),1))
  )
  update public.questions q
     set analysis_status='analyzing', analysis_started_at=now(), analysis_error=null
    from picked p
   where q.id=p.id
  returning q.*;
end;
$fn$;

create or replace function public.enable_swsi_ai_analysis()
returns void language plpgsql security definer set search_path=public as $fn$
declare j bigint;
begin
  update public.ai_analysis_job_config set enabled=true,updated_at=now() where id=true;
  select jobid into j from cron.job where jobname='swsi-ai-analysis' limit 1;
  if j is null then
    perform cron.schedule(
      'swsi-ai-analysis','*/30 * * * *',
      $cmd$select net.http_post(
        url := 'https://yumjtrdctaxyczpspuyo.supabase.co/functions/v1/analyze-pending-questions',
        headers := jsonb_build_object(
          'Content-Type','application/json',
          'x-job-key',(select job_key from public.ai_analysis_job_config where id=true)
        ),
        body := '{"limit":1}'::jsonb
      );$cmd$
    );
  else
    perform cron.alter_job(j,'*/30 * * * *',null,null,null,true);
  end if;
end;
$fn$;

create or replace function public.disable_swsi_ai_analysis()
returns void language plpgsql security definer set search_path=public as $fn$
declare j bigint;
begin
  update public.ai_analysis_job_config set enabled=false,updated_at=now() where id=true;
  select jobid into j from cron.job where jobname='swsi-ai-analysis' limit 1;
  if j is not null then perform cron.alter_job(j,null,null,null,null,false); end if;
end;
$fn$;

create or replace function public.maybe_stop_swsi_ai_analysis()
returns jsonb language plpgsql security definer set search_path=public as $fn$
declare remaining integer; review_count integer;
begin
  select count(*) into remaining from public.questions
  where analysis_status in ('pending','analyzing') and coalesce(analysis_attempts,0)<3;
  select count(*) into review_count from public.questions where analysis_status='review';
  if remaining=0 then
    perform public.disable_swsi_ai_analysis();
    return jsonb_build_object('stopped',true,'remaining',remaining,'review',review_count);
  end if;
  return jsonb_build_object('stopped',false,'remaining',remaining,'review',review_count);
end;
$fn$;

-- 考選部題幹/選項/答案有任何實質變更時，舊 AI 解析作廢並重新排隊。
create or replace function public.reset_ai_analysis_on_official_change()
returns trigger language plpgsql security definer set search_path=public as $fn$
begin
  if new.source_exam_code is not null and (
       new.question is distinct from old.question
    or new.opt_a is distinct from old.opt_a
    or new.opt_b is distinct from old.opt_b
    or new.opt_c is distinct from old.opt_c
    or new.opt_d is distinct from old.opt_d
    or new.answer is distinct from old.answer
  ) then
    new.major:=null; new.topic:=null; new.keywords:=null;
    new.exp_why:=null; new.exp_others:=null; new.exp_trap:=null; new.exp_raw:=null;
    new.mnemonic:=null; new.extension:=null; new.law:=null; new.mistake:=null;
    new.analysis_status:='pending'; new.analysis_attempts:=0; new.analysis_error:=null;
    new.analysis_started_at:=null; new.analysis_completed_at:=null;
  end if;
  return new;
end;
$fn$;

drop trigger if exists trg_reset_ai_on_official_change on public.questions;
create trigger trg_reset_ai_on_official_change
before update of question,opt_a,opt_b,opt_c,opt_d,answer on public.questions
for each row execute function public.reset_ai_analysis_on_official_change();

create or replace function public.auto_enable_ai_for_pending_question()
returns trigger language plpgsql security definer set search_path=public as $fn$
declare enabled_now boolean;
begin
  if new.source_exam_code is not null and new.analysis_status='pending' then
    select enabled into enabled_now from public.ai_analysis_job_config where id=true;
    if coalesce(enabled_now,false)=false then perform public.enable_swsi_ai_analysis(); end if;
  end if;
  return new;
end;
$fn$;

drop trigger if exists trg_auto_enable_ai_pending on public.questions;
create trigger trg_auto_enable_ai_pending
after insert or update of analysis_status on public.questions
for each row execute function public.auto_enable_ai_for_pending_question();

create or replace function public.auto_stop_ai_when_queue_drains()
returns trigger language plpgsql security definer set search_path=public as $fn$
declare enabled_now boolean;
begin
  if old.analysis_status is distinct from new.analysis_status
     and new.analysis_status in ('ready','review') then
    select enabled into enabled_now from public.ai_analysis_job_config where id=true;
    if coalesce(enabled_now,false)=true then perform public.maybe_stop_swsi_ai_analysis(); end if;
  end if;
  return new;
end;
$fn$;

drop trigger if exists trg_auto_stop_ai_queue on public.questions;
create trigger trg_auto_stop_ai_queue
after update of analysis_status on public.questions
for each row execute function public.auto_stop_ai_when_queue_drains();

-- 不讓前端匿名使用者直接控制背景工作。
revoke all on function public.enable_swsi_ai_analysis() from public,anon,authenticated;
revoke all on function public.disable_swsi_ai_analysis() from public,anon,authenticated;
revoke all on function public.maybe_stop_swsi_ai_analysis() from public,anon,authenticated;
grant execute on function public.enable_swsi_ai_analysis() to service_role;
grant execute on function public.disable_swsi_ai_analysis() to service_role;
grant execute on function public.maybe_stop_swsi_ai_analysis() to service_role;

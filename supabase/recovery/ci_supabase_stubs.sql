-- CI-only stubs used by the isolated disaster-recovery drill.
--
-- They provide the role/auth/cron surface that Supabase normally owns.
-- The cron implementation stores schedules only. It NEVER executes commands,
-- performs HTTP, or contacts production.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then
    create role service_role nologin bypassrls;
  end if;
end
$$;

grant usage on schema public to anon, authenticated, service_role;

create schema if not exists auth;
create table if not exists auth.users (
  id uuid primary key
);
grant usage on schema auth to service_role;

create schema if not exists cron;
create table if not exists cron.job (
  jobid bigint generated always as identity primary key,
  jobname text not null unique,
  schedule text,
  command text,
  database text,
  username text,
  active boolean not null default true
);

create or replace function cron.schedule(
  p_jobname text,
  p_schedule text,
  p_command text
) returns bigint
language plpgsql
as $$
declare
  v_jobid bigint;
begin
  insert into cron.job(jobname, schedule, command, active)
  values (p_jobname, p_schedule, p_command, true)
  on conflict (jobname) do update
    set schedule = excluded.schedule,
        command = excluded.command,
        active = true
  returning jobid into v_jobid;
  return v_jobid;
end;
$$;

create or replace function cron.alter_job(
  p_jobid bigint,
  p_schedule text default null,
  p_command text default null,
  p_database text default null,
  p_username text default null,
  p_active boolean default null
) returns void
language plpgsql
as $$
begin
  update cron.job
     set schedule = coalesce(p_schedule, schedule),
         command = coalesce(p_command, command),
         database = coalesce(p_database, database),
         username = coalesce(p_username, username),
         active = coalesce(p_active, active)
   where jobid = p_jobid;
end;
$$;

create or replace function cron.unschedule(p_jobname text)
returns boolean
language plpgsql
as $$
declare
  v_count integer;
begin
  delete from cron.job where jobname = p_jobname;
  get diagnostics v_count = row_count;
  return v_count > 0;
end;
$$;

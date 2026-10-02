-- Keep the AI analyzer scheduler conservative (one item every 30 minutes,
-- 25 successful completions per rolling 24h) while allowing the Qwen -> audit
-- request enough transport time to finish. No credentials are stored here.

create or replace function public.enable_swsi_ai_analysis()
returns void language plpgsql security definer set search_path=public as $fn$
declare j bigint;
declare cmd text := $cmd$select net.http_post(
  url := 'https://yumjtrdctaxyczpspuyo.supabase.co/functions/v1/analyze-pending-questions',
  headers := jsonb_build_object(
    'Content-Type','application/json',
    'x-job-key',(select job_key from public.ai_analysis_job_config where id=true)
  ),
  body := '{"limit":1}'::jsonb,
  timeout_milliseconds := 120000
);$cmd$;
begin
  update public.ai_analysis_job_config set enabled=true,updated_at=now() where id=true;
  select jobid into j from cron.job where jobname='swsi-ai-analysis' limit 1;
  if j is null then
    perform cron.schedule('swsi-ai-analysis','*/30 * * * *',cmd);
  else
    perform cron.alter_job(j,'*/30 * * * *',cmd,null,null,true);
  end if;
end;
$fn$;

-- Align the already-existing production cron job without changing its cadence.
do $do$
declare j bigint;
declare cmd text := $cmd$select net.http_post(
  url := 'https://yumjtrdctaxyczpspuyo.supabase.co/functions/v1/analyze-pending-questions',
  headers := jsonb_build_object(
    'Content-Type','application/json',
    'x-job-key',(select job_key from public.ai_analysis_job_config where id=true)
  ),
  body := '{"limit":1}'::jsonb,
  timeout_milliseconds := 120000
);$cmd$;
begin
  select jobid into j from cron.job where jobname='swsi-ai-analysis' limit 1;
  if j is not null then
    perform cron.alter_job(j,'*/30 * * * *',cmd,null,null,true);
  end if;
end;
$do$;

revoke all on function public.enable_swsi_ai_analysis() from public,anon,authenticated;
grant execute on function public.enable_swsi_ai_analysis() to service_role;

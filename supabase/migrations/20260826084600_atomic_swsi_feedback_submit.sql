create or replace function public.submit_swsi_feedback(
  p_category text,
  p_context_type text,
  p_context_id text,
  p_context_title text,
  p_source_kind text,
  p_subject text,
  p_exam_year integer,
  p_exam_round integer,
  p_question_no integer,
  p_message text,
  p_contact text,
  p_page_path text,
  p_site_origin text,
  p_app_version text,
  p_user_agent text,
  p_client_hash text,
  p_metadata jsonb
) returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_minute_count integer;
  v_day_count integer;
  v_report_no bigint;
begin
  if p_client_hash is null or length(p_client_hash) < 16 then
    raise exception using errcode = 'P0001', message = 'INVALID_CLIENT';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(p_client_hash, 0));

  select count(*) into v_minute_count
  from public.swsi_feedback_reports
  where client_hash = p_client_hash
    and created_at >= now() - interval '1 minute';

  if v_minute_count >= 3 then
    raise exception using errcode = 'P0001', message = 'RATE_MINUTE';
  end if;

  select count(*) into v_day_count
  from public.swsi_feedback_reports
  where client_hash = p_client_hash
    and created_at >= now() - interval '1 day';

  if v_day_count >= 30 then
    raise exception using errcode = 'P0001', message = 'RATE_DAY';
  end if;

  insert into public.swsi_feedback_reports(
    category, context_type, context_id, context_title, source_kind,
    subject, exam_year, exam_round, question_no, message, contact,
    page_path, site_origin, app_version, user_agent, client_hash, metadata
  ) values (
    p_category, p_context_type, p_context_id, p_context_title, p_source_kind,
    p_subject, p_exam_year, p_exam_round, p_question_no, p_message, p_contact,
    p_page_path, p_site_origin, p_app_version, p_user_agent, p_client_hash,
    coalesce(p_metadata, '{}'::jsonb)
  ) returning report_no into v_report_no;

  return v_report_no;
end;
$$;

revoke all on function public.submit_swsi_feedback(text,text,text,text,text,text,integer,integer,integer,text,text,text,text,text,text,text,jsonb) from public;
revoke all on function public.submit_swsi_feedback(text,text,text,text,text,text,integer,integer,integer,text,text,text,text,text,text,text,jsonb) from anon;
revoke all on function public.submit_swsi_feedback(text,text,text,text,text,text,integer,integer,integer,text,text,text,text,text,text,text,jsonb) from authenticated;
grant execute on function public.submit_swsi_feedback(text,text,text,text,text,text,integer,integer,integer,text,text,text,text,text,text,text,jsonb) to service_role;

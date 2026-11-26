-- Automatic legal-status labels for questions nobody has reviewed yet.
--
-- Every new MOEX exam arrives with legal_status = 'unreviewed'. Checking each
-- question by hand (4,784 so far) does not scale, so this labels what a fixed
-- rule can decide and leaves everything else for a person:
--
--   not_applicable    question, options and the AI law field cite no law, no
--                     article and no legal wording; for 社會政策與社會立法 also no
--                     social-insurance / benefit / tax wording (13 such policy
--                     questions turned out to rest on a law).
--   verified_current  every cited law is a watched law (legal_reference_registry)
--                     whose MOJ last-amended date is at least one year before the
--                     exam, checked after the exam, and no other law-like name
--                     appears. Same rule and note format as the 129 "自動規則"
--                     rows of legal batch 1.
--   (left alone)      anything else, non-standard official grading, or a
--                     question whose explanation is not ready yet.
--
-- Replayed on the 4,784 reviewed questions (2026-11-27): this function labels
-- 3,756 of them not_applicable (restored copy of the bank,
-- legal_auto_label_replay) and a read-only query of the same rule against the
-- production registry labels 93 verified_current; every prediction matches the
-- reviewed label and no question reviewed as changed is predicted. On the last
-- six exams the rule decides about 85% of each exam; the rest (25-40 questions
-- per exam) stays unreviewed for a person.
--
-- Only legal_status, legal_checked_at, legal_note and legal_source_url change,
-- and only on rows that are still unreviewed. Question text, options, answers
-- and explanations are never touched. Every applied label is logged.
--
-- Input text is NFKC-normalised here so legacy CJK compatibility glyphs in old
-- MOEX text cannot hide a law name (the production extractor does not
-- normalise). Checked by scripts/legal_auto_label_pg_selftest.py.

create table if not exists public.moex_exam_dates (
  source_exam_code text primary key,
  exam_date date not null,
  source_url text
);
alter table public.moex_exam_dates enable row level security;
revoke all on table public.moex_exam_dates from public, anon, authenticated;

-- Pinned official start dates, data/moex_social_worker_exam_dates.v1.json.
insert into public.moex_exam_dates (source_exam_code, exam_date, source_url) values
  ('104030', '2015-02-07', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=104030'),
  ('104100', '2015-07-25', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=104100'),
  ('105030', '2016-01-30', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=105030'),
  ('105090', '2016-07-23', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=105090'),
  ('106030', '2017-02-18', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=106030'),
  ('106110', '2017-07-29', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=106110'),
  ('107030', '2018-02-03', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=107030'),
  ('107110', '2018-07-28', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=107110'),
  ('108020', '2019-01-19', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=108020'),
  ('108110', '2019-07-27', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=108110'),
  ('109030', '2020-02-15', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=109030'),
  ('109110', '2020-08-01', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=109110'),
  ('110030', '2021-02-06', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=110030'),
  ('110111', '2021-08-21', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=110111'),
  ('111030', '2022-02-19', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=111030'),
  ('111110', '2022-07-30', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=111110'),
  ('112030', '2023-02-18', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=112030'),
  ('112110', '2023-07-29', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=112110'),
  ('113030', '2024-02-04', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=113030'),
  ('113100', '2024-07-27', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=113100'),
  ('114030', '2025-02-08', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=114030'),
  ('114100', '2025-07-26', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=114100'),
  ('115030', '2026-02-07', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=115030'),
  ('115100', '2026-07-25', 'https://wwwc.moex.gov.tw/main/Exam/wFrmExamDetail.aspx?c=115100')
on conflict (source_exam_code) do nothing;

create table if not exists public.legal_auto_label_log (
  id bigint generated always as identity primary key,
  question_id text not null,
  decided_at timestamptz not null default now(),
  legal_status text not null,
  reason text not null,
  legal_note text,
  legal_source_url text
);
alter table public.legal_auto_label_log enable row level security;
revoke all on table public.legal_auto_label_log from public, anon, authenticated;

create or replace function public.legal_auto_label_decide(q public.questions)
returns jsonb
language plpgsql
stable
security definer
set search_path to ''
as $function$
declare
  qtext text := normalize(concat_ws(' ', q.question, q.opt_a, q.opt_b, q.opt_c, q.opt_d), NFKC);
  law_text text := normalize(coalesce(q.law, ''), NFKC);
  names text[];
  residual text;
  exam date;
  estimated boolean := false;
  parts text[] := '{}'::text[];
  newest date;
  newest_url text;
  checked date;
  r record;
begin
  if q.source_exam_code is null then
    return jsonb_build_object('decision', 'exception', 'reason', 'no official exam source');
  end if;
  if coalesce(q.grading_mode, 'standard') <> 'standard' then
    return jsonb_build_object('decision', 'exception', 'reason', 'non-standard official grading');
  end if;

  names := array(
    select d.x from (
      select distinct x
        from unnest(coalesce(q.legal_canonical_names, '{}'::text[])
                    || public.extract_legal_canonical_names(qtext)
                    || public.extract_legal_canonical_names(law_text)) as x) d
     order by d.x collate "C");

  if btrim(law_text) = '' and cardinality(names) = 0
     and qtext !~ '第\s*[0-9一二三四五六七八九十百]+\s*條'
     and qtext !~ '(依法|依據.{0,12}(法|條例|辦法|規定)|法律|法規|條例|施行細則|辦法|準則|公約|主管機關|罰鍰|罰金|立法|修法|法定|條文|規定)'
     and (q.subject is distinct from '社會政策與社會立法'
          or qtext !~ '(保險|給付|津貼|扣除|救助|年金|退休|補助|民營化|身心障礙|長期照顧|長照|托育|育兒|育嬰|健保|勞保|國保|就保|稅|ICF|低收入|中低收入|特殊境遇|社福|福利服務|主管|政府)') then
    return jsonb_build_object('decision', 'not_applicable',
      'reason', 'no law, article or legal wording in question, options or AI law field');
  end if;

  if cardinality(names) = 0 then
    return jsonb_build_object('decision', 'exception', 'reason', 'law or benefit wording but no recognised law');
  end if;

  residual := law_text || ' ' || qtext;
  for r in select g.canonical_name from public.legal_reference_registry g
            order by length(g.canonical_name) desc loop
    residual := replace(residual, r.canonical_name, '');
  end loop;
  if residual ~ '(法|條例|辦法|準則|規則|公約|綱要|細則|規程|要點)' then
    return jsonb_build_object('decision', 'exception',
      'reason', 'mentions a law-like name outside the watched laws');
  end if;

  select d.exam_date into exam from public.moex_exam_dates d where d.source_exam_code = q.source_exam_code;
  if exam is null then
    if coalesce(q.year, '') !~ '^[0-9]{2,3}$' or q.round is null or q.round not in ('第一次', '第二次') then
      return jsonb_build_object('decision', 'exception', 'reason', 'exam date unknown');
    end if;
    -- Earliest possible date of that sitting: a conservative stand-in.
    exam := make_date(q.year::integer + 1911, case when q.round = '第一次' then 1 else 6 end, 1);
    estimated := true;
  end if;

  for r in select n.name, g.official_modified_date, g.official_url, g.last_checked_at
             from unnest(names) as n(name)
             left join public.legal_reference_registry g on g.canonical_name = n.name
            order by n.name collate "C" loop
    if r.official_modified_date is null or r.official_modified_date !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then
      return jsonb_build_object('decision', 'exception', 'reason', 'no MOJ amendment date for ' || r.name);
    end if;
    if r.last_checked_at is null or r.last_checked_at::date < exam then
      return jsonb_build_object('decision', 'exception', 'reason', 'MOJ check older than the exam for ' || r.name);
    end if;
    if r.official_modified_date::date > (exam - interval '1 year')::date then
      return jsonb_build_object('decision', 'exception',
        'reason', r.name || ' amended within a year before the exam or later');
    end if;
    parts := parts || (r.name || '最後修正公布日 ' || r.official_modified_date);
    if newest is null or r.official_modified_date::date > newest then
      newest := r.official_modified_date::date;
      newest_url := r.official_url;
    end if;
    checked := least(coalesce(checked, r.last_checked_at::date), r.last_checked_at::date);
  end loop;

  return jsonb_build_object(
    'decision', 'verified_current',
    'reason', 'every cited law last amended at least a year before the exam',
    'exam_date', exam,
    'exam_date_estimated', estimated,
    'source_url', newest_url,
    'note', '考試時點法規核對（自動規則）：' || array_to_string(parts, '、') || '，'
            || case when cardinality(parts) > 1 then '均' else '' end
            || case when estimated
                    then '早於本題考試（' || q.year || ' 年' || q.round || '，不早於 ' || exam::text || '）一年以上'
                    else '早於本題考試日 ' || exam::text || ' 一年以上' end
            || '，考試時適用條文與現行條文相同。依據：法務部全國法規資料庫（' || checked::text || ' 查核）。');
end;
$function$;

create or replace function public.legal_auto_label_apply(p_dry_run boolean default true, p_limit integer default 500)
returns jsonb
language plpgsql
volatile
security definer
set search_path to ''
as $function$
declare
  q public.questions;
  d jsonb;
  done integer;
  checked integer := 0;
  na text[] := '{}'::text[];
  vc text[] := '{}'::text[];
  ex jsonb := '[]'::jsonb;
begin
  for q in select * from public.questions
            where legal_status = 'unreviewed' and analysis_status = 'ready'
            order by id collate "C"
            limit greatest(1, least(coalesce(p_limit, 500), 1000)) loop
    checked := checked + 1;
    d := public.legal_auto_label_decide(q);
    if d->>'decision' = 'not_applicable' then
      if not p_dry_run then
        update public.questions set legal_status = 'not_applicable'
         where id = q.id and legal_status = 'unreviewed';
        get diagnostics done = row_count;
        if done = 1 then
          insert into public.legal_auto_label_log (question_id, legal_status, reason)
          values (q.id, 'not_applicable', d->>'reason');
        end if;
      end if;
      na := na || q.id;
    elsif d->>'decision' = 'verified_current' then
      if not p_dry_run then
        update public.questions
           set legal_status = 'verified_current', legal_checked_at = now(),
               legal_note = d->>'note', legal_source_url = d->>'source_url'
         where id = q.id and legal_status = 'unreviewed';
        get diagnostics done = row_count;
        if done = 1 then
          insert into public.legal_auto_label_log (question_id, legal_status, reason, legal_note, legal_source_url)
          values (q.id, 'verified_current', d->>'reason', d->>'note', d->>'source_url');
        end if;
      end if;
      vc := vc || q.id;
    else
      ex := ex || jsonb_build_object('id', q.id, 'reason', d->>'reason');
    end if;
  end loop;
  return jsonb_build_object('dry_run', p_dry_run, 'checked', checked,
    'not_applicable', to_jsonb(na), 'verified_current', to_jsonb(vc), 'left_for_review', ex);
end;
$function$;

-- Read-only regression check: how the rule would label every reviewed question.
create or replace function public.legal_auto_label_replay()
returns jsonb
language sql
stable
security definer
set search_path to ''
as $function$
  with d as (
    select q.id, q.legal_status as reviewed, public.legal_auto_label_decide(q)->>'decision' as predicted
      from public.questions q
     where q.legal_status in ('not_applicable', 'verified_current', 'changed')
  )
  select jsonb_build_object(
    'reviewed', count(*),
    'predicted_not_applicable', count(*) filter (where predicted = 'not_applicable'),
    'predicted_verified_current', count(*) filter (where predicted = 'verified_current'),
    'disagreements', count(*) filter (where predicted in ('not_applicable', 'verified_current') and predicted <> reviewed),
    'disagreement_ids', coalesce(jsonb_agg(id order by id collate "C")
      filter (where predicted in ('not_applicable', 'verified_current') and predicted <> reviewed), '[]'::jsonb))
  from d;
$function$;

revoke all on function public.legal_auto_label_decide(public.questions) from public, anon, authenticated;
revoke all on function public.legal_auto_label_apply(boolean, integer) from public, anon, authenticated;
revoke all on function public.legal_auto_label_replay() from public, anon, authenticated;
grant execute on function public.legal_auto_label_decide(public.questions) to service_role;
grant execute on function public.legal_auto_label_apply(boolean, integer) to service_role;
grant execute on function public.legal_auto_label_replay() to service_role;

-- Daily at 03:23 UTC, after the Monday 02:35 UTC law watch refreshes the
-- registry. Skipped where pg_cron is absent (local rehearsal, CI).
do $$
begin
  if exists (select 1 from pg_extension where extname = 'pg_cron') then
    perform cron.unschedule(j.jobid) from cron.job j where j.jobname = 'swsi-legal-auto-label';
    perform cron.schedule('swsi-legal-auto-label', '23 3 * * *',
                          'select public.legal_auto_label_apply(false, 500);');
  end if;
end $$;

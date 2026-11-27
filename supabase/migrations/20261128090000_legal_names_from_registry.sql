-- 以題庫推法: laws added to the watch from the question bank are also tagged on
-- questions.
--
-- The weekly MOEX sync derives the watched laws from the question bank
-- (scripts/legal_watch_names_from_bank.py) and sync-legal-watch upserts one
-- public.legal_reference_registry row per watched law. The canonical-name
-- extractor carried its own hard-coded copy of the first 52 names, so a newly
-- watched law was never put into questions.legal_canonical_names: the law
-- watch could not flag those questions when the law changes, and the daily
-- automatic label could not decide them.
--
-- The extractor now also reads registry names outside that baseline. For the
-- 52 baseline names nothing changes: same list, same order, same three alias
-- rules, same plain matching as the production function (production never
-- applied 20261003184700, so there is no NFKC step here either; the daily
-- automatic label normalises its own input). When a registry row is inserted,
-- the questions whose text contains the new name get their
-- legal_canonical_names recomputed; no other column is touched.

create or replace function public.extract_legal_canonical_names(raw_law text)
returns text[]
language plpgsql
stable
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

  -- Laws the weekly sync added to the watch from the question bank.
  for n in select g.canonical_name from public.legal_reference_registry g
            where btrim(coalesce(g.canonical_name, '')) <> ''
              and not (g.canonical_name = any(names))
            order by g.canonical_name collate "C" loop
    if position(n in s) > 0 and not (n = any(out_names)) then
      out_names := array_append(out_names, n);
    end if;
  end loop;

  return out_names;
end;
$function$;

comment on function public.extract_legal_canonical_names(text) is
  'Canonical legal-name extractor: the 52 baseline names and three alias rules, plus every name in public.legal_reference_registry (laws the weekly sync derives from the question bank). Plain matching, as in production.';

create or replace function public.refresh_legal_canonical_names_for_new_law()
returns trigger
language plpgsql
security definer
set search_path to ''
as $function$
begin
  update public.questions q
     set legal_canonical_names = public.extract_legal_canonical_names(
           concat_ws(' ', q.question, q.opt_a, q.opt_b, q.opt_c, q.opt_d, q.law))
   where position(new.canonical_name in concat_ws(' ', q.question, q.opt_a, q.opt_b, q.opt_c, q.opt_d, q.law)) > 0
     and not (coalesce(q.legal_canonical_names, '{}'::text[]) @> array[new.canonical_name]);
  return null;
end;
$function$;

revoke all on function public.refresh_legal_canonical_names_for_new_law() from public, anon, authenticated;

comment on function public.refresh_legal_canonical_names_for_new_law() is
  'After a new watched law is registered, recompute legal_canonical_names (and nothing else) for questions whose text names it.';

drop trigger if exists trg_legal_registry_new_law on public.legal_reference_registry;
create trigger trg_legal_registry_new_law
after insert on public.legal_reference_registry
for each row execute function public.refresh_legal_canonical_names_for_new_law();

-- Fail closed in migration replay if the baseline output changed.
do $$
begin
  if public.extract_legal_canonical_names('依社會救助法及民法規定')
       <> array['社會救助法', '民法']::text[] then
    raise exception 'legal canonical baseline regression';
  end if;
  if public.extract_legal_canonical_names('依性別工作平等法') <> array['性別平等工作法']::text[] then
    raise exception 'legal canonical alias regression';
  end if;
end $$;

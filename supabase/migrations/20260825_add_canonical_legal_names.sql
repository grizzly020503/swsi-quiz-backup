alter table public.questions
  add column if not exists legal_canonical_names text[] not null default '{}'::text[];

create or replace function public.extract_legal_canonical_names(raw_law text)
returns text[]
language plpgsql
immutable
set search_path = public
as $$
declare
  s text := coalesce(raw_law, '');
  out_names text[] := '{}'::text[];
  n text;
  names text[] := array[
    '兒童及少年福利與權益保障法','身心障礙者權益保障法','老人福利法','家庭暴力防治法','社會救助法','長期照顧服務法','社會工作師法','兒童及少年性剝削防制條例','特殊境遇家庭扶助條例','性侵害犯罪防治法','性別平等工作法','國民年金法','志願服務法','公益勸募條例','精神衛生法','兒童及少年未來教育與發展帳戶條例','病人自主權利法','就業保險法','少年事件處理法','消除對婦女一切形式歧視公約施行法','兒童權利公約施行法','兒童權利公約','身心障礙者權利公約施行法','身心障礙者權利公約','全民健康保險法','原住民族工作權保障法','中華民國刑法','中華民國憲法增修條文','人口販運防制法','住宅法','公益彩券發行條例','勞工保險條例','協助積極自立脫離貧窮實施辦法','國民教育法','學生輔導法','家事事件法','專科社會工作師分科甄審及接受繼續教育辦法','性別平等教育法','性騷擾防治法','跟蹤騷擾防制法','毒品危害防制條例','民法','社會工作師執業登記及繼續教育辦法','社會福利基本法','老年農民福利津貼暫行條例','長期照顧服務機構法人條例','經濟社會文化權利國際公約','全民健康保險醫療服務給付項目及支付標準','國民小學與國民中學未入學或中途輟學學生通報及復學輔導辦法','校園霸凌防制準則','社區發展工作綱要'
  ];
begin
  -- 舊名稱只做索引別名，不改原始 law 文字。
  if position('性別工作平等法' in s) > 0 and position('性別平等工作法' in s) = 0 then
    out_names := array_append(out_names, '性別平等工作法');
  end if;

  if position('兩公約施行法' in s) > 0 or position('人權公約施行法' in s) > 0 then
    out_names := array_append(out_names, '公民與政治權利國際公約及經濟社會文化權利國際公約施行法');
  end if;

  foreach n in array names loop
    if position(n in s) > 0 and not (n = any(out_names)) then
      out_names := array_append(out_names, n);
    end if;
  end loop;

  return out_names;
end;
$$;

update public.questions
set legal_canonical_names = public.extract_legal_canonical_names(law);

create or replace function public.sync_question_legal_canonical_names()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.legal_canonical_names := public.extract_legal_canonical_names(new.law);
  return new;
end;
$$;

drop trigger if exists questions_sync_legal_canonical_names on public.questions;
create trigger questions_sync_legal_canonical_names
before insert or update of law on public.questions
for each row
execute function public.sync_question_legal_canonical_names();

create index if not exists questions_legal_canonical_names_gin
  on public.questions using gin (legal_canonical_names);

-- Normalize only the legal-name matching input, never the immutable MOEX question text.
--
-- Older official exam PDFs contain CJK compatibility ideographs such as:
--   少年 -> 少年, 心理 -> 心理, 婦女 -> 婦女
-- Exact codepoint matching therefore misses otherwise explicit law names.
-- NFKC is applied inside the canonicalizer only; Official Core remains byte-for-byte untouched.
-- This migration deliberately does not backfill question rows or promote legal trust states.

create or replace function public.extract_legal_canonical_names(raw_law text)
returns text[]
language plpgsql
immutable
set search_path to ''
as $function$
declare
  s text := normalize(coalesce(raw_law, ''), NFKC);
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

comment on function public.extract_legal_canonical_names(text) is
  'Canonical legal-name extractor. NFKC-normalizes matching input so legacy MOEX CJK compatibility glyphs do not suppress explicit law-name matches; source question text is never mutated.';

-- Fail closed in migration replay if compatibility matching does not work.
do $$
begin
  if public.extract_legal_canonical_names('兒童及少年福利與權益保障法')
       <> array['兒童及少年福利與權益保障法']::text[] then
    raise exception 'NFKC legal canonical regression: 少年 was not normalized';
  end if;

  if public.extract_legal_canonical_names('國民年金法')
       <> array['國民年金法']::text[] then
    raise exception 'NFKC legal canonical regression: 年 was not normalized';
  end if;

  if not ('公民與政治權利國際公約及經濟社會文化權利國際公約施行法'
          = any(public.extract_legal_canonical_names('兩公約施行法'))) then
    raise exception 'legal canonical alias regression: 兩公約施行法';
  end if;
end $$;

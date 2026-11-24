-- SWSI 2026-11-24：考選部同步只改空白時，保留解析。
-- 只替換 public.reset_ai_analysis_on_official_change() 這個函式；不改任何題目、不改權限。
BEGIN;
create or replace function public.reset_ai_analysis_on_official_change()
returns trigger
language plpgsql
security definer
set search_path to ''
as $function$
begin
  if new.source_exam_code is not null and (
       regexp_replace(coalesce(new.question, ''), '[[:space:]  -​　﻿]+', '', 'g')
         is distinct from regexp_replace(coalesce(old.question, ''), '[[:space:]  -​　﻿]+', '', 'g')
    or regexp_replace(coalesce(new.opt_a, ''), '[[:space:]  -​　﻿]+', '', 'g')
         is distinct from regexp_replace(coalesce(old.opt_a, ''), '[[:space:]  -​　﻿]+', '', 'g')
    or regexp_replace(coalesce(new.opt_b, ''), '[[:space:]  -​　﻿]+', '', 'g')
         is distinct from regexp_replace(coalesce(old.opt_b, ''), '[[:space:]  -​　﻿]+', '', 'g')
    or regexp_replace(coalesce(new.opt_c, ''), '[[:space:]  -​　﻿]+', '', 'g')
         is distinct from regexp_replace(coalesce(old.opt_c, ''), '[[:space:]  -​　﻿]+', '', 'g')
    or regexp_replace(coalesce(new.opt_d, ''), '[[:space:]  -​　﻿]+', '', 'g')
         is distinct from regexp_replace(coalesce(old.opt_d, ''), '[[:space:]  -​　﻿]+', '', 'g')
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
SELECT
  position('regexp_replace' in pg_get_functiondef('public.reset_ai_analysis_on_official_change()'::regprocedure)) > 0 AS 已套用新規則,
  has_function_privilege('anon', 'public.reset_ai_analysis_on_official_change()', 'EXECUTE') AS 學生可執行_應為false,
  (SELECT count(*) FROM pg_trigger WHERE tgrelid = 'public.questions'::regclass AND tgname = 'trg_reset_ai_on_official_change') AS 觸發器數量_應為1;
COMMIT;

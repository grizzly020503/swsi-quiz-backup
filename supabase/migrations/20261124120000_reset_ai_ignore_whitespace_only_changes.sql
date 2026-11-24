-- Keep SWSI AI explanations when an official-text update only changes whitespace.
--
-- 2026-11-23: the MOEX sync normalised one space in HBSE-115-2-026 option D
-- ("therapy ）" -> "therapy）"). The reset trigger compared raw text, so the
-- whole explanation was cleared and the row fell back to pending with no alert.
--
-- Official wording is now compared after removing all whitespace (ASCII and
-- Unicode spaces, NBSP, ideographic space, BOM, line breaks). Any visible
-- character change still resets the explanation. answer, accepted_answers and
-- grading_mode are still compared exactly. The trigger itself is unchanged.

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

-- Re-assert the existing privilege model (unchanged by create or replace).
revoke all on function public.reset_ai_analysis_on_official_change() from public, anon, authenticated;

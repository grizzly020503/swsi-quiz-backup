alter table public.questions
  add column if not exists legal_status text not null default 'unreviewed',
  add column if not exists legal_checked_at timestamptz,
  add column if not exists legal_note text,
  add column if not exists legal_source_url text;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'questions_legal_status_check'
  ) then
    alter table public.questions
      add constraint questions_legal_status_check
      check (legal_status in ('not_applicable','unreviewed','verified_current','changed'));
  end if;
end $$;

update public.questions
set legal_status = case
  when subject = '社會政策與社會立法' or coalesce(law,'') <> '' then 'unreviewed'
  else 'not_applicable'
end
where legal_status in ('unreviewed','not_applicable')
  and legal_checked_at is null;

create index if not exists questions_legal_status_idx on public.questions(legal_status);

-- Public client hardening: students are read-only; writes stay server-side.

begin;

alter table public.questions enable row level security;
alter table public.essays enable row level security;

revoke all on table public.questions from anon, authenticated;
revoke all on table public.essays from anon, authenticated;
grant select on table public.questions to anon, authenticated;
grant select on table public.essays to anon, authenticated;

drop policy if exists "anyone can read" on public.questions;
drop policy if exists "public read" on public.questions;
drop policy if exists "authed write" on public.questions;
drop policy if exists "only admin can write" on public.questions;
create policy "public read questions"
on public.questions for select
to anon, authenticated
using (true);

drop policy if exists "public read essays" on public.essays;
drop policy if exists "authed write essays" on public.essays;
create policy "public read essays"
on public.essays for select
to anon, authenticated
using (true);

-- Internal automation tables are server-only.
revoke all on table public.ai_analysis_job_config from anon, authenticated;
revoke all on table public.current_affairs from anon, authenticated;
revoke all on table public.current_affairs_sync_runs from anon, authenticated;
revoke all on table public.legal_reference_registry from anon, authenticated;
revoke all on table public.legal_watch_hits from anon, authenticated;
revoke all on table public.moex_sync_runs from anon, authenticated;

-- Internal trigger/helper functions must not be callable through the public API.
revoke execute on function public.auto_enable_ai_for_pending_question() from public, anon, authenticated;
revoke execute on function public.auto_stop_ai_when_queue_drains() from public, anon, authenticated;
revoke execute on function public.reset_ai_analysis_on_official_change() from public, anon, authenticated;
revoke execute on function public.set_analysis_completed_at() from public, anon, authenticated;
revoke execute on function public.sync_question_legal_canonical_names() from public, anon, authenticated;

grant execute on function public.auto_enable_ai_for_pending_question() to service_role;
grant execute on function public.auto_stop_ai_when_queue_drains() to service_role;
grant execute on function public.reset_ai_analysis_on_official_change() to service_role;
grant execute on function public.set_analysis_completed_at() to service_role;
grant execute on function public.sync_question_legal_canonical_names() to service_role;

alter function public.auto_enable_ai_for_pending_question() set search_path = '';
alter function public.auto_stop_ai_when_queue_drains() set search_path = '';
alter function public.reset_ai_analysis_on_official_change() set search_path = '';
alter function public.set_analysis_completed_at() set search_path = '';

commit;

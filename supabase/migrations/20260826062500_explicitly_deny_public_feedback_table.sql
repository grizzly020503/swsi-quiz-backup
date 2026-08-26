create policy swsi_feedback_reports_deny_public
on public.swsi_feedback_reports
for all
to anon, authenticated
using (false)
with check (false);

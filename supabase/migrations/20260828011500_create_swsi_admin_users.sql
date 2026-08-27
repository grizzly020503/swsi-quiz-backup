create table if not exists public.swsi_admin_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

alter table public.swsi_admin_users enable row level security;

revoke all on table public.swsi_admin_users from anon, authenticated;

-- Bootstrap only when the project currently has exactly one Auth user.
-- No generated user ID or email is stored in GitHub.
insert into public.swsi_admin_users (user_id)
select id from auth.users
where (select count(*) from auth.users) = 1
on conflict (user_id) do nothing;

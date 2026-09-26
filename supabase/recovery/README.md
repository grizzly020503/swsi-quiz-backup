# SWSI isolated disaster-recovery source

This directory is **recovery-only**. Nothing here is automatically applied to production.

## Why it exists

The live Supabase migration history begins before the migrations that were originally checked into this repository. In particular, later migrations assume `public.questions` already exists, and the first MOEX tables were created by an older production migration.

The recovery bundle restores that missing bootstrap without putting retroactive SQL into `supabase/migrations/`, where it could be mistaken for a new production migration.

## Isolation contract

The GitHub Actions restore drill:

1. starts a brand-new PostgreSQL 17 service,
2. creates only test roles plus a minimal `auth.users` stub,
3. uses a no-op `cron` shim that stores schedule metadata but **never executes commands or HTTP**,
4. removes only the two `pg_cron` / `pg_net` extension statements from the repo-owned AI automation migration before replaying it,
5. applies the remaining repo-owned migrations,
6. inserts synthetic contract fixtures only,
7. verifies RLS / ACL / SECURITY DEFINER / grading reset / feedback / usage / telemetry behavior,
8. separately verifies D1 recovery, Edge Function source inventory, 4,800-question / 24-shard artifacts, static frontend and local browser/PWA behavior.

No production database row, feedback report, analytics row, auth user, API key, token, or password is copied into the drill.

## Deliberately excluded from automatic restore

These are cutover-time settings, not safe CI actions:

- production DNS / Cloudflare route switching,
- production D1 binding changes,
- Netlify production switching,
- Supabase Auth users,
- production `pg_cron` schedules that call hosted URLs,
- production secret values,
- user-generated feedback/analytics data.

Required external configuration is recorded by **name only** from Edge Function source during the drill. Secret values must come from the target platform's secret manager.

## Data recovery boundary

- Official question artifacts: the checked-in manifest must prove exactly **4,800 questions / 24 shards** with matching SHA-256.
- The older CSV rescue master remains a historical 4,600-question rescue file and is **not** treated as the current database backup.
- Student feedback, anonymous usage and telemetry are not copied into CI. The drill validates their schemas/RPCs using synthetic records only.
- A real incident requiring hosted-row restoration still needs a separately retained provider backup/export according to the provider's retention policy.

## Production cutover rule

A successful drill proves rebuildability; it does **not** authorize a production switch. Any binding, DNS, project, or secret cutover remains a separate human-approved action.

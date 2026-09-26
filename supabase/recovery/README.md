# SWSI Disaster Recovery source

This directory contains **schema-only recovery material**. It is not a database
backup and must never contain production auth identities, student/user data,
feedback rows, analytics rows, secrets, tokens or credentials.

## Why this exists

The repo-owned Supabase migrations did not contain the original creation of
`public.questions`, `public.essays`, `public.moex_sync_runs`, or the early
`questions.analysis_status` field. That meant the previous migration set could
not start from an empty PostgreSQL database.

`base_schema.sql` fills only that missing structural baseline. The remaining
schema is reconstructed by the ordered repo migrations in
`recovery_manifest.json`.

## CI drill

`scripts/supabase_recovery_dry_run.py` runs against a disposable PostgreSQL
service. It:

1. creates test-only Supabase roles and an empty `auth.users` stub;
2. applies the base schema and ordered recovery migrations;
3. skips only `pg_cron` / `pg_net` extension installation in portable CI;
4. verifies table/column/RLS/privilege contracts;
5. restores the public official question shards into the clean DB;
6. verifies 4,800 questions, 24 accepted-answer questions and the pinned grading
   distribution;
7. verifies the official-change reset trigger with a synthetic row.

The workflow also runs the existing clean D1 recovery smoke, verifies the exact
10-function recovery inventory, Deno-checks every Edge Function, exercises
synthetic feedback/usage/AI-telemetry RPCs, rebuilds the static site, runs
local-only student browser/PWA smokes, and runs the fully mocked admin
auth/recovery browser smoke. A restore-evidence artifact records the source SHA,
measured full-drill RTO and repo-source RPO.

## What this does not restore

Private mutable production data is intentionally not stored in Git:

- Supabase Auth identities / sessions
- user feedback rows
- anonymous usage aggregates
- AI telemetry aggregates
- any future private admin-only data

Those mutable rows are deliberately excluded because the DR issue forbids copying
real student/user data into the test environment. The automated drill measures
repo-source RPO (exact checked-out commit) and full-platform rebuild RTO. A real
incident that requires restoration of mutable hosted rows still depends on the
provider backup/export retention policy and remains a separate operational
backup concern, not permission to copy production data into CI.

## Production safety

The CI drill has no production database URL and no deployment credentials. Never
point the dry-run script at production.

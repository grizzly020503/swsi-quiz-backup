# Long-term Ops Phase A-2 — Persistence candidate

Issue: #269  
Parent: #262

## Decision in this checkpoint

The first checkpoint defined backend-neutral task semantics. This checkpoint defines a **candidate** Supabase persistence shape without applying production DDL.

The candidate intentionally uses two tightly locked `public` tables plus service-role-only Data API access instead of inventing a new queue product or requiring a new exposed schema:

- `public.swsi_ops_task_runs`
- `public.swsi_ops_review_items`

Both tables enable RLS, revoke access from `PUBLIC`, `anon`, and `authenticated`, and explicitly grant only the minimum `select/insert/update` privileges to `service_role`. There is no delete grant because unresolved/terminal history is part of the audit trail.

The write RPCs use `SECURITY INVOKER`, not `SECURITY DEFINER`, and execution is revoked from `PUBLIC`, `anon`, and `authenticated` and granted only to `service_role`.

## Why explicit grants are now mandatory design

Supabase announced in 2026 that public-schema tables are moving to explicit Data API grants, with enforcement for existing projects scheduled for 2026-10-30. Therefore this candidate never relies on historical default privileges. Grants and RLS are treated as one migration unit.

## Atomic ownership

`swsi_ops_claim_task` performs:

1. insert-if-absent on `(task_id, idempotency_key)`;
2. `SELECT ... FOR UPDATE` on the logical run;
3. live-lease / retry-window / terminal checks;
4. bounded reclaim when allowed.

This makes the database transaction the single arbiter of ownership instead of trusting two workers to coordinate in application memory.

`swsi_ops_checkpoint_task` rejects:

- unknown checkpoint versions;
- expired/not-owned leases;
- decreasing `processed_count`.

`swsi_ops_complete_task` preserves `last_success_at` across failures and updates it only for `success` / `no_change`.

## Why this is still a candidate, not a migration

Per the repository and Supabase workflow rules, production DDL is not being improvised from chat. The SQL is stored under `supabase/candidates/` until it has passed review and an isolated PostgreSQL/Supabase test. A real migration file should then be generated through the project migration workflow/CLI and reviewed before any production apply.

No Supabase project branch was created because that can incur cost and requires explicit cost confirmation. No production DDL was executed.

## Adapter boundary

`scripts/ops_task_ledger_supabase.py` maps the backend-neutral contract to the four service-role RPCs. This checkpoint intentionally exposes only `--self-test`; there is no live-write CLI yet. That prevents accidental production mutation before the schema/RLS path is approved.

## Verification

Run locally:

```bash
python scripts/ops_task_ledger_supabase.py --self-test
python scripts/ops_task_ledger_sql_smoke.py supabase/candidates/ops_task_ledger_v1.sql
python -m py_compile scripts/ops_task_ledger_supabase.py scripts/ops_task_ledger_sql_smoke.py
```

The static SQL smoke fails if the candidate loses RLS/revokes/service-role-only grants, adds `SECURITY DEFINER`, adds delete/all grants, removes row locking, or stops enforcing monotonic checkpoints.

## Third checkpoint completed

`supabase/candidates/ops_task_ledger_v1_test.sql` now defines transaction-scoped deterministic behavior tests for:

- first claim and live-lease duplicate blocking;
- retry-not-due and later reclaim;
- lease-expiry reclaim;
- retry attempt exhaustion;
- checkpoint preservation and monotonic processed counts;
- unknown checkpoint version fail-closed;
- terminal idempotency;
- `no_change` updating trusted `last_success_at`;
- review-item history resolving without deletion.

The test script intentionally ends with `ROLLBACK`; it is designed for an isolated database and has not been run against production.

`ops_task_watchdog.py` now accepts optional `--ledger-state` input and summarizes:

- run status counts;
- most recent successful run per task;
- active runs and expired leases;
- open review count;
- oldest review age;
- review reasons and oldest open items.

This remains observation-only. It does not claim, retry, repair, resolve, or mutate ledger state.

## Remaining before PR

1. Execute the candidate SQL + SQL behavior test in a disposable PostgreSQL/Supabase-compatible database.
2. Review compatibility with the repository recovery/migration harness and rollback expectations.
3. Generate the real migration through the project migration workflow/CLI rather than inventing a migration filename.
4. Re-run local/static tests and secret/diff review.
5. Only then open one evidence-backed PR.

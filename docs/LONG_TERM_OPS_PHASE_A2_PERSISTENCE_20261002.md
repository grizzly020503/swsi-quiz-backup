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

## Why explicit grants are mandatory design

This candidate never relies on historical default privileges. Grants and RLS are treated as one migration unit so Data API exposure cannot silently expand when schema/platform defaults change.

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

The review queue has matching atomic service-role RPCs:

- `swsi_ops_upsert_review_item` preserves original `first_seen_at` and merges only still-open evidence;
- `swsi_ops_touch_review_item` increments attempts and records retry/error timing;
- `swsi_ops_resolve_review_item` records a terminal `resolved / superseded / invalid` result, permits exact idempotent replay, and rejects conflicting terminal rewrites.

## Why this is still a candidate, not a migration

Per the repository and Supabase workflow rules, production DDL is not being improvised from chat. The SQL remains under `supabase/candidates/` even after isolated PostgreSQL validation. A real migration must be generated/reviewed as a separate release step before any production apply.

No Supabase development branch was created. The live cost query on 2026-10-02 returned **US$0.01344/hour**, so creating one would violate the no-new-paid-resource rule without owner approval. No production DDL was executed.

## Adapter boundary

`scripts/ops_task_ledger_supabase.py` maps the backend-neutral contract to the task and review service-role RPCs. It intentionally exposes only `--self-test`; there is no live-write CLI yet. That prevents accidental production mutation before the migration/RLS path is separately approved.

## Static/local verification

The branch runs deterministic checks for:

- backend-neutral ledger transitions;
- semantic-file / trigger-run / parent-child identities;
- Full Corpus session identities;
- MOEX run/stage identities;
- Guardian durable-review candidate identities;
- candidate SQL security invariants;
- adapter payload contracts;
- watchdog durable-ledger projection;
- refusal of non-local PostgreSQL targets.

## Isolated PostgreSQL behavior verification — completed

PR #273 added a PR-only `Ops Ledger Candidate DB QA` workflow using a disposable PostgreSQL 16 service. It has no schedule and no main-push trigger.

Run `36995156636` completed **SUCCESS** on head `a1d7e3ebbd57cfce04a91d972bb15745bccdee2b` and verified:

- zero-network Python contract/self-tests;
- candidate ledger + review RPC SQL execution on PostgreSQL 16;
- first claim and live-lease duplicate blocking;
- retry-not-due and later reclaim;
- lease-expiry reclaim and retry exhaustion;
- checkpoint preservation and monotonic `processed_count`;
- unknown checkpoint versions fail closed;
- terminal idempotency;
- `no_change` updates trusted `last_success_at`;
- review `first_seen_at` survives repeated observations;
- review attempts/next-check/error state are retained;
- resolved review history is not silently reopened;
- conflicting terminal rewrite is rejected;
- RLS is enabled on both tables;
- `anon` / `authenticated` have no direct table or RPC access;
- `service_role` has the intended select/insert/update/execute access but no delete grant.

The behavior fixture ends with `ROLLBACK`. Production credentials and production data are not used.

The existing `Ops Task Freshness Watchdog` PR validation also passed on run `36995156628`; its live scheduled-freshness job correctly skipped in PR context and is not a test failure.

## Watchdog projection

`ops_task_watchdog.py` accepts optional `--ledger-state` input and summarizes:

- run status counts;
- most recent successful run per task;
- active runs and expired leases;
- open review count;
- oldest review age;
- review reasons and oldest open items.

This remains observation-only. It does not claim, retry, repair, resolve, or mutate ledger state.

## DR compatibility review

The repository's existing `scripts/supabase_recovery_dry_run.py` already creates the portable Supabase roles `anon`, `authenticated`, and `service_role` before replaying schema/migrations into disposable PostgreSQL. The candidate therefore reuses the repository's existing PostgreSQL assumptions rather than inventing a parallel production-like environment.

When the candidate becomes a real migration, that migration work package must also update the recovery contract:

- add the generated migration to `supabase/recovery/recovery_manifest.json` migration order;
- add `swsi_ops_task_runs` and `swsi_ops_review_items` to the expected public table set;
- add runtime-contract assertions for RLS and service-role-only privileges;
- keep the DR workflow's production-write boundary unchanged.

`scripts/ops_task_ledger_candidate_db_test.py` is candidate-only. It refuses any `PGHOST` other than `127.0.0.1`, `localhost`, or `::1`, refuses system databases, loads candidate SQL, runs rollback-only behavior fixtures, and verifies the privilege boundary. It has no hosted database mode.

## Current release boundary

PR #273 is the evidence-backed **candidate/contract** PR. A green merge of this PR still does not create the production ledger because there is intentionally no production migration in it.

### Before merging PR #273

1. Keep the final diff limited to ops contracts/helpers/candidate SQL/tests/docs; no Official Core or production deployment files.
2. Require the PR-only PostgreSQL candidate QA and existing watchdog contract validation to be green.
3. Confirm no unresolved review finding or secret exposure was introduced.

### After this candidate PR is merged

Create a separate migration release work package that:

1. converts the reviewed candidate SQL into a real migration;
2. updates the DR recovery manifest and runtime contract in the same change;
3. proves rollback/recovery and permission boundaries again;
4. wires only approved trusted server-side maintenance flows to the durable adapter;
5. requires separate owner authorization before production migration/deploy.

The independent external heartbeat required by #262 P1-6 remains a separate later work package.

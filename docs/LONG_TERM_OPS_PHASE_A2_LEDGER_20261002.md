# Long-term Ops Phase A-2 — Durable task ledger contract

Issue: #269  
Parent tracker: #262

## Goal

Move SWSI maintenance from “a workflow ran recently” to a state model that can safely answer:

- what logical job is being processed;
- whether another worker already owns it;
- where a batch stopped;
- whether a retry is due or exhausted;
- whether a structural problem is quarantined;
- how long manual-review debt has been waiting.

This phase does **not** grant autonomous production publishing or Official Core mutation.

## Live production audit before implementation

Read-only inspection of the active `Swsi` Supabase project on 2026-10-02 found:

- `pg_cron` is installed;
- `pg_net` is installed;
- no `pgmq` extension was present in the extension inventory;
- the obvious public job-related table is `public.ai_analysis_job_config`, which is configuration state rather than a general durable run ledger;
- built-in `cron.job`, `cron.job_run_details`, and `net.http_request_queue` exist, but they are infrastructure-specific records and are not a replacement for SWSI logical task state.

Therefore this change starts with a backend-neutral contract instead of forcing unrelated existing tables into a new responsibility.

No production DDL, migration, RLS change, credential change, Edge Function deployment, or paid resource was made during this phase of implementation.

## Static contract vs dynamic state

`data/ops_task_ledger_contract.v1.json` is a **static specification** and belongs in Git.

Dynamic task rows must **not** be committed back to the repository on every run. Doing that would create Git churn, Actions fan-out, merge races, and an unreliable state store.

`scripts/ops_task_ledger.py` currently provides a deterministic local JSON backend only for fixture/state-transition verification. It is not the production persistence adapter.

## Required state semantics

A logical run is uniquely identified by:

`task_id + idempotency_key`

Worker outcomes are intentionally distinct:

- `success`: valid work completed;
- `no_change`: source was checked successfully, but there was nothing new to apply;
- `failed_retryable`: transient error, bounded retry allowed;
- `failed_terminal`: no more automatic retries;
- `quarantined`: structural/input uncertainty requires review.

`stale` / `missed` remain **derived watchdog states**, not worker completion outcomes.

A running job owns a time-bounded lease. A second worker cannot claim the same logical run while the lease is valid. After expiry, a later worker may reclaim it and the attempt count increases. Retries are bounded by `max_attempts` and `next_retry_at`.

## Checkpoint rules

Checkpoint format is versioned. The first contract version accepts checkpoint version `1` only. Unknown checkpoint versions fail closed rather than silently starting the whole batch over.

A reclaimed run preserves both checkpoint and processed count. This is the minimum requirement for safely resuming large corpus scans without repeating already-completed side effects.

## Review queue aging

Review items preserve:

- first seen time;
- last attempt time;
- attempt count;
- last error;
- next check time;
- terminal resolution (`resolved`, `superseded`, or `invalid`).

Backlog must not be reduced by deleting unresolved rows. A future reporting adapter should surface open count and oldest age/SLA breaches.

## Production persistence boundary

Before a production adapter is introduced:

1. prefer an internal/non-exposed schema (or equivalent least-privilege store) for operational metadata;
2. do not expose service-role credentials to the browser;
3. if an exposed schema is ever used, apply explicit grants plus RLS in the same migration;
4. generate and review migration/RLS/rollback evidence before production application;
5. keep Official Core and grading contracts outside this ledger's write authority.

Current Supabase documentation explicitly recommends keeping internal tables in non-exposed schemas and using least-privilege grants/RLS for anything exposed through the Data API.

## Local verification

Run:

```bash
python scripts/ops_task_ledger.py --self-test
python -m py_compile scripts/ops_task_ledger.py
```

The self-test covers:

- first claim;
- duplicate claim while lease is live;
- checkpoint persistence;
- transient failure and retry-not-due;
- reclaim after retry window;
- successful completion;
- duplicate trigger after terminal completion;
- reclaim after expired worker lease;
- retry exhaustion to terminal failure;
- review-item aging and resolution.

## Next integration step

After this contract is reviewed, wire the existing Full Corpus QA / MOEX / Unified QA flows to a durable adapter with the same semantics. Then extend `ops_task_watchdog.py` to consume the durable task projection while keeping the watchdog observation-only.

The truly independent external heartbeat in #262 P1-6 remains a separate later work package; this ledger only creates trustworthy state for that heartbeat to observe.

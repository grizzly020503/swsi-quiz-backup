# Analyzer Trust-Routing Activation Gate — 2026-10-05

This branch is a **source-only production activation candidate**. It is not a deployment authorization.

## Intended runtime flow

1. claim one pending question;
2. deterministic preflight before any model call;
3. special grading / multiple accepted answers / missing official answer -> review;
4. legal-risk question without canonical mapping -> review;
5. current legal-watch query/health outage -> pending hold/retry without consuming analysis attempts;
6. current-law changed / missing / untrusted -> review;
7. only after current-law trust succeeds, query the Stage7 exam-time runtime evidence snapshot + rows;
8. historical evidence query outage or incomplete snapshot -> pending hold/retry without consuming analysis attempts;
9. complete historical registry with missing/mismatched/untrusted evidence -> review;
10. legal-risk questions call models only when **both** current-law trust and exam-time historical-law proof succeed;
11. eligible question -> Qwen draft -> GPT-OSS audit -> strict validator;
12. validated candidate passes a second deterministic publication gate;
13. candidate enrichment is written only for ready / sanitized-ready routes;
14. review/hold routes write only analysis control metadata and never publish the generated candidate.

## Legal trust boundary

`current_legal_trust.ts` proves only that the latest current-law monitoring batch is healthy and internally consistent. It never substitutes for historical exam-time provenance.

`historical_law_trust.ts` consumes only the runtime evidence created from the verified Stage7/adjudicated registry. Trust requires a complete same-registry snapshot, matching question/law/exam code, `historical_version_checked=true`, an allowed verification level, valid evidence SHA-256, and the same registry SHA-256 batch.

Therefore legal automatic publication requires **two independent signals**:

- current official-law watcher says the named law is still `unchanged` in one healthy complete batch; and
- Stage7 runtime evidence proves the law version used for that specific historical exam question.

If either side is unavailable or contradictory, the route fails closed.

## Upstream release primitives already merged to main

### PR #368 — current-law run-health contract

- migration: `supabase/migrations/20261005033000_legal_watch_run_health.sql`
- `sync-legal-watch/run_health.ts`
- updated `sync-legal-watch/index.ts`
- run state: `syncing -> complete / failed`
- runtime trust requires global healthy batch plus same-batch per-law `unchanged` row
- source QA: Legal Watch Article Scope QA + DR Restore were green on the reviewed PR head

### PR #371 — Stage7 historical runtime evidence

- migration: `supabase/migrations/20261005050000_historical_law_runtime_evidence.sql`
- `historical_law_runtime_evidence`
- `historical_law_runtime_evidence_snapshot`
- `sync-historical-law-evidence` source candidate
- deterministic per-record and whole-registry fingerprints
- monotonic verified registry: additions allowed; silent deletion/evidence drift rejected

Current durable verified registry: **19 records = 13 machine-verified + 6 evidence-adjudicated**.

### PR #372 — manual production sync gate

- workflow: `Historical Law Runtime Evidence Sync`
- `workflow_dispatch` only
- must run from `main`
- requires explicit `confirm_production_sync=true`
- no push/schedule automatic production sync yet
- rebuilds and validates the durable Stage7 registry before POST
- verifies production response counts + deterministic registry SHA after POST

## Production read-only audit — 2026-10-05

Production project: `Swsi` (`yumjtrdctaxyczpspuyo`).

Observed state before activation:

- `legal_watch_run_health`: **not present**
- `historical_law_runtime_evidence`: **not present**
- `historical_law_runtime_evidence_snapshot`: **not present**
- `sync-historical-law-evidence`: **not deployed**
- `sync-legal-watch`: still production **v4**, without run-health persistence
- `analyze-pending-questions`: still production **v12**
- `legal_reference_registry`: **52/52 unchanged, 0 changed, 0 missing**
- all 52 registry rows share exactly `2026-10-02T15:29:31Z`
- tracked `data/legal_watch_report.json` already contains the new run-health payload: watch=52, matched=52, missing=0, changed=0, lookup_error=0

This means the existing per-law registry is internally clean; the missing production pieces are the new global run-health and Stage7 runtime evidence contracts.

## Required production activation order

### Phase A — current-law health first

1. Apply `20261005033000_legal_watch_run_health.sql` to production.
2. Deploy the reviewed main version of `sync-legal-watch` with `article_scope.ts` and `run_health.ts`.
3. Run one normal official legal-watch batch using the tracked `data/legal_watch_report.json` contract.
4. Read-only verify:
   - `schema_version = 1`
   - `source = github_actions`
   - `sync_status = complete`
   - `baseline = false`
   - `lookup_error_count = 0`
   - every expected per-law row has the exact same `last_checked_at` as the global batch
   - named laws needed by analyzer are `watch_status = unchanged`

Do not proceed if any of these fail.

### Phase B — Stage7 historical runtime evidence second

1. Apply `20261005050000_historical_law_runtime_evidence.sql` to production.
2. Deploy `sync-historical-law-evidence` using its reviewed source and custom GitHub-token authentication boundary.
3. Run the merged `Historical Law Runtime Evidence Sync` workflow from `main` with explicit production confirmation.
4. Read-only verify:
   - snapshot `sync_status = complete`
   - `record_count = historical_version_checked_count`
   - current expected baseline is 19 records
   - current verification-level counts are 13 machine + 6 evidence-adjudicated
   - all evidence rows use the same `source_registry_sha256` as the snapshot
   - all evidence/question/exam identities resolve correctly

Do not proceed if any of these fail.

### Phase C — analyzer canary last

1. Re-read production queue/config state.
2. Confirm Phase A + B evidence through the same service-role/Data API path used by the analyzer.
3. Deploy only the exact reviewed `analyze-pending-questions` source head after fresh exact-head QA + DR.
4. Use a **tiny bounded canary**. Verify at least:
   - one eligible non-legal route;
   - legal route behavior only when both current + historical proof exist;
   - hold/retry does not consume attempts;
   - review/hold does not publish candidate enrichment;
   - no Official Core field changes;
   - pending/review counts do not spike unexpectedly;
   - post-model accepted-answer/law sanitization gates remain active.
5. Expand gradually only after canary evidence is clean.

## Explicitly not included in this source candidate

- no production migration application yet;
- no new `sync-legal-watch` production deploy yet;
- no `sync-historical-law-evidence` production deploy yet;
- no historical registry production sync yet;
- no analyzer production deploy yet;
- no cron/schedule activation;
- no Official Core / answer / accepted-answer / grading mutation;
- no activation of Draft PR #360.

## QA ownership

Changes to this runbook are owned by `AI Analyzer Route QA`. A release-gate documentation change must therefore create a new exact-head analyzer QA result rather than inheriting a green check from an older source head.

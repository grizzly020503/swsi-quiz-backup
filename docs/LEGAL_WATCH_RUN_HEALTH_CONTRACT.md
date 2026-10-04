# Legal Watch Run Health Contract

Purpose: provide a fail-closed global evidence marker for the latest official MOJ legal-watch batch.

A per-law `legal_reference_registry` row alone is not sufficient evidence that the whole watcher run was healthy. Runtime consumers that want to trust current-law evidence must require both:

1. `legal_watch_run_health.sync_status = 'complete'`
2. `legal_watch_run_health.baseline = false`
3. `legal_watch_run_health.lookup_error_count = 0`
4. the individual `legal_reference_registry.last_checked_at` equals the same run `checked_at`
5. the individual law row is `watch_status = 'unchanged'`

Any missing row, timestamp mismatch, baseline batch, lookup error, `syncing`, `failed`, `missing`, or `changed` state must fail closed and retain review.

This repository contract does **not** by itself apply the migration, deploy `sync-legal-watch`, or activate analyzer consumption. Those remain separate production changes with exact-head QA.

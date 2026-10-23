# Current-affairs OIDC cutover and rollback

This runbook coordinates `sync-current-affairs` with `public-monitoring-feed.yml`.
It authorizes no deployment, workflow state change, secret operation or database write.
The Owner must approve the release window and both sides of the switch first.

## Preconditions

- Pin the reviewed candidate HEAD, current main HEAD, exact-head CI Run IDs and deployed Edge source/version. A PR contract pass is not production recovery.
- Save the existing Edge source bundle, shared imports, entry point and `verify_jwt` setting in maintainer-controlled storage. A version number alone is not a redeployable rollback bundle.
- Record the previous workflow source and stable Cloudflare/Netlify deployment IDs, runtime/Service Worker digests and question manifest revision. Main merge may also trigger the existing site provider integration; include it in release authorization.
- Verify offline OIDC claim and signed-token tests, Edge typecheck, source-policy checks, student-analysis quarantine, grading, full-corpus integrity and frontend checks at the candidate HEAD.
- Confirm backup/restore readiness and held official-source decisions with the Owner. Keep private backups/keys outside GitHub and normal CI artifacts.
- Never use a dual-auth compatibility bypass, disable signature verification or pass a service-role key to Actions. The new Edge accepts the pinned GitHub OIDC policy; the old caller is incompatible with it.

## Controlled switch

1. In GitHub Actions, disable **Public Monitoring Feed** for the approved maintenance window. Record that state and its start time. Wait for existing non-PR runs to finish, or explicitly cancel and record them. Verify no writer is active. Do not disable Watchdog or suppress its outage evidence.
2. With the caller paused, deploy the reviewed `sync-current-affairs` source and its reviewed `_shared/github_actions_oidc.ts` dependency to the existing SWSI project. Preserve the reviewed custom-auth gateway setting (`verify_jwt=false`); this does not remove the application-level OIDC verification. Confirm the deployed source matches the candidate. No invocation yet.
3. Merge only the authorized, reviewed candidate into main. Keep Public Monitoring Feed disabled while merge/push activity occurs. Re-read the resulting main SHA and the exact workflow source. Do not enable the caller if the merged source differs from the reviewed OIDC caller.
4. Re-enable Public Monitoring Feed. Dispatch one approved run on main. This is a real current-affairs write, not a read-only test. Record the Run ID, main SHA, deployed Edge version, response and durable sync audit timestamp. Inspect archival/audit failures as failures even if earlier upsert batches succeeded.
5. Confirm a fresh `current_affairs_sync_runs` record and expected row/status handling without publishing private payloads. Use approved negative-auth probes with no valid payload; unauthorized/empty/PR/fork/wrong-workflow requests must be rejected before database access. Do not obtain or leak live OIDC tokens merely to test rejected sources.
6. Observe the next actual scheduled run. The scheduled result must succeed and the audit timestamp must advance before declaring the recurring service healthy. A manual replay alone does not prove the schedule works. Record the temporary pause and any failed runs; do not relabel them as successful.
7. Complete authorized primary/fallback release, runtime/cache-bust/Service Worker parity, old IndexedDB/PWA refresh, offline/student quarantine and grading acceptance. Use the existing [Netlify preflight/deploy sequence](NETLIFY_CONTROLLED_DEPLOY.md). Do not create another preview site.

## Failure and rollback

1. Disable Public Monitoring Feed again and drain/cancel the active writer before changing either side. Leave failure monitoring visible.
2. If the candidate Edge deployment or caller validation fails before re-enable, keep the caller paused. Restore the captured Edge bundle and matching old workflow only as an explicitly coordinated rollback. Do not re-enable an OIDC-only caller against the legacy Edge, or a legacy caller against the OIDC-only Edge.
3. The legacy Edge may reproduce the pre-existing HTTP 403. Returning to that known degraded baseline is not a successful service recovery. If no verified matching pair is available, keep sync paused, retain the last trusted public snapshots, and record BLOCKED with the last failure Run ID/time.
4. An HTTP 500 may follow partial batch upserts. Capture counts/status evidence privately and inspect the durable audit before retrying. Do not restore the whole database or erase manual review/status decisions as an automatic rollback. Use the existing idempotent upsert only after authorization and root-cause review.
5. If a frontend release fails, restore the recorded stable provider deployment with its matching runtime/manifest, then repeat HTTP, grading and PWA/cache checks. Website rollback does not roll back Supabase automatically.

## GO / NO-GO

GO requires exact-head CI, Owner authorization, a captured usable rollback pair, successful authorized replay, fresh durable audit, a successful subsequent scheduled run, and applicable site/data/PWA acceptance evidence.

Keep NO-GO for an unresolved 403/500, missing audit record, unknown deployed source, incompatible caller/function pair, failed negative auth test, unverified Netlify credentials/parity, unsafe private restore, or unresolved release-critical official-data review. Mark each remaining item DONE, BLOCKED or HOLD; a complete but stale law snapshot is not fresh activation evidence.

The analyzer remains a separate decision: when natural eligible pending is zero, preserve the existing analyzer and retain its uncanaried candidate evidence. Do not manufacture pending rows or promote review rows to obtain a canary.

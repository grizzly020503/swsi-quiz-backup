# SWSI release validation — 2026-10-01

## Release state

- GitHub Actions quota/runner availability is restored. A rerun of Public Monitoring Feed on PR #188 reached a hosted runner and executed real steps; the earlier empty-step failures were infrastructure/quota symptoms, not test failures.
- PR #188 (`fix: handle zero feed errors in Netlify verifier`) was reviewed as a two-file CI-verifier-only fix and squash-merged to `main` as `3877e1023e1ac3d7ef544b5ba28ae041b0275b15`.
- Release progression is intentionally stopped before #189. The rerun of Public Monitoring Feed for #189 executes normally but fails the deterministic snapshot gate because regenerated `current_affairs_trends.json` differs from the tracked snapshot. This is a real release-gate failure and must not be treated as an Actions quota failure.
- #190 is not merged because the planned sequence requires #189 to clear first.
- #191 remains draft and is not merged/deployed.
- #179/#182/#185 must not be independently merged if their work is already absorbed by later current-affairs branches; re-check ancestry/diff before any future action.

## Current blocker

`Public Monitoring Feed` → `Rebuild deterministic monitoring contracts for PR` reports:

`PR deterministic snapshot drift: current_affairs_trends.json != auto/current_affairs_trends.json`

Signals and events reproduce deterministically; trends do not. The trends builder uses the current rebuild timestamp for recency/state scoring, so a snapshot can drift as wall-clock time advances even when source content is unchanged. Fix the deterministic verification contract (prefer an explicit/frozen reference time for PR verification) or intentionally regenerate/commit the trend snapshot after confirming the semantic change. Do not bypass the gate.

## Code-health guardrails carried into release work

1. Do not add new `zzz`/`zzzz` late override layers. Existing grandfathered owners must be reduced gradually behind regression tests.
2. Continue shrinking multiple runtime owners and lexical filename-order dependencies. Ownership should be explicit and covered by `runtime_owner_smoke`/release gates.
3. Dynamic DB/AI/current-affairs text entering `innerHTML` remains a security/maintainability priority. Use context-aware escaping; URLs must be restricted to safe HTTP(S) schemes. Static trusted template HTML is a separate case and should not be mechanically rewritten.
4. Do not expand `window.*` global state/functions for new features. Move behavior toward explicit modules/owners incrementally; avoid a large frontend rewrite during release stabilization.
5. Re-check for `eval`/equivalent dynamic execution and hardcoded production credentials before final production deployment. Environment-variable names such as `SUPABASE_SERVICE_ROLE_KEY` are expected; credential values must never be committed.

## Production status

No new Cloudflare/Netlify production deployment was performed after #188 because #189 did not clear the release gate. Therefore there is no new production HEAD or post-deploy smoke result to record from this run. Production must remain on the previously verified release until #189 is corrected and all downstream gates are green.

## Next safe sequence

1. Fix #189 deterministic trend verification without bypassing the gate; rerun Public Monitoring Feed and the other required QA workflows.
2. Once #189 is green, merge it and verify `main`.
3. Rebase/re-evaluate #190 against the new `main`, rerun its gates, then merge only if green.
4. Rebase/re-evaluate #191; keep it draft until its 4,800-question law-link contract and review boundary are explicitly cleared.
5. Only then run release gates, Cloudflare/Netlify deployment, production smoke, and record the final production HEAD.

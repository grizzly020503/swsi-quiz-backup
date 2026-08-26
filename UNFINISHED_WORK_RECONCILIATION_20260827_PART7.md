# Unfinished Work Reconciliation — Part 7

Date: 2026-08-27
Audit branch: `content/credibility-labels-20260827`
Scope: release-gate/runtime reconciliation only. **No repair/work branch was changed.**

## Executive verdict

| Area | Status | Priority | Current verdict |
|---|---|---:|---|
| Service Worker release-version gate | **CONFIRMED FALSE-PASS RISK** | P1 | Runtime is `v6`, but stale workflows still grep for literal `const VERSION = 'v5'`; commit `bf597c5...` added that exact stale token inside a comment, allowing grep-based checks to pass without verifying runtime version. |
| Cloudflare preview SW check | **INVALID ASSERTION** | P1 | Preview workflow checks for v5 while intended runtime is v6. Its `Mark as isolated preview` step succeeded because the v5 token exists in a comment, not because runtime is v5. |
| Netlify production SW check | **INVALID ASSERTION** | P1 | Post-deploy verifier also greps for v5 and can therefore pass a v6 worker containing the compatibility comment. It is not verifying the effective assignment. |
| pre-package browser gate | **OPERATIONAL GAP** | P1 | Manual Netlify package workflow runs static/preflight checks but does not run the Playwright browser interaction/grading smoke and does not require a successful current-commit Monthly Frontend QA check before producing a release artifact. |
| analysis/review provenance in frontend | **STILL PRESENT** | P1 | CDN rows carry `analysis_status`, but current `normalize()` retains grading metadata and drops `analysis_status`; no frontend code can distinguish `review` quarantine from ordinary `pending`/missing explanation. |
| explanation status copy | **MISLEADING STATE** | P1 | Missing explanation always renders as `解析生成中`, even for intentionally quarantined `review` questions that are not actually in the normal generation pipeline. |
| AI 429 server classification | **MOSTLY VERIFIED** | P2 | Worker distinguishes client/global daily quota with machine codes; generic rate-limit/upstream 429 remain message-only but are surfaced. |
| AI quota wrapper concurrency | **NOT SAFE UNDER OVERLAP** | P2/P1 | Client quota UI temporarily replaces global `window.swsiFetchWithTimeout`; overlapping AI calls can nest wrappers and restore a stale wrapper after completion, misrouting later 429 handling. |
| Service Worker install atomicity | **BRITTLE BUT EXPECTED** | P2 | `cache.addAll(SHELL)` means one missing/transient shell asset aborts v6 installation and leaves the old worker active. Not a current proven outage, but worth hardening/observing. |

## 1. Confirmed release-gate integrity problem: v5 token in a comment

Current repair-branch `sw.js` intentionally runs:

```js
const VERSION = 'v6';
```

But immediately above it contains:

```js
// Legacy preview smoke compatibility only; runtime no longer uses: const VERSION = 'v5';
```

This was not incidental old text. Commit `bf597c5c39466b2d70319cdeba8636176e355264` added exactly that one compatibility line; the commit message is:

> `保留 v5 預覽相容標記並維持 Service Worker v6`

The diff proves the only semantic content change was insertion of the stale v5 literal into a comment while retaining runtime v6.

That would be harmless documentation by itself, except two release workflows use plain substring grep as the assertion.

### Cloudflare preview

`.github/workflows/cloudflare-frontend-preview.yml` currently executes:

```sh
grep -q "const VERSION = 'v5'" /tmp/swsi-preview/sw.js
```

The latest run on `bf597c5...` shows:

- Build current monthly frontend: success
- Mark as isolated preview: success
- Publish preview files: failure

Because the v5 grep is inside `Mark as isolated preview`, the successful step proves the stale assertion accepted the comment token even though the effective runtime assignment is v6.

### Netlify production verifier

`.github/workflows/verify-netlify-production.yml` similarly runs:

```sh
grep -q "const VERSION = 'v5'" /tmp/prod-sw.js
```

Therefore a production `sw.js` with effective `VERSION='v6'` plus the compatibility comment satisfies the verifier. The post-deploy gate cannot currently tell v5 from v6.

### Internal inconsistency

Other current gates correctly expect v6:

- `scripts/p0_frontend_preflight.js` checks `const VERSION = 'v6'`
- `scripts/monthly_frontend_smoke.py` checks v6
- `.github/workflows/monthly-frontend-qa.yml` checks v6
- `.github/workflows/build-netlify-package.yml` checks v6

So the repository presently has conflicting release contracts: most current QA says **v6**, while Cloudflare preview and production verification still say **v5**.

**Classification: P1 release-gate integrity issue.**

This should be fixed by updating the stale workflows to parse/assert the effective version, then removing the compatibility comment. Do not keep a false marker merely to satisfy an obsolete grep.

## 2. Manual release package is not browser-gated before artifact creation

`Build Netlify Production Release Package` is manual and main-only. It correctly performs:

- P0 frontend preflight
- JS syntax checks
- production-shaped build
- static smoke
- marker/content checks
- deterministic ZIP + SHA-256

However it does **not** run:

- `scripts/grading_contract_smoke.js`
- `scripts/browser_interaction_smoke.js`
- the other Playwright interaction suites used by Monthly Frontend QA

It also does not query/require that the exact checked-out main SHA already has a successful `Monthly Frontend QA` run.

The separate `Verify Netlify Production Release` workflow does run a real browser smoke, but that is explicitly a **post-deploy** verifier against the production URL.

Therefore the current release flow can create and save a "verified production package" after only static checks even if the exact commit's browser interaction QA is missing or failed. The problem may be detected after deployment, but the package gate itself does not prevent it.

**Classification: P1 operational/release gap.**

A stronger pre-release contract should either run the browser/grading smoke inside the package workflow or enforce successful required checks for the exact source SHA before packaging.

## 3. Frontend loses `analysis_status`, so review quarantine is invisible

CDN question shards contain `analysis_status` on raw rows. Example normal rows include:

```json
"analysis_status":"ready"
```

The effective monthly patch wraps legacy `normalize()` and explicitly retains:

- `accepted_answers`
- `grading_mode`
- `source_exam_code`

but it does **not** copy `analysis_status` into the normalized frontend question object.

The base `normalize()` also does not retain it. Search of the built monthly patch found no `analysis_status` handling.

As a result, once a row reaches the browser, the UI cannot know whether the backend row is:

- `ready`
- `pending`
- `analyzing`
- deliberately quarantined as `review`

For questions with no explanation, the effective safe renderer always falls back to:

> `此題解析生成中。...詳解之後補上。`

That wording is reasonable for true pending/analyzing rows, but misleading for deliberately quarantined `review` questions. The handoff documents official multi-answer and special-credit rows intentionally held in review to prevent bad AI explanation semantics; those are not equivalent to "generation currently in progress".

**Classification: P1 trust/transparency issue.**

Recommended contract: preserve `analysis_status` (and optionally a safe public explanation-state enum) through shard normalization, then render distinct copy such as `解析審核中／暫不提供詳解` for review quarantine rather than claiming generation is in progress.

## 4. AI 429 classification: backend is materially improved

The current Worker has two different public throttling layers plus daily D1 quota.

### Daily D1 quota

Machine-readable codes exist for:

- `CLIENT_DAILY_QUOTA`
- `GLOBAL_DAILY_QUOTA`

The frontend quota wrapper clones 429 JSON, reads `error.message` and `error.code`, and replaces the generic message with the server-provided daily quota message. This is a real fix.

### Short-window rate limit and upstream 429

The minute-level rate-limit responses and upstream Groq 429 do not carry the daily-quota codes, but they do carry human-readable messages. The wrapper still surfaces those messages under an `AI 使用提醒` heading.

Therefore the earlier broad claim "AI 429 errors are all misclassified" is no longer accurate.

**Classification: MOSTLY VERIFIED, P2 residual.**

## 5. AI quota UI wrapper is globally monkey-patched and can restore stale state

`quotaAwareCall()` temporarily replaces:

```js
window.swsiFetchWithTimeout
```

with a per-call wrapper, calls the original feedback function, then in `finally` restores the previous function only if the global still points to its own wrapper.

This works for one request at a time. But UI busy-state locking is per essay ID, not global. If a user starts one AI request, navigates to another essay and starts a second before the first finishes, wrappers can nest:

1. call A installs wrapper A;
2. call B records wrapper A as its base and installs wrapper B;
3. call A finishes while global points to B, so A does not restore;
4. call B finishes and restores its base — wrapper A;
5. the stale wrapper A can remain installed globally after both calls complete.

This can cause later 429 parsing/message routing to be associated with an old request ID and makes the fetch layer stateful across calls.

No current test covers overlapping AI calls.

**Classification: P2 by normal usage, potentially P1 reliability if overlapping navigation/use is common.**

A safer implementation should avoid global monkey-patching: pass a fetch function/callback into the AI request helper, or centralize response classification in `swsiFetchWithTimeout` itself.

## 6. Service Worker installation is all-or-nothing

The v6 worker pre-caches its shell using:

```js
caches.open(CACHE).then(c => c.addAll(SHELL))
```

`SHELL` includes mutable auto payloads as well as core shell assets. `Cache.addAll()` rejects the install if any one requested asset fails. In that case `skipWaiting()` is not reached and the previous Service Worker remains active.

Because the release package normally contains these assets, this is not evidence of a current outage. It is still an operational brittleness point: a transient missing/failed shell asset can postpone activation of the worker version carrying the updated cache policy.

**Classification: P2 hardening, not a current blocker by itself.**

## 7. Updated high-priority release list

After Part 7, the strongest remaining P1 items are now:

1. **Fix the invalid v5/v6 release assertions and remove the compatibility-token false pass.**
2. **Require browser/grading QA before generating the production release artifact, not only after deployment.**
3. Cloudflare preview workflow publish/main-coupling failure from Part 6.
4. Preserve/render `analysis_status` so intentionally quarantined review rows are not labeled `解析生成中`.
5. Bound localStorage history growth.
6. Repair/update Supabase recovery schema contract.
7. Close full-app XSS with adversarial browser tests.
8. Fix keyboard accessibility of the primary quiz flow.

This round found no new evidence that the current grading math itself is wrong: the unified mock-exam contract correctly uses the shared grading helper and explicitly avoids recording unanswered `all_credit` rows as learner mistakes.

No production, Netlify, Supabase, Cloudflare, `main`, or `fix/code-health-p0-20260826` repair code was changed by this audit entry.

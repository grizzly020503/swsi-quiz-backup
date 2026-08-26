# Unfinished Work Reconciliation — Part 6

Date: 2026-08-27
Audit branch: `content/credibility-labels-20260827`
Scope: release-risk reconciliation only. **No repair/work branch was changed.**

Status vocabulary used here:
- **VERIFIED** — current code + execution evidence support completion.
- **STILL PRESENT** — current effective code still contains the issue.
- **PARTIALLY MITIGATED** — meaningful guard exists, but the full surface is not closed/proven.
- **NOT PROVEN** — code exists, but current execution/browser evidence is insufficient.
- **OPERATIONAL GAP** — recovery/deployment/release process is incomplete or stale.

## Executive verdict

| Area | Status | Priority | Current verdict |
|---|---|---:|---|
| Cloudflare frontend preview workflow | **STILL PRESENT / latest run failed** | P1 | Build passed, publish-to-main step failed; live preview validation was skipped. Workflow design also writes preview artifacts by pushing `HEAD:main` from the triggering branch. |
| localStorage learning history | **STILL PRESENT** | P1 | `swsi_v2_history` grows without an explicit retention/size bound. Storage failure is now surfaced, but growth itself is not bounded. |
| review-state localStorage | **PARTIALLY MITIGATED** | P2 | Versioned (`version:2`) and migrated from history; per-question object is naturally bounded by question IDs, but no explicit quota/repair/export contract exists. |
| dynamic essay cache | **STILL PRESENT** | P2 | `swsi_auto_essays_v1` has parse fallback but no TTL/freshness metadata; stale data can persist offline after remote fetch failure. |
| essay drafts | **PARTIALLY MITIGATED** | P2 | Per-essay drafts are local-only and exportable, but storage capacity remains browser-quota dependent. |
| Supabase recovery/source-of-truth SQL | **CONFIRMED DRIFT / OPERATIONAL GAP** | P1 | The named consolidation recovery migration predates later production migrations, including `grading_mode`; it is no longer a standalone current recovery snapshot. |
| full-app stored-XSS closure | **PARTIALLY MITIGATED / NOT PROVEN** | P1 | Quiz renderer is escaped in the later safe override, but other legacy renderers still interpolate dynamic values into `innerHTML`; no full adversarial browser closure is recorded. |
| basic document semantics | **PARTIAL** | P2 | `lang=zh-Hant`, viewport, title, PWA metadata exist. No document meta description or canonical link was found. |
| core keyboard accessibility | **STILL PRESENT** | P1 | Core answer/options and several cards are clickable `<div>` elements; no `tabindex` was found and ARIA coverage is minimal. |

## 1. Cloudflare frontend preview — build exists, latest publish run is red

The workflow `.github/workflows/cloudflare-frontend-preview.yml` is not merely a static build check. It:

1. checks out the triggering ref;
2. builds `/tmp/swsi-preview`;
3. runs JS syntax checks and `monthly_frontend_smoke.py`;
4. rewrites the preview HTML with `noindex`, a preview banner, and preview cache-busting;
5. replaces `cdn/preview` in the checkout;
6. commits that generated preview content;
7. fetches/rebases against `origin/main` and attempts `git push origin HEAD:main`;
8. only after that polls the live Worker preview URL and verifies expected markers.

This means the workflow is coupled to a write into `main`; it is not an isolated read-only preview build.

The latest identified run for this workflow on `fix/code-health-p0-20260826`, SHA `bf597c5c39466b2d70319cdeba8636176e355264`, was run **#64** and concluded **failure**. Job-level evidence is precise:

- Checkout: success
- Setup Python: success
- Build current monthly frontend: success
- Mark as isolated preview: success
- **Publish preview files into existing Cloudflare static assets: failure**
- Wait for Cloudflare preview deployment: **skipped**

Therefore the current evidence supports:

> **The preview build logic passed, but the latest publish/live-preview contract did not complete.**

It would be incorrect to call the Cloudflare preview workflow healthy merely because the workflow file exists or because the build step passes.

A second design concern remains: on any push matching its path filter, the workflow has `contents: write` and pushes the triggering checkout's `HEAD` to `main` after a rebase. Even if branch protection currently blocks an unsafe push, the workflow itself is not branch-isolated. Branch-protection configuration could not be read through the current integration, so protection must not be assumed.

**Classification:** P1 release/process issue. The safe target is a preview publication path that does not promote an arbitrary feature-branch HEAD into `main`, and then a live preview smoke that is required to pass.

## 2. localStorage/history — storage failure warning fixed, unbounded history remains

Current base code defines:

- `swsi_v2_history`
- `swsi_review_v2`
- `swsi_auto_essays_v1`
- `essay_draft_<essay-id>`
- `swsi_fs`
- later migration markers such as `swsi_verified_shard_cache_v1`

### 2.1 `swsi_v2_history`

`record()` loads the entire history array, appends one object for every answer, then writes the whole array back:

```js
function record(item,picked,correct){ const h=loadHist();
  h.push({id:item.id,subject:item.subject,major:item.major,mistake:item.mistake||'',correct,ts:Date.now()}); saveHist(h);
  updateReviewSchedule(item,correct); }
```

There is no `slice`, maximum count, age cutoff, compaction, or rolling aggregation in this path. Consequently:

- storage use grows with lifetime answer count, not unique question count;
- every write serializes the entire accumulated history;
- once browser quota is reached, future learning-state writes can fail.

The late code-health guard improves failure visibility by wrapping `saveHist`/`saveReviewState` and showing a visible `role="alert"` toast when localStorage writes fail. That is a real mitigation, but it does not address the unbounded growth condition.

**Classification:** **STILL PRESENT**, P1 data-integrity/long-term reliability.

A later fix should use one or more of: bounded event history, per-question aggregation, retention window, compaction, versioned export/import, and explicit quota tests.

### 2.2 Review state

`swsi_review_v2` has a useful schema marker (`version===2`) and one-time migration from history. This is better designed than raw history and is approximately bounded by unique question IDs.

**Classification:** **PARTIALLY MITIGATED**, P2 unless corruption/migration failures are demonstrated.

### 2.3 Dynamic essay cache

`swsi_auto_essays_v1` is refreshed when `auto/essays_auto.json` succeeds, and used as fallback when it fails. JSON parsing is guarded, but the cache carries no fetch timestamp, TTL, source version, or explicit invalidation policy.

That is appropriate for offline availability, but the UI cannot distinguish "fresh remote" from "old cached auto essays" from this key alone.

**Classification:** **STILL PRESENT**, P2 freshness/transparency issue, not a grading P0.

### 2.4 Essay drafts

Drafts use one key per essay and are flushed on `visibilitychange`/`pagehide`; the Progress page offers TXT backup. This is a useful safety net. Capacity still depends on browser storage quota, but unlike answer-event history the number of draft keys is naturally limited by essays a student actually opens.

**Classification:** **PARTIALLY MITIGATED**, P2.

## 3. Supabase recovery SQL — confirmed schema drift

`PROJECT_HANDOFF.md` names:

`supabase/migrations/20260825094110_production_qa_consolidation.sql`

as the production "recovery/source-of-truth migration" and correctly warns not to re-apply it to production merely because it exists in GitHub.

The file itself states that it consolidates production changes only through the 2026-08-25 09:41 batch. Its reset trigger covers:

- question
- opt_a ... opt_d
- answer
- accepted_answers

It does **not** include `grading_mode`, because that production concept was added later by:

`20260825110853_preserve_official_grading_mode.sql`

The later migration adds:

- `questions.grading_mode`
- allowed values `standard / all_credit / any_answer`
- 4,784 / 12 / 4 grading semantics backfill
- a consistency constraint
- an updated official-change reset trigger that includes `grading_mode`

There are also still later 2026-08-26 feedback migrations after both of those.

Therefore:

> **The 09:41 consolidation is no longer a standalone current production-recovery snapshot.**

If disaster recovery follows only the file currently described as the recovery/source-of-truth migration, the restored `questions` schema would lack the later grading-mode contract and later schema work.

This does **not** mean production is missing the migration; the handoff explicitly says the grading migration was applied to production. The problem is recovery documentation/schema reconstruction drift.

**Classification:** **CONFIRMED DRIFT / OPERATIONAL GAP**, P1.

Recommended eventual remediation: either create a new idempotent recovery snapshot through the latest production migration, or clearly redefine recovery as "apply the complete ordered migration chain" and automatically test reconstruction from empty DB in CI. Do not silently edit old already-applied migration history as the primary fix.

## 4. Full-app XSS — quiz path improved, closure still not demonstrated

The existing XSS audit correctly identified broad `innerHTML` use. Later code improved the highest-traffic quiz renderer: dynamic question/option/explanation strings are escaped through `swsiEsc`/`swsiEscLines` in the safe override.

However the base application still contains renderers such as `renderProgress()` that interpolate dynamic values into HTML directly. Example: subject labels from computed history are inserted as `${subj}` inside `accHTML`, which is later assigned through `app.innerHTML`.

This alone is not enough to claim a practical exploit from every source — source reachability and upstream sanitization matter — but it proves that the application has **not** been converted to a consistently safe rendering contract.

There is also no recorded adversarial browser test demonstrating that malicious payloads cannot survive through:

- remote question metadata → history → progress;
- cached auto data → renderers;
- trust/knowledge/law renderers;
- feedback/state surfaces;
- stored local browser state.

**Classification:** **PARTIALLY MITIGATED / NOT PROVEN**, P1. Do not mark full-app XSS closed until all reachable dynamic sinks are escaped/textContent-based and an adversarial browser smoke passes.

## 5. SEO and accessibility

### 5.1 Basic SEO/document metadata

Current `index.html` has:

- `<!DOCTYPE html>`
- `<html lang="zh-Hant">`
- UTF-8 charset
- responsive viewport
- `<title>社工師國考題庫</title>`
- PWA/mobile metadata, manifest and icons
- theme color

No `<meta name="description">` was found. No `<link rel="canonical">` was found; occurrences of the word `canonical` in the file are application data-normalization functions, not a head canonical link.

Open Graph/Twitter social metadata was not established in this audit.

**Classification:** basic semantics **PARTIAL**, missing search/social metadata is P2 polish rather than a release blocker.

### 5.2 Keyboard/accessibility contract

ARIA usage is sparse; the visible search icon has `aria-label="搜尋"`, and the storage warning uses `role="alert"`. But a repo-wide inspection of the effective base file found no `tabindex` token.

Core quiz choices are rendered as clickable `<div class="opt" ... onclick="pick(...)" ...>` elements rather than native buttons/radios, and multiple navigation/card surfaces use the same clickable-div pattern. Without `tabindex`, keyboard activation handlers, and state semantics (`aria-checked`, radio group, etc.), those controls are not equivalent to native keyboard-accessible controls.

This matters to the primary student task, not only decorative UI.

**Classification:** **STILL PRESENT**, P1 accessibility issue.

A proper fix should prefer native `<button>` / `<input type="radio">` semantics where practical rather than layering ad-hoc key handlers over many divs, then run keyboard-only browser smoke and an automated accessibility scan.

## 6. Updated release-gate interpretation

This round does not establish a new grading P0. The important remaining release concerns are P1 and process-oriented:

1. Cloudflare preview run currently red at publish; live validation skipped.
2. Cloudflare preview workflow is not safely isolated from `main` promotion semantics.
3. localStorage answer-event history remains unbounded.
4. named Supabase recovery/source-of-truth consolidation is stale relative to later production schema.
5. full-app XSS closure is not proven beyond the improved quiz path.
6. primary quiz controls are not keyboard-accessible by current markup.

SEO metadata gaps are P2.

Before calling the codebase broadly release-ready, the final gate should require at minimum:

- green syntax/static QA;
- green grading-contract smoke;
- green browser interaction smoke;
- adversarial XSS smoke;
- storage/quota/migration smoke;
- reproducible Supabase recovery test;
- green isolated preview/live smoke;
- keyboard accessibility smoke for the primary quiz flow.

No production, Netlify, Supabase, Cloudflare, `main`, or `fix/code-health-p0-20260826` repair code was changed by this audit entry.

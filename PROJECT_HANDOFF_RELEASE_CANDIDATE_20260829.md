# SWSI Release Candidate Handoff — 2026-08-29

> Read `PROJECT_HANDOFF.md` first. This delta is newer and wins when release-candidate state conflicts with older handoff text.

## Goal

Public release target: before 2026-09-01.

Do not add new student features. Prioritize P0/P1 release closure. Do not merge main or deploy Netlify production without explicit maintainer approval.

## Current Git state

- Repo: `grizzly020503/swsi-quiz-backup`
- Base: `main`
- main known SHA at this checkpoint: `63e1e3b0537f688e4b63ee5b095281bab36ccb5e`
- Release-candidate PR: #33
- Branch: `ux/simplify-learning-center-preview-fresh-20260829`
- PR title: `Release candidate: simplify SWSI learning UX and harden admin/feedback ops`
- PR remains Draft and mergeable.
- Re-read PR HEAD before every write; SHA changes during closeout.

## Release-candidate scope

Student-facing:
- simplified 練題 / 學習 / 申論 IA
- focused home
- direct Learning Center route without loading all 4,800 questions just to open the hub
- Layer 1 canonical layout foundation + Layer 2 page templates
- quiz focus mode intentionally hides footer/bottom navigation during active answering
- mobile/footer/cache-bust cleanup

Admin / operations:
- Netlify publishes `admin/`
- password recovery hard-gate before dashboard load
- grouped feedback admin view
- feedback triage policy and automation
- strict Preview CORS support for admin + feedback Edge Functions

## Official-data invariants

Do not change without new official evidence:
- questions: 4,800
- multi-answer: 24
- standard: 4,784
- all_credit: 12
- any_answer: 4

Known any_answer IDs remain:
- `SW-105-1-17`
- `SW-106-1-36`
- `HBSE-108-2-039`
- `HBSE-110-2-034`

## Supabase production state changed during release closeout

### `swsi-feedback`
Production Edge Function advanced to v4.

Origin policy:
- `https://swsi-quiznetlify.netlify.app`
- `https://wandering-wave-4418.c022050333.workers.dev`
- strict regex only for `https://deploy-preview-<number>--swsi-quiznetlify.netlify.app`
- no wildcard `*`

Existing feedback controls remain:
- POST/OPTIONS only
- JSON only
- 20 KB payload cap
- category/context/source allowlists
- stable anonymous client hash
- 3/minute and 30/day DB-side rate limits
- service-role remains server-side only

Repo source `supabase/functions/swsi-feedback/index.ts` was synchronized to deployed v4 behavior.

### `swsi-admin`
Production Edge Function is v5 with `verify_jwt=true`.

It retains:
- valid Supabase JWT requirement
- `swsi_admin_users` membership check
- strict production/Worker/Netlify Preview origins
- GET/PATCH only

v5 adds/retains:
- feedback clustering from `metadata.triage`
- deterministic fallback clustering
- normalized risk values
- latest 1,000 feedback rows for aggregation
- only latest 100 raw rows returned to old feedback list
- resolved clusters hidden from active cluster workbench

Important: deployed v5 had drifted ahead of repo source. During this closeout, `supabase/functions/swsi-admin/index.ts` was synchronized back to deployed v5 behavior. Do not redeploy an older source.

## Feedback triage automation

Automation: `SWSI Feedback Triage`

Current intent:
- enabled
- hourly
- pre-group in SQL before semantic analysis
- max 50 clusters / 500 rows per run
- max 5 representative messages per deterministic cluster
- LOW strong-evidence issues may produce dedicated Draft PR only
- MEDIUM/HIGH create/update Issues only
- never auto-merge
- never auto-change official answers/grading/legal/auth/security/migrations/secrets
- daily summary is folded into the 19:00 Asia/Taipei hourly run

Synthetic contract was verified previously. Synthetic report #7 was deleted during release closeout.

Production feedback table at this checkpoint has zero rows with `metadata.synthetic_test=true`.

`FEEDBACK_TRIAGE_POLICY.md` now explicitly includes `action=test_only` for synthetic verification only.

## QA evidence

### Netlify Deploy Preview
PR #33 Preview continues to deploy successfully.

`netlify.toml` build is meaningful QA, not a blind copy. It runs:
- `scripts/admin_auth_build.py`
- recovery-gate build assertions
- grouped feedback JS syntax
- essay-guide runtime build
- `node --check` on generated runtime
- P0 frontend preflight
- monthly frontend static smoke
- `scripts/first_paint_static_qa.py`
- runtime cache bust

`first_paint_static_qa.py` now also fail-closes on the strict feedback Preview-origin source contract.

### GitHub Actions external blocker
Multiple GitHub-hosted Actions workflows currently fail before executing any step.

Observed evidence on new PR commits:
- workflow run conclusion: failure
- jobs created
- `steps=[]` / `steps=null`
- job log blob does not exist (404)
- affects multiple unrelated workflows at once
- scheduled main workflows have shown the same execution-layer symptom

Therefore do not interpret these red checks as product test assertion failures.

Treat as:
`BLOCKED_BY_ACCOUNT_CONFIGURATION_OR_GITHUB_RUNNER_EXECUTION_LAYER`

Do not mutate product code merely to clear these no-step failures.

Once account/runner execution is restored, rerun the full relevant QA suite.

## Remaining release gates

1. GitHub-hosted Actions must execute real steps again, or maintainer explicitly accepts a release with this external CI outage after sufficient alternate evidence.
2. Preview Feedback must be manually submitted once from PR #33 UI and confirmed as HTTP 201 / DB receipt, then any test row must be removed.
3. Admin password recovery must be manually rechecked once on newest Preview: recovery email -> Preview admin -> forced new-password UI -> update password -> dashboard.
4. Final `main...PR#33` secret/artifact/debug scan.
5. Confirm official question/grading invariants immediately before merge.
6. Keep PR Draft until explicit release approval.
7. Production Netlify remains untouched until explicit approval.

## Stop rule

Do not chase cosmetic 98/99/100 scores by introducing new refactors. If release gates are satisfied and score is at least 95/100 with no P0 blocker, stop changing code and proceed to explicit merge/deploy decision.

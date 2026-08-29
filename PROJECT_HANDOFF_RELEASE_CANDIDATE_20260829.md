# SWSI Release Candidate Handoff — 2026-08-29

> Read `PROJECT_HANDOFF.md` first. This delta is newer and wins when release-candidate state conflicts with older handoff text.

## Goal
Public release target: before 2026-09-01. Do not add new student features. Prioritize P0/P1 release closure. Do not merge main or deploy Netlify production without explicit maintainer approval.

## Current Git state
- Repo: `grizzly020503/swsi-quiz-backup`
- Base: `main`
- main known SHA: `63e1e3b0537f688e4b63ee5b095281bab36ccb5e`
- Release-candidate PR: #33
- Branch: `ux/simplify-learning-center-preview-fresh-20260829`
- PR title: `Release candidate: simplify SWSI learning UX and harden admin/feedback ops`
- PR remains Draft and mergeable.
- Re-read PR HEAD before every write.

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
Latest production recheck passed exactly:
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

Do not change these without new official evidence.

## Supabase production state
### `swsi-feedback`
Production Edge Function is currently v7.
Origin policy:
- `https://swsi-quiznetlify.netlify.app`
- `https://wandering-wave-4418.c022050333.workers.dev`
- strict regex only for `https://deploy-preview-<number>--swsi-quiznetlify.netlify.app`
- no wildcard `*`

Controls retained:
- POST/OPTIONS only
- JSON only
- 20 KB payload cap
- category/context/source allowlists
- stable anonymous client hash
- 3/minute and 30/day DB-side rate limits
- service-role server-side only

Repo source `supabase/functions/swsi-feedback/index.ts` is canonical for this behavior. Versions v5-v7 were equivalent redeploys during source/production alignment; no additional permission broadening was introduced.

### `swsi-admin`
Production Edge Function is v5 with `verify_jwt=true`.
It retains:
- valid Supabase JWT requirement
- `swsi_admin_users` membership check
- strict production/Worker/Netlify Preview origins
- GET/PATCH only
- feedback clustering from `metadata.triage`
- deterministic fallback clustering
- normalized risk values
- latest 1,000 feedback rows for aggregation
- latest 100 raw feedback rows only
- resolved clusters hidden from active workbench

Repo source has been synchronized to deployed v5 behavior. Do not redeploy an older source.

## Feedback triage automation
Automation: `SWSI Feedback Triage`
Verified state:
- enabled, hourly
- SQL pre-group before semantic analysis
- max 50 clusters / 500 rows per run
- max 5 representative messages per deterministic cluster
- LOW strong-evidence -> dedicated Draft PR only
- MEDIUM/HIGH -> Issue only
- never auto-merge
- never auto-change official answers/grading/legal/auth/security/migrations/secrets
- daily summary folded into the 19:00 Asia/Taipei hourly run

Synthetic contract was verified. Synthetic report #7 was deleted.
Latest production feedback check:
- synthetic test rows: 0
- pending feedback: 0

## QA evidence
### Netlify Deploy Preview
Strengthened alternate release QA passed on `b4b604ef655c6148f17a1f5b8c533bc868739fdb`.

The successful Netlify build executed:
- `scripts/admin_auth_build.py`
- recovery-gate build assertions
- grouped feedback JS syntax
- essay-guide runtime build
- generated runtime syntax checks
- P0 frontend preflight
- `scripts/runtime_owner_smoke.js`
- `scripts/supabase_contract_smoke.js`
- `scripts/unified_question_qa_selftest.py`
- `scripts/official_exam_readonly_guard.py`
- monthly frontend static smoke
- `scripts/first_paint_static_qa.py`
- runtime cache bust

The four added non-browser release checks are read-only and need neither external network nor Playwright.

`first_paint_static_qa.py` additionally fail-closes on strict admin/feedback Preview origins, no wildcard CORS, admin JWT verification, `swsi_admin_users` membership, grouped feedback aggregation, and raw feedback cap.

### Final diff / secret / artifact scan
PASS through student/runtime HEAD `5ea7565a82219ba8573f197f6992ef2547855b1e`; later closeout changes were release docs and Netlify QA command only.

Verified:
- only expected source / QA / docs / admin / Supabase function files changed
- no `_site`, archive, screenshot, tmp output, generated test artifact, or accidental release junk
- no private-key literal
- no GitHub PAT pattern
- no OpenAI-style `sk-` token literal
- no AWS `AKIA` key literal
- no JWT-like `eyJ` literal
- `SUPABASE_SERVICE_ROLE_KEY` only as env-var name; no service-role value committed
- no `debugger`
- `console.log` additions are QA success markers only
- production DB has zero synthetic feedback rows

### GitHub Actions external blocker
GitHub-hosted jobs continue failing before any step executes:
- jobs created
- `steps=[]` / `steps=null`
- `runner_id=0`
- no job log blob
- multiple unrelated PR and scheduled-main workflows affected
- GitHub public status reports Actions operational

Classification:
`BLOCKED_BY_ACCOUNT_CONFIGURATION_OR_GITHUB_RUNNER_EXECUTION_LAYER`

Do not alter product/workflow assertions merely to clear these no-step failures. Check GitHub Billing & licensing / metered Actions usage / budgets. Once runner execution is restored, rerun the full relevant GitHub-hosted QA suite.

## Remaining release gates — only these remain
1. **EXTERNAL:** restore GitHub-hosted runner execution, OR maintainer explicitly accepts release with this external CI outage after reviewing the successful alternate QA evidence.
2. **MANUAL E2E:** submit one Feedback report from PR #33 Preview UI; confirm DB receipt; remove the test row.
3. **MANUAL E2E:** newest Preview password recovery: recovery email -> forced new-password screen -> update password -> dashboard.
4. Explicit maintainer decision to merge/deploy. Until then PR remains Draft and Netlify production remains untouched.

## Completed release gates
- official question/grading invariants: PASS
- final secret/artifact/debug scan: PASS
- synthetic feedback cleanup: PASS
- Feedback Triage enabled: PASS
- strict Preview CORS contract: PASS
- admin/feedback Edge Function source-of-truth restored: PASS
- strengthened Netlify alternate release QA: PASS
- Netlify Deploy Preview: PASS

## Stop rule
Do not chase cosmetic 98/99/100 scores by introducing new refactors. Once the remaining gates are satisfied and release score is at least 95/100 with no unaccepted P0 blocker, stop changing code and proceed only to explicit merge/deploy decision.

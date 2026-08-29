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

Latest production recheck during closeout reconfirmed all counts and IDs above exactly.

## Supabase production state changed during release closeout

### `swsi-feedback`
Production Edge Function is currently v7.

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

Repo source `supabase/functions/swsi-feedback/index.ts` is the canonical source for this strict Preview-origin behavior. Versions v5-v7 were equivalent redeploys during source/production alignment; no additional permission broadening was introduced.

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

Current verified state:
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

Production feedback table latest check:
- synthetic test rows: 0
- pending feedback: 0

`FEEDBACK_TRIAGE_POLICY.md` explicitly includes `action=test_only` for synthetic verification only.

## QA evidence

### Netlify Deploy Preview
PR #33 Preview deploy succeeded on runtime/QA HEAD `b4b604ef655c6148f17a1f5b8c533bc868739fdb` after strengthening the alternate release gate.

`netlify.toml` build is meaningful QA, not a blind copy. It now runs:
- `scripts/admin_auth_build.py`
- recovery-gate build assertions
- grouped feedback JS syntax
- essay-guide runtime build
- `node --check` on generated runtime
- P0 frontend preflight
- `scripts/runtime_owner_smoke.js`
- `scripts/supabase_contract_smoke.js`
- `scripts/unified_question_qa_selftest.py`
- `scripts/official_exam_readonly_guard.py`
- monthly frontend static smoke
- `scripts/first_paint_static_qa.py`
- runtime cache bust

The four added non-browser release checks all executed successfully because the Netlify deploy completed successfully. They are intentionally read-only and do not require external network or Playwright.

`first_paint_static_qa.py` fail-closes on:
- strict feedback Preview-origin source contract
- strict admin Preview-origin source contract
- admin JWT session verification
- `swsi_admin_users` membership verification
- grouped-feedback aggregation contract
- raw feedback cap
- wildcard CORS regression

### Final diff / secret / artifact scan

Completed against `main...PR#33` through runtime HEAD `5ea7565a82219ba8573f197f6992ef2547855b1e`; subsequent closeout commits through `b4b604e...` only changed the release handoff and Netlify QA command, not student runtime or official data.

Evidence:
- changed files were all expected source / QA / docs / admin / Supabase function files
- no `_site`, archive, screenshot, tmp output, generated test artifact, or other accidental release junk in changed filenames
- no private-key literal
- no GitHub PAT pattern
- no OpenAI-style `sk-` token literal
- no AWS `AKIA` key literal
- no JWT-like `eyJ` literal
- `SUPABASE_SERVICE_ROLE_KEY` appears only as an environment-variable name; no service-role value is committed
- no `debugger`
- `console.log` additions are QA success markers only
- synthetic-test references are policy/handoff documentation only; production DB contains zero synthetic rows

### GitHub Actions external blocker
Multiple GitHub-hosted Actions workflows currently fail before executing any step.

Latest observed evidence includes:
- workflow run conclusion: failure
- jobs created
- `steps=[]` / `steps=null`
- `runner_id=0` / no assigned runner
- job log blob does not exist (404)
- affects multiple unrelated PR workflows at once
- scheduled main workflows have shown the same execution-layer symptom
- GitHub public status reports Actions operational, so this does not look like a platform-wide Actions incident

Therefore do not interpret these red checks as product test assertion failures.

Treat as:
`BLOCKED_BY_ACCOUNT_CONFIGURATION_OR_GITHUB_RUNNER_EXECUTION_LAYER`

Do not mutate product code merely to clear these no-step failures.

For a private repository, GitHub-hosted Actions consume the repository owner's included minutes / metered budget. If included usage is exhausted without payable overage, or an applicable budget stops usage, GitHub may block further hosted-runner usage. Check GitHub Billing & licensing / metered usage / budgets before changing workflow code.

Once account/runner execution is restored, rerun the full relevant QA suite.

## Remaining release gates

1. **EXTERNAL BLOCKER:** GitHub-hosted Actions must execute real steps again, or maintainer explicitly accepts release with this external CI outage after sufficient alternate evidence.
2. **MANUAL E2E:** Preview Feedback must be submitted once from PR #33 UI and confirmed by DB receipt, then the test row must be removed.
3. **MANUAL E2E:** Admin password recovery must be rechecked once on newest Preview: recovery email -> Preview admin -> forced new-password UI -> update password -> dashboard.
4. Keep PR Draft until explicit release approval.
5. Production Netlify remains untouched until explicit approval.

Completed release gates:
- final `main...PR#33` secret/artifact/debug scan: PASS
- official question/grading production invariants: PASS
- synthetic feedback cleanup: PASS
- Feedback Triage enabled: PASS
- strict Preview CORS source/deployment contract: PASS
- strengthened Netlify alternate release QA: PASS on `b4b604e...`
- Netlify Deploy Preview build: PASS on `b4b604e...`

## Stop rule

Do not chase cosmetic 98/99/100 scores by introducing new refactors. If release gates are satisfied and score is at least 95/100 with no P0 blocker, stop changing code and proceed to explicit merge/deploy decision.

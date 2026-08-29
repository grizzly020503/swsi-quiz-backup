# SWSI Release Candidate Handoff — 2026-08-29

> Read `PROJECT_HANDOFF.md` first. This delta is newer and wins when release-candidate state conflicts with older handoff text.

## Goal
Public release target: before 2026-09-01. No new student features. Finish P0/P1 release closure only. Do not merge main or deploy Netlify production without explicit maintainer approval.

## Current state
- Repo: `grizzly020503/swsi-quiz-backup`
- Base: `main`
- main known SHA: `63e1e3b0537f688e4b63ee5b095281bab36ccb5e`
- PR #33: `Release candidate: simplify SWSI learning UX and harden admin/feedback ops`
- Branch: `ux/simplify-learning-center-preview-fresh-20260829`
- PR remains Draft and mergeable.
- Re-read PR HEAD before every write.

## Scope
Student-facing: simplified 練題 / 學習 / 申論 IA, focused home, direct Learning Center, canonical layered layout, quiz focus mode, mobile/footer/cache-bust cleanup.

Admin/ops: Netlify-published admin, password-recovery hard gate, grouped feedback, feedback triage policy/automation, strict Preview CORS for admin and feedback Edge Functions.

## Production invariants — rechecked PASS
- questions 4,800
- multi-answer 24
- standard 4,784
- all_credit 12
- any_answer 4
- any_answer IDs: `SW-105-1-17`, `SW-106-1-36`, `HBSE-108-2-039`, `HBSE-110-2-034`

Do not change without new official evidence.

## Supabase production
### `swsi-feedback`
- ACTIVE v7
- production + known Worker + strict `deploy-preview-<number>--swsi-quiznetlify.netlify.app` origins only
- no wildcard CORS
- POST/OPTIONS only, JSON only, 20 KB cap
- category/context/source allowlists
- anonymous client hash
- DB-side 3/minute + 30/day limits
- service-role server-side only
- repo `supabase/functions/swsi-feedback/index.ts` is canonical source for this behavior

### `swsi-admin`
- ACTIVE v5, `verify_jwt=true`
- valid JWT + `swsi_admin_users` membership required
- strict production/Worker/Preview origins
- GET/PATCH only
- grouped feedback, deterministic fallback clustering, normalized risk
- aggregate latest 1,000 rows, raw list capped to 100, resolved clusters hidden
- repo source synchronized to deployed v5 behavior

## Feedback triage — verified
`SWSI Feedback Triage` is enabled hourly.
- SQL pre-group first
- max 50 clusters / 500 rows per run
- max 5 representative messages per cluster
- LOW strong evidence -> Draft PR only
- MEDIUM/HIGH -> Issue only
- never auto-merge
- never auto-change official answers/grading/legal/auth/security/migrations/secrets
- synthetic contract verified; synthetic #7 removed
- production synthetic rows 0; pending feedback 0 at latest check

## Alternate release QA — PASS
GitHub-hosted runners are externally blocked, so Netlify Preview was strengthened with read-only fail-closed release checks.

Successful Preview build on `b4b604ef655c6148f17a1f5b8c533bc868739fdb` executed:
- admin auth recovery build assertions
- grouped feedback syntax
- essay-guide/runtime syntax
- P0 frontend preflight
- `runtime_owner_smoke.js`
- `supabase_contract_smoke.js`
- `unified_question_qa_selftest.py`
- `official_exam_readonly_guard.py`
- monthly frontend static smoke
- `first_paint_static_qa.py`
- cache bust

`first_paint_static_qa.py` also guards strict admin/feedback Preview origins, no wildcard CORS, admin JWT verification, admin membership check, grouped feedback aggregation and raw-row cap.

## Final diff / secret / artifact scan — PASS
Runtime diff through `5ea7565a82219ba8573f197f6992ef2547855b1e` passed; later commits are closeout docs / QA-command changes.

No private key, PAT, `sk-`, AWS key, JWT literal, service-role value, debugger, tmp/generated release junk, `_site`, archive or screenshot artifact found. `SUPABASE_SERVICE_ROLE_KEY` appears only as an environment-variable name. Production DB has zero synthetic feedback rows.

## GitHub Actions external blocker
Multiple unrelated GitHub-hosted jobs fail before execution:
- `steps=[]` / `steps=null`
- `runner_id=0`
- no log blob
- PR and scheduled-main workflows affected
- GitHub public status reports Actions operational

Classification: `BLOCKED_BY_ACCOUNT_CONFIGURATION_OR_GITHUB_RUNNER_EXECUTION_LAYER`.

Do not mutate product code to clear these no-step failures. Check GitHub Billing & licensing / Actions metered usage / budgets. Once runner execution is restored, rerun full GitHub-hosted QA.

## Remaining release gates — only these
1. Restore GitHub-hosted runner execution, **or** maintainer explicitly accepts release with this external CI outage based on the successful alternate QA evidence.
2. Manual Preview Feedback E2E: submit one report from PR #33 UI -> confirm DB receipt -> remove test row.
3. Manual Admin recovery E2E: newest Preview recovery email -> forced new-password screen -> update password -> dashboard.
4. Explicit maintainer merge/deploy approval. Until then PR stays Draft and Netlify production remains untouched.

## Stop rule
Do not chase cosmetic 98/99/100 changes. Once the remaining gates are satisfied and score is at least 95/100 with no unaccepted P0 blocker, stop changing code and proceed only to explicit merge/deploy decision.

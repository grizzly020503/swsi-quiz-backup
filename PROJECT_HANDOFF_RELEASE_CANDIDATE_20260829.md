# SWSI Release Candidate Handoff — 2026-08-29

> Read `PROJECT_HANDOFF.md` first. This delta is newer and wins when release-candidate state conflicts with older handoff text.

## Goal
Public release target: before 2026-09-01. No new student features. Finish P0/P1 release closure only. Do not merge `main` or deploy Netlify production without explicit maintainer approval.

## Current state
- Repo: `grizzly020503/swsi-quiz-backup`
- Base: `main`
- main known SHA: `63e1e3b0537f688e4b63ee5b095281bab36ccb5e`
- PR #33: `Release candidate: simplify SWSI learning UX and harden admin/feedback ops`
- Branch: `ux/simplify-learning-center-preview-fresh-20260829`
- PR remains Draft and mergeable.
- Re-read PR HEAD before every write.

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

### `swsi-admin`
- ACTIVE v5, `verify_jwt=true`
- valid JWT + `swsi_admin_users` membership required
- strict production/Worker/Preview origins
- GET/PATCH only
- grouped feedback, deterministic fallback clustering, normalized risk
- aggregate latest 1,000 rows, raw list capped to 100, resolved clusters hidden

## Feedback triage — PASS
`SWSI Feedback Triage` is enabled hourly and has executed successfully.
- SQL pre-group first
- max 50 clusters / 500 rows per run
- max 5 representative messages per cluster
- LOW strong evidence -> Draft PR only
- MEDIUM/HIGH -> Issue only
- never auto-merge
- never auto-change official answers/grading/legal/auth/security/migrations/secrets
- synthetic contract verified
- production synthetic rows 0
- production pending feedback 0 at latest check

## Preview Feedback E2E — PASS
Manual iPhone/Safari verification completed against PR #33 Preview.
- Preview report reached `swsi-feedback` and production Supabase as report #8.
- Preview origin was accepted by the strict CORS rule.
- Test row was deleted immediately after verification.
- Post-cleanup: pending feedback 0; synthetic / feedback-e2e test rows 0.
- Safari AutoFill false-positive in the legacy honeypot was fixed inside the existing feedback context owner.
- Post-fix Netlify Preview build passed.

## Admin recovery E2E — PASS
Manual real-email recovery verification completed against PR #33 Preview.
- A newly generated Supabase recovery email pointed to the Preview admin route with `adminAuth=1` and `authMode=recovery`.
- Recovery flow forced the new-password screen instead of loading the dashboard directly.
- Maintainer successfully changed the password.
- Dashboard became available only after password update completed.

This verifies the recovery gate in the real email/browser path, not only static build assertions.

## Alternate release QA — PASS
GitHub-hosted runners are externally blocked, so Netlify Preview is carrying a strengthened fail-closed alternate release gate.

Latest runtime Preview build passed checks including:
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

Latest runtime PR-head Netlify deploy-preview status is successful.

## Final diff / secret / artifact scan — PASS
Final `main...PR#33` review found no committed private credential value.
- no private key marker
- no GitHub PAT prefix
- no AWS access-key prefix
- no JWT literal
- no `SUPABASE_SERVICE_ROLE_KEY=` value
- public Supabase publishable key is expected client configuration, not a secret
- no synthetic feedback row remains in production DB
- no release-blocking tmp/generated artifact identified in the PR changed-file set

Do not weaken this boundary during merge/deploy.

## GitHub Actions external blocker
Multiple unrelated GitHub-hosted jobs still fail before executing any workflow step.
Observed on the latest affected runs:
- `labels=["ubuntu-latest"]`
- `runner_id=0`
- `runner_name=""`
- `steps=[]`
- no job log blob
- failure occurs within seconds of job creation
- PR QA and scheduled-main workflows are both affected

Classification: `BLOCKED_BY_ACCOUNT_CONFIGURATION_OR_GITHUB_RUNNER_EXECUTION_LAYER`.

There is no evidence that these runs are failing an SWSI assertion; they never start the workflow steps. Do not mutate product code to clear this state. Check GitHub Actions usage / billing / budget / account execution eligibility, then rerun the hosted suite when runner execution is restored.

## Release score
Current evidence-based score: **96/100**.

The product itself clears the 95-point release target. The remaining deduction is almost entirely the unavailable GitHub-hosted CI execution layer, plus the fact that production has not yet been updated to this release candidate.

Do not chase cosmetic 98/99/100 changes before release. Restoring hosted Actions and verifying production after deploy are the correct paths to 98–99.

## Remaining release gates — only these
1. Restore GitHub-hosted runner execution, **or** maintainer explicitly accepts release with this external CI outage based on the successful alternate QA evidence.
2. Explicit maintainer approval to merge PR #33.
3. Explicit maintainer approval to deploy production.
4. After deployment, run production smoke verification and recheck the official question/grading invariants.

Until explicit approval, PR stays Draft and Netlify production remains untouched.

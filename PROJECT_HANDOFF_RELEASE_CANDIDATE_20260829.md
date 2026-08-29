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

## Release evidence — PASS
- Production question/grading invariants: 4,800 questions / 24 multi-answer / 4,784 standard / 12 all_credit / 4 any_answer.
- Preview Feedback E2E: PASS on iPhone/Safari; test report reached Supabase and was removed.
- Admin recovery E2E: PASS using a newly generated recovery email; new-password screen was forced before dashboard access and password update completed successfully.
- Feedback triage automation: enabled hourly; synthetic rows 0; pending feedback 0 at latest check.
- Netlify alternate release gate: PASS on the latest runtime build.
- Final diff/secret/artifact scan: PASS; no private credential value identified.

## GitHub Actions external blocker
Multiple unrelated GitHub-hosted jobs fail before executing workflow steps: `runner_id=0`, empty runner name, `steps=[]`, no job log. PR QA and scheduled-main workflows are both affected. Classification: `BLOCKED_BY_ACCOUNT_CONFIGURATION_OR_GITHUB_RUNNER_EXECUTION_LAYER`.

Do not mutate product code to clear this state. Restore Actions usage/billing/budget/account execution eligibility and rerun hosted QA when runner execution is available.

## Release score
Evidence-based release score: **96/100**.

The release clears the 95-point target. The main deduction is the unavailable GitHub-hosted CI execution layer and the fact that production has not yet been deployed and smoke-verified. Restoring hosted Actions plus successful production verification are the legitimate path toward 98–99; do not chase cosmetic changes.

## Remaining gates
1. Restore GitHub-hosted runner execution, **or** maintainer explicitly accepts release with that external CI outage based on the successful alternate QA evidence.
2. Explicit maintainer approval to merge PR #33.
3. Explicit maintainer approval to deploy production.
4. After deployment, run production smoke verification and recheck official question/grading invariants.

Until explicit approval, PR stays Draft and Netlify production remains untouched.

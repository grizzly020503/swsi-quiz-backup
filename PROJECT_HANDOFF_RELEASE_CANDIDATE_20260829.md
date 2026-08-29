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

## GitHub Actions blocker — ROOT CAUSE CONFIRMED
GitHub-hosted jobs fail before executing workflow steps with `runner_id=0`, empty runner name, `steps=[]`, and no job log because the personal account has exhausted its included Actions allowance.

GitHub account notification received 2026-08-29 confirms:
- plan includes 2,000 Actions minutes per billing cycle
- 2,000 / 2,000 minutes used (100%)
- included usage resets on 2026-09-01
- usage beyond the included amount requires billable Actions eligibility; a $0 Actions budget blocks further usage until reset

Therefore this is not a SWSI workflow/YAML/product-code failure. Do not mutate product code to clear it.

To restore GitHub-hosted CI before the 2026-09-01 reset, the maintainer must use GitHub Billing settings to ensure a valid payment method and a non-zero Actions budget / spending allowance. Otherwise wait for the included usage reset on 2026-09-01.

Once hosted runner eligibility is restored, rerun the failed PR #33 workflows and require real executable steps plus passing results before choosing the strict release path.

## Release score
Evidence-based release score before hosted CI restoration: **96/100**.

Restoring hosted Actions and passing the full suite is the legitimate path toward 98–99; do not chase cosmetic changes.

## Remaining gates — strict path selected
1. Restore GitHub-hosted runner execution by billing/budget eligibility, or wait for the 2026-09-01 allowance reset.
2. Rerun PR #33 hosted QA and require all relevant workflows to execute real steps and pass.
3. Recheck final PR HEAD / diff after the hosted QA run.
4. Explicit maintainer approval to merge PR #33.
5. Explicit maintainer approval to deploy production.
6. After deployment, run production smoke verification and recheck official question/grading invariants.

Until explicit approval, PR stays Draft and Netlify production remains untouched.

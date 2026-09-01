# SWSI Release Candidate Handoff — 2026-08-29

> Read `PROJECT_HANDOFF.md` first. This delta is newer and wins when release-candidate state conflicts with older handoff text.
> Long-term operations policy: read `ZERO_COST_OPERATIONS.md` before changing CI/sync/monitoring cadence or adding recurring infrastructure cost.

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

## Zero-cost long-term operating policy
The maintainer has explicitly selected a **no-recurring-payment operating model**. Do not require paid GitHub Actions, paid infrastructure, or paid AI capacity to keep the student-facing core usable.

Canonical policy: `ZERO_COST_OPERATIONS.md`.

Key rules:
- Student core (practice, mock exam, review/progress, essay writing/local drafts) must continue when GitHub Actions or non-core automation is unavailable.
- AI, Admin, Feedback triage, MOEX sync, shard publish, and CI are enhancement/maintenance layers and must fail/degrade without breaking core study.
- Prefer local-first student state; avoid unnecessary server writes and unnecessary personal analytics.
- Preserve last verified official corpus/shards if sync/publish is unavailable.
- Do not pay by default when a free-tier allowance is exhausted; pause non-essential automation and wait for reset when reasonable.
- GitHub Actions should operate in a conservation mode after release: cheap static/invariant checks first, path-filter unrelated changes, cancel superseded runs, and reserve full browser QA for meaningful release candidates or high-risk changes.
- Normal maintenance target: leave at least 70–80% of the monthly included GitHub Actions allowance unused whenever practical.
- MOEX checking should normally be low-frequency (for example weekly), with temporary higher frequency only near a known exam-release window.
- Question shards should publish only when deterministic content/version checks show a verified change.

## GitHub Actions blocker — ROOT CAUSE CONFIRMED
GitHub-hosted jobs fail before executing workflow steps with `runner_id=0`, empty runner name, `steps=[]`, and no job log because the personal account has exhausted its included Actions allowance.

GitHub account notification received 2026-08-29 confirms:
- plan includes 2,000 Actions minutes per billing cycle
- 2,000 / 2,000 minutes used (100%)
- included usage resets on 2026-09-01
- usage beyond the included amount requires billable Actions eligibility; a $0 Actions budget blocks further usage until reset

Therefore this is not a SWSI workflow/YAML/product-code failure. Do not mutate product code to clear it.

**Maintainer decision:** do not add paid Actions capacity. Wait for the included allowance reset on 2026-09-01, then use the free minutes for one deliberate release-candidate hosted QA pass.

After reset, rerun only the release-relevant PR #33 workflows, verify that real runner steps execute, and require passing results before merge under the selected strict path. Do not burn the restored allowance on cosmetic or redundant reruns.

## Release score
Evidence-based release score before hosted CI restoration: **96/100**.

Restoring the free hosted allowance and passing the full release suite is the legitimate path toward 98–99; do not chase cosmetic changes.

## Remaining gates — strict zero-cost path selected
1. Wait for the 2026-09-01 GitHub Actions included allowance reset; do not purchase extra minutes.
2. Rerun PR #33 release-relevant hosted QA and require all relevant workflows to execute real steps and pass.
3. Recheck final PR HEAD / diff after the hosted QA run.
4. Explicit maintainer approval to merge PR #33.
5. Explicit maintainer approval to deploy production.
6. After deployment, run production smoke verification and recheck official question/grading invariants.
7. After release, implement/verify the Actions conservation plan in `ZERO_COST_OPERATIONS.md` before returning to ordinary feature work.

Until explicit approval, PR stays Draft and Netlify production remains untouched.

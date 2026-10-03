# Remaining QA push duplication — 2026-10-03

## Scope and state
- Owner requested continued progress only on unfinished work after reviewing other AI work, with about 10% Actions budget remaining (owner estimate; billing not independently verified).
- Implementer scope: remaining duplicate feature-branch QA triggers only.
- Audit baseline: `fe02f59f8f1cddb4ce4e9480b3fa7aacc06ef70f`. Publication base re-read: `07932ea266f18c86ff108983299ea61bd1c06c63`; its only new commit merges #323 and changes nine current-affairs source/snapshot files, none of this patch's workflows.
- Branch: `ci/remaining-qa-budget-20261003`.
- This is a branch-only checkpoint. No PR, merge, deployment, workflow dispatch, or rerun is part of this checkpoint. Savings take effect in main only after review/merge.
- This implements the remaining-work item in `docs/GITHUB_ACTIONS_BUDGET_POLICY_20261002.md`; it does not redo the already merged MOEX/Question Shards fan-out changes.

## Other AI work reviewed before implementation
- Recent main commits include #317 feedback review priority, #318 law study priority, #319 six evidence-adjudicated historical-law records, #320 distinct student trust labels for 19 records, and #321 future-ready law provenance guard. These were not reimplemented.
- Open #322 head `4f67ba4a30237e04c9735d3b7266f772c2c2bd9c` and #323 latest observed head `371823797ad41a88e20ed953fac5fd19b9828572` overlap on `scripts/build_current_affairs_signals_snapshot.py`. Their source diffs were inspected; do not merge both as independent fixes without reconciling.
- #322 filters synonym matches at public snapshot boundary using reason labels and score; #323 changes scoring in the analyzer and applies a public score threshold. Neither is reimplemented by this patch. This is an overlap/source review, not full semantic acceptance of either PR.
- #323 changed during this audit, added rebuilt auto/cdn snapshots, and merged as `07932ea266f18c86ff108983299ea61bd1c06c63` before this checkpoint. #322 remains open at the last re-read. Treat it as an overlapping candidate, not an independent unfinished fix. Older CI failures are not evidence about the merged revision.
- Public Monitoring Feed run `37094469073`, job `111121461517`, failed at “Rebuild deterministic monitoring contracts for PR”: generated `current_affairs_signals.json` differed from tracked `auto/current_affairs_signals.json`. Setup and earlier steps ran successfully; this is a snapshot drift finding, not an Actions-budget/no-step failure. No rerun requested.
- Build Cloudflare Frontend Preview run `37092947312` succeeded for `dcdb524...`. Preview success alone does not establish production parity.
- #261 latest discussion identifies remaining data cleanup/production steps. Those statements were treated as prior evidence, not a fresh production DB check. This task makes no production-data claim.

## Changes
Ten existing QA workflows now accept automatic push only on main; their PR and manual triggers remain:
- `.github/workflows/ai-telemetry-qa.yml`
- `.github/workflows/knowledge-runtime-snapshot.yml`
- `.github/workflows/launch-readiness-qa.yml`
- `.github/workflows/moex-importer-integrity-qa.yml`
- `.github/workflows/monthly-frontend-qa.yml`
- `.github/workflows/priority-law-question-links-qa.yml`
- `.github/workflows/runtime-owner-qa.yml`
- `.github/workflows/storage-durability-qa.yml`
- `.github/workflows/unified-question-qa.yml`
- `.github/workflows/usage-analytics-qa.yml`

- Add cancellation of superseded read-only runs to Unified Question QA, Runtime Owner QA, and Priority Law Question Links QA, scoped by workflow plus PR number/ref.
- Preserve every job, step, permission, action version, path filter on push, and test command.
- Add the previously missing `scripts/prelaunch_axe_accessibility_smoke.js` to Launch Readiness PR paths; otherwise limiting push would have removed pre-merge coverage for an axe-only edit.
- Retained schedules (monitoring, uptime, watchdog, MOEX, full-corpus), deploy/publish flows, and workflows with no equivalent PR trigger are untouched.
- Tag-triggered execution of these ten QA workflows is also no longer automatic, as a consequence of a branches-only push filter. Main/PR/manual validation remain; no tag release flow is modified.

## Local verification
- Parsed all **59** tracked workflow YAML files with PyYAML 6.0.3 (using its YAML 1.1 `on`/True mapping deliberately).
- Structural before/after comparison: exactly ten intended workflow changes; jobs byte content and parsed structures preserved; only branch filter, three concurrency sections, and the one PR path changed.
- All ten push path sets are covered by their PR path sets after the correction.
- Checked the full workflow inventory against this exact changed-path set and branch; no feature-branch push workflow is expected to match.
- Local check does not execute GitHub's scheduler or the browser/DB/runtime suites; those jobs are unchanged and must not be described as newly passed.
- No live AI provider calls or paid services.
- Final commit payload is explicitly limited to the ten workflows plus this audit; downloaded baseline/supporting files are not committed.
- Independent read-only reviewer (AI_COLLABORATION.md Level 1) found no blocking issue in the exact ten workflow changes; confirmed jobs unchanged, PR/dispatch retained, tag suppression, and no expected feature-branch push match. Reviewer did not review this audit text or run CI/production checks.

## Next step
1. Re-read main and open PR heads before preparing a consolidated PR; this branch may age while other AI work continues.
2. Open one PR when the remaining budget is allocated to its existing CI, not one PR per workflow. Do not claim this branch is already merged or saving main's runs.
3. #323 is now merged; reconcile or supersede remaining #322 against current main rather than blindly merging the overlapping fix. Verify main post-merge monitoring results without routine reruns.
4. Continue #261 data-quality gaps using current production evidence and existing gates; no queue acceleration, bulk legal cleanup, or automatic verified promotion is authorized by this workflow patch.

Rollback: revert this one commit; it only changes QA event routing/concurrency and adds this audit.

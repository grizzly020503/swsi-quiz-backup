# SWSI Public Repository — Branch Cleanup Plan

Date: 2026-10-04

## Current inventory

GitHub branch enumeration returned **367 branches**.

This document is a classification plan only. It does **not** authorize branch deletion and does not claim that deleting a branch removes content already reachable from `main` history.

## Never delete automatically

The following branches are protected by role, current work, or deployment responsibility and must be retained until an explicit later review says otherwise:

- `main`
- `chore/public-readiness-20261004`
- `fix/legal-canonical-nfkc-261-20261003` — open PR #326
- `fix/question-trust-metadata-passthrough-20261003` — open PR #328
- `swsi-public-candidate` — Cloudflare public-candidate workflow branch
- `release/cloudflare-public-soft-launch-20260901` — soft-launch release workflow branch

Any future open-PR head branch must automatically move into this protected set.

## Classification gates

A branch may be marked **DELETE CANDIDATE** only when all of the following are true:

1. it is not `main`;
2. it is not the readiness branch;
3. it is not the head of an open PR;
4. it is not referenced by a current workflow as a deployment/release branch;
5. its tip is already reachable from `main`, or the unique commits have been intentionally classified as disposable;
6. it is not the only remaining evidence for an unresolved incident, release, migration, recovery drill, or audit finding;
7. it has passed the complete all-refs history/privacy review, or the owner explicitly accepts making that branch-only history unreachable before Public;
8. no human maintainer has marked it as retained evidence.

If any gate is unknown, classify the branch **REVIEW**, not DELETE.

## High-confidence cleanup candidates by naming pattern

These names strongly indicate temporary/trigger/no-op branches, but still require the gates above before deletion:

- `noop`
- `noop-temp-should-not-create`
- `unused`
- `unused2`
- `ignore`
- `trigger-current-affairs-ui`
- `trigger-uiux-v1`
- `tmp-ai-client-owner-20260827`
- `tmp-ai-client-owner-20260827-v2`
- `tmp-law-status-consolidation-20260827`
- `tmp-law-status-consolidation-20260827-v2`
- `tmp-swsi-context-owner-20260827`

## Likely review buckets

### A. One-shot QA / probe branches

Examples:

- `probe/*`
- `qa/*`
- old `ci/*`

Most should become DELETE CANDIDATE after verifying their evidence is already preserved in `main`, an Issue/PR, an artifact, or an audit document.

### B. Old release branches

Examples:

- `release/current-affairs-*`
- `release/netlify-*`
- old `release/historical-law-*`

Do not retain a release branch only because it has `release/` in the name. Retain it only if a live workflow, rollback procedure, or unresolved audit depends on it.

### C. Old feature/fix branches

Examples:

- `feat/*`
- `fix/*`
- `ux/*`
- `data/*`

If merged or superseded and not referenced by an open PR, these are usually cleanup candidates. Branches tied to unresolved Issues #261, #262, #307, #326, #328, or current public-readiness work require extra review before classification.

### D. Operations / recovery branches

Examples:

- `ops/*`
- `infra/*`

Treat more conservatively. A branch may contain unique disaster-recovery or production evidence. Verify the relevant runbook/report exists on `main` before calling it disposable.

### E. Documentation-only closeout branches

Examples:

- `docs/*closeout*`
- `docs/*handoff*`

Usually safe to remove if the final document is already in `main` and no open PR references the branch.

## Recommended cleanup sequence

1. Run the full all-refs history scanner while all 367 branches are still present.
2. Resolve credential/security findings first.
3. Resolve the historical identity/privacy owner decision.
4. Refresh the open-PR list.
5. Scan current workflow files for explicit non-main branch references.
6. Compare each candidate tip against `main`.
7. Produce a final table: `KEEP / DELETE CANDIDATE / REVIEW`.
8. Delete only branches explicitly approved by the owner.
9. Re-run the branch inventory and history scanner after deletion.
10. Only then perform the final Public visibility review.

## Why scan before deleting

The repository is being audited for what has actually existed across current refs. Running the scanner first gives a complete evidence picture and prevents cleanup from accidentally hiding a branch-only credential/privacy finding before it is understood.

Deletion can reduce the future Public exposure surface, but it is not a substitute for understanding what was committed.

## Public-readiness rule

A high branch count is primarily an exposure/noise/maintenance problem, not proof of a secret leak. SWSI should not rewrite history or delete hundreds of refs just to make the repository look tidy. The cleanup goal is:

- preserve active work;
- preserve necessary recovery/audit evidence;
- remove obsolete disposable refs;
- keep the Public repository understandable;
- avoid creating security theater that hides rather than classifies historical findings.
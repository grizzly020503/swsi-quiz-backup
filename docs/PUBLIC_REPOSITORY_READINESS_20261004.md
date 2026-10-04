# SWSI Public Repository Readiness — 2026-10-04

Status: **YELLOW — prepare for public visibility, but do not flip the repository to Public yet.**

This document records the public-readiness work that can be completed safely without changing production, redeploying the site, or pretending that an incomplete historical audit has passed.

## Baseline checked

- Repository: `grizzly020503/swsi-quiz-backup`
- Baseline `main`: `dd1d73107ae14a9233e2c4558497ca10c495282f`
- Repository visibility at audit time: private
- `main` branch protection at audit time: disabled
- Existing open PRs at audit time: #326 and #328
- This readiness work intentionally does not modify those PRs, Official Core, Supabase production data, deployment configuration, or the student runtime.

## Positive findings already present

The repository already has several useful safety boundaries:

- `.env` / `.env.*`, private backup paths, encrypted private-backup archives, age identities, and restore reports are ignored.
- Production-style credentials are referenced through environment variables / GitHub Secrets instead of being intentionally committed as values.
- The repository has a deterministic scanner for several high-confidence credential formats in recovery/function/workflow/script areas.
- Admin data access is enforced server-side through a valid Supabase user session plus membership in `swsi_admin_users`; the admin page is not the security boundary by itself.
- The controlled Netlify production workflow uses GitHub Secrets for Netlify credentials and explicitly avoids printing their values.
- No `pull_request_target` workflow was found in the current default-branch code search during this audit.
- No `write-all` workflow permission was found in the current default-branch code search during this audit.
- Current default-branch file-content search did not find a personal Gmail address.

These are good signals, but they do **not** prove that every historical commit, deleted file, Action log, artifact, Issue, PR comment, or external provider configuration is clean.

## Blocking checks before Public

### P0-1 — Full reachable Git history secret scan

Required evidence:

- scan every blob reachable from every local ref, not only the current working tree;
- detect high-confidence credential formats and historically committed sensitive filenames;
- fail closed if a text blob is skipped because of a scan-size limit;
- do not print discovered secret values to console/logs;
- any real credential finding must be revoked/rotated before history cleanup is considered complete.

A dedicated zero-network scanner is introduced with this readiness branch as `scripts/public_repo_history_secret_scan.py`.

Passing the current-tree secret scan is **not** a substitute for this history scan.

### P0-2 — GitHub Actions logs and artifacts review

Before changing visibility, review historical workflow logs/artifacts for accidental disclosure of:

- GitHub / provider tokens;
- Supabase service-role values;
- Netlify / Cloudflare credentials;
- AI-provider keys;
- private backup material;
- user or administrator private data.

Do not paste suspected values into Issues or audit documents. Record only run/job/artifact identifiers and the classification of the finding.

If a historical secret was printed, rotate/revoke it even if the log is later deleted.

### P0-3 — Git commit metadata privacy

Tracked files are not the only data exposed by a Public repository. Git commits contain author and committer names / Emails.

This audit confirmed that repository history includes at least one non-`noreply` personal author Email in commit metadata.

Before Public, the maintainer must explicitly choose one of these paths:

1. accept that historical commit Email metadata can become public; or
2. plan a controlled history rewrite / branch cleanup to replace private author metadata.

Do not rewrite `main` casually. Rewriting history changes SHAs and can invalidate open PR ancestry, signed commits, release references, audit evidence, external links, and automation assumptions.

The history scanner should report non-`noreply` commit Email metadata **without printing the Email value**.

### P0-4 — Public/private operations boundary

The repository contains extensive operational documentation. Public visibility should not automatically mean that every operational payload belongs in Git, but ordinary architecture / recovery knowledge does not need to be hidden by default.

Use `docs/PUBLIC_DOC_CLASSIFICATION_20261004.md` as the initial classification.

Keep public when a file improves reproducibility, contribution quality, architecture understanding, or trust without exposing sensitive operational leverage.

Keep private / external when it contains credential values, account-recovery secrets, private backup payloads, private user/admin data, or evidence-backed incident detail whose disclosure materially increases active exploitability.

Do not move files mechanically: several AI handoff / test contracts reference existing document paths. Classify first, then update references deliberately.

### P1-1 — License decision

Public visibility and open-source licensing are separate decisions.

Before declaring SWSI open source, the maintainer must explicitly choose the license for **SWSI-authored code** (for example MIT / Apache-2.0 / another policy) and document the boundary for official/government source material and third-party content.

Do not silently apply a code license to material SWSI does not own.

Until that decision is made, do not describe the repository as licensed open source merely because it is publicly visible.

### P1-2 — Protect `main` after public conversion

At audit time `main` is unprotected. Once the repository is public and the account/repository feature becomes available, establish a ruleset / branch protection policy appropriate to the existing workflow.

Minimum intent:

- prevent accidental force-push/deletion of `main`;
- require PR-based review for ordinary human changes where practical;
- require the release-critical checks that are actually stable and relevant;
- preserve the explicitly reviewed monitoring-bot/update paths instead of breaking them blindly;
- do not add dozens of redundant required checks simply because they exist.

Rules must reflect the real automation architecture, not a generic template.

### P1-3 — Enable public-repo security features

After visibility changes, verify and enable the available GitHub security features that fit the repository and plan, such as:

- secret scanning / push protection where available;
- dependency alerts / Dependabot where useful;
- private vulnerability reporting if available;
- security policy discovery through `SECURITY.md`.

Do not assume these become correctly configured automatically when visibility changes.

## Publication boundary

Public repository may contain:

- source code;
- deterministic tests and QA contracts;
- official-source provenance metadata;
- public question shards if legally/operationally intended;
- public architecture and contribution documentation;
- non-sensitive monitoring and long-term-maintenance design.

Must remain private / external-secret-only:

- credential values;
- provider account recovery secrets;
- MFA/recovery codes;
- private backup encryption identities;
- private restore packages;
- raw private user/admin data;
- incident details whose publication materially increases exploitability before remediation;
- any secret copied from historical logs.

## Exact go-public sequence

1. Freeze the target public-candidate revision.
2. Run `git fetch --all --tags --prune` in a complete local clone.
3. Run `python3 scripts/public_repo_history_secret_scan.py`.
4. Resolve every history finding: false positive with evidence, or rotate/revoke + history/log cleanup for real secrets.
5. Decide whether historical non-`noreply` commit Email metadata is acceptable. If not, design and review a history-rewrite migration before executing it.
6. Audit historical GitHub Actions logs and downloadable artifacts.
7. Review `docs/PUBLIC_DOC_CLASSIFICATION_20261004.md`; move only genuinely sensitive operational material and repair references/tests.
8. Make the explicit code-license decision and add the chosen license/notice boundary.
9. Re-run current-tree safety / deterministic QA without bypassing release gates.
10. Change repository visibility to Public through GitHub repository settings.
11. Immediately configure the intended `main` ruleset/branch protection and repository security features.
12. Re-check public anonymous access: source, Issues/PRs, Actions history, releases/artifacts, Pages/deployment links, and exposed metadata.
13. Record the final public revision and date in this document / project handoff.

## Non-goals of this branch

This readiness branch does not:

- deploy production;
- merge #326 or #328;
- modify Official Core;
- rewrite Git history;
- rotate provider credentials;
- enable/disable GitHub repository settings;
- choose a license on behalf of the maintainer;
- claim the Actions-history audit is complete without evidence.

## Current readiness decision

**Do not switch visibility yet.**

The codebase is structurally close to public-ready, but the remaining high-value checks are historical-secret/log/metadata review and repository-governance setup, not more product features.

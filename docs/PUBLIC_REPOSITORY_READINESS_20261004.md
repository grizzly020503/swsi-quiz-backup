# SWSI Public Repository Readiness — 2026-10-04

Status: **YELLOW — prepare for public visibility, but do not flip the repository to Public yet.**

This document records the public-readiness work that can be completed safely without changing production, redeploying the site, or pretending that an incomplete secret-history audit has passed.

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

These are good signals, but they do **not** prove that every historical commit, deleted file, Action log, artifact, Issue, PR comment, or external provider configuration is clean.

## Blocking checks before Public

### P0-1 — Full reachable Git history secret scan

Required evidence:

- scan every blob reachable from every local ref, not only the current working tree;
- detect high-confidence credential formats and historically committed sensitive filenames;
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

### P0-3 — Public/private operations boundary

The current repository contains extensive operational documentation. Public visibility should not automatically mean that every operational runbook belongs in the public repo.

Keep public when it improves reproducibility, contribution quality, architecture understanding, or trust without exposing sensitive operational leverage, for example:

- architecture overview;
- data contracts;
- testing rules;
- non-sensitive recovery design;
- contribution rules;
- public monitoring contracts;
- official-source provenance rules.

Move to an explicitly private operational location when the material would expose unnecessary recovery/account detail, incident-sensitive context, private backup handling, private user data, or provider-account takeover information.

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
2. Run `scripts/public_repo_history_secret_scan.py` locally against a complete clone with all relevant refs fetched.
3. Resolve every history-scan finding: false positive with evidence, or rotate/revoke + history/log cleanup for real secrets.
4. Audit historical GitHub Actions logs and downloadable artifacts.
5. Classify operational documents; move only genuinely private operational material and repair references/tests.
6. Make the explicit code-license decision and add the chosen license/notice boundary.
7. Re-run current-tree safety / deterministic QA without bypassing release gates.
8. Change repository visibility to Public through GitHub repository settings.
9. Immediately configure the intended `main` ruleset/branch protection and repository security features.
10. Re-check public anonymous access: source, Issues/PRs, Actions history, releases/artifacts, Pages/deployment links, and exposed metadata.
11. Record the final public revision and date in this document / project handoff.

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

The codebase is structurally close to public-ready, but the remaining high-value checks are historical-secret/log review and repository-governance setup, not more product features.

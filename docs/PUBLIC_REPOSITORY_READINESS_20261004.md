# SWSI Public Repository Readiness — 2026-10-04

## Current decision

Status: **YELLOW — close to public-ready, but do not switch visibility yet.**

The owner has explicitly accepted historical non-`noreply` commit email visibility as a known privacy trade-off. **Do not rewrite Git history solely to hide those email addresses.** Future commits should prefer a GitHub `noreply` address when practical.

The remaining release blockers are security-history checks, not commit-email privacy.

## What is already true

- Current default-branch code search did not reveal an obvious committed GitHub PAT, Supabase secret, OpenAI-style key, or private key value.
- Existing source already uses environment-variable names such as `SUPABASE_SERVICE_ROLE_KEY` rather than embedding the production value.
- `.gitignore` excludes `.env*`, private backup bundles, age identities, and restore reports.
- Admin Edge Functions enforce authenticated sessions plus membership checks; admin access is not merely a hidden frontend route.
- No `pull_request_target` use was found in current main during the 2026-10-04 audit.
- The public-readiness branch adds `SECURITY.md`, `CONTRIBUTING.md`, document-classification guidance, and a local full-history scanner.
- The readiness-only commits do not touch Official Core, production data, deploy configuration, #326, or #328.
- The readiness-only commits have not triggered GitHub Actions runs.

## Public-before-go P0

### 1. Full Git history scan

Run from a complete local clone:

```bash
git fetch --all --tags --prune
python3 scripts/public_repo_history_secret_scan.py
```

The scan must cover reachable historical blobs and report only redacted metadata, never raw secret values.

Any finding must be classified. If a real credential was ever committed:

1. revoke / rotate the credential first;
2. determine exposure scope;
3. clean history only where necessary;
4. re-scan;
5. check related logs/artifacts.

Do not treat a clean current branch as proof that history is clean.

### 2. GitHub Actions log / artifact audit

Audit retained workflow history, especially workflows that consume production or deployment secrets. Check for:

- GitHub PATs / tokens;
- Supabase service-role or secret keys;
- Netlify tokens/site identifiers if confidential;
- Cloudflare API tokens;
- AI-provider keys;
- JWT/private-key material;
- private backup payloads;
- private user/admin/contact data;
- commands that accidentally echo environment variables.

Secret masking in GitHub Actions is helpful but is not sufficient evidence by itself.

### 3. Ops-document final review

Use `docs/PUBLIC_DOC_CLASSIFICATION_20261004.md`.

Architecture, tests, safety boundaries, recovery principles, and provider-neutral operations can stay public when they contain no sensitive payload. Do not hide a file merely because it is operational.

Move or redact only evidence-backed sensitive material such as:

- credential values;
- account recovery codes;
- private user/contact data;
- raw private backups;
- provider account identifiers where exposure creates risk;
- incident details that expose exploitable secrets.

## Privacy decision: commit email metadata

Historical commits already contain non-`noreply` email metadata. The owner has decided this is **acceptable and not a blocker** for repository publication.

Therefore:

- do **not** rewrite history solely for email privacy;
- do **not** invalidate hundreds of commit SHAs / PR references / audit evidence for this reason;
- prefer GitHub `noreply` email for future commits where convenient;
- revisit only if the owner later changes this privacy preference.

## Public-before-go P1

### License decision

Repository visibility and software licensing are separate decisions.

Before publication, explicitly choose how SWSI-authored source code may be reused. Do not automatically apply MIT/Apache/GPL without owner approval.

The license/notice must not claim ownership over official exam content, statutory text, third-party material, news content, or other material whose rights belong elsewhere.

### Main protection after publication

Current `main` was observed as unprotected while the repository is private. After publication, configure the strongest available free ruleset/branch protection that fits the real automation model, including at minimum:

- prevent accidental force-push;
- prevent branch deletion;
- prefer PR-based human/AI changes over direct interactive pushes;
- require only genuinely stable, necessary CI gates;
- preserve intentionally authorized automation that updates monitored snapshots.

Do not invent required checks that deadlock the existing bot workflows.

### Public security features

After switching to Public, inspect and enable where available:

- secret scanning;
- push protection;
- Dependabot alerts/updates;
- private vulnerability reporting;
- code scanning only if it adds signal without creating a high-noise maintenance burden.

### Anonymous-view audit

After publication, review the repository as a logged-out stranger and inspect:

- source code;
- Issues / PRs;
- Actions history;
- retained artifacts;
- releases;
- commit metadata;
- deployment URLs;
- README and documentation;
- repository metadata.

Record the public revision and date only after this check passes.

## Go-public sequence

```text
full Git history scan
→ classify / rotate any real findings
→ Actions logs + artifacts audit
→ ops document final review
→ owner license decision
→ switch repository visibility to Public
→ configure branch/ruleset protections
→ enable available public security features
→ anonymous-view audit
→ record public revision/date
```

## Safety boundaries

Public-readiness work does **not** authorize:

- production deployment;
- Official Core changes;
- unreviewed history rewrite;
- automatic license selection;
- lowering QA to make publication easier;
- treating infrastructure/quota failures as code failures;
- exposing private backups or production credentials.

## Readiness summary

Email metadata is now an accepted privacy trade-off and is no longer a release blocker.

The repository remains **YELLOW** until the full Git-history secret scan and retained Actions log/artifact audit are completed. Once those are clean (or all findings are remediated), the repository can move to the final license/visibility/ruleset steps.

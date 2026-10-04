# SWSI Public Repository Readiness — 2026-10-04

## Current decision

Status: **YELLOW — engineering blockers are substantially remediated, but do not switch visibility yet.**

Current baseline main: `dd1d73107ae14a9233e2c4558497ca10c495282f`.

Current readiness branch: `chore/public-readiness-20261004`.

Latest compare at this update: **ahead 23 / behind 0**. Changes remain confined to public-governance docs, security/workflow hardening, QA contracts, the history scanner, five GitHub→Supabase sync function sources, and an undeployed ops-ledger candidate. Official Core question/answer/grading data and production snapshots are not part of this branch diff.

The owner has explicitly accepted historical non-`noreply` **commit metadata Email** visibility. Do not rewrite Git history solely for commit metadata Email exposure. This does **not** automatically settle separate historical findings where source content explicitly identified a personal Email as an administrator identity or contained personal-name attribution.

## What is already verified

### Current source / credentials

- Current default-branch scans did not reveal an obvious committed GitHub PAT, Supabase secret, OpenAI/Groq-style key, AWS access key, or private key value.
- Source uses secret/environment variable names such as `SUPABASE_SERVICE_ROLE_KEY`; no evidence of a committed production value was found in the risk-based review.
- `.gitignore` excludes `.env*`, private backup bundles, age identities, and restore reports.
- No current `pull_request_target` use was found.

### Supabase authorization

- RLS is enabled on relevant tables.
- `questions` / `essays` expose read-only student data to public roles; write access is not granted to anon/authenticated roles.
- Sensitive/admin/current-affairs/legal-watch/telemetry tables are not directly public-readable/writeable.
- No public-schema view was found that bypasses this boundary.
- `SECURITY DEFINER` functions do not expose direct EXECUTE to anon/authenticated/PUBLIC.
- `swsi-admin` requires a valid Supabase session and membership in `swsi_admin_users` before returning private admin data.

### Actions / retained artifacts

Risk-based retained-evidence review found no token, service-role key, provider credential, private backup, or private user/admin dump in the high-risk retained runs inspected.

Verified examples include:

- Netlify production deploy: secrets masked, no retained artifact.
- DR artifact: isolated restore evidence only; no hosted mutable data or production secret payload.
- Knowledge runtime artifact: laws/theories/manifest only; secret-like scan 0 hits.
- Historical Law Stage 1–6 evidence: 8 JSON files; secret-like / Email / credential-key scans 0 hits.
- Historical Law Guardian artifact: one queue JSON; secret-like / Email / credential-key scans 0 hits.

This is **risk-based + retained-evidence** coverage, not a claim that every expired/deleted Actions run in repository history has been exhaustively enumerated.

## Public-before remediation already prepared on readiness branch

### 1. GitHub→Supabase auth now survives Private → Public safely

The following production Edge Function sources no longer require `repo.private === true`:

- `import-moex-social-worker`
- `update-question-analysis`
- `sync-legal-watch`
- `sync-current-affairs`
- `sync-essay-enrichment`

Instead, the short-lived GitHub token must prove write capability on immutable repository id `1345053575`:

```text
repo.id == 1345053575
AND
repo.permissions.push == true
```

Public repository readability is therefore not treated as authentication. External/fork read-only tokens must not pass this gate.

The undeployed `swsi-ops-ledger` candidate uses the same rule so the old Private-only assumption cannot be deployed later.

Corresponding QA contracts now explicitly require this public-safe gate and reject reintroduction of `repo.private === true`.

**Important:** these are source changes only. The five production functions have **not** been redeployed yet.

### 2. Privileged workflow trust boundaries are narrowed

- Historical Law Guardian downstream `workflow_run` evidence routing only accepts a successful `workflow_dispatch` Stage 1–6 run from this repository's `main`; PR/fork heads are not executed in the privileged downstream lane.
- Admin Production defaults to `contents: read`; PR validation is read-only. Only the non-PR production job requests `contents: write`.
- Public Monitoring Feed defaults to `contents: read`; PR deterministic/UI/five-radar validation is a read-only job. Only trusted non-PR monitoring/publish events request `contents: write`.

### 3. Current-source personal-name literals removed

The readiness branch removes the plaintext identity marker previously used by privacy denylist checks in:

- `scripts/public_content_sanitize.py`
- `.github/workflows/cloudflare-public-candidate.yml`
- `.github/workflows/prepare-cloudflare-soft-launch-artifact.yml`

The replacement is stronger and identity-neutral: structural patterns reject legacy personal attribution shapes and third-party study-guide source language without committing any person's name.

### 4. History scanner v2

`scripts/public_repo_history_secret_scan.py` now:

- checks blob size before loading content;
- scans high-confidence credential/token/private-key/JWT patterns;
- detects sensitive variable names assigned literal values;
- explicitly ignores safe runtime references such as `${{ secrets.* }}`, `github.token`, `Deno.env.get(...)`, `process.env`, and `os.environ`;
- scans historical text blobs for Email-like values without printing the Email;
- flags archive/database/credential-container history paths for manual review;
- supports a local-only identity regex file located outside the Git working tree via `SWSI_IDENTITY_REVIEW_PATTERNS_FILE`;
- separates `credential_blocking_findings`, `identity_review_findings`, and accepted commit-metadata Email information.

## Remaining Public-before P0

### 1. Run the full all-refs history scanner on a complete clone

Required sequence:

```bash
git fetch --all --tags --prune
python3 scripts/public_repo_history_secret_scan.py
```

For owner-specific historical name review, optionally provide a local file outside the repository:

```bash
SWSI_IDENTITY_REVIEW_PATTERNS_FILE=/private/path/patterns.txt \
python3 scripts/public_repo_history_secret_scan.py
```

The current connector/container cannot provide the complete local `.git` object database, so this gate is **not yet PASS**.

If credential findings are real:

1. revoke/rotate first;
2. determine exposure scope;
3. clean only what is necessary;
4. re-scan;
5. inspect related Actions logs/artifacts.

### 2. Historical identity/privacy owner decision

Two findings remain distinct from accepted commit metadata Email:

- an ancestor commit historically placed a personal Email into an admin login identity field;
- main history contains past personal-name attribution evidence.

These are not known password/token leaks. They are identity/privacy exposure decisions. Before Public, record whether the owner accepts these historical associations or chooses targeted de-identification / history rewrite.

Do not rewrite history merely because current source is now clean.

### 3. Exact-head CI / static validation

The readiness branch needs real exact-head validation before merge. At minimum verify:

- YAML/workflow syntax and permissions;
- current-affairs deterministic contract;
- MOEX importer integrity contract;
- essay enrichment contract;
- ops-ledger candidate contract;
- privacy/public-content sanitizer;
- historical-law Guardian routing contract;
- no unexpected Official Core or generated-data drift.

No merge should occur merely because the security design looks correct by inspection.

### 4. Merge + production function compatibility deployment

Only after exact-head validation:

1. merge the reviewed readiness changes;
2. deploy the five changed production Edge Functions with their existing `verify_jwt=false` custom GitHub-token authentication model;
3. run compatibility smoke tests from the trusted workflows;
4. verify MOEX/current-affairs/legal-watch/essay/analysis update lanes still authorize correctly;
5. only then consider visibility change.

Do **not** switch the repository Public first: the currently deployed functions still contain the old Private-only repository check until redeployed.

## Public-before P1 / owner decisions

### License

Visibility and licensing are separate.

No SWSI source-code license is currently committed. Public visibility may be used without automatically granting MIT/Apache/GPL-style reuse rights, but the owner should explicitly choose the intended policy.

Any license/notice must avoid claiming ownership over official exam content, statutory text, third-party material, news content, or other externally owned sources.

### Stale branch cleanup

There are 300+ current branch refs. Risk-based review of high-risk branch names did not reveal a new credential/private-payload blocker, but Public will expose current branch tips.

After full-history audit, produce a retention list:

- keep;
- safe to delete;
- retain as evidence.

Deleting a stale branch is hygiene; it does not erase content already present in main ancestry.

## Immediately after switching Public

Configure available repository protection/security features promptly:

- protect `main` from force-push and deletion;
- require only stable, necessary checks that do not deadlock authorized snapshot bots;
- ensure write-capable automations cannot be triggered by untrusted PR code;
- enable available secret scanning / push protection;
- review Dependabot and private vulnerability reporting availability;
- perform a logged-out anonymous-view audit of code, Issues/PRs, Actions, artifacts, releases, metadata, README, and deployment links.

## Updated go-public sequence

```text
complete clone + all-refs history scanner v2
→ classify credential / identity findings
→ record owner historical identity/privacy decision
→ exact-head CI / static validation of readiness branch
→ review diff and merge
→ deploy 5 public-safe GitHub→Supabase Edge Functions
→ trusted compatibility smoke
→ owner license decision (or explicitly choose no license yet)
→ switch repository visibility to Public
→ immediately configure main protection / ruleset
→ enable available public security features
→ anonymous-view audit
→ record public revision/date
```

## Safety boundaries

Public-readiness work does **not** authorize:

- changing Official Core questions/options/answers/grading;
- unreviewed history rewrite;
- automatic license selection;
- deleting hundreds of stale branches without owner authorization;
- lowering QA to make publication easier;
- exposing private backups or production credentials;
- switching visibility before the currently deployed Private-only Edge Function auth has been replaced and smoke-tested.

## Readiness summary

Engineering design risk is now materially lower than at the start of this audit. Current source no longer needs to expose a personal-name denylist, privileged PR workflow permissions have been narrowed, and the Private-only GitHub→Supabase authentication assumption has a Public-safe source replacement prepared.

The repository remains **YELLOW** because the full all-refs scan has not actually run in a complete clone, historical identity/privacy acceptance is not fully recorded, exact-head CI is still pending, and the five production Edge Functions still run their old deployed versions.

# Public / Private Documentation Classification — 2026-10-04

Purpose: classify repository documentation by **content sensitivity**, not by whether the filename sounds operational.

This is a review aid, not a claim that historical Git blobs / Issues / PR comments / Actions logs are already clean.

## A. Keep public by default

These files are useful for reproducibility, contributor safety, architecture understanding, or long-term maintenance and do not currently appear to require secrecy merely because they discuss operations:

- `README.md`
- `ARCHITECTURE.md`
- `TESTING.md`
- `AGENTS.md`
- `AI_COLLABORATION.md`
- `AI_PROJECT_CONTEXT.md`
- `ZERO_COST_OPERATIONS.md`
- `BACKUP_INVENTORY.txt`
- `docs/PORTABLE_EVIDENCE_MANIFEST_20261002.md`
- `docs/MAINTAINER_SUCCESSION_MINIMUM_SURVIVAL_20261002.md`
- `docs/AI_COUNCIL_RELAY_ARCHITECTURE.md`
- `docs/SUPABASE_FREE_TIER_PRIVATE_BACKUP.md`
- local-only backup / restore helper source code, provided it contains no real credential values, private payloads, personal identifiers, or account recovery secrets

Rationale: security should rely on authentication, authorization, secret isolation, and least privilege—not on hiding ordinary architecture or recovery concepts.

## B. Keep public, but review for freshness / unnecessary operational detail

These categories are not automatically secret, but should receive a final public-readiness review because they can accumulate live operational state or outdated instructions:

- `PROJECT_HANDOFF.md`
- `ADMIN_MONITORING_PLAN.md`
- release validation / audit documents
- current production / fallback deployment documents
- project diaries
- GitHub setup / migration instructions

Review questions:

1. Does the file contain a credential **value**, recovery code, private account identifier, or personal contact detail?
2. Does it expose raw private user/admin records or a private backup payload?
3. Does it contain an unremediated exploit path whose publication materially increases risk?
4. Is it merely an architecture / operational description that is already safely enforced server-side?
5. Is the content stale enough to mislead a contributor or future AI?

If answers 1–3 are no, the file usually does not need to be private solely because it is operational documentation.

## C. Must remain private / external-only

Never make the following payloads public through Git history, Actions artifacts, Issues, PRs, release assets, screenshots, or logs:

- real `.env` values;
- Supabase service-role credentials;
- GitHub / Netlify / Cloudflare / AI provider tokens;
- passwords;
- MFA / recovery codes;
- private backup encryption identities;
- plaintext private database dumps;
- encrypted private backup archives when the repository is not intended as their storage location;
- raw Auth user data;
- raw contact / feedback data that identifies users;
- provider account takeover / recovery material;
- incident details that expose an active, unremediated exploit path.

Existing `.gitignore` and private-backup policy are intended to keep these payloads outside Git, but historical verification is still required.

## D. Finding from this audit: commit metadata privacy

Current file-content search did not find a personal Gmail address in the default-branch source files checked during this audit.

However, historical Git commit metadata includes at least one non-`noreply` personal author Email. A Public repository can expose commit author/committer metadata even when that Email does not appear in any tracked file.

Therefore Public readiness must include a separate decision:

- **accept** historical author Email exposure; or
- perform a carefully planned history rewrite / branch cleanup before publication.

This is a privacy decision, not a secret-rotation issue. Do not rewrite `main` casually: it can invalidate SHAs, open PR ancestry, release references, signatures, links, and downstream automation.

## E. Current recommendation

Do **not** create a separate private ops repository just because the codebase contains architecture and recovery documents.

First keep non-sensitive operational knowledge public for transparency and survivability. Move only evidence-backed sensitive payloads or unnecessarily exploitable incident/account-recovery details.

The highest remaining Public blockers are historical traces:

1. reachable Git blobs;
2. Actions logs / artifacts;
3. commit Email metadata;
4. explicit license decision;
5. post-Public repository protections.

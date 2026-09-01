# SWSI Public Repository Policy

This document defines the release boundary for a future public SWSI source repository.

## Purpose

The current `swsi-quiz-backup` repository is an operational/private development repository. It contains historical branches, recovery artifacts, deployment packages, internal handoff material, and source content that is intentionally sanitized only at deploy time. It must not be made public as-is.

The public repository must be created as a **new repository with a fresh Git history** from a reviewed snapshot. Do not mirror, fork, or push the existing `.git` history into the public repository.

## Source rule

Build the public snapshot from a reviewed release candidate, never from an assumed SHA. Re-read the actual remote PR/base/HEAD and release status immediately before export.

The initial staging branch for this work was created from PR #33 HEAD `d0bb4dde704eceb57313e86af31150b7ebf77b0e`. This SHA is a historical pin only; it is not permission to skip a fresh release-state check later.

## Public snapshot allowlist

The first public snapshot is intentionally conservative. It may include only material needed to demonstrate the student runtime and selected architecture/security boundaries:

- sanitized `index.html`
- `manifest.json`
- `sw.js`
- `essay_guides.js`
- `icons/`
- `admin/`
- `cloudflare/wandering-wave-4418/worker.js`
- `supabase/functions/`
- `supabase/migrations/`
- `ARCHITECTURE.md`
- `TESTING.md`
- a curated public README
- selected public-safe source/build/test files added explicitly after review

Everything else is excluded by default until reviewed and deliberately added.

## Hard exclusions

Never copy these classes of material into the public repository:

- `.git/` or any previous Git history
- `.env`, `.env.*`, private keys, certificates, credential files, local editor state
- ZIP/TAR/7z/RAR archives or deployment packages
- `deploy-packages/`
- recovery/back-up inventory and raw rescue artifacts
- raw question-bank backup exports such as `data/questions_master_backup_*`
- private handoff/release-operation documents such as `PROJECT_HANDOFF*`
- temporary/debug branches, artifacts, or generated local logs
- production secrets, service-role keys, Groq keys, Cloudflare tokens, Netlify tokens, internal keys, passwords
- workflows with production write/deploy/sync privileges until a separate public-CI review is completed
- third-party study-guide material that the deploy-time public sanitizer already identifies as unsuitable for redistribution without an explicit publication licence

## Required transformations

Before a snapshot is accepted:

1. Run the existing public study-guide sanitizer against the copied `index.html`.
2. Remove deployment-specific identifiers that are not needed for a public example configuration.
3. Replace the private/internal README with the curated public README.
4. Run a fail-closed scan for credentials, private-key blocks, personal email addresses, archive files, and known third-party study-guide markers.
5. Produce a SHA-256 manifest of the exported files.

## Privacy boundary

A public snapshot must not expose personal commit metadata from the private repository. The new repository starts with fresh commits only. Do not preserve the old author/committer history.

The snapshot scan treats ordinary personal email addresses as a release blocker. GitHub `users.noreply.github.com` addresses may be allowed.

## Security boundary

Public source must not rely on secrecy of endpoint names or client code. Runtime authorization must continue to be enforced server-side by Supabase RLS/Auth/allowlists and Cloudflare Worker secret-backed checks.

References such as environment-variable names (`GROQ_KEY`, `SWSI_INTERNAL_KEY`, `SUPABASE_SERVICE_ROLE_KEY`) are allowed; actual secret values are not.

## Publication gate

The future public repository remains **Private** until all of the following are true:

- snapshot generated from a freshly verified release source
- public-content sanitizer passes
- credential/privacy scan passes
- binary/archive exclusions pass
- public README reviewed
- no third-party redistribution blocker remains
- user explicitly approves changing the new repository visibility to Public

Creating or updating this staging branch does not authorize merging PR #33, modifying `main`, deploying production, or changing any repository visibility.

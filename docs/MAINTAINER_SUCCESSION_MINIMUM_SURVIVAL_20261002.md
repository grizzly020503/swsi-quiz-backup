# SWSI Maintainer Succession / Minimum-Survival Contract

## Purpose

This document defines the **non-sensitive handoff surface** for a future maintainer and the fail-safe behavior when no maintainer is available.

It does not contain credentials, account identifiers, personal contact details, MFA/recovery codes, tokens, passwords, or service-role keys.

## Service responsibility registry

Canonical machine-readable registry:

- `data/service_responsibility_registry.v1.json`

Each service records only:

- stable service ID;
- purpose;
- owner **role** rather than a person;
- criticality;
- core / enhancement / fallback classification;
- repo recovery reference;
- renewal/terms type;
- safe fallback behavior;
- `external_secret_only` credential policy.

The current registry covers:

1. GitHub source + CI;
2. Cloudflare primary hosting/runtime;
3. Netlify fallback hosting;
4. Supabase backend;
5. MOEX official source;
6. optional AI enhancement.

A new maintainer should start with the recovery reference named by the registry. Credential recovery remains outside Git and always requires a human-authorized account process.

## Minimum-survival mode

Canonical machine-readable contract:

- `data/minimum_survival_contract.v1.json`

The only accepted unattended survival mode is:

`last_verified_updates_paused`

This means:

- continue serving the last verified release where existing static/local dependencies still work;
- preserve the official question corpus and grading contract;
- preserve practice, mock exams, wrong-answer review, local learning progress, essay library, and local essay drafts;
- pause or degrade AI, remote sync, feedback, admin, MOEX sync, and automated publishing if their providers are unavailable;
- disclose the last verified revision/date and that updates are paused;
- never imply that official data is still being refreshed when it is not.

This matches the zero-cost operating principle in `ZERO_COST_OPERATIONS.md`: enhancement outages must not take down the student study core.

## Human-only decisions

Automation must not decide or execute:

- account succession;
- acceptance of new provider terms;
- major security-incident response decisions;
- any new paid obligation;
- disputed official-content promotion;
- destructive migration.

These remain human decisions even if automation can gather read-only evidence.

## Allowed unattended automation

Only the explicit read-only allowlist may continue without a maintainer:

- read-only health checks;
- hash verification;
- public-source change detection;
- deterministic local validation.

The allowlist is deliberately exact. Adding a new unattended capability requires review of this contract rather than assuming a new tool is safe.

## Fail-closed rules

`scripts/maintainer_survival_validate.py` rejects:

- sensitive field keys or email-like values in these contracts;
- missing `owner_role`, fallback, or recovery reference;
- recovery references that do not exist in the checked-out repo;
- duplicate service IDs;
- any survival mode other than `last_verified_updates_paused`;
- removal of required student-core capabilities;
- widening the unattended automation allowlist;
- enabling automatic payment/account takeover/review-queue deletion/QA lowering/unverified promotion/destructive migration;
- changing the five pinned scenario responses away from the fail-safe behavior.

Synthetic regression coverage is in `scripts/maintainer_survival_selftest.py`.

## Recovery references

Existing source material remains authoritative for the underlying recovery mechanics:

- release and production boundaries: `RELEASE.md`;
- zero-cost continuity rules: `ZERO_COST_OPERATIONS.md`;
- Supabase schema-only rebuild path: `supabase/recovery/README.md`;
- current AI recovery context: `docs/AI_RECOVERY_HANDOFF_20261002.md`.

This contract does not replace those documents and does not grant permission to deploy production, change credentials, perform account recovery, or run destructive migrations.

## Important long-term rule

A 10/20/30-year platform goal does **not** mean preserving stale automation indefinitely or retaining personal data indefinitely. When stewardship is absent, truthful freshness disclosure plus a stable last-verified study core is safer than pretending maintenance is still active.

# Maintainer Succession / Minimum-Survival Contract — Phase C-3

Issue: #284  
Scope: non-sensitive responsibility metadata and deterministic survival-mode policy only.

## Goal

SWSI should remain understandable and useful even if the original maintainer is temporarily unavailable or a future successor must take over. The repository must contain enough **non-sensitive** responsibility/recovery metadata to begin recovery without turning Git into a password vault.

## What the registry records

`data/maintainer_continuity_contract.v1.json` records service responsibilities for:

- GitHub source repository;
- GitHub Actions automation;
- Cloudflare primary delivery;
- Netlify fallback delivery;
- Supabase backend;
- official MOEX source;
- AI enhancement.

Each service records only:

- purpose;
- owner **role** rather than a person/account identifier;
- criticality;
- core/enhancement/external-source classification;
- repo recovery references;
- renewal/terms-review class;
- whether payment is required by the current contract;
- fallback behavior;
- `credentials_policy=external_secret_only`.

It deliberately does **not** record names, email addresses, account IDs, passwords, tokens, MFA/recovery codes, API keys, service-role keys or private keys.

## Minimum-survival mode

The required safe state is:

`last_verified_updates_paused`

When maintainer succession/account recovery/paid decision/disputed update is unresolved:

- serve the last verified revision when safe and already deployed;
- pause unverified updates;
- disclose content freshness/staleness;
- preserve review/backlog items rather than deleting them;
- never lower QA to make the queue look healthy;
- never auto-pay or auto-take-over an account.

The existing static/local study core is expected to remain available whenever its dependencies still exist:

- home/navigation;
- official MCQ corpus;
- grading contract;
- practice sessions;
- mock exams;
- wrong-answer review;
- local learning progress;
- essay library;
- local essay drafts.

AI, sync, feedback and admin are allowed to degrade or pause without redefining the entire student core as unavailable.

## Human-only decisions

The contract reserves these decisions for a human maintainer/successor:

- account succession;
- new provider terms;
- major security incident response;
- new paid obligations;
- disputed official content;
- destructive migrations.

Automation remains limited to already-approved read-only/diagnostic activities such as health checks, hash verification, public-source checks and diagnostic export.

## Validator

`scripts/maintainer_continuity.py` validates:

- service IDs are unique;
- owner role / purpose / fallback / recovery reference exist;
- referenced recovery files exist when a repo root is supplied;
- credential policy remains `external_secret_only`;
- sensitive field names are rejected recursively;
- minimum-survival mode preserves the required core;
- queue deletion / QA lowering / auto payment / auto account takeover remain forbidden;
- human-only decision set remains complete.

It can also evaluate continuity events such as:

- `maintainer_absent`;
- `account_recovery_pending`;
- `ai_unavailable`;
- `paid_decision_pending`;
- `disputed_update`.

Unknown events fail closed into the same last-verified / updates-paused / human-decision-required posture.

## Self-test evidence

The zero-network synthetic fixture passed **7 scenarios** before the branch checkpoint:

- valid non-sensitive service metadata;
- maintainer absent;
- account recovery pending;
- paid decision pending;
- disputed update;
- AI unavailable while core remains available;
- sensitive-key and missing-recovery-reference rejection.

## Boundaries deliberately preserved

- no account ownership changes;
- no credential discovery or storage;
- no production deploy;
- no live frontend survival banner yet;
- no Auth/RLS/schema mutation;
- no automatic payment;
- no deletion of unresolved review items;
- no Official Core modification;
- no claim that an account can be recovered from repo metadata alone.

The next stage, if ever needed, should rehearse this checklist with a successor in a controlled environment and record only non-sensitive results. Credential transfer/recovery remains outside Git and requires the relevant provider's secure human process.

# SWSI Maintainer Succession / Minimum-Survival Contract

Issue: #284

## Goal

SWSI should remain understandable and safely usable even if the current maintainer is temporarily or permanently unavailable. The repository must explain **roles, responsibilities, recovery starting points and human-only decision boundaries** without turning Git into a credential vault.

This work package does not change the live frontend, assume control of any account, accept provider terms, export private data or deploy production changes.

## Non-sensitive service registry

`data/service_responsibility_registry.v1.json` records each long-lived service by functional role rather than a specific person's identity.

Required fields are:

- `service_id`
- `purpose`
- `owner_role`
- `criticality`
- `core_or_enhancement`
- `recovery_reference`
- `renewal_type`
- `fallback`
- `credential_policy`

The registry intentionally does **not** store a person's name, Email, account ID, username, password, token, API key, secret, MFA material or recovery code. Credential policy may state only a non-secret class such as `external_secret_only` or that a public source expects no credential.

Every recovery reference must exist in the checked-out repository. A future maintainer should therefore be able to start from the referenced documentation without needing the previous maintainer's memory.

## Minimum-survival mode

Mode: `last_verified_updates_paused`.

When safe maintenance cannot continue, the system should prefer an honest last-known-good state over unverified automation.

Core capabilities to preserve when the already-deployed static/local dependencies still work and the last verified core is intact include:

- homepage/navigation;
- official question bank;
- grading contract;
- practice and mock exams;
- wrong-answer review;
- local progress;
- essay library and local drafts.

Enhancements such as AI generation, unverified new-source intake, feedback submission when its backend is unavailable, admin mutation without maintainer control and other nonessential sync may be paused or degraded instead of taking down the core.

## Freshness disclosure

A paused system must not look like an actively maintained system. Its status representation must carry at least:

- `last_verified_revision`
- `content_last_verified_at`
- `updates_paused_since`
- `pause_reason_class`

This contract defines the data requirement only; this work package does not change the live UI. A later product change may render this status after the appropriate UX/release review.

## Human-only decisions

Automation may not decide:

- account succession;
- acceptance of new provider terms;
- major security incident response;
- a new paid obligation;
- disputed official content;
- destructive migration;
- credential-scope expansion.

Allowed unattended work is limited to pre-approved non-mutating work such as read-only health checks, hash verification, public-source availability checks, freshness reporting and portable-manifest generation.

## Explicitly forbidden automation

The survival contract rejects any policy that allows:

- automatic payment;
- automatic account takeover;
- automatic acceptance of provider terms;
- deleting review queues merely to clear backlog;
- lowering QA thresholds;
- marking unresolved content verified;
- publishing disputed Official Core;
- destructive schema migration;
- credential-scope expansion.

Maintainer absence is not a reason to erase uncertainty.

## Deterministic validation

```bash
python3 scripts/maintainer_survival_contract_selftest.py
python3 scripts/maintainer_survival_contract.py --json
```

The validator is zero-network and fails closed when:

- sensitive field keys or Email-like values appear;
- a required service field is missing;
- `owner_role`, `fallback` or recovery references are missing;
- a recovery reference does not exist in the checkout;
- freshness disclosure is incomplete;
- required human-only or forbidden-automation boundaries disappear;
- the five required scenarios are not defined;
- core/review/freshness invariants are weakened.

The synthetic fixture covers maintainer absence, account recovery pending, AI unavailable, paid-decision pending and disputed-update boundaries through the contract validator.

## Relationship to other long-term work

- #157 remains the controlled private-data backup/restore work; this registry does not replace private backup.
- #277 independent heartbeat may report that maintenance stopped; it does not gain account-takeover authority.
- #279 bounded recovery controls retry/degradation/release behavior.
- #283 defines portable repo evidence and private-external storage boundaries.
- #290 Council Relay remains an automation helper, not a replacement for human-only account/payment/security decisions.

## Safety boundary

- no live UI change;
- no production deploy;
- no provider/account mutation;
- no Auth/RLS/schema change;
- no secret/private payload;
- no paid service;
- no scheduled workflow.

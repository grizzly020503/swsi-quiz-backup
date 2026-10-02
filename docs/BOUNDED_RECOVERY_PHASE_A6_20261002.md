# Bounded Recovery / Degradation / Release Contract — Phase A-6

Issue: #279  
Scope: machine-readable decision layer only. No production deployment or workflow mutation.

## Existing policy reused

This work does **not** replace the existing release rules.

- `ZERO_COST_OPERATIONS.md` already requires last-known-good behavior and graceful degradation.
- `RELEASE.md` already separates branch/test/preview/merge/production and requires explicit owner approval for production actions.
- `docs/NETLIFY_CONTROLLED_DEPLOY.md` already defines static-site rollback to a previous known-good deploy after failed post-deploy verification.
- Database recovery remains a separate concern from static asset rollback. No blind database downgrade is introduced.

The missing layer was a deterministic way for automation to answer:

> Given this failure class, what is the maximum automatic action allowed?

## Core invariants

1. A decision helper may consume explicit owner authorization, but may never manufacture it.
2. Production publish is never self-approved.
3. Official Core changes, Auth/RLS/secrets, destructive/unknown migration state, and paid-service changes always stop for owner decision.
4. Transient network retry is bounded. Retry exhaustion becomes `preserve_last_known_good`, not an infinite loop.
5. Candidate/preview validation failure quarantines the candidate; it does not modify the gate or tests.
6. AI / feedback / admin outages degrade enhancements while the local/static study core remains usable.
7. Source/sync outages preserve the last trusted state rather than replacing it with empty/unverified output.
8. Static post-deploy smoke failure may require restoring the previous known-good static release.
9. Database recovery is **not** treated like static rollback; the contract returns `forward_recovery_or_restore_only`.

## Release state machine

```text
candidate
  -> isolated_verified
  -> preview_verified
  -> publish_authorized   # only after external explicit owner approval
  -> published
  -> postcheck_verified
```

Failure paths:

```text
candidate / preview failure -> quarantined
published + postcheck failure -> rollback_required
unknown/high-risk production state -> manual_required
```

## Deterministic evidence

`scripts/ops_bounded_recovery.py --self-test` covers:

- timeout / 429 / 5xx bounded retry and exhaustion;
- source outage preserves last-known-good;
- AI outage degrades enhancement but keeps core available;
- candidate and preview failures quarantine;
- static post-deploy failure requires previous known-good static release;
- destructive/unknown DB state never blind-downgrades;
- Auth/RLS/secrets, paid-service and Official Core changes are owner-required;
- release state machine cannot create production authorization by itself;
- unknown failure classes fail closed.

Current zero-network self-test result: **22 scenarios/assertions PASS**.

## Deliberately not done

- no GitHub Actions workflow added;
- no existing deployment workflow modified;
- no production deploy;
- no database mutation;
- no automatic rollback execution;
- no provider-specific paid service;
- no changes to Official Core.

A later integration may let existing workflows *consume* this contract, but only after separate review and without changing the explicit release authorization boundary.

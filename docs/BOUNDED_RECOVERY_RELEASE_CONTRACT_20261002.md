# SWSI Bounded Recovery / Degradation / Release Decision Contract

Issue: #279  
Scope: provider-neutral decision layer only. No production mutation, no automatic deploy, no database rollback executor.

## Why this exists

SWSI already has separate policies for zero-cost operation, release gating, rollback and disaster recovery. The missing piece was one deterministic contract that answers:

> Given a failure class, what is the maximum automatic action allowed before the system must stop, preserve trusted state, degrade an enhancement, quarantine a candidate, request rollback, or require a human decision?

Canonical machine-readable policy:

- `data/bounded_recovery_policy.v1.json`

Deterministic validator / decision helper:

- `scripts/bounded_recovery_contract.py`

## Non-negotiable invariants

The policy is fail-closed and requires all of the following:

- preserve the last known-good state;
- production publish authorization must come from outside this contract;
- the contract can never self-authorize production publish;
- no blind automatic database downgrade;
- no automatic paid-service activation;
- no automatic QA lowering;
- no automatic Official Core mutation.

Unknown future failure classes also fail closed to `manual_required`.

## Bounded retry

Only explicitly retryable transient classes may retry:

- timeout;
- HTTP 429 / rate limiting;
- upstream 5xx;
- source unavailable;
- stale job, within its single reclaim allowance.

Each policy row includes:

- `max_attempts`;
- `backoff_class`;
- `scope`;
- `cost_class`;
- exhaustion behavior.

The validator rejects unbounded retry counts. Retry exhaustion never becomes an infinite loop and never expands permissions.

## Core vs enhancement behavior

The decision output keeps these separate:

- `core_status`
- `enhancement_status`

Examples:

- AI unavailable → AI enhancement pauses; core study remains available.
- official source unavailable → keep the last verified official corpus; do not replace with empty/unverified data.
- quota exhausted → pause quota-limited enhancement; do not auto-pay.
- candidate validation or preview failure → quarantine the candidate; do not weaken the gate.

## High-risk boundaries

The following always require a human decision:

- Official Core change;
- Auth / RLS / secret boundary change;
- destructive schema change;
- paid-service change;
- unknown migration state.

The helper may report that owner authorization is required, but it cannot manufacture that authorization.

## Release state machine

Normal path:

```text
candidate
  -> isolated_verified
  -> preview_verified
  -> publish_authorized
  -> published
  -> postcheck_verified
```

`preview_verified -> publish_authorized` requires explicit external authorization from the owner or the existing release gate. Without that authorization, the state remains `preview_verified`.

Failure paths include:

```text
candidate validation failed -> quarantine
preview failed              -> quarantine
published postcheck failed  -> rollback_required
unknown/high-risk state     -> manual_required
```

The helper **signals** `rollback_required`; it does not execute rollback.

## Rollback boundary

Static release and database recovery are intentionally different:

- static release: after failed post-deploy verification, the previous known-good static release may be selected through the existing release process;
- database: no blind automatic downgrade; use a pre-validated forward-recovery / restore plan or owner decision;
- official answer correction: official evidence plus audit trail is required before publish.

## Deterministic validation

`python3 scripts/bounded_recovery_contract.py --self-test`

covers:

- timeout / 429 / 5xx retry and exhaustion;
- source outage preserves trusted state;
- AI outage degrades only enhancement;
- candidate QA failure quarantines;
- preview failure blocks publish;
- static postcheck failure becomes rollback-required;
- DB uncertainty is manual-required with no blind downgrade;
- Auth/RLS/secret, paid-service and Official Core changes remain owner-required;
- unknown failure fails closed;
- release state machine cannot create publish authorization by itself;
- external authorization permits only the explicit publish-authorization transition.

A PR-only exact-checkout workflow validates the current policy and self-test. It has no schedule and does not run on main push.

## Deliberately not done

This work package does **not**:

- modify any production deployment workflow;
- deploy Cloudflare / Netlify / Supabase;
- modify Official Core;
- modify production database / Auth / RLS / secrets;
- execute rollback or migrations;
- enable a paid service;
- lower any test gate;
- add a scheduled workflow.

Future integrations may consume this decision contract only through separately reviewed, bounded adapters. Existing `RELEASE.md`, `ZERO_COST_OPERATIONS.md`, disaster-recovery contracts and explicit owner authorization remain authoritative.

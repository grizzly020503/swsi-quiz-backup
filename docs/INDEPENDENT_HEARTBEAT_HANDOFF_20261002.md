# SWSI independent heartbeat handoff

Issue: #277  
Parent: #262 P1-6

## What this work package solves

The existing `scripts/ops_task_watchdog.py` is valuable, but when it runs inside GitHub Actions it is still same-platform observability. It cannot prove that GitHub Actions itself is alive.

This package defines a provider-neutral heartbeat format and a zero-secret evaluator that can run from a scheduler outside GitHub Actions. The evaluator deliberately separates:

- public site availability;
- data freshness;
- grading/answering health;
- AI degradation;
- review backlog aging;
- maintenance-task heartbeat freshness.

A homepage HTTP 200 is therefore never treated as proof that the whole platform is healthy.

## Current activation state

`independent_monitoring_active` must remain **false** until a real external scheduler is configured. Repository code alone is not an independent monitor.

This branch does **not** choose or deploy a provider. Examples of acceptable future runtimes include an existing Cloudflare scheduled worker, an external uptime/cron service, or an operator-owned cron host. A GitHub Actions cron is explicitly not independent.

## Security boundary

The external evaluator is designed to need no GitHub token, Supabase credential, Cloudflare credential, or private repository access. It reads only a public HTTPS homepage and a public heartbeat JSON.

Redirects are same-host by default, retries are bounded, responses are size-limited, and incident identity is deterministic. Public heartbeat payloads must not contain secrets, private user data, or full internal error dumps.

## Incident model

Incident keys are stable hashes of:

`component + failure_class + scope`

Repeated probes of the same failure therefore remain one ongoing incident. If a previous incident disappears from the next probe, the evaluator emits a resolved transition instead of silently deleting history.

Severity is impact-based:

- grading failure or site outage can be critical;
- stale official data is high impact but does not necessarily mean the site is down;
- AI fallback/degradation is warning-level when core question practice remains usable;
- review backlog aging is distinct from public availability.

## Activation prerequisites

Before claiming P1-6 is complete, a later release must:

1. publish a bounded public heartbeat payload from trusted internal state;
2. schedule `scripts/ops_independent_heartbeat.py` outside GitHub Actions;
3. persist its last state so incident transitions survive restarts;
4. choose a notification destination only with owner approval;
5. test a real missed-heartbeat event by intentionally withholding producer updates.

Until those steps are completed, reports must state that independent monitoring is not active.

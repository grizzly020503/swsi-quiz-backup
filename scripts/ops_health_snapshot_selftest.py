#!/usr/bin/env python3
"""Deterministic zero-network tests for ops_health_snapshot.py."""
from __future__ import annotations

from ops_health_snapshot import build_snapshot
from ops_task_watchdog import parse_time


def run_row(task_id: str, key: str, status: str, **extra):
    row = {
        "task_id": task_id,
        "idempotency_key": key,
        "status": status,
        "attempt": 1,
        "max_attempts": 3,
        "worker_id": None,
        "started_at": "2026-10-04T00:00:00Z",
        "heartbeat_at": "2026-10-04T00:00:00Z",
        "lease_expires_at": None,
        "completed_at": "2026-10-04T00:00:00Z" if status not in {"running", "failed_retryable"} else None,
        "last_success_at": None,
        "checkpoint_version": 1,
        "checkpoint": None,
        "processed_count": 0,
        "error_class": None,
        "error_message": None,
        "next_retry_at": None,
    }
    row.update(extra)
    return row


def review(item_id: str, first_seen: str, **extra):
    row = {
        "item_id": item_id,
        "task_id": "historical-law-guardian-queue",
        "reason": "semantic_conflict",
        "source_ref": "fixture",
        "state": "open",
        "first_seen_at": first_seen,
        "last_attempt_at": None,
        "attempt": 0,
        "last_error": None,
        "next_check_at": None,
        "resolved_at": None,
        "resolution": None,
    }
    row.update(extra)
    return row


def main() -> int:
    now = parse_time("2026-10-05T00:00:00Z")
    state = {
        "schema_version": 1,
        "runs": {
            # Historical quarantine must stay visible in history counts but must
            # not block a task that later recovered successfully.
            "task-a:old": run_row(
                "task-a", "old", "quarantined",
                heartbeat_at="2026-10-01T00:00:00Z",
                completed_at="2026-10-01T00:00:00Z",
            ),
            "task-a:new": run_row(
                "task-a", "new", "success",
                heartbeat_at="2026-10-04T23:00:00Z",
                completed_at="2026-10-04T23:00:00Z",
                last_success_at="2026-10-04T23:00:00Z",
            ),
            "task-b:retry": run_row(
                "task-b", "retry", "failed_retryable",
                heartbeat_at="2026-10-04T23:50:00Z",
                next_retry_at="2026-10-04T23:55:00Z",
            ),
            "task-c:terminal": run_row(
                "task-c", "terminal", "failed_terminal",
                heartbeat_at="2026-10-04T23:10:00Z",
                completed_at="2026-10-04T23:10:00Z",
            ),
            "task-d:running": run_row(
                "task-d", "running", "running",
                worker_id="worker-1",
                heartbeat_at="2026-10-04T22:00:00Z",
                lease_expires_at="2026-10-04T23:00:00Z",
            ),
        },
        "review_items": {
            "r1": review("r1", "2026-10-04T14:00:00Z"),
            "r2": review(
                "r2", "2026-10-01T16:00:00Z",
                attempt=2,
                next_check_at="2026-10-04T23:00:00Z",
            ),
            "r3": review(
                "r3", "2026-09-26T16:00:00Z",
                next_check_at="2026-10-05T06:00:00Z",
                reason="source_format_changed",
            ),
            "r4": review(
                "r4", "2026-09-01T00:00:00Z",
                state="resolved",
                resolved_at="2026-09-02T00:00:00Z",
                resolution="fixture resolved",
            ),
        },
    }

    snap = build_snapshot(state, now)
    assert snap["available"] is True
    assert snap["snapshot_schema_version"] == 1
    assert snap["projection"] == "durable_ops_health_v1"
    assert snap["runs_total"] == 5
    assert snap["run_status_counts"]["quarantined"] == 1
    assert snap["latest_task_status_counts"] == {
        "success": 1,
        "failed_retryable": 1,
        "failed_terminal": 1,
        "running": 1,
    }
    assert snap["task_states"]["task-a"]["status"] == "success"
    assert snap["task_states"]["task-b"]["retry_due"] is True
    assert snap["action_counts"]["retry_due"] == 1
    assert snap["action_counts"]["expired_active_leases"] == 1
    assert snap["action_counts"]["latest_terminal_or_quarantined"] == 1
    assert snap["review_open"] == 3
    assert snap["action_counts"]["review_due"] == 2
    assert snap["action_counts"]["review_scheduled"] == 1
    assert snap["action_counts"]["review_warn_age"] == 1
    assert snap["action_counts"]["review_block_age"] == 1
    assert snap["review_age_buckets"] == {
        "lt_24h": 1,
        "24_72h": 0,
        "72_168h": 1,
        "gte_168h": 1,
    }
    assert snap["health_status"] == "blocked"
    assert "expired_active_lease" in snap["blocked_reasons"]
    assert "latest_task_terminal_or_quarantined" in snap["blocked_reasons"]
    assert "review_age_exceeded_block_threshold" in snap["blocked_reasons"]
    assert snap["next_actions"]["retry_tasks"] == ["task-b"]
    assert snap["oldest_open_reviews"][0]["item_id"] == "r3"

    healthy = {
        "schema_version": 1,
        "runs": {
            "task-ok:1": run_row(
                "task-ok", "1", "no_change",
                heartbeat_at="2026-10-04T23:30:00Z",
                completed_at="2026-10-04T23:30:00Z",
                last_success_at="2026-10-04T23:30:00Z",
            )
        },
        "review_items": {},
    }
    clean = build_snapshot(healthy, now)
    assert clean["health_status"] == "healthy"
    assert clean["blocked_reasons"] == []
    assert clean["attention_reasons"] == []

    malformed_retry = {
        "schema_version": 1,
        "runs": {
            "task-x:1": run_row(
                "task-x", "1", "failed_retryable",
                heartbeat_at="2026-10-04T23:50:00Z",
                next_retry_at=None,
            )
        },
        "review_items": {},
    }
    bad = build_snapshot(malformed_retry, now)
    assert bad["health_status"] == "blocked"
    assert bad["next_actions"]["retry_contract_error_tasks"] == ["task-x"]
    assert "retryable_run_missing_next_retry_at" in bad["blocked_reasons"]

    try:
        build_snapshot(healthy, now, review_warn_hours=168, review_block_hours=72)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid aging thresholds must fail closed")

    print("OPS HEALTH SNAPSHOT SELFTEST OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

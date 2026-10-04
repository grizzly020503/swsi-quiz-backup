#!/usr/bin/env python3
"""Build a compact, provider-neutral health snapshot from durable ops ledger state.

This is a read-only projection. It does not query GitHub, claim/retry work, write
Supabase, resolve review items, or persist runtime state to Git.  It deliberately
reuses the existing pure durable-ledger projection in ``ops_task_watchdog`` and
adds action/aging semantics that can later be consumed by the watchdog, an
independent heartbeat, or an admin surface.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ops_task_watchdog import parse_time, summarize_ledger_state

SCHEMA_VERSION = 1
DEFAULT_REVIEW_WARN_HOURS = 72.0
DEFAULT_REVIEW_BLOCK_HOURS = 168.0


def _stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _row_observed_at(row: dict[str, Any]) -> datetime:
    for field in ("heartbeat_at", "completed_at", "started_at", "last_success_at"):
        value = row.get(field)
        if value:
            return parse_time(str(value))
    raise ValueError("run row has no observable timestamp")


def _validate_thresholds(warn_hours: float, block_hours: float) -> None:
    if warn_hours <= 0 or block_hours <= 0 or block_hours < warn_hours:
        raise ValueError("review thresholds require block_hours >= warn_hours > 0")


def build_snapshot(
    ledger_state: Any,
    now: datetime,
    *,
    review_warn_hours: float = DEFAULT_REVIEW_WARN_HOURS,
    review_block_hours: float = DEFAULT_REVIEW_BLOCK_HOURS,
) -> dict[str, Any]:
    """Return a compact health snapshot while preserving old watchdog fields."""
    _validate_thresholds(review_warn_hours, review_block_hours)
    base = summarize_ledger_state(ledger_state, now)
    runs = ledger_state["runs"]
    reviews = ledger_state["review_items"]

    latest_by_task: dict[str, tuple[datetime, dict[str, Any]]] = {}
    for key, row in runs.items():
        if not isinstance(row, dict):
            raise ValueError(f"ledger run {key!r} must be an object")
        task_id = str(row.get("task_id") or "").strip()
        if not task_id:
            raise ValueError(f"ledger run {key!r} is missing task_id")
        observed = _row_observed_at(row)
        current = latest_by_task.get(task_id)
        if current is None or observed > current[0]:
            latest_by_task[task_id] = (observed, row)

    latest_status_counts: dict[str, int] = {}
    task_states: dict[str, dict[str, Any]] = {}
    retry_due_tasks: list[str] = []
    latest_terminal_or_quarantined: list[str] = []
    retry_contract_errors: list[str] = []

    for task_id, (observed, row) in sorted(latest_by_task.items()):
        status = str(row.get("status") or "").strip()
        latest_status_counts[status] = latest_status_counts.get(status, 0) + 1
        next_retry_at = row.get("next_retry_at")
        retry_due = False
        if status == "failed_retryable":
            if not next_retry_at:
                retry_contract_errors.append(task_id)
            else:
                retry_due = parse_time(str(next_retry_at)) <= now
                if retry_due:
                    retry_due_tasks.append(task_id)
        if status in {"failed_terminal", "quarantined"}:
            latest_terminal_or_quarantined.append(task_id)

        task_states[task_id] = {
            "status": status,
            "observed_at": _stamp(observed),
            "last_success_at": base["task_last_success"].get(task_id),
            "attempt": row.get("attempt"),
            "max_attempts": row.get("max_attempts"),
            "next_retry_at": next_retry_at,
            "retry_due": retry_due,
        }

    open_reviews: list[dict[str, Any]] = []
    review_due_now = 0
    review_scheduled = 0
    review_without_next_check = 0
    review_warn_age = 0
    review_block_age = 0
    review_task_counts: dict[str, int] = {}
    age_buckets = {"lt_24h": 0, "24_72h": 0, "72_168h": 0, "gte_168h": 0}

    for item_id, row in reviews.items():
        if not isinstance(row, dict):
            raise ValueError(f"review item {item_id!r} must be an object")
        if row.get("state") != "open":
            continue
        first_seen = parse_time(str(row.get("first_seen_at") or ""))
        age_hours = max(0.0, (now - first_seen).total_seconds() / 3600.0)
        next_check_at = row.get("next_check_at")
        if next_check_at:
            due_now = parse_time(str(next_check_at)) <= now
            due_state = "due_now" if due_now else "scheduled"
            if due_now:
                review_due_now += 1
            else:
                review_scheduled += 1
        else:
            due_state = "manual_now"
            review_without_next_check += 1
            review_due_now += 1

        if age_hours >= review_block_hours:
            review_block_age += 1
        elif age_hours >= review_warn_hours:
            review_warn_age += 1

        if age_hours < 24:
            age_buckets["lt_24h"] += 1
        elif age_hours < 72:
            age_buckets["24_72h"] += 1
        elif age_hours < 168:
            age_buckets["72_168h"] += 1
        else:
            age_buckets["gte_168h"] += 1

        task_id = str(row.get("task_id") or "unknown")
        review_task_counts[task_id] = review_task_counts.get(task_id, 0) + 1
        open_reviews.append(
            {
                "item_id": row.get("item_id") or item_id,
                "task_id": task_id,
                "reason": str(row.get("reason") or "unknown"),
                "age_hours": round(age_hours, 2),
                "attempt": int(row.get("attempt") or 0),
                "next_check_at": next_check_at,
                "due_state": due_state,
            }
        )

    open_reviews.sort(key=lambda row: row["age_hours"], reverse=True)
    expired_leases = int(base["expired_active_leases"])

    blocked_reasons: list[str] = []
    attention_reasons: list[str] = []
    if expired_leases:
        blocked_reasons.append("expired_active_lease")
    if latest_terminal_or_quarantined:
        blocked_reasons.append("latest_task_terminal_or_quarantined")
    if retry_contract_errors:
        blocked_reasons.append("retryable_run_missing_next_retry_at")
    if review_block_age:
        blocked_reasons.append("review_age_exceeded_block_threshold")

    if retry_due_tasks:
        attention_reasons.append("retry_due")
    if review_due_now:
        attention_reasons.append("review_due")
    if review_warn_age:
        attention_reasons.append("review_age_exceeded_warn_threshold")
    if latest_status_counts.get("failed_retryable", 0) and "retry_due" not in attention_reasons:
        attention_reasons.append("retry_pending")

    health_status = "blocked" if blocked_reasons else "attention" if attention_reasons else "healthy"

    # Keep the pre-existing watchdog keys at top level so current consumers can
    # migrate incrementally instead of breaking when this projection is adopted.
    return {
        **base,
        "snapshot_schema_version": SCHEMA_VERSION,
        "generated_at": _stamp(now),
        "projection": "durable_ops_health_v1",
        "health_status": health_status,
        "blocked_reasons": blocked_reasons,
        "attention_reasons": attention_reasons,
        "latest_task_status_counts": latest_status_counts,
        "task_states": task_states,
        "action_counts": {
            "retry_due": len(retry_due_tasks),
            "expired_active_leases": expired_leases,
            "latest_terminal_or_quarantined": len(latest_terminal_or_quarantined),
            "review_due": review_due_now,
            "review_scheduled": review_scheduled,
            "review_without_next_check": review_without_next_check,
            "review_warn_age": review_warn_age,
            "review_block_age": review_block_age,
        },
        "review_age_buckets": age_buckets,
        "review_task_counts": review_task_counts,
        "review_thresholds_hours": {
            "warn": review_warn_hours,
            "block": review_block_hours,
        },
        "next_actions": {
            "retry_tasks": retry_due_tasks,
            "terminal_or_quarantined_tasks": latest_terminal_or_quarantined,
            "retry_contract_error_tasks": retry_contract_errors,
            "review_items": [row["item_id"] for row in open_reviews if row["due_state"] != "scheduled"][:50],
        },
        "oldest_open_reviews": open_reviews[:10],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SWSI durable ops health snapshot")
    parser.add_argument("--ledger-state", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--now", help="ISO-8601 timestamp for deterministic runs")
    parser.add_argument("--review-warn-hours", type=float, default=DEFAULT_REVIEW_WARN_HOURS)
    parser.add_argument("--review-block-hours", type=float, default=DEFAULT_REVIEW_BLOCK_HOURS)
    args = parser.parse_args()

    state = json.loads(args.ledger_state.read_text(encoding="utf-8"))
    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    snapshot = build_snapshot(
        state,
        now,
        review_warn_hours=args.review_warn_hours,
        review_block_hours=args.review_block_hours,
    )
    rendered = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

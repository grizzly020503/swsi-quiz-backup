#!/usr/bin/env python3
"""Backend-neutral SWSI ops-ledger contract harness.

Local JSON is fixture/test storage only. Runtime state must never be committed
back to Git merely to persist job progress.
"""
from __future__ import annotations

import argparse, json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
TERMINAL = {"success", "no_change", "failed_terminal", "quarantined"}
STATUSES = TERMINAL | {"running", "failed_retryable"}
OUTCOMES = TERMINAL | {"failed_retryable"}
REVIEW_TERMINAL = {"resolved", "superseded", "invalid"}


def parse_time(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("timestamp is empty")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def empty_state() -> dict[str, Any]:
    return {"schema_version": 1, "runs": {}, "review_items": {}}


def run_key(task_id: str, idempotency_key: str) -> str:
    if not task_id.strip() or not idempotency_key.strip():
        raise ValueError("task_id and idempotency_key are required")
    return f"{task_id}:{idempotency_key}"


def validate(state: Any) -> None:
    if not isinstance(state, dict) or state.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("ledger must be schema_version=1")
    if not isinstance(state.get("runs"), dict) or not isinstance(state.get("review_items"), dict):
        raise ValueError("runs and review_items must be objects")
    for key, row in state["runs"].items():
        if row.get("status") not in STATUSES:
            raise ValueError(f"{key}: invalid status")
        attempt, maximum = int(row.get("attempt", 0)), int(row.get("max_attempts", 0))
        if attempt < 1 or maximum < 1 or attempt > maximum:
            raise ValueError(f"{key}: invalid attempt bounds")
        if row["status"] == "running" and (not row.get("worker_id") or not row.get("lease_expires_at")):
            raise ValueError(f"{key}: active run needs owner and lease")
        if row["status"] in TERMINAL and not row.get("completed_at"):
            raise ValueError(f"{key}: terminal run needs completed_at")


def claim(state: dict[str, Any], *, task_id: str, idempotency_key: str, worker_id: str,
          now: datetime, lease_seconds: int, max_attempts: int) -> dict[str, Any]:
    if not worker_id.strip() or lease_seconds <= 0 or max_attempts <= 0:
        raise ValueError("worker_id, positive lease_seconds and max_attempts are required")
    key = run_key(task_id, idempotency_key)
    row = state["runs"].get(key)
    if row is None:
        row = {
            "task_id": task_id, "idempotency_key": idempotency_key, "status": "running",
            "attempt": 1, "max_attempts": max_attempts, "worker_id": worker_id,
            "started_at": stamp(now), "heartbeat_at": stamp(now),
            "lease_expires_at": stamp(now + timedelta(seconds=lease_seconds)),
            "completed_at": None, "last_success_at": None, "checkpoint_version": 1,
            "checkpoint": None, "processed_count": 0, "error_class": None,
            "error_message": None, "next_retry_at": None,
        }
        state["runs"][key] = row
        return {"result": "claimed", "run": row}
    if row["status"] in TERMINAL:
        return {"result": "already_terminal", "run": row}
    if row["status"] == "running" and parse_time(row["lease_expires_at"]) > now:
        return {"result": "busy", "run": row}
    if row["status"] == "failed_retryable" and row.get("next_retry_at") and parse_time(row["next_retry_at"]) > now:
        return {"result": "retry_not_due", "run": row}
    if int(row["attempt"]) >= int(row["max_attempts"]):
        row.update(status="failed_terminal", completed_at=stamp(now), worker_id=None,
                   lease_expires_at=None, next_retry_at=None)
        row["error_class"] = row.get("error_class") or "attempt_limit"
        row["error_message"] = row.get("error_message") or "retry limit reached"
        return {"result": "attempt_limit", "run": row}
    row.update(status="running", attempt=int(row["attempt"]) + 1, worker_id=worker_id,
               heartbeat_at=stamp(now), lease_expires_at=stamp(now + timedelta(seconds=lease_seconds)),
               completed_at=None, next_retry_at=None)
    return {"result": "reclaimed", "run": row}


def owned(state: dict[str, Any], key: str, worker_id: str, now: datetime) -> dict[str, Any]:
    row = state["runs"][key]
    if row.get("status") != "running" or row.get("worker_id") != worker_id:
        raise PermissionError("worker does not own active run")
    if parse_time(row["lease_expires_at"]) <= now:
        raise TimeoutError("lease expired")
    return row


def checkpoint(state: dict[str, Any], *, key: str, worker_id: str, now: datetime,
               value: Any, processed_count: int, version: int = 1) -> None:
    if version != 1 or processed_count < 0:
        raise ValueError("unsupported checkpoint version/count")
    row = owned(state, key, worker_id, now)
    row.update(checkpoint_version=version, checkpoint=value, processed_count=processed_count,
               heartbeat_at=stamp(now))


def complete(state: dict[str, Any], *, key: str, worker_id: str, now: datetime,
             outcome: str, error_class: str | None = None, error_message: str | None = None,
             retry_after_seconds: int = 60) -> None:
    if outcome not in OUTCOMES:
        raise ValueError("invalid outcome")
    row = owned(state, key, worker_id, now)
    row.update(status=outcome, heartbeat_at=stamp(now), worker_id=None, lease_expires_at=None,
               error_class=error_class, error_message=error_message)
    if outcome == "failed_retryable":
        row.update(completed_at=None, next_retry_at=stamp(now + timedelta(seconds=max(1, retry_after_seconds))))
    else:
        row.update(completed_at=stamp(now), next_retry_at=None)
        if outcome in {"success", "no_change"}:
            row["last_success_at"] = stamp(now)


def upsert_review(state: dict[str, Any], *, item_id: str, reason: str, source_ref: str, now: datetime) -> None:
    if not item_id.strip() or not reason.strip():
        raise ValueError("item_id and reason are required")
    row = state["review_items"].get(item_id)
    if row is None:
        state["review_items"][item_id] = {
            "item_id": item_id, "reason": reason, "source_ref": source_ref, "state": "open",
            "first_seen_at": stamp(now), "last_attempt_at": None, "attempt": 0,
            "last_error": None, "next_check_at": None, "resolved_at": None, "resolution": None,
        }
    elif row.get("state") == "open":
        row.update(reason=reason, source_ref=source_ref)


def touch_review(state: dict[str, Any], *, item_id: str, now: datetime, error: str | None,
                 next_check_at: datetime | None) -> None:
    row = state["review_items"][item_id]
    if row.get("state") != "open":
        raise ValueError("review item is not open")
    row.update(attempt=int(row["attempt"]) + 1, last_attempt_at=stamp(now), last_error=error,
               next_check_at=stamp(next_check_at) if next_check_at else None)


def resolve_review(state: dict[str, Any], *, item_id: str, now: datetime, final_state: str,
                   resolution: str) -> None:
    if final_state not in REVIEW_TERMINAL:
        raise ValueError("invalid review terminal state")
    state["review_items"][item_id].update(state=final_state, resolved_at=stamp(now), resolution=resolution)


def summarize(state: dict[str, Any], now: datetime) -> dict[str, Any]:
    counts: dict[str, int] = {}
    last_success: dict[str, str] = {}
    for row in state["runs"].values():
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        task, success = row.get("task_id"), row.get("last_success_at")
        if task and success and (task not in last_success or parse_time(success) > parse_time(last_success[task])):
            last_success[task] = success
    open_items = [x for x in state["review_items"].values() if x.get("state") == "open"]
    oldest = None
    if open_items:
        first = min(parse_time(x["first_seen_at"]) for x in open_items)
        oldest = round(max(0.0, (now - first).total_seconds() / 3600), 2)
    return {"schema_version": 1, "runs_total": len(state["runs"]), "run_status_counts": counts,
            "task_last_success": last_success, "review_open": len(open_items),
            "review_oldest_age_hours": oldest}


def self_test() -> dict[str, Any]:
    s, t0 = empty_state(), parse_time("2026-10-02T00:00:00Z")
    a = claim(s, task_id="full-corpus-question-qa", idempotency_key="dataset-a", worker_id="w1",
              now=t0, lease_seconds=60, max_attempts=3)
    assert a["result"] == "claimed"
    key = run_key("full-corpus-question-qa", "dataset-a")
    assert claim(s, task_id="full-corpus-question-qa", idempotency_key="dataset-a", worker_id="w2",
                 now=t0 + timedelta(seconds=10), lease_seconds=60, max_attempts=3)["result"] == "busy"
    checkpoint(s, key=key, worker_id="w1", now=t0 + timedelta(seconds=20),
               value={"session": "110-2"}, processed_count=12)
    complete(s, key=key, worker_id="w1", now=t0 + timedelta(seconds=30), outcome="failed_retryable",
             error_class="http_503", retry_after_seconds=30)
    assert claim(s, task_id="full-corpus-question-qa", idempotency_key="dataset-a", worker_id="w2",
                 now=t0 + timedelta(seconds=40), lease_seconds=60, max_attempts=3)["result"] == "retry_not_due"
    again = claim(s, task_id="full-corpus-question-qa", idempotency_key="dataset-a", worker_id="w2",
                  now=t0 + timedelta(seconds=61), lease_seconds=60, max_attempts=3)
    assert again["result"] == "reclaimed" and again["run"]["processed_count"] == 12
    complete(s, key=key, worker_id="w2", now=t0 + timedelta(seconds=70), outcome="success")
    assert claim(s, task_id="full-corpus-question-qa", idempotency_key="dataset-a", worker_id="w3",
                 now=t0 + timedelta(seconds=80), lease_seconds=60, max_attempts=3)["result"] == "already_terminal"
    claim(s, task_id="moex-social-worker-sync", idempotency_key="weekly-1", worker_id="w1",
          now=t0, lease_seconds=10, max_attempts=2)
    k2 = run_key("moex-social-worker-sync", "weekly-1")
    assert claim(s, task_id="moex-social-worker-sync", idempotency_key="weekly-1", worker_id="w2",
                 now=t0 + timedelta(seconds=11), lease_seconds=10, max_attempts=2)["result"] == "reclaimed"
    complete(s, key=k2, worker_id="w2", now=t0 + timedelta(seconds=12), outcome="failed_retryable",
             error_class="parse_error", retry_after_seconds=1)
    exhausted = claim(s, task_id="moex-social-worker-sync", idempotency_key="weekly-1", worker_id="w3",
                      now=t0 + timedelta(seconds=14), lease_seconds=10, max_attempts=2)
    assert exhausted["result"] == "attempt_limit" and exhausted["run"]["next_retry_at"] is None
    upsert_review(s, item_id="source:example", reason="source_format_changed", source_ref="example", now=t0)
    touch_review(s, item_id="source:example", now=t0 + timedelta(hours=2), error="selector_missing",
                 next_check_at=t0 + timedelta(hours=8))
    assert summarize(s, t0 + timedelta(hours=3))["review_oldest_age_hours"] == 3.0
    resolve_review(s, item_id="source:example", now=t0 + timedelta(hours=4), final_state="resolved",
                   resolution="parser updated")
    validate(s)
    return {"ok": True, "summary": summarize(s, t0 + timedelta(hours=4))}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--state", type=Path)
    p.add_argument("--summary", action="store_true")
    p.add_argument("--now")
    args = p.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2)); return 0
    if not args.state:
        raise SystemExit("--state is required unless --self-test is used")
    state = json.loads(args.state.read_text(encoding="utf-8")); validate(state)
    if args.summary:
        now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
        print(json.dumps(summarize(state, now), ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"ok": True, "runs": len(state["runs"]), "review_items": len(state["review_items"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

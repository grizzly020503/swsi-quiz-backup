#!/usr/bin/env python3
"""Supabase Data API adapter contract for #269.

This module deliberately has no live-write CLI. Callers must opt in from trusted
server-side code and supply a service-role credential through environment/runtime
configuration. Self-test uses an in-memory transport and never touches a network.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, Protocol


class Transport(Protocol):
    def rpc(self, name: str, payload: dict[str, Any]) -> Any: ...
    def select(self, table: str, query: dict[str, str]) -> Any: ...


@dataclass
class OpsLedgerSupabaseAdapter:
    transport: Transport

    def claim(self, *, task_id: str, idempotency_key: str, worker_id: str,
              now: str, lease_seconds: int = 900, max_attempts: int = 3) -> Any:
        return self.transport.rpc("swsi_ops_claim_task", {
            "p_task_id": task_id,
            "p_idempotency_key": idempotency_key,
            "p_worker_id": worker_id,
            "p_now": now,
            "p_lease_seconds": lease_seconds,
            "p_max_attempts": max_attempts,
        })

    def checkpoint(self, *, task_id: str, idempotency_key: str, worker_id: str,
                   checkpoint: Any, processed_count: int, now: str,
                   checkpoint_version: int = 1, extend_lease_seconds: int = 900) -> Any:
        if checkpoint_version != 1:
            raise ValueError("unknown checkpoint version: fail closed")
        return self.transport.rpc("swsi_ops_checkpoint_task", {
            "p_task_id": task_id,
            "p_idempotency_key": idempotency_key,
            "p_worker_id": worker_id,
            "p_checkpoint": checkpoint,
            "p_processed_count": processed_count,
            "p_now": now,
            "p_checkpoint_version": checkpoint_version,
            "p_extend_lease_seconds": extend_lease_seconds,
        })

    def heartbeat(self, *, task_id: str, idempotency_key: str, worker_id: str,
                  now: str, extend_lease_seconds: int = 900) -> Any:
        return self.transport.rpc("swsi_ops_heartbeat_task", {
            "p_task_id": task_id,
            "p_idempotency_key": idempotency_key,
            "p_worker_id": worker_id,
            "p_now": now,
            "p_extend_lease_seconds": extend_lease_seconds,
        })

    def complete(self, *, task_id: str, idempotency_key: str, worker_id: str,
                 outcome: str, now: str, error_class: str | None = None,
                 error_message: str | None = None, retry_after_seconds: int = 60) -> Any:
        allowed = {"success", "no_change", "failed_retryable", "failed_terminal", "quarantined"}
        if outcome not in allowed:
            raise ValueError(f"invalid outcome: {outcome}")
        return self.transport.rpc("swsi_ops_complete_task", {
            "p_task_id": task_id,
            "p_idempotency_key": idempotency_key,
            "p_worker_id": worker_id,
            "p_outcome": outcome,
            "p_now": now,
            "p_error_class": error_class,
            "p_error_message": error_message,
            "p_retry_after_seconds": retry_after_seconds,
        })

    def recent_runs(self, *, task_id: str, limit: int = 20) -> Any:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be 1..100")
        return self.transport.select("swsi_ops_task_runs", {
            "select": "task_id,idempotency_key,status,attempt,max_attempts,heartbeat_at,completed_at,last_success_at,processed_count,error_class,next_retry_at",
            "task_id": f"eq.{task_id}",
            "order": "heartbeat_at.desc",
            "limit": str(limit),
        })

    def open_review_items(self, *, limit: int = 100) -> Any:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be 1..500")
        return self.transport.select("swsi_ops_review_items", {
            "select": "item_id,task_id,reason,source_ref,state,first_seen_at,last_attempt_at,attempt,last_error,next_check_at",
            "state": "eq.open",
            "order": "first_seen_at.asc",
            "limit": str(limit),
        })


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def rpc(self, name: str, payload: dict[str, Any]) -> Any:
        self.calls.append(("rpc", name, payload))
        return {"ok": True, "name": name}

    def select(self, table: str, query: dict[str, str]) -> Any:
        self.calls.append(("select", table, dict(query)))
        return []


def self_test() -> dict[str, Any]:
    fake = FakeTransport()
    adapter = OpsLedgerSupabaseAdapter(fake)
    now = "2026-10-02T10:00:00Z"
    adapter.claim(task_id="full-corpus-question-qa", idempotency_key="rev-a", worker_id="w1", now=now)
    adapter.checkpoint(task_id="full-corpus-question-qa", idempotency_key="rev-a", worker_id="w1",
                       checkpoint={"session": "110-2"}, processed_count=100, now=now)
    adapter.heartbeat(task_id="full-corpus-question-qa", idempotency_key="rev-a", worker_id="w1", now=now)
    adapter.complete(task_id="full-corpus-question-qa", idempotency_key="rev-a", worker_id="w1",
                     outcome="no_change", now=now)
    adapter.recent_runs(task_id="full-corpus-question-qa")
    adapter.open_review_items()
    assert [c[1] for c in fake.calls[:4]] == [
        "swsi_ops_claim_task", "swsi_ops_checkpoint_task", "swsi_ops_heartbeat_task", "swsi_ops_complete_task"
    ]
    assert fake.calls[1][2]["p_checkpoint_version"] == 1
    assert fake.calls[3][2]["p_outcome"] == "no_change"
    try:
        adapter.checkpoint(task_id="x", idempotency_key="y", worker_id="z", checkpoint={},
                           processed_count=0, now=now, checkpoint_version=2)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown checkpoint version must fail closed")
    return {"ok": True, "calls": len(fake.calls)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not args.self_test:
        raise SystemExit("Only --self-test is supported in this checkpoint; no live-write CLI is exposed.")
    print(json.dumps(self_test(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

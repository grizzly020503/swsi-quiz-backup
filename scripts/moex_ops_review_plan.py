#!/usr/bin/env python3
"""Build a zero-network gateway request plan from one MOEX ops-event.

This module does not call the candidate gateway, Supabase, GitHub, or any other
network service. It only validates the event against the static durable-review
namespace policy and, when manual review is required, returns the exact
`review_upsert` request body that a future trusted server-side caller may send.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "data/ops_review_namespace.v1.json"
TASK_ID = "moex-social-worker-sync"
ALLOWED_EVENT_TYPES = {"moex_probe_decision", "moex_payload_scheme_decision"}
REVIEW_OUTCOMES = {"quarantined", "failed_terminal"}
REVIEW_ACTIONS = {"quarantine", "manual_review"}
NON_REVIEW_ACTIONS = {"continue", "retry"}


def _policy() -> tuple[str, set[str]]:
    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("unknown_task_policy") != "deny":
        raise ValueError("review namespace policy must be schema_version=1 and fail closed")
    for row in payload.get("task_namespaces") or []:
        if row.get("task_id") != TASK_ID:
            continue
        prefix = str(row.get("item_prefix") or "").strip()
        reasons = {str(value) for value in row.get("allowed_reasons") or []}
        if not prefix or row.get("reason_policy") != "explicit_allowlist" or not reasons:
            raise ValueError("MOEX review namespace policy is incomplete")
        return prefix, reasons
    raise ValueError("MOEX review namespace is missing from policy")


def _text(value: Any, *, field: str, max_len: int) -> str:
    text = str(value or "").strip()
    if not text or len(text) > max_len:
        raise ValueError(f"{field} is required or too long")
    return text


def build_review_plan(event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict) or event.get("schema_version") != 1:
        raise ValueError("ops-event must be a schema_version=1 object")
    if event.get("task_id") != TASK_ID:
        raise ValueError("ops-event task_id is not MOEX")
    event_type = _text(event.get("event_type"), field="event_type", max_len=80)
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError(f"unsupported MOEX ops-event type: {event_type}")
    exam_code = _text(event.get("exam_code"), field="exam_code", max_len=12)
    if not re.fullmatch(r"\d{3}(030|100)", exam_code):
        raise ValueError(f"invalid exam_code: {exam_code}")

    action = _text(event.get("action"), field="action", max_len=64)
    review_required = event.get("review_required")
    review_item = event.get("review_item")
    ledger_outcome = event.get("ledger_outcome")

    if review_required is False:
        if action not in NON_REVIEW_ACTIONS:
            raise ValueError("non-review event has unsupported action")
        if review_item is not None:
            raise ValueError("non-review event must not carry review_item")
        if action == "continue" and ledger_outcome is not None:
            raise ValueError("continue event must not complete the durable task")
        if action == "retry" and ledger_outcome != "failed_retryable":
            raise ValueError("retry event must use failed_retryable")
        return {
            "schema_version": 1,
            "task_id": TASK_ID,
            "exam_code": exam_code,
            "operation": None,
            "gateway_request": None,
            "reason": "review_not_required",
        }

    if review_required is not True:
        raise ValueError("review_required must be an explicit boolean")
    if action not in REVIEW_ACTIONS or ledger_outcome not in REVIEW_OUTCOMES:
        raise ValueError("manual-review event has incompatible action/outcome")
    if not isinstance(review_item, dict):
        raise ValueError("review_required event must carry review_item")

    prefix, allowed_reasons = _policy()
    item_id = _text(review_item.get("item_id"), field="review_item.item_id", max_len=512)
    if not item_id.startswith(prefix):
        raise ValueError("MOEX review item is outside its allowed namespace")
    if review_item.get("task_id") != TASK_ID:
        raise ValueError("review item task_id does not match MOEX")
    reason = _text(review_item.get("reason"), field="review_item.reason", max_len=512)
    if reason not in allowed_reasons:
        raise ValueError(f"MOEX review reason is not allowlisted: {reason}")
    source_ref = _text(review_item.get("source_ref"), field="review_item.source_ref", max_len=1000)
    metadata = review_item.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("review_item.metadata must be an object")
    if metadata.get("schema_version") != 1:
        raise ValueError("review metadata must be schema_version=1")
    if metadata.get("exam_code") != exam_code:
        raise ValueError("review metadata exam_code must match event exam_code")
    if len(json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))) > 20000:
        raise ValueError("review metadata exceeds gateway size limit")

    request = {
        "action": "review_upsert",
        "task_id": TASK_ID,
        "item_id": item_id,
        "reason": reason,
        "source_ref": source_ref,
        "metadata": metadata,
    }
    return {
        "schema_version": 1,
        "task_id": TASK_ID,
        "exam_code": exam_code,
        "operation": "review_upsert",
        "gateway_request": request,
        "reason": reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a dry-run MOEX durable-review gateway request")
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    event = json.loads(args.event.read_text(encoding="utf-8"))
    plan = build_review_plan(event)
    rendered = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail-closed check for an isolated SWSI backup-restore target.

Input is a count-only JSON document in SWSI_RESTORE_PREFLIGHT. NEVER accept a
production database URL or credentials in this command's arguments or output.
This is a gate, not proof that the target is genuinely isolated: the caller
MUST also enforce separate environment/project identity and explicit consent.
"""
from __future__ import annotations

import json
import os
import sys

# Use explicit table-specific counts, not pg_stat_user_tables. Planner estimates
# are not suitable for a destructive-data safety gate.
REQUIRED_EMPTY = (
    "auth_users",
    "storage_objects",
    "feedback_reports",
    "usage_daily_rows",
    "ai_telemetry_client_daily_rows",
    "ai_telemetry_5m_rows",
    "ops_task_runs",
    "ops_review_items",
    "admin_allowlist_rows",
)


def validate(payload: object) -> None:
    if type(payload) is not dict:
        raise ValueError("preflight is not a JSON object")
    for field in REQUIRED_EMPTY:
        if field not in payload:
            raise ValueError(f"missing required empty-target count: {field}")
        count = payload[field]
        # Reject bool, float, numeric string, null and negative values. A blank
        # or ambiguous count must NEVER be treated as zero.
        if type(count) is not int or count != 0:
            raise ValueError(f"isolated target is not empty at {field}")


def main() -> int:
    try:
        raw = os.environ.get("SWSI_RESTORE_PREFLIGHT", "")
        if not raw or len(raw) > 8192:
            raise ValueError("missing/oversized count-only preflight")
        validate(json.loads(raw))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        # This deliberately omits the original payload and all URL/credentials.
        print(f"ISOLATED TARGET PREFLIGHT REFUSED: {exc}", file=sys.stderr)
        return 64
    print("ISOLATED TARGET PRIVATE TABLE COUNT CHECK OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Attach durable ledger identities to a Full Corpus QA diagnostic report.

Read-only with respect to SWSI data. The only optional write is replacing or
creating the diagnostic JSON file explicitly supplied by the caller.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ops_task_identity import child_identity
from ops_task_identity_resolver import DEFAULT_CONTRACT, read_json, resolve, validate_contract

TASK_ID = "full-corpus-question-qa"
UNIT_TYPE = "exam_session"


def canonical_unit_id(row: dict[str, Any]) -> str:
    year = str(row.get("year") or "").strip()
    round_name = str(row.get("round") or "").strip()
    if not year or not round_name:
        raise ValueError("full-corpus session needs year and round")
    return f"{year}-{round_name}"


def decorate_report(report: Any, parent_key: str) -> dict[str, Any]:
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("full-corpus report must be schema_version=1")
    sessions = report.get("sessions")
    if not isinstance(sessions, list):
        raise ValueError("full-corpus report sessions[] is required")
    seen: set[str] = set()
    decorated_sessions: list[dict[str, Any]] = []
    for raw in sessions:
        if not isinstance(raw, dict):
            raise ValueError("every full-corpus session must be an object")
        unit_id = canonical_unit_id(raw)
        if unit_id in seen:
            raise ValueError(f"duplicate full-corpus session identity: {unit_id}")
        seen.add(unit_id)
        row = dict(raw)
        row["ops_identity"] = {
            "parent_task": TASK_ID,
            "unit_type": UNIT_TYPE,
            "unit_id": unit_id,
            "idempotency_key": child_identity(parent_key, UNIT_TYPE, unit_id),
        }
        decorated_sessions.append(row)
    out = dict(report)
    out["sessions"] = decorated_sessions
    out["ops_identity"] = {
        "task_id": TASK_ID,
        "strategy": "semantic_files_v1",
        "idempotency_key": parent_key,
        "checkpoint_unit": "manifest_exam_session",
        "session_count": len(decorated_sessions),
    }
    return out


def self_test() -> dict[str, Any]:
    sample = {
        "schema_version": 1,
        "dataset_revision": "fixture",
        "sessions": [
            {"year": "115", "round": "第一次"},
            {"year": "115", "round": "第二次"},
        ],
    }
    parent = "sem1:" + "a" * 64
    out = decorate_report(sample, parent)
    keys = [row["ops_identity"]["idempotency_key"] for row in out["sessions"]]
    assert out["ops_identity"]["session_count"] == 2
    assert len(set(keys)) == 2
    assert all(key.startswith("child1:") for key in keys)
    try:
        decorate_report({"schema_version": 1, "sessions": [sample["sessions"][0], sample["sessions"][0]]}, parent)
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate session must fail closed")
    return {"ok": True, "sessions": 2, "duplicate_fail_closed": True}


def main() -> int:
    p = argparse.ArgumentParser(description="Decorate Full Corpus QA report with durable task identities")
    p.add_argument("--report", type=Path)
    p.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    p.add_argument("--out", type=Path)
    p.add_argument("--in-place", action="store_true")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()

    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0
    if not args.report:
        raise SystemExit("--report is required unless --self-test is used")
    if args.in_place and args.out:
        raise SystemExit("--in-place and --out are mutually exclusive")
    contract = read_json(args.contract)
    validate_contract(contract)
    parent = resolve(contract, TASK_ID)["idempotency_key"]
    report = json.loads(args.report.read_text(encoding="utf-8"))
    rendered = json.dumps(decorate_report(report, parent), ensure_ascii=False, indent=2) + "\n"
    target = args.report if args.in_place else args.out
    if target:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

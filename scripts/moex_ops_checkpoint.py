#!/usr/bin/env python3
"""Build durable #269 MOEX run/stage checkpoint identities without writing a ledger."""
from __future__ import annotations

import argparse
import json
from typing import Any

from ops_task_identity import child_identity, trigger_run_identity

TASK_ID = "moex-social-worker-sync"
PROVIDER = "github"
STAGES = {
    "legal_watch",
    "official_fetch",
    "backup_payload",
    "essay_enrichment_validation",
    "essay_enrichment_sync",
    "local_health",
    "import_changed_exam",
    "remote_health",
    "persist_repo_state",
}


def build_checkpoint(run_id: str, stage: str, exam_code: str | None = None) -> dict[str, Any]:
    run_id = str(run_id or "").strip()
    stage = str(stage or "").strip()
    exam_code = str(exam_code or "").strip() or None
    if not run_id:
        raise ValueError("run_id is required")
    if stage not in STAGES:
        raise ValueError(f"unknown MOEX stage: {stage}")
    if stage == "import_changed_exam" and not exam_code:
        raise ValueError("import_changed_exam requires exam_code")
    if stage != "import_changed_exam" and exam_code:
        raise ValueError(f"{stage} must not carry exam_code")

    parent = trigger_run_identity(TASK_ID, PROVIDER, run_id)
    if exam_code:
        unit_type = "exam_import"
        unit_id = exam_code
    else:
        unit_type = "pipeline_stage"
        unit_id = stage
    stage_key = child_identity(parent, unit_type, unit_id)
    return {
        "schema_version": 1,
        "task_id": TASK_ID,
        "provider": PROVIDER,
        "run_id": run_id,
        "idempotency_key": parent,
        "checkpoint": {
            "version": 1,
            "stage": stage,
            "exam_code": exam_code,
            "unit_type": unit_type,
            "unit_id": unit_id,
            "idempotency_key": stage_key,
        },
    }


def self_test() -> dict[str, Any]:
    a = build_checkpoint("123", "official_fetch")
    b = build_checkpoint("123", "official_fetch")
    c = build_checkpoint("123", "remote_health")
    d = build_checkpoint("124", "official_fetch")
    e = build_checkpoint("123", "import_changed_exam", "116010")
    assert a == b
    assert a["idempotency_key"] == c["idempotency_key"]
    assert a["checkpoint"]["idempotency_key"] != c["checkpoint"]["idempotency_key"]
    assert a["idempotency_key"] != d["idempotency_key"]
    assert e["checkpoint"]["unit_type"] == "exam_import"
    try:
        build_checkpoint("123", "import_changed_exam")
    except ValueError:
        pass
    else:
        raise AssertionError("exam import without exam_code must fail closed")
    return {"ok": True, "same_run_resumable": True, "stage_isolated": True, "new_run_new_identity": True}


def main() -> int:
    p = argparse.ArgumentParser(description="Build MOEX durable run/stage checkpoint identity")
    p.add_argument("--run-id")
    p.add_argument("--stage")
    p.add_argument("--exam-code")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0
    if not args.run_id or not args.stage:
        raise SystemExit("--run-id and --stage are required unless --self-test is used")
    print(json.dumps(build_checkpoint(args.run_id, args.stage, args.exam_code), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

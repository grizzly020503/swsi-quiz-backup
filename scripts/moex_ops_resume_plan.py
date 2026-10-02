#!/usr/bin/env python3
"""Build a migration-ready, read-only MOEX resume plan for #274.

This module does not write the durable ledger or call Supabase. It converts the
existing GITHUB_RUN_ID-based MOEX checkpoint identities into an ordered plan so
runtime wiring can resume a rerun without repeating completed side effects.
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Iterable

from moex_ops_checkpoint import TASK_ID, build_checkpoint

STAGE_ORDER = [
    "legal_watch",
    "official_fetch",
    "backup_payload",
    "essay_enrichment_validation",
    "essay_enrichment_sync",
    "local_health",
    "import_changed_exam",
    "remote_health",
    "persist_repo_state",
]

SIDE_EFFECT_CLASS = {
    "legal_watch": "repo_worktree_candidate",
    "official_fetch": "read_only_external",
    "backup_payload": "local_derived_artifact",
    "essay_enrichment_validation": "read_only_validation",
    "essay_enrichment_sync": "remote_mutation",
    "local_health": "read_only_validation",
    "import_changed_exam": "remote_mutation",
    "remote_health": "read_only_remote",
    "persist_repo_state": "git_mutation",
}


def unit(run_id: str, stage: str, exam_code: str | None = None) -> dict[str, Any]:
    row = build_checkpoint(run_id, stage, exam_code)
    cp = row["checkpoint"]
    return {
        "task_id": TASK_ID,
        "run_id": row["run_id"],
        "parent_idempotency_key": row["idempotency_key"],
        "stage": stage,
        "exam_code": cp["exam_code"],
        "unit_type": cp["unit_type"],
        "unit_id": cp["unit_id"],
        "unit_idempotency_key": cp["idempotency_key"],
        "side_effect_class": SIDE_EFFECT_CLASS[stage],
    }


def build_units(run_id: str, changed_exam_codes: Iterable[str] = ()) -> list[dict[str, Any]]:
    codes = sorted({str(code).strip() for code in changed_exam_codes if str(code).strip()})
    rows: list[dict[str, Any]] = []
    for stage in STAGE_ORDER:
        if stage == "import_changed_exam":
            rows.extend(unit(run_id, stage, code) for code in codes)
        else:
            rows.append(unit(run_id, stage))
    return rows


def build_plan(
    run_id: str,
    *,
    changed_exam_codes: Iterable[str] = (),
    completed_unit_keys: Iterable[str] = (),
) -> dict[str, Any]:
    run_id = str(run_id or "").strip()
    if not run_id:
        raise ValueError("run_id is required")
    completed = {str(value).strip() for value in completed_unit_keys if str(value).strip()}
    rows = build_units(run_id, changed_exam_codes)
    known = {row["unit_idempotency_key"] for row in rows}
    unknown = sorted(completed - known)
    if unknown:
        raise ValueError("completed checkpoint does not belong to this run/plan")
    remaining = [row for row in rows if row["unit_idempotency_key"] not in completed]
    parent_keys = {row["parent_idempotency_key"] for row in rows}
    if len(parent_keys) != 1:
        raise AssertionError("one MOEX run must have exactly one parent identity")
    return {
        "schema_version": 1,
        "task_id": TASK_ID,
        "run_id": run_id,
        "parent_idempotency_key": next(iter(parent_keys)),
        "completed_count": len(completed),
        "remaining_count": len(remaining),
        "done": not remaining,
        "units": rows,
        "remaining_units": remaining,
        "safety": {
            "same_github_run_resumes": True,
            "new_github_run_gets_new_parent_identity": True,
            "completed_side_effect_units_are_not_replanned": True,
            "ledger_write_enabled": False,
            "production_mutation_enabled_by_this_module": False,
        },
    }


def classify_pipeline_outcome(*, source_ok: bool, parser_ok: bool, changed_count: int | None) -> str:
    """Map MOEX source result to ledger outcome without treating errors as no-change."""
    if not source_ok:
        return "failed_retryable"
    if not parser_ok or changed_count is None or changed_count < 0:
        return "quarantined"
    return "no_change" if changed_count == 0 else "success"


def self_test() -> dict[str, Any]:
    first = build_plan("37000000001", changed_exam_codes=["116010", "116020"])
    assert first["remaining_count"] == 10
    assert len({row["parent_idempotency_key"] for row in first["units"]}) == 1
    completed = [row["unit_idempotency_key"] for row in first["units"][:4]]
    resumed = build_plan(
        "37000000001",
        changed_exam_codes=["116020", "116010"],
        completed_unit_keys=completed,
    )
    assert resumed["completed_count"] == 4
    assert resumed["remaining_count"] == 6
    assert all(row["unit_idempotency_key"] not in set(completed) for row in resumed["remaining_units"])

    new_dispatch = build_plan("37000000002", changed_exam_codes=["116010", "116020"])
    assert new_dispatch["parent_idempotency_key"] != first["parent_idempotency_key"]
    assert set(row["unit_idempotency_key"] for row in new_dispatch["units"]).isdisjoint(
        row["unit_idempotency_key"] for row in first["units"]
    )

    try:
        build_plan("37000000002", completed_unit_keys=[completed[0]])
    except ValueError:
        pass
    else:
        raise AssertionError("checkpoint from another run must fail closed")

    assert classify_pipeline_outcome(source_ok=True, parser_ok=True, changed_count=0) == "no_change"
    assert classify_pipeline_outcome(source_ok=True, parser_ok=True, changed_count=2) == "success"
    assert classify_pipeline_outcome(source_ok=False, parser_ok=False, changed_count=None) == "failed_retryable"
    assert classify_pipeline_outcome(source_ok=True, parser_ok=False, changed_count=None) == "quarantined"

    remote_mutations = [
        row for row in first["units"] if row["side_effect_class"] == "remote_mutation"
    ]
    assert len(remote_mutations) == 3
    return {
        "ok": True,
        "same_run_resume": True,
        "new_dispatch_isolated": True,
        "cross_run_checkpoint_fail_closed": True,
        "no_change_distinct_from_source_error": True,
        "remote_mutation_units": len(remote_mutations),
        "ledger_write_enabled": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a read-only MOEX durable-ledger resume plan")
    parser.add_argument("--run-id")
    parser.add_argument("--changed-exam", action="append", default=[])
    parser.add_argument("--completed-key", action="append", default=[])
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if not args.run_id:
        raise SystemExit("--run-id is required unless --self-test is used")
    print(json.dumps(
        build_plan(
            args.run_id,
            changed_exam_codes=args.changed_exam,
            completed_unit_keys=args.completed_key,
        ),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

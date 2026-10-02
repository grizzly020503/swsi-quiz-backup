#!/usr/bin/env python3
"""Plan resumable Full Corpus QA session work for the #274 durable ledger.

This module is read-only. It maps the manifest's stable session order to child
idempotency keys and converts the last completed checkpoint into the remaining
work set. It never claims or writes the ledger.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ops_task_identity import child_identity
from ops_task_identity_resolver import DEFAULT_CONTRACT, read_json, resolve, validate_contract
from unified_question_qa import canon_round

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "cdn" / "question-shards" / "manifest.json"
DEFAULT_POLICY = ROOT / "data" / "question_qa_policy_v1.json"
TASK_ID = "full-corpus-question-qa"
UNIT_TYPE = "exam_session"


def unit_id(year: str, round_name: str) -> str:
    year = str(year or "").strip()
    round_name = str(round_name or "").strip()
    if not year or round_name not in {"第一次", "第二次"}:
        raise ValueError(f"invalid session identity: {year!r} {round_name!r}")
    return f"{year}-{round_name}"


def manifest_units(manifest: Any, policy: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    shards = manifest.get("shards")
    if not isinstance(shards, list) or not shards:
        raise ValueError("manifest shards[] is empty or invalid")

    rows: list[dict[str, Any]] = []
    seen_units: set[str] = set()
    seen_files: set[str] = set()
    for index, raw in enumerate(shards):
        if not isinstance(raw, dict):
            raise ValueError(f"shards[{index}] is not an object")
        year = str(raw.get("year") or "").strip()
        round_name = canon_round(raw.get("round"), policy)
        ident = unit_id(year, round_name)
        filename = str(raw.get("file") or "").strip()
        if ident in seen_units:
            raise ValueError(f"duplicate manifest session: {ident}")
        if not filename or filename in seen_files:
            raise ValueError(f"missing or duplicate manifest file: {filename!r}")
        seen_units.add(ident)
        seen_files.add(filename)
        rows.append(
            {
                "index": index,
                "unit_id": ident,
                "year": year,
                "round": round_name,
                "file": filename,
                "question_count": int(raw.get("question_count") or 0),
                "sha256": str(raw.get("sha256") or "").strip().lower(),
            }
        )
    declared = int(manifest.get("shard_count") or len(rows))
    if declared != len(rows):
        raise ValueError(f"manifest shard_count mismatch: declared={declared} actual={len(rows)}")
    return rows


def checkpoint_for(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": 1,
        "completed_unit_id": unit["unit_id"],
        "completed_index": int(unit["index"]),
    }


def build_plan(
    manifest: Any,
    policy: dict[str, Any],
    parent_key: str,
    checkpoint_unit: str | None = None,
) -> dict[str, Any]:
    parent_key = str(parent_key or "").strip()
    if not parent_key:
        raise ValueError("parent idempotency key is required")
    units = manifest_units(manifest, policy)
    rendered: list[dict[str, Any]] = []
    for row in units:
        item = dict(row)
        item["idempotency_key"] = child_identity(parent_key, UNIT_TYPE, row["unit_id"])
        item["checkpoint"] = checkpoint_for(row)
        rendered.append(item)

    completed_count = 0
    checkpoint_unit = str(checkpoint_unit or "").strip() or None
    if checkpoint_unit:
        matches = [row for row in rendered if row["unit_id"] == checkpoint_unit]
        if len(matches) != 1:
            raise ValueError(f"checkpoint unit is not in current manifest: {checkpoint_unit}")
        completed_count = int(matches[0]["index"]) + 1

    remaining = rendered[completed_count:]
    return {
        "schema_version": 1,
        "task_id": TASK_ID,
        "idempotency_key": parent_key,
        "checkpoint_version": 1,
        "checkpoint_unit": checkpoint_unit,
        "manifest_session_count": len(rendered),
        "completed_count": completed_count,
        "remaining_count": len(remaining),
        "done": not remaining,
        "next_unit_id": remaining[0]["unit_id"] if remaining else None,
        "remaining": remaining,
    }


def self_test() -> dict[str, Any]:
    policy = {"round_aliases": {}}
    manifest = {
        "shard_count": 3,
        "shards": [
            {"year": "114", "round": "第一次", "file": "114-1.json", "question_count": 200},
            {"year": "114", "round": "第二次", "file": "114-2.json", "question_count": 200},
            {"year": "115", "round": "第一次", "file": "115-1.json", "question_count": 200},
        ],
    }
    parent = "sem1:" + "a" * 64
    fresh = build_plan(manifest, policy, parent)
    assert fresh["remaining_count"] == 3
    assert fresh["next_unit_id"] == "114-第一次"
    resumed = build_plan(manifest, policy, parent, "114-第二次")
    assert resumed["completed_count"] == 2
    assert [row["unit_id"] for row in resumed["remaining"]] == ["115-第一次"]
    done = build_plan(manifest, policy, parent, "115-第一次")
    assert done["done"] is True and done["remaining_count"] == 0
    assert resumed["remaining"][0]["checkpoint"]["completed_index"] == 2
    try:
        build_plan(manifest, policy, parent, "113-第一次")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown checkpoint must fail closed")
    bad = dict(manifest)
    bad["shards"] = list(manifest["shards"]) + [dict(manifest["shards"][0])]
    bad["shard_count"] = 4
    try:
        build_plan(bad, policy, parent)
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate manifest session must fail closed")
    return {
        "ok": True,
        "fresh_count": 3,
        "resume_skips_completed_prefix": True,
        "unknown_checkpoint_fail_closed": True,
        "duplicate_manifest_fail_closed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan resumable Full Corpus QA work")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--checkpoint-unit")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0

    manifest = read_json(args.manifest)
    policy = read_json(args.policy)
    contract = read_json(args.contract)
    validate_contract(contract)
    parent = resolve(contract, TASK_ID)["idempotency_key"]
    output = build_plan(manifest, policy, parent, args.checkpoint_unit)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

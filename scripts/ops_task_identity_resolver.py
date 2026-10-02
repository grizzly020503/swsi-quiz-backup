#!/usr/bin/env python3
"""Resolve durable SWSI task identities from data/ops_task_identity.v1.json.

This is a read-only helper. It never writes the ops ledger or production.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from ops_task_identity import child_identity, semantic_file_fingerprint, trigger_run_identity

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "data" / "ops_task_identity.v1.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_relative_path(raw: str) -> Path:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("component path is required")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"component path must stay inside repo: {value}")
    return ROOT / path


def find_entry(contract: dict[str, Any], name: str) -> tuple[str, dict[str, Any]]:
    name = str(name or "").strip()
    for section in ("tasks", "integration_units"):
        rows = contract.get(section)
        if isinstance(rows, dict) and name in rows:
            row = rows[name]
            if not isinstance(row, dict):
                raise ValueError(f"{section}.{name} must be an object")
            return section, row
    raise KeyError(f"identity entry not found: {name}")


def validate_contract(contract: Any) -> None:
    if not isinstance(contract, dict) or contract.get("schema_version") != 1:
        raise ValueError("identity contract must be schema_version=1")
    seen: set[str] = set()
    for section in ("tasks", "integration_units"):
        rows = contract.get(section)
        if not isinstance(rows, dict):
            raise ValueError(f"{section} must be an object")
        for name, row in rows.items():
            if name in seen:
                raise ValueError(f"duplicate identity entry: {name}")
            seen.add(name)
            if not isinstance(row, dict):
                raise ValueError(f"{section}.{name} must be an object")
            strategy = str(row.get("strategy") or "").strip()
            if strategy not in {"semantic_files_v1", "trigger_run_v1", "parent_child_v1"}:
                raise ValueError(f"{name}: unsupported strategy {strategy!r}")
            if strategy == "semantic_files_v1":
                components = row.get("components")
                if not isinstance(components, list) or not components:
                    raise ValueError(f"{name}: semantic_files_v1 requires components")
                labels: set[str] = set()
                for item in components:
                    if not isinstance(item, list) or len(item) != 2:
                        raise ValueError(f"{name}: component must be [label,path]")
                    label = str(item[0] or "").strip()
                    if not label or label in labels:
                        raise ValueError(f"{name}: duplicate/empty component label {label!r}")
                    labels.add(label)
                    validate_relative_path(str(item[1]))
            elif strategy == "trigger_run_v1":
                if not str(row.get("provider") or "").strip():
                    raise ValueError(f"{name}: trigger_run_v1 requires provider")
            else:
                if not str(row.get("unit_type") or "").strip():
                    raise ValueError(f"{name}: parent_child_v1 requires unit_type")


def resolve(
    contract: dict[str, Any],
    name: str,
    *,
    run_id: str | None = None,
    parent_key: str | None = None,
    unit_id: str | None = None,
) -> dict[str, Any]:
    section, row = find_entry(contract, name)
    strategy = row["strategy"]
    if strategy == "semantic_files_v1":
        components: list[tuple[str, Path]] = []
        rendered: list[dict[str, str]] = []
        for label, raw_path in row["components"]:
            path = validate_relative_path(str(raw_path))
            if not path.is_file():
                raise FileNotFoundError(f"{name}: required semantic component missing: {path.relative_to(ROOT)}")
            components.append((str(label), path))
            rendered.append({"label": str(label), "path": str(path.relative_to(ROOT))})
        key = semantic_file_fingerprint(name, components)
        return {"schema_version": 1, "name": name, "section": section, "strategy": strategy,
                "idempotency_key": key, "components": rendered}
    if strategy == "trigger_run_v1":
        resolved_run_id = str(run_id or os.getenv(str(row.get("provider_run_id") or ""), "") or "").strip()
        if not resolved_run_id:
            raise ValueError(f"{name}: run id is required")
        provider = str(row["provider"]).strip()
        key = trigger_run_identity(name, provider, resolved_run_id)
        return {"schema_version": 1, "name": name, "section": section, "strategy": strategy,
                "idempotency_key": key, "provider": provider, "run_id": resolved_run_id}
    resolved_parent = str(parent_key or "").strip()
    resolved_unit = str(unit_id or "").strip()
    if not resolved_parent or not resolved_unit:
        raise ValueError(f"{name}: parent_key and unit_id are required")
    unit_type = str(row["unit_type"]).strip()
    key = child_identity(resolved_parent, unit_type, resolved_unit)
    return {"schema_version": 1, "name": name, "section": section, "strategy": strategy,
            "idempotency_key": key, "parent_key": resolved_parent, "unit_type": unit_type,
            "unit_id": resolved_unit}


def self_test() -> dict[str, Any]:
    sample = {
        "schema_version": 1,
        "tasks": {
            "remote": {"strategy": "trigger_run_v1", "provider": "github", "provider_run_id": "TEST_RUN_ID"}
        },
        "integration_units": {
            "child": {"strategy": "parent_child_v1", "unit_type": "exam_session"}
        },
    }
    validate_contract(sample)
    a = resolve(sample, "remote", run_id="123")
    b = resolve(sample, "remote", run_id="123")
    c = resolve(sample, "child", parent_key=a["idempotency_key"], unit_id="115-2")
    assert a["idempotency_key"] == b["idempotency_key"]
    assert c["idempotency_key"].startswith("child1:")
    try:
        resolve(sample, "remote")
    except ValueError:
        pass
    else:
        raise AssertionError("missing run id must fail closed")
    return {"ok": True, "trigger_run": True, "parent_child": True, "fail_closed": True}


def main() -> int:
    p = argparse.ArgumentParser(description="Resolve SWSI durable task idempotency keys")
    p.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--name")
    p.add_argument("--run-id")
    p.add_argument("--parent-key")
    p.add_argument("--unit-id")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0
    if not args.name:
        raise SystemExit("--name is required unless --self-test is used")
    contract = read_json(args.contract)
    validate_contract(contract)
    result = resolve(
        contract,
        args.name,
        run_id=args.run_id,
        parent_key=args.parent_key,
        unit_id=args.unit_id,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["idempotency_key"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

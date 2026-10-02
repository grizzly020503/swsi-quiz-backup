#!/usr/bin/env python3
"""Deterministic task identity helpers for SWSI durable ops ledger (#269).

File-backed jobs use semantic input fingerprints. Live-fetch jobs use an explicit
trigger-run identity so retries/reruns of the same orchestration run can resume
without suppressing a deliberately new fetch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Iterable

SCHEMA_VERSION = 1


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def semantic_file_fingerprint(task_id: str, components: Iterable[tuple[str, Path]]) -> str:
    task_id = str(task_id or "").strip()
    if not task_id:
        raise ValueError("task_id is required")
    normalized = []
    labels = set()
    for label, path in components:
        label = str(label or "").strip()
        path = Path(path)
        if not label or label in labels:
            raise ValueError(f"component label missing or duplicated: {label!r}")
        labels.add(label)
        if not path.is_file():
            raise FileNotFoundError(path)
        normalized.append({
            "label": label,
            "sha256": sha256_file(path),
            "size": path.stat().st_size,
        })
    if not normalized:
        raise ValueError("at least one semantic component is required")
    normalized.sort(key=lambda row: row["label"])
    payload = {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "strategy": "semantic_files_v1",
        "components": normalized,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sem1:" + hashlib.sha256(raw).hexdigest()


def trigger_run_identity(task_id: str, provider: str, run_id: str) -> str:
    task_id = str(task_id or "").strip()
    provider = str(provider or "").strip().lower()
    run_id = str(run_id or "").strip()
    if not task_id or not provider or not run_id:
        raise ValueError("task_id, provider, and run_id are required")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "strategy": "trigger_run_v1",
        "provider": provider,
        "run_id": run_id,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "run1:" + hashlib.sha256(raw).hexdigest()


def child_identity(parent_key: str, unit_type: str, unit_id: str) -> str:
    parent_key = str(parent_key or "").strip()
    unit_type = str(unit_type or "").strip()
    unit_id = str(unit_id or "").strip()
    if not parent_key or not unit_type or not unit_id:
        raise ValueError("parent_key, unit_type, and unit_id are required")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "strategy": "parent_child_v1",
        "parent": parent_key,
        "unit_type": unit_type,
        "unit_id": unit_id,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "child1:" + hashlib.sha256(raw).hexdigest()


def parse_component(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise ValueError("--file requires LABEL=PATH")
    label, path = raw.split("=", 1)
    return label.strip(), Path(path.strip())


def self_test() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        a = root / "a.txt"; b = root / "b.txt"
        a.write_text("alpha\n", encoding="utf-8")
        b.write_text("beta\n", encoding="utf-8")
        one = semantic_file_fingerprint("task", [("a", a), ("b", b)])
        reordered = semantic_file_fingerprint("task", [("b", b), ("a", a)])
        assert one == reordered
        a.write_text("alpha changed\n", encoding="utf-8")
        changed = semantic_file_fingerprint("task", [("a", a), ("b", b)])
        assert changed != one
        r1 = trigger_run_identity("moex-social-worker-sync", "github", "123")
        assert r1 == trigger_run_identity("moex-social-worker-sync", "github", "123")
        assert r1 != trigger_run_identity("moex-social-worker-sync", "github", "124")
        c1 = child_identity(one, "exam_session", "115-2")
        assert c1 == child_identity(one, "exam_session", "115-2")
        assert c1 != child_identity(one, "exam_session", "115-1")
        return {"ok": True, "semantic_stable": True, "content_sensitive": True, "trigger_sensitive": True}


def main() -> int:
    p = argparse.ArgumentParser(description="SWSI durable task identity helper")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    sem = sub.add_parser("semantic-files")
    sem.add_argument("--task", required=True)
    sem.add_argument("--file", action="append", default=[], help="LABEL=PATH; repeatable")
    run = sub.add_parser("trigger-run")
    run.add_argument("--task", required=True); run.add_argument("--provider", required=True); run.add_argument("--run-id", required=True)
    child = sub.add_parser("child")
    child.add_argument("--parent-key", required=True); child.add_argument("--unit-type", required=True); child.add_argument("--unit-id", required=True)
    args = p.parse_args()
    if args.command == "self-test":
        print(json.dumps(self_test(), ensure_ascii=False, indent=2)); return 0
    if args.command == "semantic-files":
        print(semantic_file_fingerprint(args.task, [parse_component(x) for x in args.file])); return 0
    if args.command == "trigger-run":
        print(trigger_run_identity(args.task, args.provider, args.run_id)); return 0
    print(child_identity(args.parent_key, args.unit_type, args.unit_id)); return 0


if __name__ == "__main__":
    raise SystemExit(main())

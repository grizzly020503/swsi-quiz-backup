#!/usr/bin/env python3
"""Audit official incoming payloads against the approved exam-scheme registry.

Exit codes:
- 0: every selected payload matches an approved profile
- 2: one or more payloads look like a structural candidate change
- 3: one or more payloads have invalid identity/session metadata

The report is diagnostic evidence only. Candidate profiles are NEVER executable
or auto-approved by this script.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from exam_scheme import DEFAULT_REGISTRY, ExamSchemeError, compare_payload, load_registry, read_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INCOMING = ROOT / "incoming"


def collect_paths(inputs: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        if item.is_dir():
            paths.extend(sorted(item.glob("[0-9][0-9][0-9][0-9][0-9][0-9].json")))
        else:
            paths.append(item)
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def main() -> int:
    ap = argparse.ArgumentParser(description="Fail-closed SWSI exam-scheme intake gate")
    ap.add_argument("inputs", nargs="*", type=Path, default=[DEFAULT_INCOMING])
    ap.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--fail-on-change", action="store_true")
    args = ap.parse_args()

    try:
        registry = load_registry(args.registry)
    except Exception as exc:
        raise SystemExit(f"EXAM SCHEME GATE FAILED: cannot load registry: {exc}") from exc

    paths = collect_paths(args.inputs or [DEFAULT_INCOMING])
    if not paths:
        raise SystemExit("EXAM SCHEME GATE FAILED: no exam payloads selected")

    results = []
    for path in paths:
        try:
            payload = read_json(path)
            result = compare_payload(payload, registry)
        except (OSError, json.JSONDecodeError, ExamSchemeError) as exc:
            result = {
                "status": "invalid_identity",
                "approved": False,
                "exam_code": path.stem,
                "roc_year": None,
                "round": None,
                "profile_id": None,
                "identity_issues": [{"field": "payload", "message": str(exc)}],
                "diffs": [],
                "expected": None,
                "observed": None,
                "candidate_profile": None,
                "requires_maintainer_decision": True,
            }
        result["source"] = path.as_posix()
        results.append(result)

    counts: dict[str, int] = {}
    for result in results:
        status = str(result["status"])
        counts[status] = counts.get(status, 0) + 1

    report = {
        "schema_version": 1,
        "registry": args.registry.as_posix(),
        "policy": "approved profile match proceeds; any difference is quarantined and never auto-approved",
        "payload_count": len(results),
        "status_counts": dict(sorted(counts.items())),
        "all_approved": all(row["status"] == "match" for row in results),
        "results": results,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")

    if not args.fail_on_change:
        return 0
    if any(row["status"] == "invalid_identity" for row in results):
        return 3
    if any(row["status"] != "match" for row in results):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

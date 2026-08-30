#!/usr/bin/env python3
"""Fail-closed structure guard for SWSI monthly runtime parts.

This intentionally does not judge product behavior. It prevents the historical
"add one more later zzz override" pattern from silently growing and makes any
increase in runtime-part count an explicit architecture decision.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS_DIR = ROOT / "monthly_patch_parts"
CONFIG_PATH = ROOT / "config" / "monthly_patch_structure.json"


def fail(messages: list[str]) -> int:
    print("SWSI MAINTAINABILITY GUARD FAILED", file=sys.stderr)
    for message in messages:
        print(f"- {message}", file=sys.stderr)
    return 1


def main() -> int:
    if not PARTS_DIR.is_dir():
        return fail([f"missing parts directory: {PARTS_DIR.relative_to(ROOT)}"])
    if not CONFIG_PATH.is_file():
        return fail([f"missing config: {CONFIG_PATH.relative_to(ROOT)}"])

    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return fail([f"cannot read structure config: {exc}"])

    errors: list[str] = []
    parts = sorted(path.name for path in PARTS_DIR.iterdir() if path.is_file() and path.suffix == ".part")

    try:
        part_ceiling = int(config["part_count_ceiling"])
        late_ceiling = int(config["late_layer_count_ceiling"])
        preferred = re.compile(str(config["preferred_new_part_pattern"]))
        grandfathered_noncanonical = set(config["grandfathered_noncanonical_parts"])
        grandfathered_late = set(config["grandfathered_late_layers"])
    except (KeyError, TypeError, ValueError, re.error) as exc:
        return fail([f"invalid structure config: {exc}"])

    if len(parts) > part_ceiling:
        errors.append(
            f"runtime part count grew to {len(parts)}; reviewed ceiling is {part_ceiling}. "
            "Consolidate an owner or explicitly review the architecture ceiling."
        )

    late = {name for name in parts if name.startswith("z")}
    if len(late) > late_ceiling:
        errors.append(f"late z-layer count grew to {len(late)}; reviewed ceiling is {late_ceiling}")

    unexpected_late = sorted(late - grandfathered_late)
    missing_late = sorted(grandfathered_late - late)
    if unexpected_late:
        errors.append("new z-layer part(s) are forbidden: " + ", ".join(unexpected_late))
    if missing_late:
        errors.append(
            "grandfathered z-layer inventory is stale after deletion/rename: "
            + ", ".join(missing_late)
            + ". Update the config in the same reviewed consolidation change."
        )

    actual_noncanonical: set[str] = set()
    for name in parts:
        if name.startswith("z"):
            continue
        if not preferred.fullmatch(name):
            actual_noncanonical.add(name)

    unexpected_noncanonical = sorted(actual_noncanonical - grandfathered_noncanonical)
    missing_noncanonical = sorted(grandfathered_noncanonical - actual_noncanonical)
    if unexpected_noncanonical:
        errors.append(
            "new noncanonical part filename(s): "
            + ", ".join(unexpected_noncanonical)
            + ". New parts must use NN.descriptive-kebab-name.part."
        )
    if missing_noncanonical:
        errors.append(
            "grandfathered filename inventory is stale after deletion/rename: "
            + ", ".join(missing_noncanonical)
            + ". Update the config in the same reviewed migration."
        )

    if errors:
        return fail(errors)

    print("SWSI MAINTAINABILITY GUARD OK")
    print(f"runtime parts: {len(parts)}/{part_ceiling}")
    print(f"grandfathered late z-layers: {len(late)}/{late_ceiling}")
    print("new-part naming policy: NN.descriptive-kebab-name.part")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

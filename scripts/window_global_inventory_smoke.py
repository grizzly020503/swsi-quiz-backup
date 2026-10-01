#!/usr/bin/env python3
"""Fail-closed inventory guard for direct window.* runtime globals.

SWSI still carries legacy global runtime hooks for compatibility. This guard does
not remove them; it makes the current owner set explicit so new globals or new
owners cannot silently accumulate.

Only direct assignments are inventoried here (window.foo = ... and
window['foo'] = ...). Calls such as window.addEventListener(...) are not globals
owned by SWSI and are intentionally ignored.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "monthly_patch_parts"
CONFIG = ROOT / "config" / "window_global_inventory.json"
INSTALLER = ROOT / "scripts" / "install_current_affairs_ui.py"

DOT_ASSIGN = re.compile(r"\bwindow\.([A-Za-z_$][A-Za-z0-9_$]*)\s*=(?!=)")
BRACKET_ASSIGN = re.compile(r"\bwindow\[\s*['\"]([^'\"]+)['\"]\s*\]\s*=(?!=)")


def scan_file(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    names = set(DOT_ASSIGN.findall(text))
    names.update(BRACKET_ASSIGN.findall(text))
    return names


def current_inventory() -> dict[str, list[str]]:
    owners: dict[str, set[str]] = defaultdict(set)
    files = sorted(PARTS.glob("*.part"))
    if INSTALLER.is_file():
        files.append(INSTALLER)
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        for name in scan_file(path):
            owners[name].add(rel)
    return {name: sorted(paths) for name, paths in sorted(owners.items())}


def main() -> int:
    if not CONFIG.is_file():
        print(f"missing window-global inventory config: {CONFIG.relative_to(ROOT)}", file=sys.stderr)
        return 1
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read window-global inventory config: {exc}", file=sys.stderr)
        return 1
    if config.get("schema_version") != 1 or not isinstance(config.get("owners"), dict):
        print("invalid window-global inventory config", file=sys.stderr)
        return 1

    expected = {
        str(name): sorted(str(path) for path in paths)
        for name, paths in config["owners"].items()
        if isinstance(paths, list)
    }
    actual = current_inventory()

    errors: list[str] = []
    new_names = sorted(set(actual) - set(expected))
    removed_names = sorted(set(expected) - set(actual))
    if new_names:
        errors.append("new direct window global(s) are forbidden without reviewed baseline update: " + ", ".join(new_names))
    if removed_names:
        errors.append("baseline still lists removed window global(s): " + ", ".join(removed_names))
    for name in sorted(set(actual) & set(expected)):
        if actual[name] != expected[name]:
            errors.append(
                f"window.{name} owner set changed: expected {expected[name]!r}, actual {actual[name]!r}"
            )

    if errors:
        print("SWSI WINDOW GLOBAL INVENTORY FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print("CURRENT_WINDOW_GLOBAL_INVENTORY_JSON", file=sys.stderr)
        print(json.dumps({"schema_version": 1, "owners": actual}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    owner_edges = sum(len(paths) for paths in actual.values())
    duplicates = {name: paths for name, paths in actual.items() if len(paths) > 1}
    print("SWSI WINDOW GLOBAL INVENTORY OK")
    print(f"direct globals: {len(actual)}; owner edges: {owner_edges}; multi-owner globals: {len(duplicates)}")
    if duplicates:
        for name, paths in duplicates.items():
            print(f"multi-owner window.{name}: {' -> '.join(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

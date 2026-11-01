#!/usr/bin/env python3
"""Elide timestamp-only monitoring snapshot commits, without hiding real changes.

Trusted GitHub Actions main-branch publisher only. It never connects to a
provider, edits questions, creates commits or touches the frozen backup site.
The scanner still runs and all existing validation still executes before this
narrow, local working-tree normalization.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

NAMES = (
    "current_affairs_signals.json",
    "current_affairs_events.json",
    "current_affairs_trends.json",
)


def parse(raw: bytes, label: str) -> dict:
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError(label + ": invalid snapshot JSON") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError(label + ": schema_version must be 1")
    stamp = data.get("generated_at")
    if not isinstance(stamp, str) or not stamp.endswith("Z"):
        raise ValueError(label + ": expected UTC generated_at")
    try:
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(label + ": invalid generated_at") from exc
    if dt.utcoffset() is None or dt.year < 2025 or dt.year > 2100:
        raise ValueError(label + ": invalid generated_at bounds")
    return data


def semantic(data: dict) -> dict:
    """Keep every substantive field, including event observations and scores."""
    result = dict(data)
    result.pop("generated_at")
    return result


def decide(previous: bytes, built: bytes, label: str) -> bool:
    """True ONLY for timestamp-only change. A backwards timestamp is unsafe."""
    old, new = parse(previous, label + " HEAD"), parse(built, label + " generated")
    old_time = datetime.fromisoformat(old["generated_at"].replace("Z", "+00:00"))
    new_time = datetime.fromisoformat(new["generated_at"].replace("Z", "+00:00"))
    if new_time < old_time:
        raise ValueError(label + ": generated_at moved backwards")
    if new != old and new_time == old_time and semantic(new) != semantic(old):
        raise ValueError(label + ": actual content changed without new generated_at")
    return new != old and semantic(new) == semantic(old)


def baseline_file(path: str) -> bytes:
    proc = subprocess.run(
        ["git", "show", "HEAD:" + path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=15,
    )
    if proc.returncode != 0:
        raise ValueError(path + ": tracked HEAD baseline unavailable")
    return proc.stdout


def normalize(root: Path, get_previous=baseline_file) -> dict:
    restored, substantive, unchanged = [], [], []
    # Read and validate ALL files first. Failure never produces a half-patched
    # pair or skips validation for a later snapshot.
    planned: list[tuple[Path, Path, bytes, bool, str]] = []
    for name in NAMES:
        a, b = root / "auto" / name, root / "cdn" / "auto" / name
        if not a.is_file() or not b.is_file():
            raise ValueError(name + ": auto/CDN pair missing")
        current, cdn_current = a.read_bytes(), b.read_bytes()
        old, cdn_old = get_previous("auto/" + name), get_previous("cdn/auto/" + name)
        if current != cdn_current:
            raise ValueError(name + ": generated CDN and root diverged")
        if old != cdn_old:
            raise ValueError(name + ": HEAD CDN and root baseline diverged")
        drop = decide(old, current, name)
        planned.append((a, b, old, drop, name))
        if drop:
            restored.append(name)
        elif old == current:
            unchanged.append(name)
        else:
            substantive.append(name)
    for a, b, old, drop, _ in planned:
        if drop:
            a.write_bytes(old)
            b.write_bytes(old)
    return {
        "timestamp_only_elided": restored,
        "substantive_kept": substantive,
        "already_unchanged": unchanged,
        "no_source_changes": True,
        "backup_untouched": True,
    }


def selftest() -> None:
    def data(stamp: str, value: int = 1) -> bytes:
        return (json.dumps({
            "schema_version": 1, "generated_at": stamp,
            "count": value, "items": [{"id": "source-a", "confidence": value}],
        }, ensure_ascii=False) + "\n").encode()
    t1, t2 = "2026-10-31T15:55:01Z", "2026-10-31T21:28:36Z"
    assert decide(data(t1), data(t2), "test")
    assert not decide(data(t1), data(t1), "test")
    assert not decide(data(t1), data(t2, 2), "test")
    for wrong in (data("2026-10-30T00:00:00Z"), b"not-json",
                  b'{"schema_version":2,"generated_at":"2026-11-01T00:00:00Z"}'):
        try:
            decide(data(t1), wrong, "test")
        except ValueError:
            continue
        raise AssertionError("invalid generated snapshot accepted")
    try:
        decide(data(t1), data(t1, 2), "test")
    except ValueError:
        pass
    else:
        raise AssertionError("unversioned content change accepted")
    with TemporaryDirectory(prefix="swsi-noop-monitoring-") as temp:
        root = Path(temp)
        prior = {}
        for name in NAMES:
            for prefix in ("auto", "cdn/auto"):
                path = prefix + "/" + name
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data(t2))
                prior[path] = data(t1)
        result = normalize(root, prior.__getitem__)
        assert len(result["timestamp_only_elided"]) == 3
        for name in NAMES:
            assert (root / "auto" / name).read_bytes() == data(t1)
            assert (root / "cdn/auto" / name).read_bytes() == data(t1)
        first = NAMES[0]
        for prefix in ("auto", "cdn/auto"):
            (root / prefix / first).write_bytes(data(t2, 2))
        result = normalize(root, prior.__getitem__)
        assert result["substantive_kept"] == [first], result
        assert len(result["already_unchanged"]) == 2
        assert (root / "cdn/auto" / first).read_bytes() == data(t2, 2)
        # Fail closed on split CDN and never modify earlier pairs.
        (root / "cdn/auto" / first).write_bytes(data(t2, 3))
        before = (root / "auto" / NAMES[1]).read_bytes()
        try:
            normalize(root, prior.__getitem__)
        except ValueError as exc:
            assert "CDN and root diverged" in str(exc)
        else:
            raise AssertionError("split CDN accepted")
        assert (root / "auto" / NAMES[1]).read_bytes() == before
    print("SWSI MONITORING NO-OP SELFTEST OK: "
          "timestamp-only skip, real updates, synced CDN, fail-closed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    if args.selftest:
        selftest()
    else:
        print(json.dumps(normalize(args.root.resolve()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

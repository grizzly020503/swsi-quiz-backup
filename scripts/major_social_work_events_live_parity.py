#!/usr/bin/env python3
"""Read-only Cloudflare major-event archive parity diagnostic.

Never changes content, questions, deployments, backups or monitoring gating.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://wandering-wave-4418.c022050333.workers.dev"
REL = "auto/major_social_work_events.json"


def valid(data: bytes) -> bool:
    try:
        obj = json.loads(data)
        rows = obj.get("events")
        return (
            obj.get("schema_version") == 1
            and obj.get("selection_method") == "major-social-work-v1"
            and isinstance(rows, list)
            and obj.get("event_count") == len(rows)
            and isinstance(obj.get("revision"), str)
            and len(obj["revision"]) == 16
            and all(
                isinstance(row, dict)
                and row.get("admission_rule") == "major-social-work-v1"
                and len(row.get("evidence") or []) >= 2
                and len(row.get("practice_essays") or []) == 2
                for row in rows
            )
        )
    except (ValueError, AttributeError, TypeError):
        return False


def compare(a: bytes, b: bytes) -> str:
    if not valid(a):
        return "SOURCE_DRIFT"
    if not valid(b):
        return "STALE"
    if a == b:
        return "MATCH"
    try:
        return "MATCH" if json.loads(a) == json.loads(b) else "STALE"
    except (ValueError, TypeError):
        return "STALE"


def selftest() -> None:
    empty = json.dumps({
        "schema_version": 1, "selection_method": "major-social-work-v1",
        "revision": "4f53cda18c2baa0c", "event_count": 0, "events": [],
    }).encode()
    assert valid(empty)
    assert compare(empty, empty) == "MATCH"
    assert compare(empty, empty + b" \n") == "MATCH"
    assert compare(empty, b"<!doctype html>") == "STALE"
    assert compare(b"{}", empty) == "SOURCE_DRIFT"
    assert compare(empty, empty.replace(b'"revision"', b'"changed"')) == "STALE"
    print("SWSI MAJOR EVENT ARCHIVE LIVE PARITY SELFTEST PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--cache-bust", default="manual")
    parser.add_argument("--out")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return 0
    if not args.live:
        parser.error("choose --live or --selftest")

    report = {"status": "NOT_VERIFIED", "http_status": None, "local_events": None}
    try:
        expected = (ROOT / REL).read_bytes()
        cdn = (ROOT / "cdn" / REL).read_bytes()
        if not valid(expected) or expected != cdn:
            report["status"] = "SOURCE_DRIFT"
            report["reason"] = "repo auto/CDN archive diverged or is invalid"
        else:
            report["local_events"] = json.loads(expected)["event_count"]
            tag = str(args.cache_bust).replace("/", "")[:80]
            url = f"{ORIGIN}/{REL}?major_parity={tag}"
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "SWSI-Major-Archive-Parity/1.0",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                report["http_status"] = response.status
                live = response.read(2_000_001)
            if len(live) > 2_000_000:
                raise ValueError("oversize hosted archive")
            report["status"] = compare(expected, live)
            if valid(live):
                report["live_events"] = json.loads(live)["event_count"]
            report["local_sha256"] = hashlib.sha256(expected).hexdigest()
            report["live_sha256"] = hashlib.sha256(live).hexdigest()
    except (OSError, ValueError, urllib.error.URLError, TimeoutError) as exc:
        report["reason"] = (type(exc).__name__ + ": " + str(exc))[:240]
    print("SWSI MAJOR EVENT ARCHIVE LIVE PARITY:", report["status"])
    print("SWSI MAJOR EVENT ARCHIVE DATA:", json.dumps(report, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0  # Diagnostic; availability is an independent gate.


if __name__ == "__main__":
    raise SystemExit(main())

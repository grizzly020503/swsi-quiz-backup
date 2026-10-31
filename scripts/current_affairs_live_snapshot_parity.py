#!/usr/bin/env python3
"""READ-ONLY Cloudflare/current-main current-affairs snapshot parity audit.

Independent of uptime: a successful 200/schema/count is not proof that latest
GitHub-generated events/signals/trends were deployed. This diagnostic never
writes to Cloudflare, Supabase, GitHub main or the frozen Netlify backup.
Run with --strict only as a deliberate freshness release gate; default exits 0
with an explicit non-MATCH status suitable for an independent health summary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://wandering-wave-4418.c022050333.workers.dev"
KINDS = ("current_affairs_signals", "current_affairs_events", "current_affairs_trends")
MAX_BYTES = 3_000_000
STATUS = {"MATCH", "STALE", "DIVERGED", "UNREACHABLE", "INVALID_JSON"}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def parse_snapshot(raw: bytes, label: str) -> dict:
    if len(raw) > MAX_BYTES:
        raise ValueError(label + " exceeds expected public JSON size")
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError(label + " missing version-1 JSON object")
    timestamp = value.get("generated_at")
    if not isinstance(timestamp, str):
        raise ValueError(label + " generated_at missing")
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if dt.utcoffset() is None:
        raise ValueError(label + " generated_at has no timezone")
    if dt.year < 2025 or dt.year > 2100:
        raise ValueError(label + " invalid generation year")
    if value.get("note") is None:
        raise ValueError(label + " missing warning note")
    return value


def expected(root: Path) -> dict[str, tuple[bytes, dict]]:
    baseline = {}
    for kind in KINDS:
        public = root / "cdn/auto" / f"{kind}.json"
        generated = root / "auto" / f"{kind}.json"
        raw = public.read_bytes()
        if raw != generated.read_bytes():
            raise ValueError(f"repo auto/ vs cdn/auto/ physical mismatch: {kind}")
        payload = parse_snapshot(raw, "tracked " + kind)
        key = {"current_affairs_events": "events",
               "current_affairs_signals": "items",
               "current_affairs_trends": "trends"}[kind]
        items = payload.get(key)
        if not isinstance(items, list) or len(items) < 1:
            raise ValueError(f"tracked {kind} has empty or missing {key}")
        if kind == "current_affairs_signals" and payload.get("questions_loaded") != 4800:
            raise ValueError("tracked signals question count not 4800")
        baseline[kind] = (raw, payload)
    return baseline


def http_read(kind: str, cache_bust: str) -> bytes:
    # Only the explicitly configured Cloudflare primary is contacted. Never
    # request from the backup host, allow a POST or transmit credentials.
    path = f"/auto/{kind}.json"
    url = ORIGIN + path + "?" + urllib.parse.urlencode({"snapshot_parity": cache_bust})
    req = urllib.request.Request(
        url, method="GET",
        headers={"User-Agent": "SWSI-Snapshot-Parity/1.0",
                 "Cache-Control": "no-cache", "Pragma": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=12) as result:
        if result.geturl().split("?")[0] != ORIGIN + path:
            raise ValueError("unexpected redirect from primary origin")
        if result.status != 200:
            raise ValueError(f"HTTP {result.status}")
        raw = result.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("hosted body exceeds public JSON limit")
    return raw


def compare(root: Path, fetch: Callable[[str], bytes]) -> dict:
    baseline = expected(root)  # baseline failure is a validation error, not MATCH.
    results = {}
    for kind in KINDS:
        old_raw, old = baseline[kind]
        item = {
            "status": None,
            "expected_sha256": digest(old_raw),
            "expected_generated_at": old["generated_at"],
            "live_sha256": None,
            "live_generated_at": None,
        }
        try:
            live_raw = fetch(kind)
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            item["status"] = "UNREACHABLE"
            item["reason"] = type(exc).__name__  # no private response bodies
        else:
            item["live_sha256"] = digest(live_raw)
            try:
                live = parse_snapshot(live_raw, "live " + kind)
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
                item["status"] = "INVALID_JSON"
            else:
                item["live_generated_at"] = live["generated_at"]
                if old_raw == live_raw:
                    item["status"] = "MATCH"
                else:
                    old_ts = datetime.fromisoformat(old["generated_at"].replace("Z", "+00:00"))
                    live_ts = datetime.fromisoformat(live["generated_at"].replace("Z", "+00:00"))
                    item["status"] = "STALE" if live_ts < old_ts else "DIVERGED"
        results[kind] = item
    statuses = {item["status"] for item in results.values()}
    if statuses == {"MATCH"}:
        overall = "MATCH"
    elif "UNREACHABLE" in statuses or "INVALID_JSON" in statuses:
        overall = "NOT_VERIFIED"
    elif "DIVERGED" in statuses:
        overall = "DIVERGED"
    else:
        overall = "STALE"
    return {
        "status": overall, "source": "read_only_cloudflare_primary_vs_git_main_files",
        "target": "cloudflare-primary-only", "comparison": "physical_SHA256_and_generated_at",
        "snapshots": results, "no_production_write": True,
        "no_backup_contact": True, "official_core_modified": False,
        "deployment_performed": False,
    }


def fixture_files(root: Path, now: str = "2026-11-01T00:00:00Z") -> dict[str, bytes]:
    baselines = {}
    for kind in KINDS:
        payload = {"schema_version": 1, "generated_at": now,
                   "note": "不代表命題保證"}
        field = {"current_affairs_events": "events",
                 "current_affairs_signals": "items",
                 "current_affairs_trends": "trends"}[kind]
        payload[field] = [{"id": "test"}]
        if kind == "current_affairs_signals":
            payload["questions_loaded"] = 4800
        raw = (json.dumps(payload, ensure_ascii=False) + "\n").encode()
        for prefix in ("auto", "cdn/auto"):
            file = root / prefix / f"{kind}.json"
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(raw)
        baselines[kind] = raw
    return baselines


def selftest() -> None:
    with tempfile.TemporaryDirectory(prefix="swsi-public-snapshot-") as directory:
        root = Path(directory)
        fixture = fixture_files(root)
        live = lambda kind: fixture[kind]
        assert compare(root, live)["status"] == "MATCH"
        stale = dict(fixture)
        first = KINDS[0]
        stale[first] = stale[first].replace(b"2026-11-01T00:00:00Z",
                                           b"2026-10-31T00:00:00Z")
        r = compare(root, lambda kind: stale[kind])
        assert r["status"] == "STALE" and r["snapshots"][first]["status"] == "STALE"
        diverged = dict(fixture)
        diverged[first] = diverged[first].replace(b"test", b"tampered")
        assert compare(root, lambda kind: diverged[kind])["status"] == "DIVERGED"
        bad = dict(fixture)
        bad[first] = b'{"schema_version":1,"generated_at":"broken"'
        assert compare(root, lambda kind: bad[kind])["status"] == "NOT_VERIFIED"
        def failing(kind: str) -> bytes:
            if kind == first:
                raise OSError("synthetic outage")
            return fixture[kind]
        assert compare(root, failing)["snapshots"][first]["status"] == "UNREACHABLE"
        (root / "auto" / f"{first}.json").write_bytes(b"tampered")
        try:
            compare(root, live)
        except ValueError as exc:
            assert "physical mismatch" in str(exc)
        else:
            raise AssertionError("unexpected trusted source mismatch not rejected")
    print("SWSI PUBLIC SNAPSHOT PARITY SELFTEST PASS: match/stale/diverged/corrupt/unreachable/repo-drift, zero writes")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--strict", action="store_true",
                        help="require exact live SHA match (opt-in release gate)")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--cache-bust", default="manual")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return 0
    if not args.live:
        parser.error("specify --selftest or explicitly --live")
    if args.out is not None:
        out = args.out.resolve()
        if out == ROOT or ROOT in out.parents:
            parser.error("report must be outside the repository")
    result = compare(ROOT, lambda kind: http_read(kind, args.cache_bust))
    print("SWSI CLOUDFLARE PUBLIC SNAPSHOT PARITY " + result["status"])
    for kind, d in result["snapshots"].items():
        print(f"{kind}: {d['status']} expected={d['expected_generated_at']} "
              f"live={d['live_generated_at'] or 'unknown'} "
              f"expected_sha256={d['expected_sha256'][:16]} "
              f"live_sha256={(d['live_sha256'] or '-')[:16]}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    return 0 if not args.strict or result["status"] == "MATCH" else 2


if __name__ == "__main__":
    raise SystemExit(main())

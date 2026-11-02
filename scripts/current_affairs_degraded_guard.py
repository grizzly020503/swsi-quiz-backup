#!/usr/bin/env python3
"""Gate current-affairs writes when a required external feed temporarily fails.

A bounded, already-verified last-good public snapshot can keep serving students,
but must not turn a missing RSS source into fresh data. This gate runs BEFORE
Supabase sync, static snapshot rebuild, and GitHub snapshot publication.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

SNAPSHOTS = (
    "current_affairs.json",
    "current_affairs_signals.json",
    "current_affairs_events.json",
    "current_affairs_trends.json",
    "legal_watch.json",
)
MAX_AGE = timedelta(hours=24)
MAX_SKEW = timedelta(minutes=5)


def timestamp(raw: str) -> datetime:
    value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("snapshot timestamp lacks timezone")
    return value.astimezone(timezone.utc)


def last_good_snapshot(root: Path, now: datetime) -> float:
    """Return oldest coherent generation's age, or reject unsafe fallback."""
    data = {}
    for filename in SNAPSHOTS:
        primary = root / "auto" / filename
        cdn = root / "cdn" / "auto" / filename
        original = primary.read_bytes()
        if original != cdn.read_bytes():
            raise ValueError("public/CDN snapshot mismatch: " + filename)
        data[filename] = json.loads(original)
        if not isinstance(data[filename], dict):
            raise ValueError("snapshot is not an object: " + filename)

    news = data["current_affairs.json"]
    signals = data["current_affairs_signals.json"]
    events = data["current_affairs_events.json"]
    trends = data["current_affairs_trends.json"]
    laws = data["legal_watch.json"]
    if (int(news.get("schema_version", -1)) != 2
        or int(news.get("source_feed_count", -1)) < 17
        or int(news.get("feed_error_count", -1)) != 0
        or not isinstance(news.get("items"), list)
        or not news["items"]):
        raise ValueError("last-good current-affairs source contract invalid")
    if (int(signals.get("questions_loaded", -1)) != 4800
        or not isinstance(signals.get("items"), list)
        or int(signals.get("item_count", -1)) != len(signals["items"])):
        raise ValueError("last-good 4,800-question signal contract invalid")
    if (not isinstance(events.get("events"), list)
        or int(events.get("event_count", -1)) != len(events["events"])
        or not isinstance(trends.get("trends"), list)
        or int(trends.get("event_count", -1)) != len(events["events"])):
        raise ValueError("last-good event/trend contract invalid")
    if (int(laws.get("watch_count", -1)) < 52
        or int(laws.get("matched_count", -1)) < 0
        or int(laws.get("missing_count", -1)) < 0):
        raise ValueError("last-good legal-watch contract invalid")
    generated = [timestamp(x["generated_at"]) for x in (signals, events, trends)]
    if max(generated) - min(generated) > MAX_SKEW:
        raise ValueError("last-good snapshot generations disagree")
    if max(generated) > now + MAX_SKEW:
        raise ValueError("last-good snapshot is future-dated")
    age = now - min(generated)
    if age > MAX_AGE:
        raise ValueError("last-good snapshot expired after 24 hours")
    return max(0.0, age.total_seconds() / 3600)


def decide(payload: dict, root: Path, now: datetime) -> tuple[str, float | None]:
    if (not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or not isinstance(payload.get("feed_errors"), list)
        or not isinstance(payload.get("optional_feed_errors"), list)
        or int(payload.get("feed_count", -1)) < 17
        or int(payload.get("fetched_count", -1)) <= 0
        or not isinstance(payload.get("items"), list)):
        raise ValueError("untrusted current-affairs scan payload")
    if not payload["feed_errors"]:
        return "healthy", None
    if len(payload["feed_errors"]) >= int(payload["feed_count"]):
        raise ValueError("all current-affairs sources failed")
    return "degraded", last_good_snapshot(root, now)


def write_summary(mode: str, failures: int, age: float | None) -> None:
    output = os.environ.get("GITHUB_STEP_SUMMARY")
    if output:
        with open(output, "a", encoding="utf-8") as file:
            file.write("\n### Current-affairs source health\n")
            file.write(f"- Mode: **{mode}**\n")
            file.write(f"- Mandatory source failures: **{failures}**\n")
            if age is not None:
                file.write(f"- Last verified public snapshot age: **{age:.2f} hours** (maximum 24)\n")
                file.write("- Recovery policy: skip Supabase sync, new snapshots and snapshot pushes; preserve last-good bytes.\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return 0
    if args.payload is None:
        parser.error("--payload is required")
    try:
        payload = json.loads(args.payload.read_text(encoding="utf-8"))
        mode, age = decide(payload, args.root, datetime.now(timezone.utc))
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(f"::error title=Current-affairs source health HOLD::{type(exc).__name__}: {exc}")
        return 2
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as file:
            file.write(f"mode={mode}\n")
    failures = len(payload["feed_errors"])
    write_summary(mode, failures, age)
    if mode == "degraded":
        print("::warning title=Current-affairs temporarily degraded::"
              f"{failures} mandatory source(s) failed; last verified snapshot {age:.2f}h old; "
              "no current-affairs sync/publish will run.")
    else:
        print("CURRENT AFFAIRS SOURCE GATE OK: complete scan; normal sync/publish allowed")
    return 0


def selftest() -> None:
    fixed = datetime(2026, 11, 2, 10, tzinfo=timezone.utc)
    healthy = {"schema_version": 1, "feed_count": 23, "fetched_count": 100,
               "feed_errors": [], "optional_feed_errors": [], "items": [{"id": "x"}]}
    names = {
        "current_affairs.json": {"schema_version": 2, "source_feed_count": 23,
                                 "feed_error_count": 0, "items": [{"id": "x"}]},
        "current_affairs_signals.json": {"generated_at": "2026-11-02T09:00:00Z",
                                        "questions_loaded": 4800, "item_count": 1,
                                        "items": [{"id": "x"}]},
        "current_affairs_events.json": {"generated_at": "2026-11-02T09:00:00Z",
                                        "event_count": 1, "events": [{"id": "x"}]},
        "current_affairs_trends.json": {"generated_at": "2026-11-02T09:00:00Z",
                                        "event_count": 1, "trends": [{"id": "x"}]},
        "legal_watch.json": {"watch_count": 52, "matched_count": 52, "missing_count": 0},
    }
    def pairs(root: Path, payloads: dict) -> None:
        for section in ("auto", "cdn/auto"):
            (root / section).mkdir(parents=True, exist_ok=True)
            for filename, content in payloads.items():
                (root / section / filename).write_text(
                    json.dumps(content, ensure_ascii=False), encoding="utf-8")
    def rejects(action) -> None:
        try:
            action()
        except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError):
            return
        raise AssertionError("unsafe degraded-data fallback accepted")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pairs(root, names)
        assert decide(healthy, root, fixed) == ("healthy", None)
        optional = dict(healthy, optional_feed_errors=["optional unavailable"])
        assert decide(optional, root, fixed) == ("healthy", None)
        degraded = dict(healthy, feed_errors=["education RSS malformed"])
        assert decide(degraded, root, fixed) == ("degraded", 1.0)
        rejects(lambda: decide(degraded, root, fixed + timedelta(hours=25)))
        (root / "cdn/auto/current_affairs.json").write_text("{}", encoding="utf-8")
        rejects(lambda: decide(degraded, root, fixed))
        pairs(root, names)
        (root / "auto/current_affairs_signals.json").write_text("{not json", encoding="utf-8")
        rejects(lambda: decide(degraded, root, fixed))
        pairs(root, names)
        inconsistent = dict(names["current_affairs_trends.json"], generated_at="2026-11-02T09:30:00Z")
        (root / "auto/current_affairs_trends.json").write_text(json.dumps(inconsistent), encoding="utf-8")
        (root / "cdn/auto/current_affairs_trends.json").write_text(json.dumps(inconsistent), encoding="utf-8")
        rejects(lambda: decide(degraded, root, fixed))
        pairs(root, names)
        future = fixed - timedelta(hours=25)
        rejects(lambda: decide(degraded, root, future))
        rejects(lambda: decide(dict(healthy, feed_count=1), root, fixed))
        rejects(lambda: decide(dict(healthy, feed_errors=["x"] * 23), root, fixed))
    print("CURRENT AFFAIRS SAFE DEGRADE SELFTEST OK: healthy/optional, "
          "temporary source loss, expiry, CDN drift, malformed, generation skew, "
          "future clock and total failure")


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Read-only Cloudflare current-affairs UI parity diagnostic.

Compares *actual hosted UI source* against current cdn/index.html.
A passing home uptime check or snapshot freshness check does not prove UI
deployment. This is intentionally diagnostic-only and never contacts Netlify.
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
RADAR_MARKER = "<!-- SWSI CURRENT AFFAIRS RADAR V1 -->"
LEGACY_BEGIN = "/* ===== 時事庫注入 START"
LEGACY_END = "/* ===== 時事庫注入 END"


def fingerprint(blob: str) -> str:
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def regions(html: str) -> dict[str, str]:
    """Extract one dynamic radar and one evergreen case-study renderer."""
    if html.count(RADAR_MARKER) != 1:
        raise ValueError("expected exactly one radar UI block")
    first = html.index(RADAR_MARKER)
    script_start = html.find("<script>", first)
    script_end = html.find("</script>", script_start)
    if script_start < first or script_end < 0:
        raise ValueError("radar script boundary missing")
    if html[first + len(RADAR_MARKER):script_start].strip():
        raise ValueError("unexpected radar script prefix")
    if html.count(LEGACY_BEGIN) != 1 or html.count(LEGACY_END) != 1:
        raise ValueError("expected exactly one evergreen news renderer")
    begin = html.index(LEGACY_BEGIN)
    end = html.index(LEGACY_END, begin)
    close = html.find("*/", end)
    if close < 0:
        raise ValueError("evergreen news renderer boundary missing")
    evergreen = html[begin:close + 2]
    # Verify the new archived-case route is present; older large-card lists
    # must never silently pass as the latest student experience.
    if not all(marker in evergreen for marker in (
        "nl-history-entry", "NL.history()", "function renderHistory()",
    )):
        raise ValueError("evergreen single-entry navigation not installed")
    return {
        "dynamic_radar": html[first:script_end + len("</script>")],
        "evergreen_cases": html[begin:close + 2],
    }


def compare(expected: str, hosted: str) -> dict:
    local = regions(expected)
    try:
        remote = regions(hosted)
    except ValueError as exc:
        return {
            "status": "STALE",
            "reason": str(exc),
            "regions": {
                name: {"status": "MISSING", "source_sha256": fingerprint(block)}
                for name, block in local.items()
            },
        }
    results = {}
    for name, text in local.items():
        expected_sha = fingerprint(text)
        live_sha = fingerprint(remote[name])
        results[name] = {
            "status": "MATCH" if expected_sha == live_sha else "STALE",
            "source_sha256": expected_sha,
            "live_sha256": live_sha,
        }
    return {
        "status": "MATCH" if all(item["status"] == "MATCH" for item in results.values()) else "STALE",
        "regions": results,
    }


def selftest() -> None:
    sample = (
        "<!doctype html>" + RADAR_MARKER + "\n<script>(function(){return 1})()</script>"
        + LEGACY_BEGIN + " nl-history-entry NL.history() function renderHistory() */"
        + LEGACY_END + " */"
    )
    assert compare(sample, sample)["status"] == "MATCH"
    changed = sample.replace("return 1", "return 2")
    result = compare(sample, changed)
    assert result["status"] == "STALE"
    assert result["regions"]["dynamic_radar"]["status"] == "STALE"
    assert result["regions"]["evergreen_cases"]["status"] == "MATCH"
    missing = sample.replace(RADAR_MARKER, "")
    assert compare(sample, missing)["status"] == "STALE"
    stale_history = sample.replace("NL.history()", "NL.legacy()")
    assert compare(sample, stale_history)["status"] == "STALE"
    for bad in (missing, sample + RADAR_MARKER):
        try:
            regions(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid source was accepted")
    archive = json.dumps({
        "schema_version": 1, "selection_method": "major-social-work-v1",
        "event_count": 0, "events": [],
    }, ensure_ascii=False).encode()
    assert compare_major_archive(archive, archive)["status"] == "MATCH"
    assert compare_major_archive(archive, archive + b" ")["status"] == "STALE"
    try:
        compare_major_archive(archive, b'{"schema_version":1,"events":[{"title":"unverified"}]}')
    except ValueError:
        pass
    else:
        raise AssertionError("unverified major archive accepted")
    print("SWSI CURRENT AFFAIRS UI LIVE PARITY SELFTEST PASS")


def compare_major_archive(expected_raw: bytes, hosted_raw: bytes) -> dict:
    """Verify exact hosted bytes and the practice-only publication contract."""
    expected, hosted = json.loads(expected_raw), json.loads(hosted_raw)
    for data in (expected, hosted):
        if (data.get("schema_version") != 1
                or data.get("selection_method") != "major-social-work-v1"
                or int(data.get("event_count", -1)) != len(data.get("events") or [])):
            raise ValueError("major archive contract invalid")
        for event in data.get("events") or []:
            if (event.get("admission_rule") != "major-social-work-v1"
                    or len(event.get("evidence") or []) < 2
                    or len(event.get("practice_essays") or []) != 2
                    or not all(q.get("type") == "practice_only"
                               for q in event.get("practice_essays") or [])):
                raise ValueError("major archive contains unverified event or official-like essay")
    expected_sha = hashlib.sha256(expected_raw).hexdigest()
    hosted_sha = hashlib.sha256(hosted_raw).hexdigest()
    return {
        "status": "MATCH" if expected_sha == hosted_sha else "STALE",
        "source_sha256": expected_sha,
        "live_sha256": hosted_sha,
        "event_count": len(hosted.get("events") or []),
    }


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
        parser.error("use --live or --selftest")

    report: dict
    try:
        source = (ROOT / "cdn" / "index.html").read_text(encoding="utf-8")
        root = (ROOT / "index.html").read_text(encoding="utf-8")
        expected_regions = regions(source)
        root_regions = regions(root)
        if expected_regions != root_regions:
            report = {"status": "SOURCE_DRIFT", "reason": "root/CDN UI regions differ"}
        else:
            url = ORIGIN + "/?ui_parity=" + str(args.cache_bust).replace("/", "")[:80]
            request = urllib.request.Request(
                url, headers={
                    "User-Agent": "SWSI-Current-Affairs-UI-Parity/1.0",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status != 200:
                    raise urllib.error.URLError(f"home HTTP {response.status}")
                hosted = response.read(3_000_001)
            if len(hosted) > 3_000_000:
                raise ValueError("hosted index exceeds 3MB")
            report = compare(source, hosted.decode("utf-8", "replace"))
            local_major = (ROOT / "auto" / "major_social_work_events.json").read_bytes()
            cdn_major = (ROOT / "cdn" / "auto" / "major_social_work_events.json").read_bytes()
            if local_major != cdn_major:
                raise ValueError("major archive auto/CDN source drift")
            archive_url = (
                ORIGIN + "/auto/major_social_work_events.json?ui_parity="
                + str(args.cache_bust).replace("/", "")[:80]
            )
            archive_request = urllib.request.Request(
                archive_url, headers={
                    "User-Agent": "SWSI-Current-Affairs-UI-Parity/1.0",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(archive_request, timeout=20) as response:
                if response.status != 200:
                    raise urllib.error.URLError(f"major archive HTTP {response.status}")
                archive_bytes = response.read(2_000_001)
            if len(archive_bytes) > 2_000_000:
                raise ValueError("major archive too large")
            archive_comparison = compare_major_archive(local_major, archive_bytes)
            report["regions"]["major_event_archive"] = archive_comparison
            if archive_comparison["status"] != "MATCH":
                report["status"] = "STALE"
    except ValueError as exc:
        report = {"status": "SOURCE_DRIFT", "reason": str(exc)}
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        report = {"status": "UNREACHABLE", "reason": str(exc)[:240]}

    if args.out:
        Path(args.out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print("SWSI CLOUDFLARE CURRENT AFFAIRS UI PARITY:", report["status"])
    for name, item in report.get("regions", {}).items():
        print(name, item["status"], item.get("source_sha256", "")[:16],
              item.get("live_sha256", "")[:16])
    if report.get("regions", {}).get("major_event_archive"):
        print("major archive verified events:", report["regions"]["major_event_archive"]["event_count"])
    if report.get("reason"):
        print("diagnostic:", report["reason"])
    # Non-gating: a stale UI means deployment is pending, not that uptime failed.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

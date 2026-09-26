#!/usr/bin/env python3
"""Read-only live parity check for SWSI Cloudflare production static assets."""

from __future__ import annotations

import argparse
import hashlib
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CDN = ROOT / "cdn"
ORIGIN = "https://wandering-wave-4418.c022050333.workers.dev"
UA = "SWSI-Cloudflare-Production-Parity/1.0"


def fetch(path: str, check: str) -> tuple[int, bytes]:
    url = f"{ORIGIN}{path}?release_check={check}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return int(res.status), res.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", default="manual")
    ap.add_argument("--attempts", type=int, default=36)
    ap.add_argument("--sleep", type=float, default=5.0)
    args = ap.parse_args()

    expected_index = (CDN / "index.html").read_text(encoding="utf-8")
    expected_patch = (CDN / "monthly_patch.js").read_bytes()
    expected_sw = (CDN / "sw.js").read_bytes()

    tag = re.search(r'<script src="monthly_patch\.js\?v=([0-9a-f]{16})"></script>', expected_index)
    source = re.search(r'<meta name="swsi-release-source" content="([0-9a-f]{40})">', expected_index)
    if not tag or not source:
        raise SystemExit("Cloudflare production source/cache-bust marker missing from tracked cdn/index.html")

    expected_tag = tag.group(0)
    expected_source = source.group(0)
    patch_sha = sha(expected_patch)
    sw_sha = sha(expected_sw)

    last = ""
    for attempt in range(1, args.attempts + 1):
        token = f"{args.check}-{attempt}"
        try:
            home_status, home_body = fetch("/", token)
            patch_status, live_patch = fetch("/monthly_patch.js", token)
            sw_status, live_sw = fetch("/sw.js", token)
            home = home_body.decode("utf-8", "replace")

            checks = {
                "home_http": home_status == 200,
                "patch_http": patch_status == 200,
                "sw_http": sw_status == 200,
                "cache_bust": expected_tag in home,
                "release_source": expected_source in home,
                "soft_launch": "SWSI CLOUDFLARE PUBLIC SOFT LAUNCH" in home,
                "noindex": 'noindex,nofollow,noarchive' in home,
                "no_preview": "SWSI CLOUDFLARE FRONTEND PREVIEW" not in home and "swsi-preview-banner" not in home,
                "patch_bytes": sha(live_patch) == patch_sha,
                "sw_bytes": sha(live_sw) == sw_sha,
                "exam_label": b"swsi-exam-date-label" in live_patch,
            }
            if all(checks.values()):
                print(
                    "CLOUDFLARE PRODUCTION HTTP PARITY OK "
                    f"attempt={attempt} patch_sha256={patch_sha[:16]} "
                    f"sw_sha256={sw_sha[:16]} source={source.group(1)}"
                )
                return 0
            last = ", ".join(f"{k}={v}" for k, v in checks.items())
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"

        print(f"Waiting for Cloudflare production parity: attempt={attempt}/{args.attempts} {last}")
        if attempt < args.attempts:
            time.sleep(args.sleep)

    raise SystemExit(f"CLOUDFLARE PRODUCTION HTTP PARITY FAILED: {last}")


if __name__ == "__main__":
    raise SystemExit(main())

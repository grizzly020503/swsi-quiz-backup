#!/usr/bin/env python3
"""Fail-closed contract for tracked Cloudflare production frontend artifacts."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "monthly_patch_parts"
CDN = ROOT / "cdn"


def fail(message: str) -> None:
    raise SystemExit(f"CLOUDFLARE RELEASE ARTIFACT FAILED: {message}")


def main() -> int:
    parts = sorted(PARTS.glob("*.part"))
    if not parts:
        fail("monthly_patch_parts is empty")

    expected = b"".join(path.read_bytes() for path in parts)
    actual_path = CDN / "monthly_patch.js"
    if not actual_path.is_file():
        fail("cdn/monthly_patch.js missing")
    actual = actual_path.read_bytes()
    if actual != expected:
        fail("cdn/monthly_patch.js does not equal canonical monthly_patch_parts build")

    digest = hashlib.sha256(actual).hexdigest()[:16]
    index_path = CDN / "index.html"
    if not index_path.is_file():
        fail("cdn/index.html missing")
    html = index_path.read_text(encoding="utf-8")

    required = (
        "<!-- SWSI CLOUDFLARE PUBLIC SOFT LAUNCH -->",
        '<meta name="robots" content="noindex,nofollow,noarchive">',
        'https://wandering-wave-4418.c022050333.workers.dev/',
        f'<script src="monthly_patch.js?v={digest}"></script>',
    )
    for marker in required:
        if marker not in html:
            fail(f"production index marker missing: {marker}")

    release = re.search(
        r'<meta name="swsi-release-source" content="([0-9a-f]{40})">',
        html,
    )
    if not release:
        fail("swsi-release-source marker missing or invalid")

    forbidden = (
        "SWSI CLOUDFLARE FRONTEND PREVIEW",
        "swsi-preview-banner",
        "SWSI CLOUDFLARE PUBLIC CANDIDATE",
        "swsi-public-candidate-wandering-wave-4418",
    )
    for marker in forbidden:
        if marker in html:
            fail(f"preview/candidate marker leaked into production: {marker}")

    current_affairs_marker = '<!-- SWSI CURRENT AFFAIRS RADAR V1 -->'
    if html.count(current_affairs_marker) != 1:
        fail("tracked CDN current-affairs UI owner must appear exactly once")
    installer = (ROOT / "scripts" / "install_current_affairs_ui.py").read_text(encoding="utf-8")
    block_prefix = "BLOCK = r'''"
    canonical_start = installer.find(block_prefix)
    canonical_end = installer.find("\n'''", canonical_start + len(block_prefix))
    if canonical_start < 0 or canonical_end < 0:
        fail("canonical current-affairs installer block missing")
    canonical = installer[canonical_start + len(block_prefix):canonical_end].strip()
    block_start = html.index(current_affairs_marker)
    script_start = html.find('<script>', block_start)
    script_end = html.find('</script>', script_start)
    if script_start < 0 or script_end < 0:
        fail("tracked CDN current-affairs script boundary missing")
    live_block = html[block_start:script_end + len('</script>')].strip()
    if live_block != canonical:
        fail("tracked CDN current-affairs UI does not match canonical installer")

    patch_text = actual.decode("utf-8")
    for marker in (
        ".swsi-exam-date-label",
        'for="swsi-exam-date-input">考試日期</label>',
        ".swsi-report-help{display:flex",
        "color:#6E746E",
    ):
        if marker not in patch_text:
            fail(f"verified accessibility runtime marker missing: {marker}")

    if (CDN / "sw.js").read_bytes() != (ROOT / "sw.js").read_bytes():
        fail("cdn/sw.js differs from canonical root sw.js")

    print(
        "CLOUDFLARE RELEASE ARTIFACT OK "
        f"parts={len(parts)} patch_sha256={digest} source={release.group(1)} sw=parity"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

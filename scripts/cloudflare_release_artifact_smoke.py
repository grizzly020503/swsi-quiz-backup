#!/usr/bin/env python3
"""Fail-closed contract for tracked Cloudflare production frontend artifacts."""

from __future__ import annotations

import hashlib
import json
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

    # The Cloudflare tracked artifact must use the same maintained study UI
    # as the production-shaped Netlify build, never the retired radar label.
    if "目前 3 個國考重點" not in html:
        fail("tracked Cloudflare study-priorities UI is not canonical")
    if "命題趨勢雷達" in html:
        fail("obsolete trend-radar UI in tracked Cloudflare production artifact")
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

    patch_text = actual.decode("utf-8")
    for marker in (
        ".swsi-exam-date-label",
        'for="swsi-exam-date-input">考試日期</label>',
        ".swsi-report-help{display:flex",
        "color:#6E746E",
    ):
        if marker not in patch_text:
            fail(f"verified accessibility runtime marker missing: {marker}")

    # Primary Cloudflare static guide artifact must include the already-reviewed
    # 68 historical corrections and all 10 official 115-2 question guide overlays.
    # The canonical builder is byte-compared independently in Essay Guide Overlay QA.
    guide_path = CDN / "essay_guides.js"
    if not guide_path.is_file():
        fail("cdn/essay_guides.js missing")
    guide_raw = guide_path.read_text(encoding="utf-8")
    found = re.fullmatch(
        r"/\\*[^\\n]*\\*/\\nwindow\\.ESSAY_GUIDES = (\\{[^\\n]+\\});\\n?",
        guide_raw,
    )
    if not found:
        fail("Cloudflare student essay guide artifact is malformed")
    try:
        guide_map = json.loads(found.group(1))
    except (ValueError, TypeError):
        fail("Cloudflare student essay guide artifact is not JSON")
    if not isinstance(guide_map, dict) or len(guide_map) != 240:
        fail("Cloudflare student guide count must be 240")
    e_ids = [key for key in guide_map if re.fullmatch(r"E-115-2-(?:HBSE|SW|DS|R|SP)-[12]", key)]
    if len(e_ids) != 10 or any(
        not isinstance(guide_map[key], dict)
        or guide_map[key].get("review_status") != "verified"
        or guide_map[key].get("is_official") is not False
        for key in e_ids
    ):
        fail("10 verified, explicitly nonofficial 115-2 guides must be present")

    if (CDN / "sw.js").read_bytes() != (ROOT / "sw.js").read_bytes():
        fail("cdn/sw.js differs from canonical root sw.js")

    # Calm UI is shipped in BOTH HTML entrypoints; fail closed on UI drift.
    # No mutable JS, official exam data, AI contract or SW bytes are changed.
    root_html = (ROOT / "index.html").read_text(encoding="utf-8")
    style_tag = re.compile(
        r'<style id="swsi-calm-student-design-v2">([\s\S]*?)</style>'
    )
    root_styles = style_tag.findall(root_html)
    cdn_styles = style_tag.findall(html)
    if len(root_styles) != 1 or len(cdn_styles) != 1:
        fail("calm student style is missing or duplicated in root/CDN")
    if root_styles[0] != cdn_styles[0]:
        fail("Cloudflare and canonical root calm student CSS differ")
    if "<!-- SWSI CALM STUDENT DESIGN V2 START -->" not in html:
        fail("calm student design release marker missing")

    def luminance(color: str) -> float:
        channels = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    def contrast(first: str, second: str) -> float:
        a, b = luminance(first), luminance(second)
        return (max(a, b) + 0.05) / (min(a, b) + 0.05)

    for token, background in (
        ("--ink-soft", "#FFFFFF"),
        ("--pine", "#FFFFFF"),
        ("--pine-deep", "#FFFFFF"),
        ("--wrong", "#FFF2F0"),
        ("--correct", "#EDF7F1"),
    ):
        hit = re.search(r'(?m)^\s*' + re.escape(token) + r':(#[0-9A-Fa-f]{6})\s*;', cdn_styles[0])
        if not hit:
            fail(f"calm design color token missing: {token}")
        if contrast(hit.group(1), background) < 4.5:
            fail(f"calm design text contrast below WCAG AA: {token}")
    for required in (
        "body .ux-home-intro",
        "body .swsi-focus-primary",
        "body .tabbar",
        "body .qcard",
        "body .opt",
        "body .swsi-explanation-more",
        ":focus-visible",
        "prefers-reduced-motion",
        "min-width:768px",
    ):
        if required not in cdn_styles[0]:
            fail(f"calm design responsive/accessibility contract missing: {required}")

    print(
        "CLOUDFLARE RELEASE ARTIFACT OK "
        f"parts={len(parts)} patch_sha256={digest} source={release.group(1)} sw=parity"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

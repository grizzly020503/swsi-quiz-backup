#!/usr/bin/env python3
"""Read-only Cloudflare/Netlify V4 presentation parity; never deploy or modify data."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("NETLIFY V4 VISUAL PARITY FAILED: " + message)


def style(html: str, tag: str, label: str) -> str:
    pattern = re.compile(r'<style id="' + re.escape(tag) + r'">(.*?)</style>', re.S)
    matches = pattern.findall(html)
    require(len(matches) == 1, f"{label}: expected exactly one {tag} stylesheet")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, help="Netlify production-shaped build directory")
    args = parser.parse_args()

    root = (ROOT / "index.html").read_text(encoding="utf-8")
    cloudflare = (ROOT / "cdn/index.html").read_text(encoding="utf-8")
    for name in ("swsi-calm-student-design-v2", "swsi-calm-learning-ui-v3"):
        require(style(root, name, "Netlify") == style(cloudflare, name, "Cloudflare"),
                name + " differs between primary and backup")

    require('meta name="swsi-netlify-release"' in root,
            "Netlify release identity missing")
    for marker in ("SWSI CLOUDFLARE PUBLIC SOFT LAUNCH",
                   'id="swsi-source-hold-review-guard"',
                   'name="swsi-release-source"'):
        require(marker not in root, "Cloudflare-only marker leaked: " + marker)

    home = (ROOT / "monthly_patch_parts/20.product-philosophy.part").read_text(encoding="utf-8")
    nav = (ROOT / "monthly_patch_parts/zzzz_product_v1_lock.part").read_text(encoding="utf-8")
    require('swsi-v4-hero' in home and 'renderHome=function()' in home,
            "shared V4 homepage source missing")
    require('swsi-v4-tab-quiz' in nav and "setNavButton('t-review'" in nav,
            "shared four-tab navigation owner missing")

    if args.site:
        site = args.site.resolve()
        html = (site / "index.html").read_text(encoding="utf-8")
        for name in ("swsi-calm-student-design-v2", "swsi-calm-learning-ui-v3"):
            require(style(html, name, "Built Netlify") == style(cloudflare, name, "Cloudflare"),
                    "built Netlify stylesheet differs: " + name)
        runtime = (site / "monthly_patch.js").read_text(encoding="utf-8")
        require('swsi-v4-hero' in runtime and 'swsi-v4-tab-quiz' in runtime,
                "built Netlify runtime missing shared V4 homepage/navigation")
    print("NETLIFY V4 VISUAL PARITY OK: V2/V3 shared styles, isolated deployment identities, shared V4 runtime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

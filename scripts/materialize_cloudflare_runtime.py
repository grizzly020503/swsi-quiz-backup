#!/usr/bin/env python3
"""Materialize tracked Cloudflare frontend runtime from canonical patch parts.

This script is repository-only. It does not deploy. It keeps the tracked
`cdn/monthly_patch.js` byte-for-byte equal to sorted `monthly_patch_parts/*.part`
and updates the existing Cloudflare soft-launch cache-bust marker in
`cdn/index.html` to the matching 16-character SHA-256 prefix.
"""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "monthly_patch_parts"
PATCH = ROOT / "cdn" / "monthly_patch.js"
INDEX = ROOT / "cdn" / "index.html"
TAG_RE = re.compile(r'<script src="monthly_patch\.js\?v=[0-9a-f]{16}"></script>')


def expected_patch() -> bytes:
    parts = sorted(PARTS.glob("*.part"), key=lambda path: path.name)
    if not parts:
        raise RuntimeError("monthly_patch_parts is empty")
    return b"".join(path.read_bytes() for path in parts)


def expected_index(patch: bytes) -> str:
    if not INDEX.is_file():
        raise RuntimeError("cdn/index.html missing")
    text = INDEX.read_text(encoding="utf-8")
    matches = TAG_RE.findall(text)
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one tracked monthly_patch cache-bust tag, found {len(matches)}")
    digest = hashlib.sha256(patch).hexdigest()[:16]
    tag = f'<script src="monthly_patch.js?v={digest}"></script>'
    return TAG_RE.sub(tag, text, count=1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    patch = expected_patch()
    index = expected_index(patch)
    digest = hashlib.sha256(patch).hexdigest()[:16]

    if args.check:
        current_patch = PATCH.read_bytes() if PATCH.is_file() else b""
        current_index = INDEX.read_text(encoding="utf-8") if INDEX.is_file() else ""
        if current_patch != patch or current_index != index:
            raise SystemExit(
                "CLOUDFLARE RUNTIME MATERIALIZATION DRIFT: run scripts/materialize_cloudflare_runtime.py"
            )
        print(f"CLOUDFLARE RUNTIME MATERIALIZATION OK sha256={digest}")
        return 0

    PATCH.write_bytes(patch)
    INDEX.write_text(index, encoding="utf-8")
    print(f"Materialized tracked Cloudflare runtime sha256={digest} bytes={len(patch)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

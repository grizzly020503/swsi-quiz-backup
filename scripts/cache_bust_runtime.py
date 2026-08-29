#!/usr/bin/env python3
"""Version mutable front-end runtime assets in the built HTML.

Netlify Deploy Preview reuses the same hostname for every commit. Some mobile
browsers / embedded preview shells can keep an older monthly_patch.js even after
a successful redeploy. Add a content-hash query string so every changed patch
gets a new URL without changing the deployed filename.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('site', nargs='?', default='_site')
    args = ap.parse_args()

    site = Path(args.site)
    index = site / 'index.html'
    patch = site / 'monthly_patch.js'
    if not index.exists() or not patch.exists():
        raise RuntimeError('cache bust: built index.html or monthly_patch.js missing')

    digest = hashlib.sha256(patch.read_bytes()).hexdigest()[:16]
    text = index.read_text(encoding='utf-8')
    old = '<script src="monthly_patch.js"></script>'
    new = f'<script src="monthly_patch.js?v={digest}"></script>'
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'cache bust: expected one monthly_patch script tag, found {count}')
    index.write_text(text.replace(old, new, 1), encoding='utf-8')
    print(f'Cache-busted monthly_patch.js: {digest}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

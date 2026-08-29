#!/usr/bin/env python3
"""Remove administrator identity hints from the published Admin login page.

Authorization remains server-side (Supabase Auth + swsi_admin_users). This build
step is privacy defense-in-depth: the public artifact must not prefill or silently
fall back to a maintainer email address.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def require_count(text: str, pattern: str, expected: int, label: str) -> None:
    count = len(re.findall(pattern, text, flags=re.M))
    if count != expected:
        raise RuntimeError(f"admin identity privacy expected {expected} {label}; found {count}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="_site/admin/index.html")
    args = ap.parse_args()
    path = Path(args.path)
    text = path.read_text(encoding="utf-8")

    # The source currently has one visible email input prefill. Remove the value
    # without knowing or embedding the actual administrator identity here.
    email_tag_re = re.compile(r'<input\b[^>]*\bid="email"[^>]*>', re.I)
    match = email_tag_re.search(text)
    if not match:
        raise RuntimeError("admin identity privacy could not find email input")
    tag = match.group(0)
    value_matches = re.findall(r'\svalue="[^"]*"', tag, flags=re.I)
    if len(value_matches) != 1:
        raise RuntimeError(
            f"admin identity privacy expected one email input prefill; found {len(value_matches)}"
        )
    clean_tag = re.sub(r'\svalue="[^"]*"', '', tag, count=1, flags=re.I)
    text = text[:match.start()] + clean_tag + text[match.end():]

    # Remove the source-only default identity and the assignment that preloads it.
    default_re = r'^\s*const\s+DEFAULT_ADMIN_EMAIL\s*=.*?;\s*$'
    require_count(text, default_re, 1, "default admin email declaration")
    text = re.sub(default_re, '', text, count=1, flags=re.M)

    assignment_re = r"^\s*\$\('email'\)\.value\s*=\s*DEFAULT_ADMIN_EMAIL;\s*$"
    require_count(text, assignment_re, 1, "default admin email assignment")
    text = re.sub(assignment_re, '', text, count=1, flags=re.M)

    # Password reset and magic-link actions must require manually entered email.
    fallback = "||DEFAULT_ADMIN_EMAIL"
    if text.count(fallback) != 2:
        raise RuntimeError(
            f"admin identity privacy expected two default-email fallbacks; found {text.count(fallback)}"
        )
    text = text.replace(fallback, '')

    if 'DEFAULT_ADMIN_EMAIL' in text:
        raise RuntimeError("admin identity privacy left a default administrator identity reference")

    final_match = email_tag_re.search(text)
    if not final_match or re.search(r'\svalue=', final_match.group(0), flags=re.I):
        raise RuntimeError("admin identity privacy left the email input prefilled")

    path.write_text(text, encoding="utf-8")
    print("ADMIN IDENTITY PRIVACY OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail closed if the published Admin page exposes a maintainer identity.

Authorization remains server-side (Supabase Auth + swsi_admin_users). The source
must already be privacy-safe: no prefilled email and no silent default identity
for login, password reset, or magic-link actions.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="_site/admin/index.html")
    args = ap.parse_args()
    path = Path(args.path)
    text = path.read_text(encoding="utf-8")

    email_tag_re = re.compile(r'<input\b[^>]*\bid="email"[^>]*>', re.I)
    match = email_tag_re.search(text)
    if not match:
        raise RuntimeError("admin identity privacy could not find email input")

    # The public login form must never reveal or prefill an administrator identity.
    if re.search(r'\svalue\s*=', match.group(0), flags=re.I):
        raise RuntimeError("admin identity privacy found a prefilled email input")
    if "DEFAULT_ADMIN_EMAIL" in text:
        raise RuntimeError("admin identity privacy found a default administrator identity")

    # Recovery and magic-link flows must use only the email explicitly typed into
    # the form. No hidden account fallback is allowed.
    entered_email = "const email=$('email').value.trim();"
    if text.count(entered_email) != 2:
        raise RuntimeError(
            f"admin identity privacy expected two explicit entered-email flows; found {text.count(entered_email)}"
        )
    missing_email_guard = "if(!email){showLogin('請先輸入管理者 Email。','error');return;}"
    if text.count(missing_email_guard) != 2:
        raise RuntimeError(
            f"admin identity privacy expected two missing-email guards; found {text.count(missing_email_guard)}"
        )

    print("ADMIN IDENTITY PRIVACY OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

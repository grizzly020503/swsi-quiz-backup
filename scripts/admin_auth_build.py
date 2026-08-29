#!/usr/bin/env python3
"""Harden the built admin auth flow and attach admin-only runtimes.

This build step fail-closes if the expected admin source contract drifts. It
separates password recovery from magic-link login, prevents the dashboard from
loading until a recovery password has actually been updated, removes any
published admin-login identity prefill/fallback, and injects the grouped-feedback
admin runtime into the built admin page.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"admin auth build expected exactly one {label}; found {count}")
    return text.replace(old, new, 1)


def strip_admin_identity_prefill(text: str) -> str:
    """Never publish or silently fall back to an administrator login identity."""
    email_input = re.search(r'<input\b[^>]*\bid=(["\'])email\1[^>]*>', text, flags=re.I)
    if not email_input:
        raise RuntimeError("admin privacy build could not find management email input")

    original_tag = email_input.group(0)
    clean_tag = re.sub(r'\s+value=(["\']).*?\1', '', original_tag, flags=re.I)
    text = text[: email_input.start()] + clean_tag + text[email_input.end() :]

    fallback = "$('email').value.trim()||DEFAULT_ADMIN_EMAIL"
    fallback_count = text.count(fallback)
    if fallback_count not in (0, 2):
        raise RuntimeError(
            f"admin privacy build expected zero or two default-email fallbacks; found {fallback_count}"
        )
    text = text.replace(fallback, "$('email').value.trim()")

    text = re.sub(
        r'(?m)^\s*const\s+DEFAULT_ADMIN_EMAIL\s*=\s*(["\']).*?\1;\s*\n?',
        '',
        text,
    )
    text = re.sub(
        r"(?m)^\s*\$\('email'\)\.value\s*=\s*DEFAULT_ADMIN_EMAIL;\s*\n?",
        '',
        text,
    )

    if 'DEFAULT_ADMIN_EMAIL' in text:
        raise RuntimeError("admin privacy build left a default admin identity reference")

    built_email_input = re.search(r'<input\b[^>]*\bid=(["\'])email\1[^>]*>', text, flags=re.I)
    if not built_email_input:
        raise RuntimeError("admin privacy build lost management email input")
    if re.search(r'\svalue\s*=', built_email_input.group(0), flags=re.I):
        raise RuntimeError("admin privacy build left the management email prefilled")

    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="_site/admin/index.html")
    args = ap.parse_args()
    path = Path(args.path)
    text = path.read_text(encoding="utf-8")

    text = strip_admin_identity_prefill(text)

    text = replace_once(
        text,
        "  const client=window.supabase.createClient(SUPABASE_URL,SUPABASE_PUBLISHABLE_KEY,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true}});\n  let payload=null; let recoveryMode=false;",
        "  const authQuery=new URLSearchParams(location.search);\n  const authHash=new URLSearchParams(location.hash.replace(/^#/,''));\n  let payload=null;\n  let recoveryMode=authQuery.get('authMode')==='recovery'||authHash.get('type')==='recovery';\n  const client=window.supabase.createClient(SUPABASE_URL,SUPABASE_PUBLISHABLE_KEY,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true}});",
        "pre-auth recovery gate",
    )

    text = replace_once(
        text,
        "  const callbackUrl=()=>location.origin+location.pathname+'?adminAuth=1';",
        "  const callbackUrl=(mode)=>{const u=new URL(location.origin+location.pathname);u.searchParams.set('adminAuth','1');u.searchParams.set('authMode',mode);return u.toString();};",
        "callback URL helper",
    )

    text = replace_once(
        text,
        "  function showAdmin(){recoveryMode=false;hideAuthViews();$('adminView').classList.remove('hidden');}",
        "  function showAdmin(){if(recoveryMode){showRecovery('請先設定新的管理密碼。');return;}hideAuthViews();$('adminView').classList.remove('hidden');}",
        "showAdmin recovery guard",
    )

    text = replace_once(
        text,
        "  async function loadAdmin(){try{payload=await adminFetch();showAdmin();render();}",
        "  async function loadAdmin(){if(recoveryMode){showRecovery('請先設定新的管理密碼。');return;}try{payload=await adminFetch();showAdmin();render();}",
        "loadAdmin recovery guard",
    )

    text = replace_once(
        text,
        "client.auth.resetPasswordForEmail(email,{redirectTo:callbackUrl()})",
        "client.auth.resetPasswordForEmail(email,{redirectTo:callbackUrl('recovery')})",
        "password recovery callback",
    )

    text = replace_once(
        text,
        "emailRedirectTo:callbackUrl()",
        "emailRedirectTo:callbackUrl('magic')",
        "magic-link callback",
    )

    text = replace_once(
        text,
        "history.replaceState({},'',location.pathname);$('recoveryMessage').className='success';",
        "recoveryMode=false;history.replaceState({},'',location.pathname);$('recoveryMessage').className='success';",
        "recovery completion unlock",
    )

    old_listener = "  client.auth.onAuthStateChange((event,session)=>{if(event==='PASSWORD_RECOVERY'){showRecovery('請設定一組新的管理密碼。');return;}if(session&&!recoveryMode)loadAdmin();});"
    new_listener = "  client.auth.onAuthStateChange((event,session)=>{if(event==='PASSWORD_RECOVERY')recoveryMode=true;if(recoveryMode){showRecovery(session?'請設定一組新的管理密碼。':'正在驗證密碼重設連結…');return;}if(session)loadAdmin();});"
    text = replace_once(text, old_listener, new_listener, "auth-state recovery gate")

    old_boot = "  client.auth.getSession().then(({data})=>{const wantsRecovery=new URLSearchParams(location.search).has('adminAuth')&&location.hash.includes('type=recovery');if(wantsRecovery&&data.session)showRecovery('請設定一組新的管理密碼。');else if(data.session)loadAdmin();else showLogin();});"
    new_boot = "  if(recoveryMode)showRecovery('正在驗證密碼重設連結…');\n  client.auth.getSession().then(({data})=>{if(recoveryMode){showRecovery(data.session?'請設定一組新的管理密碼。':'正在驗證密碼重設連結…');return;}if(data.session)loadAdmin();else showLogin();});"
    text = replace_once(text, old_boot, new_boot, "initial recovery gate")

    if "feedback_clusters.js" not in text:
        text = replace_once(
            text,
            "</body>",
            '<script src="./feedback_clusters.js"></script>\n</body>',
            "admin grouped-feedback runtime insertion point",
        )

    required = [
        "authMode')==='recovery'",
        "callbackUrl('recovery')",
        "callbackUrl('magic')",
        "if(recoveryMode){showRecovery('請先設定新的管理密碼。');return;}",
        "if(event==='PASSWORD_RECOVERY')recoveryMode=true",
        "recoveryMode=false;history.replaceState",
        '<script src="./feedback_clusters.js"></script>',
    ]
    for marker in required:
        if marker not in text:
            raise RuntimeError(f"admin auth build marker missing: {marker}")

    path.write_text(text, encoding="utf-8")
    print("ADMIN AUTH RECOVERY + FEEDBACK CLUSTERS + IDENTITY PRIVACY OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

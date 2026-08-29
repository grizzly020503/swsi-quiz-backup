#!/usr/bin/env python3
"""Harden the built admin auth flow without changing student runtime.

This build step fail-closes if the expected admin source contract drifts. It
separates password recovery from magic-link login and prevents the dashboard
from loading until a recovery password has actually been updated.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"admin auth build expected exactly one {label}; found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="_site/admin/index.html")
    args = ap.parse_args()
    path = Path(args.path)
    text = path.read_text(encoding="utf-8")

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

    required = [
        "authMode')==='recovery'",
        "callbackUrl('recovery')",
        "callbackUrl('magic')",
        "if(recoveryMode){showRecovery('請先設定新的管理密碼。');return;}",
        "if(event==='PASSWORD_RECOVERY')recoveryMode=true",
        "recoveryMode=false;history.replaceState",
    ]
    for marker in required:
        if marker not in text:
            raise RuntimeError(f"admin auth build marker missing: {marker}")

    path.write_text(text, encoding="utf-8")
    print("ADMIN AUTH RECOVERY GATE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

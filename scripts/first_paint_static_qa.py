#!/usr/bin/env python3
"""Fail closed if SWSI student first paint regains known blocking startup work."""
from __future__ import annotations

import argparse
from pathlib import Path


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', default='_site')
    args = ap.parse_args()
    site = Path(args.site)
    html = (site / 'index.html').read_text(encoding='utf-8')
    patch = (site / 'monthly_patch.js').read_text(encoding='utf-8')

    require('cdn.jsdelivr.net/npm/@supabase/supabase-js@2' not in html,
            'student first paint again blocks on Supabase JS SDK')
    require('window.__SWSI_STUDENT_REST_ONLY__=true;' in html,
            'student REST-only startup marker missing')
    require('fonts.googleapis.com' not in html and 'fonts.gstatic.com' not in html,
            'student first paint again depends on external Google Fonts')
    require('<meta name="swsi-font-policy" content="system-font-first">' in html,
            'system-font-first startup marker missing')
    require('介面先顯示，題庫資料會在背景準備。' in html,
            'visible first-paint shell missing')
    require('window.__SWSI_BOOT_DEFERRED__=true;' in html,
            'legacy init is no longer deferred until monthly patch owners are installed')

    verified_boot = '''if(window.__SWSI_BOOT_DEFERRED__){
    window.__SWSI_BOOT_DEFERRED__=false;
    init().catch(showLoadError);
  }'''
    require(verified_boot in patch,
            'verified deferred init boot contract missing from monthly patch')
    require('__SWSI_FAST_BOOT_VERSION__' not in patch,
            'experimental UI-first boot override returned')

    print('FIRST PAINT STATIC QA OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

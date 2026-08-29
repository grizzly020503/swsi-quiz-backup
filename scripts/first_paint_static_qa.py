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
    require('media="print" onload="this.media=\'all\'"' in html,
            'Google Fonts stylesheet is render-blocking again')
    require('介面先顯示，題庫資料會在背景準備。' in html,
            'UI-first initial shell missing')
    require("window.__SWSI_FAST_BOOT_VERSION__='2026-08-29.ui-first.v1'" in patch,
            'UI-first runtime boot marker missing')
    require("tabbar.style.display='flex';" in patch and "go('home');" in patch,
            'home shell is not rendered synchronously by fast boot')
    fast_pos = patch.find("window.__SWSI_FAST_BOOT_VERSION__='2026-08-29.ui-first.v1'")
    home_pos = patch.find("go('home');", fast_pos)
    hydrate_pos = patch.find('await loadQuestionManifest();', fast_pos)
    require(fast_pos >= 0 and home_pos >= 0 and hydrate_pos > home_pos,
            'question catalog hydration moved back ahead of Home')
    require('await loadAutoEssays();' in patch[hydrate_pos:],
            'background essay hydration marker missing')

    print('FIRST PAINT STATIC QA OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

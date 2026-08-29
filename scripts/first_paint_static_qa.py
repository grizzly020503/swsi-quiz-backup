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

    marker = "window.__SWSI_FAST_BOOT_VERSION__='2026-08-29.ui-first.v2'"
    require(marker in patch, 'UI-first runtime boot marker missing')
    require("tabbar.style.display='flex';" in patch and "go('home');" in patch,
            'home shell boot is missing')

    fast_pos = patch.find(marker)
    defer_pos = patch.find('Promise.resolve().then(function(){', fast_pos)
    home_pos = patch.find("go('home');", defer_pos)
    paint_gap_pos = patch.find('setTimeout(function(){', home_pos)
    hydrate_pos = patch.find('loadQuestionManifest()', paint_gap_pos)
    essay_pos = patch.find('loadAutoEssays()', paint_gap_pos)
    require(fast_pos >= 0 and defer_pos > fast_pos and home_pos > defer_pos,
            'Home is no longer deferred until later runtime owners are installed')
    require(paint_gap_pos > home_pos,
            'background hydration starts before the browser gets a paint opportunity')
    require(hydrate_pos > paint_gap_pos and essay_pos > paint_gap_pos,
            'question or essay hydration moved back ahead of Home')
    require('Promise.allSettled([manifestTask,essayTask])' in patch[paint_gap_pos:],
            'background data hydration is no longer isolated from first paint')

    print('FIRST PAINT STATIC QA OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail closed if SWSI first paint or global layout ownership regresses."""
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

    # First-paint contract.
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

    # Layered layout contract. One module owns the shell; page and component
    # modules are not allowed to bring back the old spacing hacks.
    require(patch.count('SWSI Layout Foundation V1 2026-08-29') == 1,
            'canonical layout foundation missing or duplicated')
    require("swsi-layout-foundation-v1" in patch,
            'layout foundation style marker missing')
    require("data-swsi-page" in patch and "swsi-layout-ready" in patch,
            'page-template classifier missing from layout foundation')
    require('padding-bottom:calc(128px' not in patch,
            'oversized 128px footer padding returned')
    require('margin-top:clamp(150px' not in patch,
            'arbitrary loading/footer spacer returned')
    require('body:has(#app .swsi-focus-hero) .wrap' not in patch,
            'home feature module regained global wrap ownership')

    # The repo-source checks make ownership explicit instead of merely hoping
    # concatenation order keeps competing shell rules harmless.
    parts = Path('monthly_patch_parts')
    if parts.is_dir():
        foundation = (parts / '15.layout-foundation.part').read_text(encoding='utf-8')
        require('SWSI Layout Foundation V1 2026-08-29' in foundation,
                'layout foundation source marker missing')

        constrained = {
            '50.home-spacing-essay-entry.part': ['.wrap{', 'main{', 'footer{', '.tabbar{'],
            '72.prelaunch-mobile-polish.part': ['.wrap{', 'main{', 'footer{', '.tabbar{'],
            '99_p0_mobile_ai_guardrails.part': ['.wrap{', 'main{', 'header{', 'footer{', '.tabbar{'],
            'zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz_preview_layout_polish.part': ['.wrap{', 'main{', 'footer{', '.tabbar{'],
        }
        for name, forbidden in constrained.items():
            text = (parts / name).read_text(encoding='utf-8')
            for token in forbidden:
                require(token not in text,
                        f'{name} regained Layer-1 shell ownership via {token}')

    print('FIRST PAINT + LAYOUT OWNERSHIP STATIC QA OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

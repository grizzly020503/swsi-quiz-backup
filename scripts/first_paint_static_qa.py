#!/usr/bin/env python3
"""Fail closed if SWSI first paint or global layout/ops ownership regresses."""
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

    # Feedback-origin contract. Production feedback must stay closed to arbitrary
    # origins while still permitting the exact Netlify deploy-preview host shape
    # used for pre-release E2E verification.
    feedback_edge = Path('supabase/functions/swsi-feedback/index.ts')
    if feedback_edge.is_file():
        feedback = feedback_edge.read_text(encoding='utf-8')
        require('https://swsi-quiznetlify.netlify.app' in feedback,
                'production Netlify feedback origin missing')
        require('https://wandering-wave-4418.c022050333.workers.dev' in feedback,
                'known Worker feedback origin missing')
        require('deploy-preview-' in feedback and '--swsi-quiznetlify\\.netlify\\.app' in feedback,
                'strict Netlify deploy-preview feedback origin contract missing')
        require('NETLIFY_PREVIEW_ORIGIN.test(origin)' in feedback,
                'deploy-preview feedback origin is defined but not enforced')
        require('Access-Control-Allow-Origin\": \"*\"' not in feedback,
                'feedback CORS regressed to wildcard origin')

    # Admin source-of-truth contract. This guards against redeploying the older
    # pre-v5 admin function that lacked Preview CORS and grouped feedback.
    admin_edge = Path('supabase/functions/swsi-admin/index.ts')
    if admin_edge.is_file():
        admin = admin_edge.read_text(encoding='utf-8')
        require('https://swsi-quiznetlify.netlify.app' in admin,
                'production Netlify admin origin missing')
        require('https://wandering-wave-4418.c022050333.workers.dev' in admin,
                'known Worker admin origin missing')
        require('deploy-preview-' in admin and '--swsi-quiznetlify\\.netlify\\.app' in admin,
                'strict Netlify deploy-preview admin origin contract missing')
        require('NETLIFY_PREVIEW_ORIGIN.test(origin)' in admin,
                'deploy-preview admin origin is defined but not enforced')
        require('admin.auth.getUser(token)' in admin,
                'admin Edge Function lost JWT session verification')
        require('.from("swsi_admin_users")' in admin,
                'admin Edge Function lost administrator membership check')
        require('.limit(1000)' in admin and 'feedback_clusters' in admin,
                'admin Edge Function lost grouped-feedback aggregation contract')
        require('rawFeedbackRows = feedbackRows.slice(0, 100)' in admin,
                'admin raw feedback cap regressed')
        require('Access-Control-Allow-Origin\": \"*\"' not in admin,
                'admin CORS regressed to wildcard origin')

    print('FIRST PAINT + LAYOUT + ADMIN/FEEDBACK OPS STATIC QA OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

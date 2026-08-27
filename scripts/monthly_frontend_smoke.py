#!/usr/bin/env python3
"""Static smoke checks for the built SWSI front end."""
# Keep Service Worker assertions aligned with the effective runtime contract.
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
    sw = (site / 'sw.js').read_text(encoding='utf-8')
    auto_essay_path = site / 'auto' / 'essays_auto.json'
    auto_essay = auto_essay_path.read_text(encoding='utf-8') if auto_essay_path.exists() else ''

    require('<script src="monthly_patch.js"></script>' in html, 'monthly_patch.js not injected')
    require('window.__SWSI_BOOT_DEFERRED__=true;' in html, 'legacy boot was not deferred')
    require('<title>社工師國考免費題庫｜SWSI</title>' in html, 'SEO title missing')
    require('rel="canonical" href="https://swsi-quiznetlify.netlify.app/"' in html, 'canonical missing')
    require('picked===q.answer||/一律給分|送分/' not in html, 'legacy simulation grading still present')
    require("isCorrectAnswer(q,picked)" in html, 'simulation grading helper missing')
    require("answerLabel(q)" in html, 'simulation answer label helper missing')
    require('value="第一次"' not in html and 'value="第二次"' not in html, 'round regression still present')
    require('\uE129' not in html and '\uE12A' not in html and '\uE12B' not in html, 'MOEX PUA glyphs remain in built HTML')
    require('' not in auto_essay and '' not in auto_essay and '' not in auto_essay, 'MOEX PUA glyphs remain in deployed auto essays')

    for token in [
        'SWSI_QUESTION_CDN_BASE', 'acceptedAnswers(item)', 'gradingMode(item)',
        'isCorrectAnswer(item,picked)', 'ensureAllQuestionsLoaded',
        'X-SWSI-Client-ID', 'files.length>3', 'renderTopics=function',
        '官方一律給分（未作答也得分）', 'any_answer',
        'SWSI Code Health P0 Runtime Guard 2026-08-26',
        'SWSI MK Unified Grading Contract 2026-08-26',
        'SWSI MK Record Policy 2026-08-27',
        'swsiMockRecordPolicyVersion',
    ]:
        require(token in patch, f'monthly patch critical token missing: {token}')

    require("const VERSION = 'v6';" in sw, 'service worker version was not bumped to v6')
    for asset in ['/monthly_patch.js', '/essay_guides.js', '/manifest.json']:
        require(asset in sw, f'mutable asset missing from service-worker handling: {asset}')
    require('networkFirstAfterCleanup(req, null, true)' in sw, 'mutable assets are not cleanup + no-store network-first')
    print('MONTHLY FRONTEND STATIC SMOKE OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

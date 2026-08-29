#!/usr/bin/env python3
"""Return 0 when a Git commit can safely skip a Netlify production deploy.

Netlify's ignore command treats exit 0 as "ignore this build" and non-zero as
"build it". Pure backend/audit changes are ignored. A PUA-only cleanup in the
auto essay payload is also ignored because the monthly build already normalizes
those glyphs and there is no student-visible semantic change.
"""
from __future__ import annotations

import json
import subprocess
import sys

STUDENT_EXACT = {
    'index.html', 'essay_guides.js', 'manifest.json', 'sw.js',
    'netlify.toml', 'scripts/monthly_patch_build.py', 'scripts/netlify_ignore.py',
    'scripts/cache_bust_runtime.py', 'scripts/first_paint_static_qa.py',
    'scripts/admin_auth_build.py',
    'auto/questions_auto.json', 'auto/essays_auto.json',
}


def git(*args: str) -> str:
    return subprocess.check_output(['git', *args], text=True, stderr=subprocess.DEVNULL)


def normalize_pua(value):
    if isinstance(value, str):
        return value.replace('\uE129','（一）').replace('\uE12A','（二）').replace('\uE12B','（三）')
    if isinstance(value, list):
        return [normalize_pua(x) for x in value]
    if isinstance(value, dict):
        return {k: normalize_pua(v) for k,v in value.items()}
    return value


def semantic_same_auto_essays(base: str, head: str) -> bool:
    path='auto/essays_auto.json'
    try:
        old=json.loads(git('show',f'{base}:{path}'))
        new=json.loads(git('show',f'{head}:{path}'))
    except Exception:
        return False
    return normalize_pua(old)==normalize_pua(new)


def main() -> int:
    if len(sys.argv) != 3:
        print('usage: netlify_ignore.py <cached-ref> <commit-ref>', file=sys.stderr)
        return 1
    base, head=sys.argv[1:]
    try:
        changed=[x.strip() for x in git('diff','--name-only',base,head).splitlines() if x.strip()]
    except Exception:
        return 1

    relevant=[]
    for path in changed:
        if (path in STUDENT_EXACT
                or path.startswith('icons/')
                or path.startswith('monthly_patch_parts/')
                or path.startswith('admin/')):
            relevant.append(path)
    if not relevant:
        print('Netlify ignore: no student-facing or deploy-pipeline files changed.')
        return 0

    if set(relevant)=={'auto/essays_auto.json'} and semantic_same_auto_essays(base,head):
        print('Netlify ignore: auto essay change is PUA-normalization only.')
        return 0

    print('Netlify build required:', ', '.join(relevant))
    return 1


if __name__=='__main__':
    raise SystemExit(main())
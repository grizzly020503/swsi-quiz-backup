#!/usr/bin/env python3
from pathlib import Path

replacements = {
    Path('scripts/p0_frontend_preflight.js'): (
        "if(!/if \\(isMutableStatic\\) \\{[\\s\\S]{0,180}networkFirst\\(req, null, true\\)/.test(sw)){",
        "if(!/if \\(isMutableStatic\\) \\{[\\s\\S]{0,220}networkFirstAfterCleanup\\(req, null, true\\)/.test(sw)){",
    ),
    Path('scripts/monthly_frontend_smoke.py'): (
        "require('networkFirst(req, null, true)' in sw, 'mutable assets are not no-store network-first')",
        "require('networkFirstAfterCleanup(req, null, true)' in sw, 'mutable assets are not cleanup + no-store network-first')",
    ),
}

for path, (old, new) in replacements.items():
    text = path.read_text(encoding='utf-8')
    if old in text:
        if text.count(old) != 1:
            raise SystemExit(f'{path}: expected one old matcher, found {text.count(old)}')
        text = text.replace(old, new, 1)
        path.write_text(text, encoding='utf-8')
        print(f'patched {path}')
    elif new in text:
        print(f'already patched {path}')
    else:
        raise SystemExit(f'{path}: expected matcher not found; refusing to guess')

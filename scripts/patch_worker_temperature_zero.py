#!/usr/bin/env python3
from pathlib import Path

PATH = Path('cloudflare/wandering-wave-4418/worker.js')
OLD = 'Math.max(Number(body.temperature) || 0.4, 0)'
NEW = 'Math.max(Number.isFinite(Number(body.temperature)) ? Number(body.temperature) : 0.4, 0)'

text = PATH.read_text(encoding='utf-8')
count = text.count(OLD)
if count == 0:
    if NEW in text:
        print('Worker temperature zero patch already applied.')
        raise SystemExit(0)
    raise SystemExit('Expected temperature expression not found; refusing to guess.')
if count != 1:
    raise SystemExit(f'Expected exactly one temperature expression, found {count}.')

text = text.replace(OLD, NEW, 1)
PATH.write_text(text, encoding='utf-8')
print('Patched worker temperature handling: explicit 0 is now preserved.')

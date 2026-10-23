#!/usr/bin/env python3
"""Offline guard for the existing preview workflow's publication boundary."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/cloudflare-frontend-preview.yml'
PUBLISH = 'Publish preview files into existing Cloudflare static assets'
WAIT = 'Wait for Cloudflare preview deployment'
GUARD = "github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' && inputs.publish_preview == true"


def step(source, name):
    anchor = '      - name: ' + name + '\n'
    assert source.count(anchor) == 1, 'missing or duplicate step: ' + name
    return source.split(anchor, 1)[1].split('\n      - name:', 1)[0]


def validate(source):
    dispatch = source.split('  workflow_dispatch:\n', 1)[1].split('\n  push:', 1)[0]
    assert re.search(r'(?m)^      publish_preview:$', dispatch), 'missing explicit publish choice'
    assert re.search(r'(?m)^        type: boolean$', dispatch), 'publish choice must be boolean'
    assert re.search(r'(?m)^        default: false$', dispatch), 'default must not publish'
    for name in (PUBLISH, WAIT):
        condition = re.search(r'(?m)^        if: (.+)$', step(source, name))
        assert condition and condition.group(1) == GUARD, 'unsafe publication gate: ' + name
    assert source.count('git push ') == step(source, PUBLISH).count('git push ') == 1, 'unexpected writer'
    build = step(source, 'Build current monthly frontend')
    assert '        if:' not in build, 'build QA must still run without publication'
    assert 'p0_frontend_preflight.js' in build and 'monthly_frontend_smoke.py' in build, 'build safety checks missing'


def main():
    source = WORKFLOW.read_text(encoding='utf-8')
    validate(source)
    # A green static guard must reject the unsafe automatic/default paths.
    for changed in (
        source.replace('default: false', 'default: true'),
        source.replace(GUARD, "github.ref == 'refs/heads/main'", 1),
        source.replace(GUARD, GUARD + ' || true', 1),
        source.replace(GUARD, "inputs.publish_preview == true", 1),
        source + '\n          git push origin HEAD:main\n',
    ):
        try:
            validate(changed)
        except (AssertionError, IndexError):
            continue
        raise AssertionError('unsafe preview workflow fixture was accepted')
    print('CLOUDFLARE PREVIEW PUBLISH POLICY OK: default build-only, manual main publish, 5 negative fixtures')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Offline source-backed official graphic integration guard. No network access."""
import hashlib, json, struct
from pathlib import Path
R=Path(__file__).resolve().parents[1]
j=json.loads((R/'data/official_figure_assets.v1.json').read_text())
assert j['schema_version']==1 and len(j['figures'])==2
assert j['official_core_modified'] is False and j['answer_grading_modified'] is False
assert j['release_approved'] is False
for row in j['figures']:
    raw=(R/row['path']).read_bytes()
    assert raw.startswith(b'\x89PNG\r\n\x1a\n'),row['id']+' missing PNG magic'
    assert hashlib.sha256(raw).hexdigest()==row['published_png_sha256'],row['id']+' hash mismatch'
    assert struct.unpack('>II',raw[16:24])==(row['width'],row['height']),row['id']+' dimensions mismatch'
    for tree in ('', 'cdn/'):
        twin=(R/tree/row['path']).read_bytes()
        assert twin==raw,row['id']+' root/CDN visual mismatch'
for html in ('index.html','cdn/index.html'):
    s=(R/html).read_text()
    for needle in ("function swsiOfficialFigureMarkup", "swsiOfficialFigureMarkup(item)",
                   "swsiOfficialFigureMarkup(q)", "swsiOfficialFigureReady(Q[idx])",
                   "var gradedTotal=Q.length-excluded", "swsiOfficialFigureQuestion(q)"):
        assert needle in s,html+' missing '+needle
    for row in j['figures']:
        assert s.count("'"+row['id']+"'")>=1,html+' missing '+row['id']
# The maintained runtime overrides the legacy HTML renderer. Guard that owner too.
runtime=(R/'monthly_patch_parts/00.part').read_text()
for needle in ("const figureReady=swsiOfficialFigureReady(item)",
               "swsiOfficialFigureMarkup(item)", "if(!figureReady)optHTML=",
               "if(!selected || !swsiOfficialFigureReady(queue[idx])) return;"):
    assert needle in runtime,'canonical runtime missing '+needle
for name in ('sw.js','cdn/sw.js'):
    sw=(R/name).read_text()
    for row in j['figures']:
        assert "./"+row['path'] in sw,name+' does not precache '+row['id']
# Owner froze the backup site: candidate must retain the exact main config.
assert hashlib.sha256((R/'netlify.toml').read_bytes()).hexdigest()=='3ae451ea75b48614db95e7438e675deb7a43354cb0324711150754cd805483a5','backup configuration must remain frozen'
# Primary Workers assets are the tracked CDN tree; no preview/deploy action.
assert '"directory": "./cdn"' in (R/'wrangler.jsonc').read_text()
# The CI local _site build must include assets used by the service worker's
# atomic cache.addAll; a missing file otherwise blocks SW installation.
launch=(R/'.github/workflows/launch-readiness-qa.yml').read_text()
assert 'mkdir -p _site/icons _site/official-figures' in launch
assert 'cp official-figures/*.png _site/official-figures/' in launch

print('OFFICIAL FIGURES UI QA OK: source-backed 2 image assets, root/CDN parity, grading guard, mock/quiz image gates and PWA pre-cache; human approval pending')

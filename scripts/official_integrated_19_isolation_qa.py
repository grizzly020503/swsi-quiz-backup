#!/usr/bin/env python3
"""Run exact PR #503 historical QA inside a reconstructed disposable snapshot.

This is only used after the current 19-row integration has independently
passed SHA-locked validation. It does not alter Git/working files, databases,
deployments or the frozen Netlify backup.
"""
from __future__ import annotations
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from official_combined_nineteen_integrity_smoke import reverse_overlay

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / 'audit/official_combined_nineteen_candidate_20261031.json'
TESTS = (
    'scripts/official_next_three_p0_source_smoke.py',
    'scripts/official_eight_p0_pdf_review_crosswalk_smoke.py',
    'scripts/official_428_review_priority_queue_smoke.py',
    'scripts/official_r105138_pdf_visual_nochange_smoke.py',
    'scripts/official_111_2_shared_context_six_smoke.py',
    'scripts/official_two_row_p0_candidate_smoke.py',
    'scripts/official_figure_ui_qa.py',
    'scripts/official_exam_readonly_guard.py',
)
def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def main():
    p = json.loads(PROOF.read_text())
    manifest_raw = (ROOT/'cdn/question-shards/manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    rows = [r for meta in manifest['shards']
            for r in json.loads((ROOT/'cdn/question-shards'/meta['file']).read_bytes())['questions']]
    lock = json.loads((ROOT/'data/official_exam_readonly.lock.json').read_text())
    parent_rows,parent_lock,parent_manifest = reverse_overlay(rows,lock,manifest_raw)
    assert len(parent_rows) == 4800 and len(parent_lock['essays']) == 240
    parent_by_id = {r['id']:r for r in parent_rows}
    new_ids = {x['id'] for x in p['changed_rows']}
    assert len(new_ids) == 8
    with tempfile.TemporaryDirectory(prefix='swsi-official-19-parent-') as directory:
        target = Path(directory)/'repository'
        shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns(
            '.git','node_modules','.venv','__pycache__','.pytest_cache'))
        for name,expected in p['old_shards'].items():
            shard_path = target/'cdn/question-shards'/name
            doc = json.loads(shard_path.read_bytes())
            edited = 0
            for row in doc['questions']:
                if row['id'] in new_ids:
                    row.clear()
                    row.update(parent_by_id[row['id']])
                    edited += 1
            assert edited > 0
            old_raw = (json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n').encode()
            assert digest(old_raw) == expected['sha256'] and len(old_raw) == expected['bytes']
            shard_path.write_bytes(old_raw)
        assert digest(parent_manifest) == p['parent_manifest_sha256']
        (target/'cdn/question-shards/manifest.json').write_bytes(parent_manifest)
        lock_raw = (json.dumps(parent_lock,ensure_ascii=False,indent=2)+'\n').encode()
        assert digest(lock_raw) == p['parent_lock_sha256']
        (target/'data/official_exam_readonly.lock.json').write_bytes(lock_raw)
        for name in TESTS:
            print('REPLAY EXACT PR503 QA:',name,flush=True)
            subprocess.run([sys.executable,str(target/name)],cwd=target,check=True)
    print('INTEGRATED 19-ROW ISOLATED HISTORICAL QA PASS: original 11-row gates all executed, no relaxed SHA/answer/essay checks, no production changes')
if __name__ == '__main__':
    main()

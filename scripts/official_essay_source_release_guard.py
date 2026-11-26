#!/usr/bin/env python3
"""Verify the 2026-11-24 official essay source release.

230 historical official essays gained source_exam_code/source_url taken from
the same subject paper as their session MCQs (each essay text checked against
that MOEX PDF by scripts/official_source_repair_pdf_verify.py). One essay
(社會工作-112-2-申論2) carried text that does not occur in its official paper
and is corrected to the paper's wording.

This guard proves the current embedded essays and lock equal the recorded
postimage, then rebuilds the exact predecessor (restoring the essay lock and
row) and replays the previous source-repair release guard and its whole chain.
"""
import argparse
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from official_exam_readonly_guard import ESSAY_FIELDS, canonical_row, row_hash

ROOT = Path(__file__).resolve().parents[1]
PROOF = 'audit/official_essay_source_release_20261124c.json'
ESSAYS_RE = re.compile(r"(window\.ESSAYS\s*=\s*)(\[.*?\])(;\s*\n\s*window\.CLUSTER_ANCHORS)", re.S)


def require(test, reason):
    if not test:
        raise SystemExit('ESSAY SOURCE RELEASE GUARD FAILED: ' + reason)


def embedded(path: Path) -> list:
    match = ESSAYS_RE.search(path.read_text(encoding='utf-8'))
    require(match is not None, 'window.ESSAYS missing in ' + str(path))
    return json.loads(match.group(2))


def build_predecessor(root: Path, target: Path) -> None:
    proof = json.loads((root / PROOF).read_text(encoding='utf-8'))
    require(proof['owner_approved'] is True, 'owner approval missing')
    fix = proof['essay_text_repair']
    lock = json.loads((root / 'data/official_exam_readonly.lock.json').read_text(encoding='utf-8'))
    require(lock['essays'][fix['id']] == fix['after_lock'], 'essay lock postimage drift')
    require(row_hash(canonical_row(fix['after'], ESSAY_FIELDS)) == fix['after_lock'], 'recorded postimage hash drift')
    require(row_hash(canonical_row(fix['before'], ESSAY_FIELDS)) == fix['before_lock'], 'recorded preimage hash drift')
    for page in ('index.html', 'cdn/index.html'):
        rows = {e['id']: e for e in embedded(root / page)}
        require(rows[fix['id']] == fix['after'], 'essay postimage drift in ' + page)
        for ident, meta in proof['source_metadata'].items():
            row = rows.get(ident)
            require(row is not None, 'essay missing ' + ident)
            require(row.get('source_exam_code') == meta['source_exam_code'] and row.get('source_url') == meta['source_url'],
                    'source metadata drift ' + ident + ' in ' + page)
            require(str(meta['source_url']).startswith('https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx?'),
                    'non-MOEX source ' + ident)
    shutil.copytree(root / 'cdn/question-shards', target / 'cdn/question-shards')
    lock['essays'][fix['id']] = fix['before_lock']
    (target / 'data').mkdir()
    (target / 'data/official_exam_readonly.lock.json').write_text(json.dumps(lock, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.symlink(root / 'audit', target / 'audit', target_is_directory=True)
    html = (root / 'cdn/index.html').read_text(encoding='utf-8')
    match = ESSAYS_RE.search(html)
    rows = json.loads(match.group(2))
    for row in rows:
        if row['id'] == fix['id']:
            row.clear()
            row.update(fix['before'])
        if row['id'] in proof['source_metadata']:
            row.pop('source_exam_code', None)
            row.pop('source_url', None)
    html = html[:match.start(2)] + json.dumps(rows, ensure_ascii=False, separators=(',', ':')) + html[match.end(2):]
    (target / 'cdn/index.html').write_text(html, encoding='utf-8')


def replay(root: Path, selftest: bool) -> None:
    import official_source_repair_release_b_guard as previous
    with tempfile.TemporaryDirectory(prefix='swsi-essay-source-predecessor-') as tmp:
        target = Path(tmp)
        (target / 'cdn').mkdir()
        build_predecessor(root, target)
        previous.replay(target, selftest)
        if selftest:
            saved = previous.ROOT
            try:
                previous.ROOT = target
                previous.negative_selftest()
            finally:
                previous.ROOT = saved


def negative_selftest() -> None:
    proof = json.loads((ROOT / PROOF).read_text(encoding='utf-8'))
    fix_id = proof['essay_text_repair']['id']
    some = sorted(proof['source_metadata'])[0]
    cases = [
        (fix_id, lambda e: e.update(q=e['q'] + '。')),
        (some, lambda e: e.update(source_url='https://example.com/x.pdf')),
        (some, lambda e: e.pop('source_exam_code', None)),
    ]
    rejected = 0
    with tempfile.TemporaryDirectory(prefix='swsi-essay-source-negative-') as tmp:
        for n, (ident, mutate) in enumerate(cases):
            work = Path(tmp) / str(n)
            (work / 'cdn').mkdir(parents=True)
            shutil.copytree(ROOT / 'cdn/question-shards', work / 'cdn/question-shards')
            (work / 'data').mkdir()
            shutil.copy(ROOT / 'data/official_exam_readonly.lock.json', work / 'data')
            os.symlink(ROOT / 'audit', work / 'audit', target_is_directory=True)
            for page in ('index.html', 'cdn/index.html'):
                html = (ROOT / page).read_text(encoding='utf-8')
                match = ESSAYS_RE.search(html)
                rows = json.loads(match.group(2))
                for row in rows:
                    if row['id'] == ident:
                        mutate(row)
                html = html[:match.start(2)] + json.dumps(rows, ensure_ascii=False, separators=(',', ':')) + html[match.end(2):]
                (work / page).write_text(html, encoding='utf-8')
            try:
                with tempfile.TemporaryDirectory() as out:
                    (Path(out) / 'cdn').mkdir()
                    build_predecessor(work, Path(out))
            except SystemExit:
                rejected += 1
                continue
            raise AssertionError('tamper accepted: case ' + str(n))
    print(f'ESSAY SOURCE NEGATIVES PASS: {rejected} unauthorized changes rejected')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    # A later owner-approved release moved the current corpus; the newest
    # guard rebuilds this release's exact successor state and replays it.
    from legal_status_batch35_release_guard import replay as replay_newest
    replay_newest(ROOT, args.selftest)
    print('ESSAY SOURCE RELEASE PASS: 230 essay sources from PDF-verified subject papers; 1 essay text matched to its '
          'official paper; MCQ locks unchanged; exact predecessor and full earlier release chain replayed')

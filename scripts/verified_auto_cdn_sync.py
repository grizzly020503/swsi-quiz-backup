#!/usr/bin/env python3
"""Stage verified canonical auto MCQ into Cloudflare's tracked CDN mirror.

Run ONLY after the existing MOEX ingestion + Supabase shard validation.  The
source must match every non-baseline incoming record, AND the independently
generated Supabase shard must agree on all Official Core/grading fields.
This tool neither changes official data nor approves essay enrichment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
BASELINE_EXAMS = {'115030'}
OFFICIAL_FIELDS = (
    'id', 'subject', 'year', 'round', 'qno', 'question',
    'opt_a', 'opt_b', 'opt_c', 'opt_d', 'answer',
    'accepted_answers', 'grading_mode', 'source_exam_code', 'source_url',
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def by_id(rows, label: str):
    if not isinstance(rows, list) or not rows:
        raise ValueError(f'{label}: missing/non-array data')
    result = {}
    for row in rows:
        ident = row.get('id') if isinstance(row, dict) else None
        if not isinstance(ident, str) or not ident.strip() or ident in result:
            raise ValueError(f'{label}: missing/duplicate official ID {ident!r}')
        result[ident] = row
    return result


def verified_rows(incoming_dir: Path, auto_path: Path, shards_dir: Path) -> int:
    expected = {}
    seen_exams = set()
    paths = sorted(incoming_dir.glob('[0-9][0-9][0-9][0-9][0-9][0-9].json'))
    if not paths:
        raise ValueError('no MOEX incoming files')
    for path in paths:
        payload = load_json(path)
        code = str(payload.get('exam_code') or '')
        if not code or code != path.stem or code in seen_exams:
            raise ValueError(f'{path}: exam code invalid/duplicate')
        seen_exams.add(code)
        if code in BASELINE_EXAMS:
            continue
        items = by_id(payload.get('questions'), str(path))
        # Reconfirm one complete new exam; do not silently export partial PDFs.
        if len(items) != 200:
            raise ValueError(f'{path}: expected 200 questions, got {len(items)}')
        for ident, row in items.items():
            if ident in expected or str(row.get('source_exam_code')) != code:
                raise ValueError(f'{path}: duplicate/source mismatch {ident}')
            expected[ident] = row

    canonical = by_id(load_json(auto_path), str(auto_path))
    if expected.keys() != canonical.keys():
        raise ValueError(
            f'auto/incoming ID drift: missing={sorted(expected.keys()-canonical.keys())[:5]} '
            f'extra={sorted(canonical.keys()-expected.keys())[:5]}'
        )
    for ident, source in expected.items():
        if canonical[ident] != source:
            raise ValueError(f'auto/incoming official payload mismatch: {ident}')

    shard_rows = {}
    for path in sorted(shards_dir.glob('[0-9][0-9][0-9]-[12].json')):
        payload = load_json(path)
        records = payload.get('questions') if isinstance(payload, dict) else None
        if not isinstance(records, list) or len(records) != 200:
            raise ValueError(f'{path}: incomplete published shard')
        for ident, record in by_id(records, str(path)).items():
            if ident in canonical:
                if ident in shard_rows:
                    raise ValueError(f'duplicate shard question {ident}')
                shard_rows[ident] = record

    if canonical.keys() != shard_rows.keys():
        raise ValueError(
            f'auto/Supabase-shard ID drift: missing={sorted(canonical.keys()-shard_rows.keys())[:5]} '
            f'extra={sorted(shard_rows.keys()-canonical.keys())[:5]}'
        )
    for ident in sorted(canonical):
        source, shard = canonical[ident], shard_rows[ident]
        for field in OFFICIAL_FIELDS:
            # The Supabase shard explicitly serializes null for some legacy
            # absent optional fields; absent and null are equivalent here.
            # In particular B/D accepted-answer lists must compare exactly.
            if source.get(field) != shard.get(field):
                raise ValueError(f'{ident}.{field}: MOEX canonical and published shard disagree')
    return len(canonical)


def stage_verified(incoming_dir: Path, auto_path: Path, shards_dir: Path, target: Path):
    count = verified_rows(incoming_dir, auto_path, shards_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    canonical_bytes = auto_path.read_bytes()
    # Preserve the verified source bytes exactly: no row rewriting, no grading
    # heuristics, no essay status change. A git commit is a separate action.
    if not target.is_file() or target.read_bytes() != canonical_bytes:
        target.write_bytes(canonical_bytes)
        print(f'AUTO/CDN MCQ MIRROR STAGED: {count} verified rows')
    else:
        print(f'AUTO/CDN MCQ MIRROR UNCHANGED: {count} verified rows')


def selftest():
    with TemporaryDirectory(prefix='swsi-auto-cdn-') as tmp:
        top = Path(tmp)
        inc, shards = top / 'incoming', top / 'shards'
        inc.mkdir()
        shards.mkdir()
        source = []
        for i in range(200):
            source.append({
                'id': f'DS-115-2-{i+1:03d}',
                'subject': '社會工作直接服務', 'year': '115',
                'round': '第二次', 'qno': str(i+1),
                'question': '合成測試題，不屬於官方題庫',
                'opt_a': 'a', 'opt_b': 'b', 'opt_c': 'c', 'opt_d': 'd',
                'answer': 'B', 'grading_mode': 'standard',
                'source_exam_code': '115100',
                'source_url': 'https://wwwq.moex.gov.tw/synthetic',
            })
        source[39]['accepted_answers'] = ['B', 'D']
        incoming_file = inc / '115100.json'
        auto_file = top / 'auto.json'
        shard_file = shards / '115-2.json'
        cdn_file = top / 'cdn' / 'auto' / 'questions_auto.json'

        def put(path, data):
            path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

        put(incoming_file, {'exam_code': '115100', 'questions': source})
        put(auto_file, source)
        put(shard_file, {'questions': source})
        assert verified_rows(inc, auto_file, shards) == 200
        stage_verified(inc, auto_file, shards, cdn_file)
        assert cdn_file.read_bytes() == auto_file.read_bytes()

        def rejects():
            try:
                verified_rows(inc, auto_file, shards)
            except ValueError:
                return
            raise AssertionError('unverified exam/grading drift was incorrectly accepted')

        altered = [dict(x) for x in source]
        altered[39].pop('accepted_answers')
        put(shard_file, {'questions': altered})
        rejects()  # B/D correction lost in Supabase shard
        put(shard_file, {'questions': source})
        altered = [dict(x) for x in source]
        altered[39]['accepted_answers'] = ['B']
        put(auto_file, altered)
        rejects()  # canonical root changed without MOEX source
        put(auto_file, source)
        put(shard_file, {'questions': source[:-1]})
        rejects()  # partial shard
        put(shard_file, {'questions': source})
        put(auto_file, source[:-1])
        rejects()  # partial root
        put(auto_file, source)
        assert verified_rows(inc, auto_file, shards) == 200
        print('VERIFIED AUTO CDN MCQ SELFTEST OK: valid B/D + 4 synthetic fail-closed cases')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--incoming', type=Path, default=ROOT / 'incoming')
    ap.add_argument('--auto', type=Path, default=ROOT / 'auto/questions_auto.json')
    ap.add_argument('--shards', type=Path, default=ROOT / 'cdn/question-shards')
    ap.add_argument('--target', type=Path, default=ROOT / 'cdn/auto/questions_auto.json')
    ap.add_argument('--stage', action='store_true',
                    help='Write verified source to tracked CDN mirror; does NOT git commit or deploy')
    ap.add_argument('--selftest', action='store_true')
    opts = ap.parse_args()
    if opts.selftest:
        selftest()
        return 0
    if opts.stage:
        stage_verified(opts.incoming, opts.auto, opts.shards, opts.target)
    else:
        count = verified_rows(opts.incoming, opts.auto, opts.shards)
        print(f'VERIFIED AUTO MCQ SOURCE OK: {count} IDs; CDN mirror not modified')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

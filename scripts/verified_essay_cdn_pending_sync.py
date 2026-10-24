#!/usr/bin/env python3
"""Publish only verified NEW MOEX essays to CDN, with analysis_status=pending.

Never promotes existing CDN enrichment. Default is read-only. An existing
approved exam scheme and the upstream MOEX/shard validation are prerequisites.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit, parse_qs

BASELINE_EXAMS = {'115030'}
OFFICIAL = ('id', 'subject', 'year', 'round', 'qno', 'q', 'points',
            'source_exam_code', 'source_url')
LIST_META = ('keywords', 'theories', 'laws', 'related')
TEXT_META = ('topic', 'major', 'difficulty', 'frequency', 'qtype', 'cluster', 'cluster_name')
KNOWN_SOURCE_FIELDS = set(OFFICIAL) | set(LIST_META) | set(TEXT_META) | {'analysis_status'}
ALLOWED_STATES = {'pending', 'ready', 'reviewed', 'verified'}
ROUNDS = {'第一次': 1, '第二次': 2}


def indexed(rows: object, label: str) -> dict[str, dict]:
    if not isinstance(rows, list) or not rows:
        raise ValueError(f'{label}: expected non-empty JSON list')
    result: dict[str, dict] = {}
    for row in rows:
        ident = row.get('id') if isinstance(row, dict) else None
        if not isinstance(ident, str) or not ident.strip() or ident in result:
            raise ValueError(f'{label}: invalid or duplicate id: {ident!r}')
        result[ident] = row
    return result


def official_equal(a: dict, b: dict, ident: str) -> None:
    for key in OFFICIAL:
        if (key in a) != (key in b) or a.get(key) != b.get(key):
            raise ValueError(f'{ident}.{key}: official source changed or missing')


def approved_shape(payload: dict, registry: dict) -> dict:
    """Independent approved exam scheme structural gate; fail closed on changes."""
    if not isinstance(payload, dict) or not isinstance(registry, dict) or registry.get('schema_version') != 1:
        raise ValueError('official payload/approved registry has invalid shape')
    if payload.get('exam_type') != registry.get('exam_type'):
        raise ValueError('exam_type not equal to approved registry')
    year = str(payload.get('roc_year') or '')
    round_name = str(payload.get('round') or '')
    code = str(payload.get('exam_code') or '')
    if not year.isdecimal() or round_name not in ROUNDS:
        raise ValueError('invalid exam year or session round')
    session = (int(year), ROUNDS[round_name])
    matches = []
    for row in registry.get('profiles') or []:
        if not isinstance(row, dict) or row.get('status') != 'approved':
            continue
        start = row.get('effective_from') or {}
        end = row.get('effective_to')
        try:
            start_session = (int(start['roc_year']), ROUNDS[str(start['round'])])
            end_session = (int(end['roc_year']), ROUNDS[str(end['round'])]) if end is not None else None
        except (ValueError, TypeError, KeyError):
            raise ValueError('approved registry contains invalid effective window')
        if start_session <= session and (end_session is None or session <= end_session):
            matches.append((start_session, row))
    if not matches:
        raise ValueError('future exam structure not approved for this session')
    profile = max(matches, key=lambda x: x[0])[1]
    suffix = str((profile.get('exam_code_suffixes') or {}).get(round_name) or '')
    if len(code) != 6 or code != f'{year}{suffix}':
        raise ValueError('official exam code does not match approved session/round')
    subjects = [str(x.get('name') or '') for x in profile.get('subjects') or []]
    if len(subjects) != len(set(subjects)) or not subjects or any(not s for s in subjects):
        raise ValueError('invalid approved subject set')
    for key, configuration in [('questions', profile.get('mcq') or {}), ('essays', profile.get('essay') or {})]:
        rows = payload.get(key)
        expected_total = int(configuration['expected_total'])
        expected_each = int(configuration['per_subject'])
        first = int(configuration['qno_min'])
        last = int(configuration['qno_max'])
        if not isinstance(rows, list) or len(rows) != expected_total:
            raise ValueError(f'{key}: source does not match approved total {expected_total}')
        actual = defaultdict(list)
        for item in rows:
            if not isinstance(item, dict) or str(item.get('year') or '') != year or item.get('round') != round_name:
                raise ValueError(f'{key}: source session metadata mismatch')
            if str(item.get('source_exam_code') or '') != code:
                raise ValueError(f'{key}: source exam code mismatch')
            n = str(item.get('qno') or '')
            if not n.isdecimal():
                raise ValueError(f'{key}: invalid question number')
            actual[str(item.get('subject') or '')].append(int(n))
        if set(actual) != set(subjects):
            raise ValueError(f'{key}: subject set differs from approved profile')
        for subject in subjects:
            numbers = actual[subject]
            if len(numbers) != expected_each or sorted(numbers) != list(range(first, last + 1)):
                raise ValueError(f'{key}/{subject}: number distribution not approved')
    return profile


def verified_moex_url(text: str, exam_code: str, subject_code: str) -> bool:
    """Do not confuse another exam or answer PDF with this official question PDF."""
    try:
        parsed = urlsplit(text)
        query = parse_qs(parsed.query, keep_blank_values=True)
        return (
            parsed.scheme == 'https'
            and parsed.hostname == 'wwwq.moex.gov.tw'
            and parsed.username is None and parsed.password is None
            and parsed.port in (None, 443)
            and parsed.path == '/exam/wHandExamQandA_File.ashx'
            and not parsed.fragment
            and set(query) == {'c', 'code', 'q', 's', 't'}
            and query.get('c') == ['103']
            and query.get('code') == [exam_code]
            and query.get('s') == [subject_code]
            and query.get('t') == ['Q']
            and query.get('q') == ['1']
        )
    except ValueError:
        return False


def collect_official(incoming_dir: Path, registry_path: Path) -> dict[str, dict]:
    official: dict[str, dict] = {}
    registry = json.loads(registry_path.read_text(encoding='utf-8'))
    paths = sorted(p for p in incoming_dir.glob('*.json') if re.fullmatch(r'\d{6}\.json', p.name))
    if not paths:
        raise ValueError('No approved incoming exam files')
    for path in paths:
        exam = json.loads(path.read_text(encoding='utf-8'))
        code = exam.get('exam_code') if isinstance(exam, dict) else None
        if code != path.stem:
            raise ValueError(f'{path.name}: official exam code mismatch')
        if code in BASELINE_EXAMS:
            continue
        profile = approved_shape(exam, registry)
        subject_profiles = {
            str(row['name']): (str(row['prefix']), str(row['code']))
            for row in profile['subjects']
        }
        new = indexed(exam.get('essays'), str(path))
        if len(new) != int(profile['essay']['expected_total']):
            raise ValueError(f'{path.name}: approved essay total mismatch')
        for ident, row in new.items():
            if ident in official or row.get('source_exam_code') != code:
                raise ValueError(f'{ident}: duplicate ID or wrong exam source')
            unknown = set(row) - KNOWN_SOURCE_FIELDS
            if unknown:
                raise ValueError(f'{ident}: unknown incoming fields (privacy review required): {sorted(unknown)}')
            prefix, subject_code = subject_profiles[row['subject']]
            expected_id = f'E-{exam["roc_year"]}-{ROUNDS[exam["round"]]}-{prefix}-{int(row["qno"])}'
            if ident != expected_id:
                raise ValueError(f'{ident}: official essay ID disagrees with source (expected {expected_id})')
            if not verified_moex_url(str(row.get('source_url') or ''), code, subject_code):
                raise ValueError(f'{ident}: official MOEX exam/subject/question provenance missing')
            for k in OFFICIAL:
                if row.get(k) in (None, ''):
                    raise ValueError(f'{ident}.{k}: missing official field')
            if not isinstance(row.get('q'), str) or not row['q'].strip():
                raise ValueError(f'{ident}: official essay prompt is empty')
            try:
                points = int(row['points'])
            except (ValueError, TypeError):
                raise ValueError(f'{ident}: points not integer')
            if not 1 <= points <= 50:
                raise ValueError(f'{ident}: points outside range; human review required')
            official[ident] = row
    if not official:
        raise ValueError('No additional approved incoming essays')
    return official


def staged_rows(incoming: dict[str, dict], canonical_rows: list, cdn_rows: list) -> tuple[list[dict], int]:
    canonical = indexed(canonical_rows, 'auto/essays_auto.json')
    cdn = indexed(cdn_rows, 'cdn/auto/essays_auto.json')
    if set(canonical) != set(incoming):
        raise ValueError('canonical auto and incoming essay IDs differ: '
                         f'missing={sorted(set(incoming)-set(canonical))[:5]} '
                         f'extra={sorted(set(canonical)-set(incoming))[:5]}')
    if set(cdn) - set(canonical):
        raise ValueError(f'CDN contains unrecognized essays: {sorted(set(cdn)-set(canonical))[:5]}')
    for ident, official in incoming.items():
        official_equal(official, canonical[ident], ident)
    for ident, published in cdn.items():
        official_equal(incoming[ident], published, ident)
        if published.get('analysis_status') not in ALLOWED_STATES:
            raise ValueError(f'{ident}: invalid existing CDN analysis status')

    output = []
    additions = 0
    for canonical_row in canonical_rows:
        ident = canonical_row['id']
        if ident in cdn:
            output.append(cdn[ident])  # preserve reviews, enrichment, and status exactly
        else:
            row = {key: incoming[ident][key] for key in OFFICIAL}
            row.update({key: [] for key in LIST_META})
            row.update({key: None for key in TEXT_META})
            row['analysis_status'] = 'pending'  # never borrow root's "ready"
            output.append(row)
            additions += 1
    return output, additions


def write_atomically(target: Path, rows: list[dict]) -> None:
    if not target.is_file() or target.is_symlink():
        raise ValueError('CDN target must be an existing regular non-symlink file')
    original_mode = target.stat().st_mode & 0o777
    content = json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=target.parent, prefix='.swsi-essay-', delete=False) as stream:
            tmp_name = stream.name
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp_name, original_mode)
        os.replace(tmp_name, target)
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--incoming', type=Path, required=True)
    ap.add_argument('--auto', type=Path, required=True)
    ap.add_argument('--cdn', type=Path, required=True)
    ap.add_argument('--registry', type=Path, required=True)
    ap.add_argument('--stage', action='store_true', help='Stage verified local file only; never commits or deploys')
    args = ap.parse_args()
    incoming = collect_official(args.incoming, args.registry)
    canonical = json.loads(args.auto.read_text(encoding='utf-8'))
    if not args.cdn.is_file():
        raise SystemExit('CDN auto essay snapshot missing; refusing automatic bootstrap')
    cdn = json.loads(args.cdn.read_text(encoding='utf-8'))
    result, additions = staged_rows(incoming, canonical, cdn)
    print(f'ESSAY CDN PENDING SYNC VERIFIED: incoming={len(incoming)} published={len(cdn)} new_pending={additions}')
    if args.stage and additions:
        write_atomically(args.cdn, result)
        print(f'STAGED LOCALLY {additions} unreviewed official essay rows (NO cloud writes)')


if __name__ == '__main__':
    main()

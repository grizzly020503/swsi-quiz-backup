#!/usr/bin/env python3
import json
from pathlib import Path

from exam_scheme import ExamSchemeError, load_registry, require_approved_payload

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / 'incoming'
AUTO = ROOT / 'auto'
ESSAY_ENRICHMENT = ROOT / 'data' / 'essay_enrichment.json'
AUTO.mkdir(exist_ok=True)

# 115030 已完整存在既有 Supabase 4600 題母庫，不能重複載入。
BASELINE_EXAMS = {'115030'}

# Only SWSI-authored teaching metadata may be overlaid. Official MOEX facts/text
# remain owned by incoming payloads and are separately protected by the readonly
# guard. Unknown keys fail closed instead of silently modifying official data.
ESSAY_ENRICHMENT_FIELDS = {
    'topic', 'major', 'keywords', 'theories', 'laws', 'difficulty', 'frequency',
    'qtype', 'related', 'cluster', 'cluster_name', 'analysis_status',
}
ESSAY_LIST_FIELDS = {'keywords', 'theories', 'laws', 'related'}
ESSAY_TEXT_FIELDS = ESSAY_ENRICHMENT_FIELDS - ESSAY_LIST_FIELDS
DIFFICULTIES = {'基礎', '中等', '困難'}
FREQUENCIES = {'低頻', '中頻', '高頻'}
ANALYSIS_STATES = {'pending', 'ready', 'reviewed', 'verified'}


def load_essay_enrichment():
    if not ESSAY_ENRICHMENT.exists():
        return {}
    payload = json.loads(ESSAY_ENRICHMENT.read_text(encoding='utf-8'))
    if not isinstance(payload, dict) or payload.get('schema_version') != 1:
        raise SystemExit(f'{ESSAY_ENRICHMENT}: expected schema_version=1 object')
    records = payload.get('records')
    if not isinstance(records, list):
        raise SystemExit(f'{ESSAY_ENRICHMENT}: records must be a list')

    overlays = {}
    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            raise SystemExit(f'{ESSAY_ENRICHMENT}: record {index} is not an object')
        ident = str(raw.get('id') or '').strip()
        if not ident:
            raise SystemExit(f'{ESSAY_ENRICHMENT}: record {index} missing id')
        if ident in overlays:
            raise SystemExit(f'{ESSAY_ENRICHMENT}: duplicate essay id {ident}')
        unknown = set(raw) - {'id'} - ESSAY_ENRICHMENT_FIELDS
        if unknown:
            raise SystemExit(
                f'{ESSAY_ENRICHMENT}: {ident} contains non-enrichment fields: {sorted(unknown)}'
            )

        clean = {}
        for field in ESSAY_LIST_FIELDS:
            value = raw.get(field, [])
            if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
                raise SystemExit(f'{ESSAY_ENRICHMENT}: {ident}.{field} must be a list of non-empty strings')
            clean[field] = list(dict.fromkeys(x.strip() for x in value))
        for field in ESSAY_TEXT_FIELDS:
            value = raw.get(field)
            if not isinstance(value, str) or not value.strip():
                raise SystemExit(f'{ESSAY_ENRICHMENT}: {ident}.{field} must be a non-empty string')
            clean[field] = value.strip()

        if clean['difficulty'] not in DIFFICULTIES:
            raise SystemExit(f'{ESSAY_ENRICHMENT}: {ident}.difficulty invalid: {clean["difficulty"]}')
        if clean['frequency'] not in FREQUENCIES:
            raise SystemExit(f'{ESSAY_ENRICHMENT}: {ident}.frequency invalid: {clean["frequency"]}')
        if clean['analysis_status'] not in ANALYSIS_STATES:
            raise SystemExit(f'{ESSAY_ENRICHMENT}: {ident}.analysis_status invalid: {clean["analysis_status"]}')
        overlays[ident] = clean
    return overlays


def main():
    questions = {}
    essays = {}
    exams = []
    overlays = load_essay_enrichment()
    applied = set()
    registry = load_registry()

    for path in sorted(INCOMING.glob('[0-9][0-9][0-9][0-9][0-9][0-9].json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        code = str(data.get('exam_code') or path.stem)

        # This is the authoritative structural intake gate. A future session that
        # matches the latest approved profile proceeds without a code change. A
        # different subject/question/essay structure is an unapproved candidate
        # and must stop here before backup payloads or Supabase import are built.
        try:
            scheme = require_approved_payload(data, registry, path.as_posix())
        except ExamSchemeError as exc:
            raise SystemExit(str(exc)) from exc

        if code in BASELINE_EXAMS:
            continue
        qs = data.get('questions') or []
        es = data.get('essays') or []
        for q in qs:
            if q.get('id'):
                questions[str(q['id'])] = q
        for source in es:
            ident = str(source.get('id') or '')
            if not ident:
                continue
            row = dict(source)
            if ident in overlays:
                row.update(overlays[ident])
                applied.add(ident)
            essays[ident] = row
        exams.append({
            'exam_code': code,
            'roc_year': data.get('roc_year'),
            'round': data.get('round'),
            'source_page': data.get('source_page'),
            'mc_count': len(qs),
            'essay_count': len(es),
            'exam_scheme_id': scheme['profile_id'],
            'stats': data.get('stats') or {},
        })

    orphaned = sorted(set(overlays) - applied)
    if orphaned:
        raise SystemExit(
            f'{ESSAY_ENRICHMENT}: overlay IDs not found in owned incoming essays: {orphaned}'
        )

    qrows = sorted(questions.values(), key=lambda x: (str(x.get('year','')), str(x.get('round','')), str(x.get('subject','')), int(x.get('qno') or 0)))
    erows = sorted(essays.values(), key=lambda x: (str(x.get('year','')), str(x.get('round','')), str(x.get('subject','')), int(x.get('qno') or 0)))

    (AUTO / 'questions_auto.json').write_text(json.dumps(qrows, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    (AUTO / 'essays_auto.json').write_text(json.dumps(erows, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    (AUTO / 'sync_state.json').write_text(json.dumps({
        'baseline_exams': sorted(BASELINE_EXAMS),
        'exam_scheme_registry': 'data/exam_scheme_registry.v1.json',
        'included_exams': exams,
        'mc_count': len(qrows),
        'essay_count': len(erows),
        'essay_enrichment_count': len(applied),
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    print(
        f'auto payload: {len(qrows)} MC + {len(erows)} essays from {len(exams)} exams; '
        f'essay enrichment={len(applied)}; schemes={sorted({x["exam_scheme_id"] for x in exams})}'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

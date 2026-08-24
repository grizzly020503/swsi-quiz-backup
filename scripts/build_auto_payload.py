#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / 'incoming'
AUTO = ROOT / 'auto'
AUTO.mkdir(exist_ok=True)

# 115030 已完整存在既有 Supabase 4600 題母庫，不能重複載入。
BASELINE_EXAMS = {'115030'}

questions = {}
essays = {}
exams = []

for path in sorted(INCOMING.glob('[0-9][0-9][0-9][0-9][0-9][0-9].json')):
    data = json.loads(path.read_text(encoding='utf-8'))
    code = str(data.get('exam_code') or path.stem)
    if code in BASELINE_EXAMS:
        continue
    qs = data.get('questions') or []
    es = data.get('essays') or []
    if len(qs) != 200 or len(es) != 10:
        raise SystemExit(f'{path}: refusing incomplete payload MC={len(qs)} Essay={len(es)}')
    for q in qs:
        if q.get('id'):
            questions[str(q['id'])] = q
    for e in es:
        if e.get('id'):
            essays[str(e['id'])] = e
    exams.append({
        'exam_code': code,
        'roc_year': data.get('roc_year'),
        'round': data.get('round'),
        'source_page': data.get('source_page'),
        'mc_count': len(qs),
        'essay_count': len(es),
        'stats': data.get('stats') or {},
    })

qrows = sorted(questions.values(), key=lambda x: (str(x.get('year','')), str(x.get('round','')), str(x.get('subject','')), int(x.get('qno') or 0)))
erows = sorted(essays.values(), key=lambda x: (str(x.get('year','')), str(x.get('round','')), str(x.get('subject','')), int(x.get('qno') or 0)))

(AUTO / 'questions_auto.json').write_text(json.dumps(qrows, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
(AUTO / 'essays_auto.json').write_text(json.dumps(erows, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
(AUTO / 'sync_state.json').write_text(json.dumps({
    'baseline_exams': sorted(BASELINE_EXAMS),
    'included_exams': exams,
    'mc_count': len(qrows),
    'essay_count': len(erows),
}, ensure_ascii=False, indent=2), encoding='utf-8')

print(f'auto payload: {len(qrows)} MC + {len(erows)} essays from {len(exams)} exams')

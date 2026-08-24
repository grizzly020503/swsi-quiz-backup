#!/usr/bin/env python3
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / 'incoming'
AUTO = ROOT / 'auto'
INDEX = ROOT / 'index.html'

EXAM_TYPE = '專門職業及技術人員高等考試社會工作師'
SUBJECTS = {
    '社會工作',
    '社會工作直接服務',
    '社會政策與社會立法',
    '人類行為與社會環境',
    '社會工作研究方法',
}
VALID_ANSWERS = {'A', 'B', 'C', 'D', '一律給分'}
BASELINE_EXAMS = {'115030'}
BASELINE_QUESTION_COUNT = 4600


def die(message):
    raise SystemExit(f'HEALTH CHECK FAILED: {message}')


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        die(f'{path}: JSON 無法讀取：{exc}')


def qno_int(row):
    try:
        return int(str(row.get('qno') or '').strip())
    except Exception:
        return None


def validate_exam(path):
    data = read_json(path)
    code = str(data.get('exam_code') or '')
    if not re.fullmatch(r'\d{3}(030|100)', code):
        die(f'{path}: exam_code 異常：{code}')
    if data.get('exam_type') != EXAM_TYPE:
        die(f'{path}: exam_type 不符')

    questions = data.get('questions') or []
    essays = data.get('essays') or []
    if len(questions) != 200:
        die(f'{path}: 選擇題應為 200 題，實際 {len(questions)}')
    if len(essays) != 10:
        die(f'{path}: 申論題應為 10 題，實際 {len(essays)}')

    q_ids = [str(q.get('id') or '') for q in questions]
    e_ids = [str(e.get('id') or '') for e in essays]
    if any(not x for x in q_ids) or len(set(q_ids)) != 200:
        die(f'{path}: 選擇題 ID 空白或重複')
    if any(not x for x in e_ids) or len(set(e_ids)) != 10:
        die(f'{path}: 申論題 ID 空白或重複')

    q_subjects = {q.get('subject') for q in questions}
    e_subjects = {e.get('subject') for e in essays}
    if q_subjects != SUBJECTS:
        die(f'{path}: 選擇題科目集合異常：{sorted(str(x) for x in q_subjects)}')
    if e_subjects != SUBJECTS:
        die(f'{path}: 申論題科目集合異常：{sorted(str(x) for x in e_subjects)}')

    for q in questions:
        qid = q.get('id')
        if q.get('source_exam_code') != code:
            die(f'{path}: {qid} source_exam_code 不一致')
        if q.get('answer') not in VALID_ANSWERS:
            die(f'{path}: {qid} 答案異常：{q.get("answer")}')
        for key in ('subject', 'year', 'round', 'qno', 'question', 'opt_a', 'opt_b', 'opt_c', 'opt_d', 'source_url'):
            if not str(q.get(key) or '').strip():
                die(f'{path}: {qid} 缺 {key}')
        n = qno_int(q)
        if n is None or not 1 <= n <= 40:
            die(f'{path}: {qid} 題號異常：{q.get("qno")}')

    for e in essays:
        eid = e.get('id')
        if e.get('source_exam_code') != code:
            die(f'{path}: {eid} source_exam_code 不一致')
        for key in ('subject', 'year', 'round', 'qno', 'q', 'source_url'):
            if not str(e.get(key) or '').strip():
                die(f'{path}: {eid} 缺 {key}')
        n = qno_int(e)
        if n not in (1, 2):
            die(f'{path}: {eid} 申論題號異常：{e.get("qno")}')

    for subject in sorted(SUBJECTS):
        sq = [q for q in questions if q.get('subject') == subject]
        se = [e for e in essays if e.get('subject') == subject]
        if len(sq) != 40:
            die(f'{path}: {subject} 應有 40 題選擇題，實際 {len(sq)}')
        if len(se) != 2:
            die(f'{path}: {subject} 應有 2 題申論，實際 {len(se)}')
        if {qno_int(q) for q in sq} != set(range(1, 41)):
            die(f'{path}: {subject} 選擇題題號不是完整 1–40')
        if {qno_int(e) for e in se} != {1, 2}:
            die(f'{path}: {subject} 申論題題號不是 1、2')

    stats = data.get('stats') or {}
    for subject in SUBJECTS:
        s = stats.get(subject) or {}
        if s.get('mc') != 40 or s.get('essay') != 2:
            die(f'{path}: stats 的 {subject} 不是 40+2')

    return data


def incoming_payloads():
    files = sorted(INCOMING.glob('[0-9][0-9][0-9][0-9][0-9][0-9].json'))
    if not files:
        die('incoming/ 找不到任何考試 JSON')
    out = []
    seen_codes = set()
    for path in files:
        data = validate_exam(path)
        code = data['exam_code']
        if code in seen_codes:
            die(f'incoming/ 出現重複考試代碼：{code}')
        seen_codes.add(code)
        out.append((path, data))
    return out


def local_check(write_report=True):
    payloads = incoming_payloads()
    expected_q = {}
    expected_e = {}
    included_codes = []

    for _path, data in payloads:
        code = data['exam_code']
        if code in BASELINE_EXAMS:
            continue
        included_codes.append(code)
        for q in data['questions']:
            expected_q[q['id']] = q
        for e in data['essays']:
            expected_e[e['id']] = e

    qpath = AUTO / 'questions_auto.json'
    epath = AUTO / 'essays_auto.json'
    spath = AUTO / 'sync_state.json'
    if not qpath.exists() or not epath.exists() or not spath.exists():
        die('auto/ 備援檔不完整，請先執行 build_auto_payload.py')

    actual_q_rows = read_json(qpath)
    actual_e_rows = read_json(epath)
    state = read_json(spath)
    if not isinstance(actual_q_rows, list) or not isinstance(actual_e_rows, list):
        die('auto 題庫不是 JSON 陣列')

    actual_q = {str(x.get('id') or ''): x for x in actual_q_rows}
    actual_e = {str(x.get('id') or ''): x for x in actual_e_rows}
    if '' in actual_q or len(actual_q) != len(actual_q_rows):
        die('auto/questions_auto.json 有空白或重複 ID')
    if '' in actual_e or len(actual_e) != len(actual_e_rows):
        die('auto/essays_auto.json 有空白或重複 ID')

    if actual_q != expected_q:
        missing = sorted(set(expected_q) - set(actual_q))[:5]
        extra = sorted(set(actual_q) - set(expected_q))[:5]
        changed = sorted(k for k in set(expected_q) & set(actual_q) if expected_q[k] != actual_q[k])[:5]
        die(f'選擇題備援檔與 incoming 不一致 missing={missing} extra={extra} changed={changed}')
    if actual_e != expected_e:
        missing = sorted(set(expected_e) - set(actual_e))[:5]
        extra = sorted(set(actual_e) - set(expected_e))[:5]
        changed = sorted(k for k in set(expected_e) & set(actual_e) if expected_e[k] != actual_e[k])[:5]
        die(f'申論備援檔與 incoming 不一致 missing={missing} extra={extra} changed={changed}')

    if any(q.get('source_exam_code') in BASELINE_EXAMS for q in actual_q_rows):
        die('auto/questions_auto.json 不應包含 115030 母庫考次')
    if any(e.get('source_exam_code') in BASELINE_EXAMS for e in actual_e_rows):
        die('auto/essays_auto.json 不應包含 115030 母庫考次')

    expected_mc = len(expected_q)
    expected_essay = len(expected_e)
    if state.get('mc_count') != expected_mc or state.get('essay_count') != expected_essay:
        die('auto/sync_state.json 題數與實際備援檔不一致')
    state_codes = sorted(str(x.get('exam_code')) for x in (state.get('included_exams') or []))
    if state_codes != sorted(included_codes):
        die(f'auto/sync_state.json 考次不一致：{state_codes} != {sorted(included_codes)}')

    expected_total_questions = BASELINE_QUESTION_COUNT + expected_mc
    report = {
        'status': 'ok',
        'baseline_question_count': BASELINE_QUESTION_COUNT,
        'baseline_exams': sorted(BASELINE_EXAMS),
        'included_exams': sorted(included_codes),
        'auto_mc_count': expected_mc,
        'auto_essay_count': expected_essay,
        'expected_total_questions': expected_total_questions,
        'checks': [
            '每考次 5 科、各 40 題選擇＋2 題申論',
            '題號完整且 ID 不重複',
            '題幹與 A/B/C/D 選項皆非空白',
            '官方答案僅允許 A/B/C/D/一律給分',
            'auto 備援檔與 incoming 官方資料完全一致',
        ],
    }
    if write_report:
        AUTO.mkdir(exist_ok=True)
        (AUTO / 'health.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'LOCAL HEALTH OK: incoming={len(payloads)} exams, auto={expected_mc} MC + {expected_essay} essays, expected DB={expected_total_questions}')
    return report, payloads


def extract_supabase_config():
    text = INDEX.read_text(encoding='utf-8')
    url_match = re.search(r'\burl\s*:\s*["\']([^"\']+supabase\.co)["\']', text)
    key_match = re.search(r'\bkey\s*:\s*["\']([^"\']+)["\']', text)
    if not url_match or not key_match:
        die('index.html 找不到 Supabase URL / anon key')
    return url_match.group(1).rstrip('/'), key_match.group(1)


def rest_count(base_url, key, table, filters=None):
    params = {'select': 'id'}
    for k, v in (filters or {}).items():
        params[k] = f'eq.{v}'
    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Prefer': 'count=exact',
        'Range': '0-0',
    }
    r = requests.get(f'{base_url}/rest/v1/{table}', params=params, headers=headers, timeout=30)
    if r.status_code not in (200, 206):
        die(f'Supabase {table} 查詢失敗 HTTP {r.status_code}: {r.text[:160]}')
    content_range = r.headers.get('content-range') or r.headers.get('Content-Range') or ''
    if '/' not in content_range:
        die(f'Supabase {table} 沒有回傳 Content-Range：{content_range!r}')
    total = content_range.rsplit('/', 1)[-1]
    if total == '*':
        die(f'Supabase {table} 無法取得精確筆數')
    try:
        return int(total)
    except ValueError:
        die(f'Supabase {table} Content-Range 異常：{content_range}')


def remote_check():
    report, payloads = local_check(write_report=False)
    url, key = extract_supabase_config()

    total_questions = rest_count(url, key, 'questions')
    total_essays = rest_count(url, key, 'essays')
    if total_questions != report['expected_total_questions']:
        die(f'Supabase questions 總數應為 {report["expected_total_questions"]}，實際 {total_questions}')
    if total_essays != report['auto_essay_count']:
        die(f'Supabase essays 總數應為 {report["auto_essay_count"]}，實際 {total_essays}')

    for _path, data in payloads:
        code = data['exam_code']
        if code in BASELINE_EXAMS:
            continue
        qcount = rest_count(url, key, 'questions', {'source_exam_code': code})
        ecount = rest_count(url, key, 'essays', {'source_exam_code': code})
        if qcount != 200:
            die(f'Supabase {code} 選擇題應為 200，實際 {qcount}')
        if ecount != 10:
            die(f'Supabase {code} 申論題應為 10，實際 {ecount}')

    print(f'REMOTE HEALTH OK: Supabase questions={total_questions}, essays={total_essays}')


def main():
    ap = argparse.ArgumentParser(description='社工師題庫健康檢查')
    group = ap.add_mutually_exclusive_group()
    group.add_argument('--local', action='store_true', help='只檢查 incoming 與 auto 備援檔')
    group.add_argument('--remote', action='store_true', help='檢查 Supabase 與本機備援資料的一致性')
    args = ap.parse_args()

    if args.local:
        local_check(write_report=True)
    elif args.remote:
        remote_check()
    else:
        local_check(write_report=True)
        remote_check()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except requests.RequestException as exc:
        print(f'HEALTH CHECK FAILED: network error: {exc}', file=sys.stderr)
        raise SystemExit(1)

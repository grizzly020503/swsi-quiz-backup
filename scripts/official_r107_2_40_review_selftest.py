#!/usr/bin/env python3
"""Exact-source, read-only Q40 review candidate. NEVER approves or publishes."""
import copy
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from official_exam_readonly_guard import canonical_row, row_hash, MCQ_FIELDS

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'audit/official_r107_2_40_option_tail_candidate_20261105.json'
SHARD = ROOT / 'cdn/question-shards/107-2.json'
MANIFEST = ROOT / 'cdn/question-shards/manifest.json'
REGISTRY = ROOT / 'data/moex_source_subjects.v1.json'
LOCK = ROOT / 'data/official_exam_readonly.lock.json'
CASE = 'R-107-2-40'
OFFICIAL_D = '兩個變項間有高度相關，則非常可能有因果關係'
WRONG_D = OFFICIAL_D + ' 備 註：第 12 題答 B 或 C 或 BC 者均給分。'
PDF_SHA = '65fc5955c9a6190db3a4792eb0889678d958e856e544ecaa8c22c86cf952468d'


def require(ok, reason):
    if not ok:
        raise ValueError('Q40 NO-GO proof mismatch: ' + reason)


def official_url_identity(url):
    p = urlsplit(url)
    require(p.scheme == 'https' and p.netloc == 'wwwq.moex.gov.tw'
            and p.path == '/exam/wHandExamQandA_File.ashx', 'source host/path')
    args = dict(parse_qsl(p.query, keep_blank_values=True))
    require(len(parse_qsl(p.query, keep_blank_values=True)) == 5
            and args == {'t':'Q', 'code':'107110', 'c':'107', 's':'0606', 'q':'1'},
            'paper query identity')


def check(proof=None, observed_row=None):
    a = copy.deepcopy(proof) if proof is not None else json.loads(AUDIT.read_text())
    require(a.get('schema_version') == 1 and a.get('case_id') == CASE
            and a.get('phase') == 'SOURCE_REVIEW_CANDIDATE_ONLY_NO_GO', 'scope')
    require(all(a.get(k) is False for k in
                ('human_approval', 'release_approved', 'official_core_modified',
                 'production_write', 'backup_operation')), 'unapproved/read-only')
    pdf = a.get('official_pdf', {})
    require(pdf.get('sha256') == PDF_SHA and pdf.get('bytes') == 347855
            and pdf.get('exam_code') == '107110' and pdf.get('paper_code') == '10770'
            and pdf.get('printed_page') == '4-4' and pdf.get('pdf_page_number') == 4,
            'immutable MOEX PDF identity')
    official_url_identity(pdf.get('url', ''))
    registry = json.loads(REGISTRY.read_text())['records']
    paper = [p for p in registry if p['exam_code'] == '107110'
             and p['c'] == '107' and p['s'] == '0606']
    require(len(paper) == 1 and paper[0]['pdf_sha256'] == PDF_SHA
            and paper[0]['http']['bytes'] == 347855, 'pinned source registry')
    official_url_identity(paper[0]['url'])

    raw = SHARD.read_bytes()
    manifest = json.loads(MANIFEST.read_text())
    entry = [item for item in manifest['shards'] if item['file'] == '107-2.json']
    require(len(entry) == 1 and entry[0]['question_count'] == 200
            and entry[0]['bytes'] == len(raw)
            and entry[0]['sha256'] == hashlib.sha256(raw).hexdigest(),
            'live 200-row shard/manifest mismatch')
    rows = json.loads(raw)['questions']
    require(len(rows) == 200 and len({row['id'] for row in rows}) == 200,
            'unique full exam session')
    matches = [row for row in rows if row['id'] == CASE]
    require(len(matches) == 1, 'official case count')
    actual = matches[0] if observed_row is None else observed_row
    before = a.get('before_row', {})
    require(actual == before, 'exact preimage (all columns)')
    require(before.get('opt_d') == WRONG_D and before.get('answer') == 'D'
            and before.get('accepted_answers') is None
            and before.get('grading_mode') == 'standard'
            and before.get('analysis_status') == 'ready', 'original error/grading')
    require(before.get('source_exam_code') == '107110', 'row exam identity')
    official_url_identity(before.get('source_url', ''))
    locks = json.loads(LOCK.read_text())['mcq']
    require(row_hash(canonical_row(actual, MCQ_FIELDS)) == locks.get(CASE),
            'immutable official core lock')
    proposal = a.get('proposal', {})
    require(proposal.get('changed_official_fields') == ['opt_d']
            and proposal.get('opt_d') == OFFICIAL_D
            and proposal.get('grading_answer') == 'D'
            and proposal.get('grading_mode') == 'standard'
            and proposal.get('accepted_answers') is None,
            'exact one-field repair + unchanged scoring')
    require('quarantine' in str(proposal.get('handling', '')).lower()
            and 'review' in str(proposal.get('handling', '')).lower(),
            'stale analysis quarantine requirement')
    # A candidate is not a release: original shard, lock, answer and status
    # remain untouched; no non-Q40 official rows or any essay are modified.
    return {'id': CASE, 'status': 'NO-GO', 'changed_fields_proposed': 1,
            'human_approval': False, 'official_core_modified': False}


def selftest():
    baseline = json.loads(AUDIT.read_text())
    check(baseline)
    variants = [
        ('fake approval', lambda a: a.update(human_approval=True)),
        ('fake release', lambda a: a.update(release_approved=True)),
        ('wrong PDF', lambda a: a['official_pdf'].update(sha256='0' * 64)),
        ('wrong paper', lambda a: a['official_pdf'].update(exam_code='107120')),
        ('wrong source', lambda a: a['official_pdf'].update(url='https://example.com/q.pdf')),
        ('wrong answer', lambda a: a['before_row'].update(answer='C')),
        ('mutated original option', lambda a: a['before_row'].update(opt_d=OFFICIAL_D)),
        ('altered review field list', lambda a: a['proposal'].update(changed_official_fields=['answer', 'opt_d'])),
        ('unapproved text drift', lambda a: a['proposal'].update(opt_d=OFFICIAL_D+'。')),
        ('uncleared stale grading', lambda a: a['proposal'].update(grading_answer='B'))
    ]
    for label, mutation in variants:
        altered = copy.deepcopy(baseline)
        mutation(altered)
        try:
            check(altered)
        except ValueError:
            continue
        raise RuntimeError('FAIL-OPEN: ' + label)
    print('Q40 READ-ONLY NO-GO SELFTEST OK: 1 exact source candidate, '
          '10 fail-closed mutations, 200 rows / official lock; 0 writes')


if __name__ == '__main__':
    check()
    selftest()

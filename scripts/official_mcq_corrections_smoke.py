#!/usr/bin/env python3
"""Verify exact boundaries of the 25 raw-PDF-backed MCQ correction candidates."""
import hashlib
import json
from pathlib import Path
from audit_moex_source_subjects import load_registry, require_source
from official_mcq_pdf_audit import answer_identity, TEXT_FIELDS
from official_exam_readonly_guard import canonical_row, row_hash, MCQ_FIELDS

ROOT=Path(__file__).resolve().parents[1]
def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def check():
    proof=json.loads((ROOT/'audit/official_mcq_corrections_20261025.json').read_text())
    assert proof['count']==len(proof['rows'])==15 and proof['human_approval'] is False
    assert proof['maintainer_review_required'] is True and proof['official_production_write'] is False
    expected={'SW-106-1-40','R-105-1-24','SW-109-1-05','DS-115-1-18','DS-115-1-22'}|{'SP113-1-'+str(n) for n in (30,31,32,33,34,35,37,38,39,40)}
    assert {r['id'] for r in proof['rows']}==expected
    registry=load_registry();transport=json.loads((ROOT/'data/moex_answer_sources.v1.json').read_text())['records'];allrows={}
    for s in proof['manifest_after']['shards']:
        path=ROOT/'cdn/question-shards'/s['file'];raw=path.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==s['sha256'] and len(raw)==s['bytes']
        payload=json.loads(raw);rows=payload if isinstance(payload,list) else payload['questions']
        assert len(rows)==s['question_count']
        allrows.update({r['id']:r for r in rows})
    assert len(allrows)==4800
    extra=json.loads((ROOT/'audit/official_mcq_corrections_additional_20261025.json').read_text())
    assert extra['count']==len(extra['rows'])==10 and extra['human_approval'] is False
    assert {r['id'] for r in extra['rows']}=={'DS-104-1-25', 'DS-106-1-10', 'DS-106-1-37', 'DS-110-2-14', 'R-106-2-02', 'R-113-2-30', 'SP106-2-25', 'SP106-2-35', 'SP111-2-37', 'SW-105-2-25'}
    historical_rows=dict(allrows)
    for item in extra['rows']:
        historical_rows[item['id']]=item['before']
    assert digest({k:r for k,r in historical_rows.items() if k not in expected})==proof['unchanged_other_mcq_rows_sha256'], 'undeclared MCQ field changes'
    assert digest({k:{f:r.get(f) for f in ('answer','accepted_answers','grading_mode')} for k,r in allrows.items()})==proof['baseline_grading_map_sha256'], 'answers or grading changed'
    locked=json.loads((ROOT/'data/official_exam_readonly.lock.json').read_text())['mcq'];restored=dict(locked)
    for row in proof['rows'] + extra['rows']:
        before,after=row['before'],row['after'];ident=row['id']
        assert allrows[ident]==after
        assert all(before[k]==after[k] for k in ('id','subject','year','round','qno','answer','accepted_answers','grading_mode'))
        assert row_hash(canonical_row(before,MCQ_FIELDS))==row['before_lock_sha256']
        assert row_hash(canonical_row(after,MCQ_FIELDS))==locked[ident]==row['after_lock_sha256']
        restored[ident]=row['before_lock_sha256']
        assert row['before_lock_sha256']!=row['after_lock_sha256'] and row['question_page'] in (1,2,3,4,6)
        source=require_source(registry,after['source_exam_code'],after['subject'],after['source_url'])
        assert source['pdf_sha256']==row['question_pdf_sha256'] and source['url']==row['question_source_url']
        answers=[r for r in transport if r['exam_code']==after['source_exam_code'] and r['subject']==after['subject']]
        final=next((r for r in answers if r['kind']=='M'),next(r for r in answers if r['kind']=='S'))
        assert final['status']=='downloaded' and final['http_status']==200 and 'pdf' in final['mime'].lower()
        identity=answer_identity(row['answer_source_url'])
        assert final['sha256']==row['answer_pdf_sha256'] and final['url']==row['answer_source_url']
        assert (identity['code'],identity['c'],identity['s'])==(source['exam_code'],source['c'],source['s'])
        rule=row['official_answer_rule']
        assert after['answer']==rule['answer'] and after['grading_mode']==rule['grading_mode'] and after['accepted_answers']==rule.get('accepted_answers')
        assert row['human_approval'] is False and row['maintainer_review_required'] is True
        assert after['analysis_status']=='review'
        for field in ('major','topic','keywords','exp_why','exp_others','exp_trap','exp_raw','mnemonic','extension','law','mistake'):
            assert after[field] is None, 'stale enrichment returned'
    assert digest(restored)==proof['baseline_mcq_lock_map_sha256']
    manifest=json.loads((ROOT/'cdn/question-shards/manifest.json').read_text())
    assert manifest==proof['manifest_after']
    assert manifest['total_uncompressed_bytes']==sum(s['bytes'] for s in manifest['shards'])
    revision=hashlib.sha256('\n'.join(s['file']+':'+s['sha256'] for s in manifest['shards']).encode()).hexdigest()[:20]
    assert manifest['dataset_revision']==revision
    print('CONTROLLED MCQ CORRECTIONS OK: 25 text/option candidates; 4775 other rows and all 4800 answer/grading tuples unchanged; hashes and manifest verified; human approval pending')

if __name__=='__main__':check()

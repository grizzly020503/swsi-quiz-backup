#!/usr/bin/env python3
"""Eight source/page-bound font extraction dispositions; never change options."""
import hashlib
import json
from pathlib import Path
from official_pdf_review_dispositions import digest, require
from official_exam_readonly_guard import canonical_row,row_hash,MCQ_FIELDS
ROOT=Path(__file__).resolve().parents[1]
PROOF_PATH='audit/official_pdf_ds107_glyph_dispositions_20261029.json'
PROOF_SHA256='ecdbce15ef142c56f834b696c3464e3a05d2003e2077a167566c535b511ef259'
PRINTED={
 9:['①③⑤','①②③④','①②④⑤','①②③'],10:['①②③④⑤','⑤③④②①','①②③⑤④','②①③⑤④'],
 11:['①③','①②','①③④','①④'],13:['②③④⑤','①②④⑤','①②③④','①④⑤'],
 35:['②③④','①②③','①③④','①②③④'],36:['②③④','①②④','①③④','①②③'],
 38:['①②③④','②③④⑤','①②③④⑤','①②④⑤'],39:['②③④','①②③④','①③④','①②③']}
IDS={'DS-107-2-'+str(n).zfill(2) for n in PRINTED}
ANSWERS=dict(zip((9,10,11,13,35,36,38,39),'CDBCBDDD'))
FIELDS=('opt_a','opt_b','opt_c','opt_d')


def validate_item(item,observed,current,registry,transport):
    ident=item['id'];n=int(current['qno'])
    require(ident in IDS and ident==observed['id']==current['id'],'glyph identity drift')
    require(current['source_exam_code']=='107110' and current['subject']=='社會工作直接服務' and observed['exam_code']=='107110' and observed['subject']==current['subject'],'glyph source identity')
    require(observed['status']=='review' and observed.get('answer_difference') is None and observed.get('answer_comparison_completed') is True,'glyph answer comparison unresolved')
    require(digest(observed)==item['baseline_comparison_row_sha256'] and observed['text_differences']==item['baseline_differences'],'glyph baseline drift')
    require(digest(current)==item['current_full_row_sha256'] and row_hash(canonical_row(current,MCQ_FIELDS))==item['current_core_lock_sha256'],'glyph current row/core drift')
    require(item['classification']=='circled_glyph_extraction_only' and item['human_approval'] is False,'glyph approval/classification drift')
    expected=dict(zip(FIELDS,PRINTED[n]))
    require(item['official_field_transcription']==expected and all(current[f]==expected[f] for f in FIELDS),'unverified printed glyph options')
    require(set(observed['text_differences'])==set(FIELDS) and all(observed['text_differences'][f]['stored']==current[f] for f in FIELDS),'unreviewed glyph field')
    require(current['answer']==ANSWERS[n] and all(current.get(f)==item['official_answer_rule'][f] for f in ('answer','accepted_answers','grading_mode')),'glyph official grading drift')
    page=2 if n<20 else 4
    require(item['printed_page']=='4-'+str(page) and item['pdf_page_number']==page and item['answer_page']==1,'glyph wrong PDF page')
    from audit_moex_source_subjects import require_source
    source=require_source(registry,'107110',current['subject'],item['source_url'])
    require(source['pdf_sha256']==item['pdf_sha256']==observed['question_pdf_sha256']=='338ec25a9c997894aabdc1fa45417ef15522341c839ca6b8ebc54378ffb42cb1' and item['source_url']==observed['question_source_url'],'glyph question PDF mismatch')
    candidates=[r for r in transport if r['exam_code']=='107110' and r['subject']==current['subject']]
    final=next((r for r in candidates if r['kind']=='M'),next(r for r in candidates if r['kind']=='S'))
    require(final['status']=='downloaded' and final['http_status']==200 and 'pdf' in final['mime'].lower() and final['sha256']==item['answer_pdf_sha256']==observed['answer_pdf_sha256']=='414ff76db49acf61735e0986885dc1945ef48081a192a80e8f5330bf2a10f21e' and final['url']==item['answer_source_url']==observed['answer_source_url'],'glyph final answer PDF mismatch')


def validated_ids(report,root=ROOT):
    root=Path(root);raw=(root/PROOF_PATH).read_bytes()
    require(hashlib.sha256(raw).hexdigest()==PROOF_SHA256,'glyph proof drift');proof=json.loads(raw)
    require(proof['count']==len(proof['rows'])==8 and {r['id'] for r in proof['rows']}==IDS,'glyph proof scope')
    require(all(proof[k] is False for k in ('human_approval','release_approved','official_core_modified')),'glyph proof approval')
    require(proof['comparison_sha256']==hashlib.sha256((root/'audit/official_mcq_pdf_comparison_20261025.json').read_bytes()).hexdigest(),'glyph raw comparison drift')
    from official_combined_candidate_guard import view
    view(root)
    current={r['id']:r for r in json.loads((root/'cdn/question-shards/107-2.json').read_text())['questions']}
    from audit_moex_source_subjects import load_registry
    registry=load_registry();transport=json.loads((root/'data/moex_answer_sources.v1.json').read_text())['records'];observed={r['id']:r for r in report['rows']}
    for item in proof['rows']:validate_item(item,observed[item['id']],current[item['id']],registry,transport)
    return set(IDS)

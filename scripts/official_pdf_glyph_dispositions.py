#!/usr/bin/env python3
"""Source/page-bound font extraction dispositions; never change options."""
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
LEGACY_IDS={'DS-107-2-'+str(n).zfill(2) for n in PRINTED}
ANSWERS=dict(zip((9,10,11,13,35,36,38,39),'CDBCBDDD'))
FIELDS=('opt_a','opt_b','opt_c','opt_d')
NEW_PROOF_PATH='audit/official_pdf_circle_followup_20261029.json'
NEW_PROOF_SHA256='44b4a0a9c16feefbe68903e589259a7ee2d57b7f2ab734d0a717fc6c44bbe9d8'
FOLLOWUP={
 'DS-105-2-09':(['①②③④⑤','僅①②⑤','僅②④⑤','僅①③④'],'A',2),
 'DS-105-2-10':(['①②③⑤','①④⑤⑥','僅②③④⑥','①②③④⑥'],'D',2),
 'R-107-2-02':(['僅①④','僅②③','僅①②④','①②③④'],'A',1),
 'R-107-2-23':(['僅①④','僅②③','僅①②','①②③'],'D',3)}
IDS=LEGACY_IDS|set(FOLLOWUP)
PAPERS={
 'DS107':('107110','社會工作直接服務','338ec25a9c997894aabdc1fa45417ef15522341c839ca6b8ebc54378ffb42cb1','414ff76db49acf61735e0986885dc1945ef48081a192a80e8f5330bf2a10f21e'),
 'DS105':('105090','社會工作直接服務','bc62d02d54064ab139b10af93f33766c3464eb4a95256cc373ed4f2140487132','50449484677816cf1814077854fca0c8d04cbd1af37606dce31365a01201df58'),
 'R107':('107110','社會工作研究方法','65fc5955c9a6190db3a4792eb0889678d958e856e544ecaa8c22c86cf952468d','7cd59dddf3456e4a328bdb765bcfda1397fec55fbcfdae288c494aa01bb79410')}


def rules(ident):
    require(ident in IDS,'glyph identity drift')
    if ident in LEGACY_IDS:
        n=int(ident.rsplit('-',1)[1]);opts,answer,page=PRINTED[n],ANSWERS[n],2 if n<20 else 4;paper='DS107'
    else:
        opts,answer,page=FOLLOWUP[ident];paper='DS105' if ident.startswith('DS') else 'R107'
    return dict(zip(FIELDS,opts)),answer,page,PAPERS[paper]


def validate_item(item,observed,current,registry,transport):
    ident=item['id'];expected,answer,page,paper=rules(ident)
    code,subject,pdf_sha,answer_sha=paper
    require(ident in IDS and ident==observed['id']==current['id'],'glyph identity drift')
    require(current['source_exam_code']==code and current['subject']==subject and observed['exam_code']==code and observed['subject']==current['subject'],'glyph source identity')
    require(observed['status']=='review' and observed.get('answer_difference') is None and observed.get('answer_comparison_completed') is True,'glyph answer comparison unresolved')
    require(digest(observed)==item['baseline_comparison_row_sha256'] and observed['text_differences']==item['baseline_differences'],'glyph baseline drift')
    require(digest(current)==item['current_full_row_sha256'] and row_hash(canonical_row(current,MCQ_FIELDS))==item['current_core_lock_sha256'],'glyph current row/core drift')
    require(item['classification']=='circled_glyph_extraction_only' and item['human_approval'] is False,'glyph approval/classification drift')
    require(item['official_field_transcription']==expected and all(current[f]==expected[f] for f in FIELDS),'unverified printed glyph options')
    require(set(observed['text_differences'])==(set(FIELDS)-{'opt_c'} if ident=='R-107-2-23' else set(FIELDS)) and all(delta['stored']==current[f] for f,delta in observed['text_differences'].items()),'unreviewed glyph field')
    require(current['answer']==answer and all(current.get(f)==item['official_answer_rule'][f] for f in ('answer','accepted_answers','grading_mode')),'glyph official grading drift')
    require(item['printed_page']=='4-'+str(page) and item['pdf_page_number']==page and item['answer_page']==1,'glyph wrong PDF page')
    from audit_moex_source_subjects import require_source
    source=require_source(registry,code,current['subject'],item['source_url'])
    require(source['pdf_sha256']==item['pdf_sha256']==observed['question_pdf_sha256']==pdf_sha and item['source_url']==observed['question_source_url'],'glyph question PDF mismatch')
    candidates=[r for r in transport if r['exam_code']==code and r['subject']==current['subject']]
    final=next((r for r in candidates if r['kind']=='M'),next(r for r in candidates if r['kind']=='S'))
    require(final['status']=='downloaded' and final['http_status']==200 and 'pdf' in final['mime'].lower() and final['sha256']==item['answer_pdf_sha256']==observed['answer_pdf_sha256']==answer_sha and final['url']==item['answer_source_url']==observed['answer_source_url'],'glyph final answer PDF mismatch')


def validated_ids(report,root=ROOT):
    root=Path(root);items=[];seen=set()
    report_sha=hashlib.sha256((root/'audit/official_mcq_pdf_comparison_20261025.json').read_bytes()).hexdigest()
    for path,sha,expected_ids in [(PROOF_PATH,PROOF_SHA256,LEGACY_IDS),(NEW_PROOF_PATH,NEW_PROOF_SHA256,set(FOLLOWUP))]:
        raw=(root/path).read_bytes();require(hashlib.sha256(raw).hexdigest()==sha,'glyph proof drift');proof=json.loads(raw)
        actual={r['id'] for r in proof['rows']}
        require(proof['count']==len(proof['rows'])==len(expected_ids) and actual==expected_ids and not seen&actual,'glyph proof scope')
        require(all(proof[k] is False for k in ('human_approval','release_approved','official_core_modified')),'glyph proof approval')
        require(proof['comparison_sha256']==report_sha,'glyph raw comparison drift')
        seen.update(actual);items.extend(proof['rows'])
    from official_combined_candidate_guard import view
    view(root)
    current={r['id']:r for name in ('105-2','107-2') for r in json.loads((root/('cdn/question-shards/'+name+'.json')).read_text())['questions']}
    from audit_moex_source_subjects import load_registry
    registry=load_registry();transport=json.loads((root/'data/moex_answer_sources.v1.json').read_text())['records'];observed={r['id']:r for r in report['rows']}
    for item in items:validate_item(item,observed[item['id']],current[item['id']],registry,transport)
    return set(IDS)

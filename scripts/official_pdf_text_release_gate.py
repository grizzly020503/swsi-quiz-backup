#!/usr/bin/env python3
"""Fail closed on stale, malformed or unresolved official PDF text comparisons.

An evidence-only check confirms reproducibility metadata, never release approval.
The default command remains NO-GO while any official text comparison is held.\nA strict, evidence-bound twelve-row overlay can clear only exact official corrections.
"""
from collections import Counter
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
CONFIGS=[('audit/official_mcq_pdf_comparison_20261025.json',4800,'normalized_pdf_text_and_answer_match',{'scripts/official_mcq_pdf_audit.py','scripts/moex_sync.py','scripts/moex_sync_v2.py','cdn/question-shards/manifest.json','data/moex_source_subjects.v1.json','data/moex_answer_sources.v1.json'}),('audit/official_essay_pdf_comparison_20261025.json',240,'normalized_pdf_text_match',{'scripts/official_essay_pdf_audit.py','scripts/moex_sync.py','scripts/moex_sync_v2.py','index.html','auto/essays_auto.json','data/moex_source_subjects.v1.json'})]



# Immutable original PDF extraction remains untouched. A tightly scoped,
# source-page-inspected delta is permitted only for twelve exact Official Core
# fixes, with all other rows and all grading semantics still bound by guards.
BASE_MCQLAYOUT_MANIFEST_SHA256 = 'e5f177ed6d0fad75c7b211362de5a2e68828a0cb1842ef2abd9eb2955f7c10d4'
REVIEWED_DELTA_MANIFEST_SHA256 = 'd8dd80c13231cafa2b72961c47e7bd6a78516e0f4796bd3df7715ae192a30e72'
REVIEWED_DELTA_IDS = {'DS-104-1-25', 'DS-106-1-10', 'DS-106-1-37', 'DS-110-2-14', 'R-106-2-02', 'R-113-2-30', 'SP106-2-25', 'SP106-2-35', 'SP111-2-37', 'SW-105-2-25', 'DS-109-2-23', 'SW-108-2-01'}


def validate_three_official_pdf_corrections(report, observed_manifest_digest):
    """Recompare twelve corrected rows against already-captured official PDF text.

    No other review is cleared. A future manifest, changed extraction, edited
    report, changed answer or missing proof fails closed.
    """
    if (report.get('input_sha256', {}).get('cdn/question-shards/manifest.json') != BASE_MCQLAYOUT_MANIFEST_SHA256
            or observed_manifest_digest != REVIEWED_DELTA_MANIFEST_SHA256):
        raise ValueError('unexpected original/corrected manifest for official PDF delta')
    from official_essay_pdf_audit import normalize
    from official_exam_readonly_guard import canonical_row, row_hash, MCQ_FIELDS
    extra=json.loads((ROOT/'audit/official_mcq_corrections_additional_20261025.json').read_text())
    if (extra.get('count') != 12 or extra.get('human_approval') is not False
            or extra.get('official_production_write') is not False
            or {r['id'] for r in extra.get('rows', [])} != REVIEWED_DELTA_IDS):
        raise ValueError('unexpected or unapproved official PDF delta proof')
    from official_combined_candidate_guard import view
    _, _, manifest = view(ROOT)
    previous=json.loads((ROOT/'audit/official_mcq_corrections_20261025.json').read_text())
    if manifest != previous['manifest_after']:
        raise ValueError('official PDF delta diverges from controlled manifest')
    rows_by_id={row['id']:row for row in report['rows'] if row['id'] in REVIEWED_DELTA_IDS}
    if len(rows_by_id) != 12 or report['counts'].get('review') != 441:
        raise ValueError('baseline official PDF comparison was altered')
    shards={}
    lock=json.loads((ROOT/'data/official_exam_readonly.lock.json').read_text())['mcq']
    for item in extra['rows']:
        ident=item['id']; before=item['before']; after=item['after']; observed=rows_by_id[ident]
        if (observed.get('status') != 'review' or observed.get('answer_difference') is not None
                or observed.get('question_pdf_sha256') != item['question_pdf_sha256']
                or observed.get('question_source_url') != item['question_source_url']
                or observed.get('answer_pdf_sha256') != item['answer_pdf_sha256']
                or observed.get('answer_source_url') != item['answer_source_url']):
            raise ValueError('unverified official PDF correction: '+ident)
        if any(before[k] != after[k] for k in ('answer', 'accepted_answers', 'grading_mode', 'id', 'subject', 'year', 'round', 'qno')):
            raise ValueError('official answer or identity mutation: '+ident)
        if (row_hash(canonical_row(before,MCQ_FIELDS)) != item['before_lock_sha256']
                or row_hash(canonical_row(after,MCQ_FIELDS)) != item['after_lock_sha256']
                or lock[ident] != item['after_lock_sha256']):
            raise ValueError('official PDF delta lock mismatch: '+ident)
        changed={k for k in ('question','opt_a','opt_b','opt_c','opt_d') if before[k] != after[k]}
        diffs=observed.get('text_differences') or {}
        if changed != set(diffs):
            raise ValueError('unreviewed wording difference: '+ident)
        for field in changed:
            if ident == 'SW-105-2-25':
                # Four option groups use circled glyphs reduced to "111" in
                # machine extraction. Verify one exact official PDF and page.
                visual = {
                    'question':'每一門專業都有其核心的社會使命要去完成，有關Morales & Sheafor（1998）提出的社會工 作存在的三個使命（3C’s），下列何者正確？①照顧（caring）②改變社會（changing the society）③慈善（charity）④治療（curing）',
                    'opt_a':'①②③','opt_b':'①②④','opt_c':'①③④','opt_d':'②③④',
                }
                if (item['question_pdf_sha256'] != '6cb957f74ae14d66bb2c0d83a8a61ec741d520e9c5cec08e0c008eb5a0238332'
                        or item['question_page'] != 3
                        or after[field] != visual[field]
                        or diffs[field]['stored'] != before[field]):
                    raise ValueError('unverified circled options: '+ident+'/'+field)
            elif diffs[field]['stored'] != before[field] or normalize(diffs[field]['official_extraction']) != normalize(after[field]):
                raise ValueError('new text is not official extraction: '+ident+'/'+field)
        for field in ('major','topic','keywords','exp_why','exp_others','exp_trap','exp_raw','mnemonic','extension','law','mistake'):
            if after[field] is not None:
                raise ValueError('stale enrichment survived correction: '+ident)
        if after.get('analysis_status') != 'review' or item.get('human_approval') is not False:
            raise ValueError('unapproved official text published: '+ident)
        path='cdn/question-shards/'+str(after['year'])+('-1.json' if after['round']=='第一次' else '-2.json')
        if path not in shards:
            shards[path]={row['id']:row for row in json.loads((ROOT/path).read_text())['questions']}
        if shards[path].get(ident) != after:
            raise ValueError('release shard differs from reviewed correction: '+ident)
    return len(REVIEWED_DELTA_IDS)


def validate(report,count,match_status,inputs):
    if report.get('schema_version')!=1 or set(report.get('input_sha256',{}))!=inputs:raise ValueError('missing or unexpected input fingerprints')
    applied_delta=0
    for name,expected in report['input_sha256'].items():
        observed=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        if observed==expected:continue
        if name=='cdn/question-shards/manifest.json' and count==4800:
            from official_combined_candidate_guard import view, checked_json, PROJECTION_SHA
            view(ROOT)  # Check actual 41-row bytes before projecting the old audit input.
            projection=checked_json(ROOT, 'audit/official_combined_base_projection_20261029.json', PROJECTION_SHA)
            applied_delta=validate_three_official_pdf_corrections(report,projection['base_manifest_sha256'])
        else:
            raise ValueError('stale comparison input: '+name)
    rows=report.get('rows',[])
    if len(rows)!=count or len({r.get('id') for r in rows})!=count or any(not r.get('id') for r in rows):raise ValueError('missing/duplicate comparison identities')
    counts=Counter(r.get('status') for r in rows)
    if set(counts)-{match_status,'review'} or dict(counts)!=report.get('counts'):raise ValueError('unknown status or inconsistent comparison counts')
    if any(r.get('human_approval') is not False for r in rows):raise ValueError('mechanical comparisons must not claim human approval')
    if applied_delta and counts.get('review',0) < applied_delta:raise ValueError('delta overcounts PDF reviews')
    if count == 4800:
        from official_pdf_review_dispositions import validated_ids
        applied_delta += len(validated_ids(report, ROOT))
        from official_pdf_stem_repairs import validated_ids as validated_stem_ids
        applied_delta += len(validated_stem_ids(report, ROOT))
    return counts.get('review',0)-applied_delta


def inspect():
    result={}
    reports={}
    for path,count,status,inputs in CONFIGS:
        name='mcq' if count==4800 else 'essays'
        reports[name]=json.loads((ROOT/path).read_text())
        result[name]=validate(reports[name],count,status,inputs)
    # The manifest hash alone is insufficient if a shard changes without its
    # manifest. Bind all actual question bytes to the compared snapshot too.
    manifest=json.loads((ROOT/'cdn/question-shards/manifest.json').read_text())
    if len(manifest['shards'])!=24 or manifest['total_questions']!=4800:raise ValueError('question manifest coverage mismatch')
    mcq_ids=set()
    for s in manifest['shards']:
        raw=(ROOT/'cdn/question-shards'/s['file']).read_bytes()
        if len(raw)!=s['bytes'] or hashlib.sha256(raw).hexdigest()!=s['sha256']:raise ValueError('question shard drift: '+s['file'])
        payload=json.loads(raw);rows=payload if isinstance(payload,list) else payload['questions']
        mcq_ids.update(r['id'] for r in rows)
    from official_exam_readonly_guard import collect_essays
    if mcq_ids!={r['id'] for r in reports['mcq']['rows']} or set(collect_essays())!={r['id'] for r in reports['essays']['rows']}:
        raise ValueError('comparison identities differ from the actual question bank')
    return result


def selftest():
    path,count,status,inputs=CONFIGS[0];report=json.loads((ROOT/path).read_text());assert validate(report,count,status,inputs)>=0
    wrong=copy.deepcopy(report);wrong['rows'][0]['id']=wrong['rows'][1]['id']
    stale=copy.deepcopy(report);stale['input_sha256'][next(iter(inputs))]='0'*64
    inconsistent=copy.deepcopy(report);inconsistent['counts']['review']+=1
    human=copy.deepcopy(report);human['rows'][0]['human_approval']=True
    source_mismatch=copy.deepcopy(report)
    next(r for r in source_mismatch['rows'] if r['id']=='SW-108-2-01')['question_pdf_sha256']='0'*64
    year_mismatch=copy.deepcopy(report)
    next(r for r in year_mismatch['rows'] if r['id']=='SW-108-2-01')['text_differences']['opt_d']['official_extraction']='1972 年政府通過設置社會工作員實驗計畫'
    for bad in (wrong,stale,inconsistent,human,source_mismatch,year_mismatch):
        try:validate(bad,count,status,inputs)
        except ValueError:pass
        else:raise AssertionError('tampered comparison accepted')
    print('OFFICIAL PDF RELEASE GATE SELFTEST OK: stale input, duplicate identities, count drift, false human approval, wrong PDF and altered 1971 evidence rejected')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check-evidence-only',action='store_true');p.add_argument('--selftest',action='store_true');a=p.parse_args()
    try:
        if a.selftest:selftest();return 0
        holds=inspect();held=sum(holds.values());print(json.dumps(dict(status='NO-GO' if held else 'TEXT_COMPARISONS_CLEAR',unresolved=holds,total_unresolved=held,evidence_only=a.check_evidence_only,human_approval=False),ensure_ascii=False))
        return 0 if a.check_evidence_only or held==0 else 2
    except (ValueError,KeyError,TypeError,OSError) as error:
        print('OFFICIAL PDF RELEASE EVIDENCE INVALID: '+str(error),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())

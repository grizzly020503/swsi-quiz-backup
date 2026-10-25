#!/usr/bin/env python3
"""Fail closed on stale, malformed or unresolved official PDF text comparisons.

An evidence-only check confirms reproducibility metadata, never release approval.
The default command remains NO-GO while any of the 5040 text comparisons is held.
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


def validate(report,count,match_status,inputs):
    if report.get('schema_version')!=1 or set(report.get('input_sha256',{}))!=inputs:raise ValueError('missing or unexpected input fingerprints')
    for name,expected in report['input_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('stale comparison input: '+name)
    rows=report.get('rows',[])
    if len(rows)!=count or len({r.get('id') for r in rows})!=count or any(not r.get('id') for r in rows):raise ValueError('missing/duplicate comparison identities')
    counts=Counter(r.get('status') for r in rows)
    if set(counts)-{match_status,'review'} or dict(counts)!=report.get('counts'):raise ValueError('unknown status or inconsistent comparison counts')
    if any(r.get('human_approval') is not False for r in rows):raise ValueError('mechanical comparisons must not claim human approval')
    return counts.get('review',0)


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
    for bad in (wrong,stale,inconsistent,human):
        try:validate(bad,count,status,inputs)
        except ValueError:pass
        else:raise AssertionError('tampered comparison accepted')
    print('OFFICIAL PDF RELEASE GATE SELFTEST OK: stale input, duplicate identities, count drift and false human approval rejected')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check-evidence-only',action='store_true');p.add_argument('--selftest',action='store_true');a=p.parse_args()
    try:
        if a.selftest:selftest();return 0
        holds=inspect();held=sum(holds.values());print(json.dumps(dict(status='NO-GO' if held else 'TEXT_COMPARISONS_CLEAR',unresolved=holds,total_unresolved=held,evidence_only=a.check_evidence_only,human_approval=False),ensure_ascii=False))
        return 0 if a.check_evidence_only or held==0 else 2
    except (ValueError,KeyError,TypeError,OSError) as error:
        print('OFFICIAL PDF RELEASE EVIDENCE INVALID: '+str(error),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())

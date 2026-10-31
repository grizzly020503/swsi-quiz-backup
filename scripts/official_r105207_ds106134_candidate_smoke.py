#!/usr/bin/env python3
"""MOEX source-bound TWO question fixes; reconstruct parent before all previous gates.

Not a production release authorization. This layer remains review-only until
the original exam PDFs receive independent human approval.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from official_exam_readonly_guard import canonical_row, row_hash, MCQ_FIELDS

R=Path(__file__).resolve().parents[1]
PROOF=R/'audit/official_r105207_ds106134_source_candidate_20261031.json'
IDS={'R-105-2-07','DS-106-1-34'}
ENRICH=('major','topic','keywords','exp_why','exp_others','exp_trap','exp_raw','mnemonic','extension','law','mistake')
SHA={
'R-105-2-07':('6afea97bde8d58d00358d23bc5a31a0372a47f98d60b99ebc8f04495e3e9d836','cd5a72370dc1e1ad4309a93c223fe92bb7a420da87c051a6d1cd45ec4122a18f','B','4-2'),
'DS-106-1-34':('9f6d1a64364b25387606e32b8f0a89142ad42fa8e1474c64f712b7e3fad9179c','6e65c4a998e0b2b8ab4bd356d25d1932646110f8ccd891a0fcb2741623942aa3','B','4-4'),
}

def digest(b):return hashlib.sha256(b).hexdigest()

def projected_parent_shard_bytes(filename):
    """Return bytes for the previous #499 parent after exact two-row undo.

    Older release guards inspect on-disk shards rather than only in-memory rows;
    verify the new file and reconstruct their known parent bytes in the two
    changed shards. All other shards are read unchanged and still hash-checked.
    """
    raw=(R/'cdn/question-shards'/filename).read_bytes()
    if filename not in ('105-2.json','106-1.json'):
        return raw
    proof=json.loads(PROOF.read_text())
    changes=[x for x in proof['changes'] if x['file']==filename]
    assert len(changes)==1
    c=changes[0]
    assert digest(raw)==c['shard_after_sha256'] and len(raw)==c['shard_after_bytes']
    document=json.loads(raw)
    actual=next(x for x in document['questions'] if x['id']==c['id'])
    assert actual==c['full_after']
    actual.clear();actual.update(c['full_before'])
    prior=(json.dumps(document,ensure_ascii=False,separators=(',',':'))+'\n').encode()
    assert len(prior)==c['shard_before_bytes'] and digest(prior)==c['shard_before_sha256']
    return prior

def validate_overlay(p,rows,lock,manifest_raw):
    assert p['schema_version']==1 and p['scope']=='TWO_VERIFIED_MOEX_SOURCE_TEXT_P0_CANDIDATES'
    assert p['base_candidate']=='ada95f436a8b151967de1cdae59f8bac9a5dbc90'
    assert p['release_approved'] is False and p['independent_human_approval'] is False
    assert p['production_written'] is False and p['backup_modified'] is False
    assert p['grading_changed'] is False and p['pending_old_pdf_reviews_unchanged']==428
    assert len(p['changes'])==2 and {c['id'] for c in p['changes']}==IDS
    assert digest(manifest_raw)==p['new_manifest_sha256']
    before_raw=p['old_manifest_raw'].encode('utf-8')
    assert digest(before_raw)==p['old_manifest_sha256']
    after_manifest=json.loads(manifest_raw)
    before_manifest=json.loads(before_raw)
    assert after_manifest['dataset_revision']==p['revision_after']
    assert before_manifest['dataset_revision']==p['revision_before']
    assert len(after_manifest['shards'])==len(before_manifest['shards'])==24
    assert after_manifest['total_questions']==before_manifest['total_questions']==4800
    assert after_manifest['total_uncompressed_bytes']==sum(x['bytes'] for x in after_manifest['shards'])
    before_info={s['file']:s for s in before_manifest['shards']}
    after_info={s['file']:s for s in after_manifest['shards']}
    assert {name for name in before_info if before_info[name]!=after_info[name]}=={'105-2.json','106-1.json'}
    assert len(rows)==len({q['id'] for q in rows})==4800
    assert len(lock['mcq'])==4800 and len(lock['essays'])==240
    index={q['id']:q for q in rows}
    for sh in after_manifest['shards']:
        raw=(R/'cdn/question-shards'/sh['file']).read_bytes()
        assert len(raw)==sh['bytes'] and digest(raw)==sh['sha256']
        part=json.loads(raw)
        assert len(part['questions'])==sh['question_count']
        for q in part['questions']:
            assert q['id'] in index and q==index[q['id']]
    old_rows=copy.deepcopy(rows); old_idx={x['id']:x for x in old_rows}
    old_lock=copy.deepcopy(lock)
    for c in p['changes']:
        id=c['id'];before=c['full_before'];after=c['full_after'];src=c['source']
        assert (src['sha256'],src['answer_sha256'],src['answer'],src['printed_page'])==SHA[id]
        assert src['pdf_page'] in (2,4)
        assert src['url'].startswith('https://wwwq.moex.gov.tw/exam/')
        assert before['id']==after['id']==id and index[id]==after
        assert row_hash(canonical_row(before,MCQ_FIELDS))==c['before_lock_sha256']
        assert row_hash(canonical_row(after,MCQ_FIELDS))==c['after_lock_sha256']==lock['mcq'][id]
        assert all(before[k]==after[k] for k in ('answer','accepted_answers','grading_mode','source_url','source_exam_code','id','subject','year','round','qno'))
        assert before['answer']==after['answer']=='B'
        assert after['analysis_status']=='review'
        assert all(after[k] is None for k in ENRICH)
        expected=copy.deepcopy(before)
        assert set(c['changed_fields'])==({'question','opt_a','opt_b','opt_c','opt_d'} if id=='R-105-2-07' else {'question','opt_a','opt_c','opt_d'})
        for k in c['changed_fields']:expected[k]=after[k]
        for k in ENRICH:expected[k]=None
        expected['analysis_status']='review'
        assert expected==after
        old_idx[id].clear();old_idx[id].update(before)
        old_lock['mcq'][id]=c['before_lock_sha256']

    for c in p['changes']:
        path=R/'cdn/question-shards'/c['file']
        raw=path.read_bytes()
        assert len(raw)==c['shard_after_bytes'] and digest(raw)==c['shard_after_sha256']
        shard=json.loads(raw)
        for row in shard['questions']:
            if row['id']==c['id']:
                row.clear();row.update(c['full_before'])
        original=(json.dumps(shard,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
        assert len(original)==c['shard_before_bytes']==before_info[c['file']]['bytes']
        assert digest(original)==c['shard_before_sha256']==before_info[c['file']]['sha256']
    assert all(x['answer']==y['answer'] and x['accepted_answers']==y['accepted_answers']
               and x['grading_mode']==y['grading_mode'] for x,y in zip(rows,old_rows))
    assert old_lock['essays']==lock['essays']
    return old_rows,old_lock,before_raw

def main():
    p=json.loads(PROOF.read_text())
    raw=(R/'cdn/question-shards/manifest.json').read_bytes()
    m=json.loads(raw);rows=[]
    for info in m['shards']:
        b=(R/'cdn/question-shards'/info['file']).read_bytes()
        assert digest(b)==info['sha256'] and len(b)==info['bytes']
        rows.extend(json.loads(b)['questions'])
    lock=json.loads((R/'data/official_exam_readonly.lock.json').read_text())
    validate_overlay(p,rows,lock,raw)
    for kind in ('target','answer','unrelated','source-sha','answer-sha','lock','manifest'):
        x,rs,lk=copy.deepcopy((p,rows,lock))
        if kind=='target':next(q for q in rs if q['id']=='R-105-2-07')['opt_c']+='tamper'
        elif kind=='answer':next(q for q in rs if q['id']=='DS-106-1-34')['answer']='C'
        elif kind=='unrelated':next(q for q in rs if q['id'] not in IDS)['question']+='tamper'
        elif kind=='source-sha':x['changes'][0]['source']['sha256']='0'*64
        elif kind=='answer-sha':x['changes'][1]['source']['answer_sha256']='0'*64
        elif kind=='lock':lk['mcq']['DS-106-1-34']='0'*64
        elif kind=='manifest':x['new_manifest_sha256']='0'*64
        try:validate_overlay(x,rs,lk,raw)
        except AssertionError:pass
        else:raise AssertionError('unverified official edit accepted: '+kind)
    print('MOEX TWO SOURCE-VERIFIED P0 QA PASS: restored alpha/beta and three duplicate choices; 4798 unrelated full rows, 4800 grading tuples and 240 essay locks preserved; 7 negative tests rejected; no release approval')

if __name__=='__main__':main()

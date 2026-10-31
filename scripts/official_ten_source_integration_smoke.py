#!/usr/bin/env python3
"""Exact ten-row official-source transition over main 73460bf. Offline, no writes.

Reconstruct its exact parent so earlier five/13/genogram assertions remain intact.
These deterministic checks do not supply independent human approval.
"""
import copy,hashlib,json
from pathlib import Path
from official_exam_readonly_guard import canonical_row,row_hash,MCQ_FIELDS
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'audit/official_ten_source_release_transition_20261031.json'
PINNED={'DS-108-2-23': ['0184f676fd339d7c8f67071fbda0e528d44b5a34025c498c6892db0b6dd4cf60', '78e9473d144f9165622f02ac3e5a004658b0ca7dd516c436f56cfdf4042b3e9b', 'aa489636b5c0c62a4262b1fe51739e0de0d11bbf7d297d95f2f5220d3c474e79', None, 3, 'B'], 'R-114-1-17': ['03877f398a6d5d8f00c09c560a8fcfe3a28e5453a2fff04089b38a441c20dbab', 'e2103e4eb154b5ac0c8de24026a7b35fe3a8370678f606356c919540c87646e2', 'c5a309fa1e5b11cdd828501534f164177e707be5dbe98671811ae33b40d2d728', None, 3, 'A'], 'R-111-2-14': ['5d56a0cf1a9b1da672395bd567b8f4150ffd4a25f0195285b29a3c64d35b44d2', '14ba09396d90e0ccd8330821e7fa3fbb2f41a57ecfdb807e3bf18be924375153', 'a0e0d318c8ec8bb8812734ea1da761412b866a1575b026ea5e5964ad90fa2a59', 'ac56d815ae912afb37c0620a2ab1192786bb3c2af19e1f483ec48da614af018f', 2, 'A'], 'R-111-2-15': ['284d19753bace099a90b2a266d45046fb1764c4cf0a3db402096527ea8f8523a', '14ba09396d90e0ccd8330821e7fa3fbb2f41a57ecfdb807e3bf18be924375153', 'a0e0d318c8ec8bb8812734ea1da761412b866a1575b026ea5e5964ad90fa2a59', 'ac56d815ae912afb37c0620a2ab1192786bb3c2af19e1f483ec48da614af018f', 2, 'C'], 'R-111-2-17': ['ccae7c6ca286c610af8cb62837dec8dc9e3e9c4a84c137198b376552bcdc4582', '14ba09396d90e0ccd8330821e7fa3fbb2f41a57ecfdb807e3bf18be924375153', 'a0e0d318c8ec8bb8812734ea1da761412b866a1575b026ea5e5964ad90fa2a59', 'ac56d815ae912afb37c0620a2ab1192786bb3c2af19e1f483ec48da614af018f', 2, 'C'], 'R-111-2-18': ['0f39b135655bd6d78db231a10e9f7b9304b926a65d073afe8d401db4f705c031', '14ba09396d90e0ccd8330821e7fa3fbb2f41a57ecfdb807e3bf18be924375153', 'a0e0d318c8ec8bb8812734ea1da761412b866a1575b026ea5e5964ad90fa2a59', 'ac56d815ae912afb37c0620a2ab1192786bb3c2af19e1f483ec48da614af018f', 2, 'A'], 'R-111-2-29': ['72ac0edfa1aba2ad77e0f62f0000936544c5705ad95641cc2f7f6346ea45dbf8', '14ba09396d90e0ccd8330821e7fa3fbb2f41a57ecfdb807e3bf18be924375153', 'a0e0d318c8ec8bb8812734ea1da761412b866a1575b026ea5e5964ad90fa2a59', 'ac56d815ae912afb37c0620a2ab1192786bb3c2af19e1f483ec48da614af018f', 3, 'D'], 'R-111-2-30': ['e2542a192a2804ad42e0dd7770f4f5e53b64ea8a51c29f89ed9a3e0d8597a91a', '14ba09396d90e0ccd8330821e7fa3fbb2f41a57ecfdb807e3bf18be924375153', 'a0e0d318c8ec8bb8812734ea1da761412b866a1575b026ea5e5964ad90fa2a59', 'ac56d815ae912afb37c0620a2ab1192786bb3c2af19e1f483ec48da614af018f', 3, 'B'], 'R-105-2-07': ['a4f8bd6e2a54e81aac20859d7d2e833f8aed81851f77a80b6aa69ea2fcb77d04', '6afea97bde8d58d00358d23bc5a31a0372a47f98d60b99ebc8f04495e3e9d836', 'cd5a72370dc1e1ad4309a93c223fe92bb7a420da87c051a6d1cd45ec4122a18f', None, 2, 'B'], 'DS-106-1-34': ['8cec5413acc605bf126c2d3db37fbedb019b561a76a89cbd381fbfebccc77730', '9f6d1a64364b25387606e32b8f0a89142ad42fa8e1474c64f712b7e3fad9179c', '6e65c4a998e0b2b8ab4bd356d25d1932646110f8ccd891a0fcb2741623942aa3', None, 4, 'B']}
IDS=set(PINNED)
ENRICH=('major','topic','keywords','exp_why','exp_others','exp_trap','exp_raw','mnemonic','extension','law','mistake')
GRADING=('answer','accepted_answers','grading_mode')
sha=lambda b:hashlib.sha256(b).hexdigest()
digest=lambda v:sha(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
encode=lambda v:(json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n').encode()

def projected_parent_shard_bytes(filename):
    """Verify physical shard, reverse only pinned rows, require exact parent bytes."""
    p=json.loads(P.read_text());raw=(ROOT/'cdn/question-shards'/filename).read_bytes()
    if filename not in p['new_shards']:return raw
    assert sha(raw)==p['new_shards'][filename]['sha256'] and len(raw)==p['new_shards'][filename]['bytes']
    data=json.loads(raw);source={r['id']:r for r in p['rows']}
    for row in data['questions']:
        if row['id'] in source:
            item=source[row['id']];assert row==item['published_after']
            row.clear();row.update(item['published_before'])
    prior=encode(data)
    assert sha(prior)==p['old_shards'][filename]['sha256'] and len(prior)==p['old_shards'][filename]['bytes']
    return prior

def validate_transition(p,rows,lock,raw):
    assert p['schema_version']==1 and p['scope']=='TEN_PINNED_OFFICIAL_SOURCE_CORRECTIONS'
    assert p['base_main']=='73460bfdfbc3503e0c7d3d7674c857a954429152'
    assert p['independent_human_approval'] is False and p['whole_platform_release_approved'] is False
    assert p['backup_changed'] is False and p['analyzer_configuration_changed'] is False
    assert sha(raw)==p['manifest_after_sha256']
    prior=p['manifest_before_raw'].encode();assert sha(prior)==p['manifest_before_sha256']
    five=json.loads((ROOT/'audit/official_five_source_corrections_20261031.json').read_text())
    assert p['manifest_before_sha256']==five['new_manifest_sha256']
    before,after=json.loads(prior),json.loads(raw)
    assert after['dataset_revision']==p['dataset_revision_after']
    assert len(before['shards'])==len(after['shards'])==24 and after['total_questions']==4800
    assert after['total_uncompressed_bytes']==sum(m['bytes'] for m in after['shards'])
    expected_files={'105-2.json','106-1.json','108-2.json','111-2.json','114-1.json'}
    assert {a['file'] for a,b in zip(before['shards'],after['shards']) if a!=b}==expected_files
    assert set(p['new_shards'])==set(p['old_shards'])==expected_files
    index={r['id']:r for r in rows};assert len(index)==len(rows)==4800
    assert len(lock['mcq'])==4800 and len(lock['essays'])==240
    assert len(p['rows'])==10 and {r['id'] for r in p['rows']}==IDS
    restored=copy.deepcopy(rows);ix={r['id']:r for r in restored};oldlock=copy.deepcopy(lock)
    for c in p['rows']:
        ident=c['id'];old,new=c['published_before'],c['published_after'];s=c['source'];pin=PINNED[ident]
        assert [c['source_after_sha256'],s['question_sha256'],s['answer_sha256'],s['correction_sha256'],s['pdf_page'],new['answer']]==pin
        assert digest({k:new[k] for k in ('question','opt_a','opt_b','opt_c','opt_d')})==pin[0]
        assert s['fresh_source_text_verified'] is True and s['pdf_page_visually_verified'] is True
        fresh=c['fresh_source_checks'];assert fresh['source_text_mismatch_fields']==[]
        assert [fresh['question_sha256'],fresh['standard_answer_sha256'],fresh['correction_sha256']]==pin[1:4]
        assert fresh['final_answer']=={'answer':pin[5]}
        assert index[ident]==new and old['id']==new['id']==ident
        assert all(old[k]==new[k] for k in GRADING+('source_url','source_exam_code','subject','year','round','qno'))
        assert row_hash(canonical_row(old,MCQ_FIELDS))==c['before_core_lock_sha256']
        assert row_hash(canonical_row(new,MCQ_FIELDS))==c['after_core_lock_sha256']==lock['mcq'][ident]
        expected=copy.deepcopy(old);assert set(c['edits'])<=set(('question','opt_a','opt_b','opt_c','opt_d'))
        expected.update(c['edits']);expected.update({k:None for k in ENRICH});expected['analysis_status']='review';assert expected==new
        dbold,dbnew=c['database_before'],c['database_after'];dbexpected=copy.deepcopy(dbold)
        assert len(dbold)==len(dbnew)==37 and all(dbold[k]==v for k,v in old.items()) and all(dbnew[k]==v for k,v in new.items())
        dbexpected.update(c['edits']);dbexpected.update({k:None for k in ENRICH});dbexpected.update(analysis_status='review',analysis_attempts=0,analysis_error=None,analysis_started_at=None,analysis_completed_at=None,analysis_last_attempt_at=None)
        assert dbexpected==dbnew
        ix[ident].clear();ix[ident].update(old);oldlock['mcq'][ident]=c['before_core_lock_sha256']
    assert digest(sorted([r for r in rows if r['id'] not in IDS],key=lambda r:r['id']))==p['unchanged_other_rows_sha256']
    assert digest(sorted([[r['id'],r['answer'],r['accepted_answers'],r['grading_mode']] for r in rows]))==p['grading_tuples_sha256']
    assert digest({k:v for k,v in lock['mcq'].items() if k not in IDS})==p['unchanged_other_mcq_locks_sha256']
    assert digest(lock['essays'])==p['unchanged_essay_locks_sha256']
    for meta,oldmeta in zip(after['shards'],before['shards']):
        b=(ROOT/'cdn/question-shards'/meta['file']).read_bytes();data=json.loads(b)
        assert sha(b)==meta['sha256'] and len(b)==meta['bytes'] and len(data['questions'])==meta['question_count']==200
        assert all(index[r['id']]==r for r in data['questions'])
        ancestor=projected_parent_shard_bytes(meta['file'])
        assert sha(ancestor)==oldmeta['sha256'] and len(ancestor)==oldmeta['bytes']
    return restored,oldlock,prior

def reverse_current(rows,lock,raw):
    return validate_transition(json.loads(P.read_text()),rows,lock,raw)

def main():
    p=json.loads(P.read_text());raw=(ROOT/'cdn/question-shards/manifest.json').read_bytes();rows=[]
    for m in json.loads(raw)['shards']:rows+=json.loads((ROOT/'cdn/question-shards'/m['file']).read_bytes())['questions']
    lock=json.loads((ROOT/'data/official_exam_readonly.lock.json').read_text());validate_transition(p,rows,lock,raw)
    for kind in ('target','answer','other-row','source-url','source-hash','source-page','source-correction','lock','approval','enrichment','manifest','database'):
        cp,rs,lk=copy.deepcopy((p,rows,lock));t=next(r for r in rs if r['id']=='R-111-2-14')
        if kind=='target':t['question']=t['question'].split('\n\n')[-1]
        elif kind=='answer':t['answer']='B'
        elif kind=='other-row':next(r for r in rs if r['id'] not in IDS)['question']+='tamper'
        elif kind=='source-url':t['source_url']='https://example.invalid/'
        elif kind=='source-hash':cp['rows'][0]['source']['question_sha256']='0'*64
        elif kind=='source-page':cp['rows'][0]['source']['pdf_page']=1
        elif kind=='source-correction':next(r for r in cp['rows'] if r['id']=='R-111-2-14')['source']['correction_sha256']=None
        elif kind=='lock':lk['mcq'][t['id']]='0'*64
        elif kind=='approval':cp['independent_human_approval']=True
        elif kind=='enrichment':t['analysis_status']='ready'
        elif kind=='manifest':cp['manifest_after_sha256']='0'*64
        else:cp['rows'][0]['database_after']['analysis_attempts']=9
        try:validate_transition(cp,rs,lk,raw)
        except AssertionError:pass
        else:raise AssertionError('Unauthorized transition accepted: '+kind)
    print('TEN OFFICIAL SOURCE TRANSITION PASS: 10 pinned original source/answer rows; 4790 other full rows, 4800 grades and 240 essay locks preserved; 12 negatives rejected. No independent human approval or whole-platform release approval inferred.')
if __name__=='__main__':main()

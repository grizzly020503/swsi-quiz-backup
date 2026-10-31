#!/usr/bin/env python3
"""Source-locked four-row overlay QA. Reverses ONLY latest four rows for the
older ten/five/shared-case/genogram historical regression chain. Draft, no writes.
"""
import copy
import hashlib
import json
from pathlib import Path
from official_exam_readonly_guard import canonical_row, row_hash, MCQ_FIELDS

ROOT=Path(__file__).resolve().parents[1]
PROOF_PATH=ROOT/'audit/official_four_remaining_source_candidate_20261031.json'
MANIFEST=ROOT/'cdn/question-shards/manifest.json'
LOCK=ROOT/'data/official_exam_readonly.lock.json'
SHARD_DIR=ROOT/'cdn/question-shards'
IDS={'SW-105-2-12','SP108-2-09','DS-108-2-38','DS-109-2-26'}
SHARDS={'105-2.json','108-2.json','109-2.json'}
PDF_HASHES={
 'SW-105-2-12':'6cb957f74ae14d66bb2c0d83a8a61ec741d520e9c5cec08e0c008eb5a0238332',
 'SP108-2-09':'956025f3383d3d721ae428e3dd8a3a97b0abed4026c5ed71bafc6e8a1171ff03',
 'DS-108-2-38':'78e9473d144f9165622f02ac3e5a004658b0ca7dd516c436f56cfdf4042b3e9b',
 'DS-109-2-26':'0351cc6a62bfc1f922ed58cea35cde6b20dde02db4d9768379273ba6baf9798e',
}
CORE_HASHES={
 'SW-105-2-12':'01dcd9cd261ef5d9034941e65fab7372bf8abdcabc50821e788478107cd601e9',
 'SP108-2-09':'fde0f5e5b5bf17456290224114238b96be9206043dc065f7b19f00de3fb5327b',
 'DS-108-2-38':'332f09aa770ebd8030006f446977ea7335f83c980815ea7903768d54486da26c',
 'DS-109-2-26':'b2720a25ee8e06db73aef1d5f31f0c3ee3872b858e8cd8386827250569eecc69',
}
ENRICH=('major','topic','keywords','exp_why','exp_others','exp_trap',
        'exp_raw','mnemonic','extension','law','mistake')
ALLOWED=set(MCQ_FIELDS)|set(ENRICH)|{'analysis_status'}
IMMUTABLE=('id','subject','year','round','qno','source_exam_code','source_url',
           'answer','accepted_answers','grading_mode')
sha=lambda data:hashlib.sha256(data).hexdigest()
encode=lambda data:(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')

def audit():
    return json.loads(PROOF_PATH.read_text(encoding='utf-8'))

def check_proof(p,raw):
    assert p['schema_version']==1 and p['status']=='DRAFT_NO_GO'
    assert p['base_main_sha']=='e3fb69e77870164d3c1e18b89e56878969bc0aee'
    assert p['source_candidate_pr']==506 and p['changed_row_count']==4
    assert p['mcq_total']==4800 and p['essay_total']==240
    assert p['official_grading_preserved'] is True and p['non_target_rows_preserved'] is True
    assert p['independent_human_approval'] is False and p['production_db_written'] is False
    assert p['main_deployed'] is False and p['netlify_backup_changed'] is False
    assert p['pdf_rechecked_in_this_turn'] is False and p['unresolved_pdf_review_baseline']==428
    assert sha(raw)==p['current_manifest_sha256']
    parent=p['parent_manifest_raw'].encode('utf-8')
    previous_ten=json.loads((ROOT/'audit/official_ten_source_release_transition_20261031.json').read_text(encoding='utf-8'))
    assert sha(parent)==previous_ten['manifest_after_sha256']
    before,after=json.loads(parent),json.loads(raw)
    assert before['dataset_revision']=='bcfb073e5672d0b15bd0'
    assert after['dataset_revision']==p['dataset_revision']
    assert before['total_questions']==after['total_questions']==4800
    assert len(before['shards'])==len(after['shards'])==24
    assert before['total_uncompressed_bytes']==sum(z['bytes'] for z in before['shards'])
    assert after['total_uncompressed_bytes']==sum(z['bytes'] for z in after['shards'])
    old_index={z['file']:z for z in before['shards']}
    new_index={z['file']:z for z in after['shards']}
    assert set(old_index)==set(new_index)
    assert {name for name in old_index if old_index[name]!=new_index[name]}==SHARDS
    for name in SHARDS:
        for field in ('sha256','bytes'):
            assert p['parent_three_shards'][name][field]==old_index[name][field]
            assert p['current_three_shards'][name][field]==new_index[name][field]
    assert len(p['changes'])==4 and {r['id'] for r in p['changes']}==IDS
    return parent

def validate_transition(p,rows,lock,raw):
    previous=check_proof(p,raw)
    assert len(rows)==len({r['id'] for r in rows})==4800
    assert len(lock['mcq'])==4800 and len(lock['essays'])==240
    idx={r['id']:r for r in rows}
    restored=copy.deepcopy(rows);back={r['id']:r for r in restored}
    oldlock=copy.deepcopy(lock)
    for item in p['changes']:
        ident=item['id'];old=item['old_public_row'];new=item['new_public_row']
        assert item['official_pdf_sha256']==PDF_HASHES[ident]
        assert item['after_core_sha256']==CORE_HASHES[ident]
        assert item['shard'] in SHARDS
        assert idx[ident]==new and old['id']==new['id']==ident
        assert all(old[k]==new[k] for k in IMMUTABLE)
        actual={k for k in set(old)|set(new) if old.get(k)!=new.get(k)}
        assert actual==set(item['changed_fields']) and actual<=ALLOWED
        assert row_hash(canonical_row(old,MCQ_FIELDS))==item['before_core_sha256']
        assert row_hash(canonical_row(new,MCQ_FIELDS))==item['after_core_sha256']==lock['mcq'][ident]
        if ident in ('SW-105-2-12','SP108-2-09'):
            assert old['analysis_status']=='ready' and new['analysis_status']=='review'
            assert all(new[k] is None for k in ENRICH)
        assert item['grading_unchanged'] is True
        back[ident].clear();back[ident].update(old)
        oldlock['mcq'][ident]=item['before_core_sha256']
    # Historical ten/five/shared-case/genealogy gates subsequently inspect EVERY
    # other row and lock with their original source-bound whole-corpus digest.
    return restored,oldlock,previous

def projected_parent_shard_bytes(filename):
    """Exact current file -> original ten-source release file, no drift accepted."""
    p=audit()
    current=MANIFEST.read_bytes()
    check_proof(p,current)
    raw=(SHARD_DIR/filename).read_bytes()
    after=json.loads(current)
    ent=next(s for s in after['shards'] if s['file']==filename)
    assert sha(raw)==ent['sha256'] and len(raw)==ent['bytes']
    if filename not in SHARDS:
        return raw
    data=json.loads(raw)
    changes={row['id']:row for row in p['changes'] if row['shard']==filename}
    assert changes and len(data['questions'])==200
    found=set()
    for row in data['questions']:
        item=changes.get(row['id'])
        if not item:
            continue
        assert row==item['new_public_row']
        found.add(row['id'])
        row.clear();row.update(item['old_public_row'])
    assert found==set(changes)
    prior=encode(data)
    expected=p['parent_three_shards'][filename]
    assert sha(prior)==expected['sha256'] and len(prior)==expected['bytes']
    return prior

def main():
    p=audit();raw=MANIFEST.read_bytes()
    manifest=json.loads(raw)
    rows=[]
    for ent in manifest['shards']:
        content=(SHARD_DIR/ent['file']).read_bytes()
        assert sha(content)==ent['sha256'] and len(content)==ent['bytes']
        rows.extend(json.loads(content)['questions'])
    locks=json.loads(LOCK.read_text(encoding='utf-8'))
    validate_transition(p,rows,locks,raw)
    for name in SHARDS:
        projected_parent_shard_bytes(name)
    for kind in ('target','answer','other-row','lock','source-sha','false-human','manifest','analysis'):
        proof,rs,lk=copy.deepcopy((p,rows,locks))
        target=next(q for q in rs if q['id']=='SW-105-2-12')
        if kind=='target': target['opt_a']+='TAMPER'
        elif kind=='answer': target['answer']='A'
        elif kind=='other-row': next(q for q in rs if q['id'] not in IDS)['question']+='TAMPER'
        elif kind=='lock': lk['mcq'][target['id']]='0'*64
        elif kind=='source-sha': proof['changes'][0]['official_pdf_sha256']='0'*64
        elif kind=='false-human': proof['independent_human_approval']=True
        elif kind=='manifest': proof['current_manifest_sha256']='0'*64
        elif kind=='analysis': target['analysis_status']='ready'
        try:
            restored,oldlock,parent=validate_transition(proof,rs,lk,raw)
            from official_ten_source_integration_smoke import validate_transition as previous_ten
            previous_ten(json.loads((ROOT/'audit/official_ten_source_release_transition_20261031.json').read_text()),restored,oldlock,parent)
        except AssertionError:
            pass
        else:
            raise AssertionError('Source overlay tamper not rejected: '+kind)
    print('FOUR OFFICIAL SOURCE OVERLAY OK: 4 source-pinned rows, 4796 unrelated rows / 4800 grading / 240 essays guarded; 8 negative cases rejected; DRAFT NO-GO')

if __name__=='__main__':
    main()

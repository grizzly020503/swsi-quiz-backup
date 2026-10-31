#!/usr/bin/env python3
"""Strict three-row MOEX OCR source correction overlay; never approves release.

The added three revisions sit on top of the independently source-backed
8-row PR#499. Reverse only these three source-verified rows/locks and
the manifest before invoking all prior release guards unchanged.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash

ROOT=Path(__file__).resolve().parents[1]
PROOF_FILE=ROOT/'audit/official_next_three_p0_source_candidate_20261031.json'
IDS={'SW-105-2-12','R-105-2-07','DS-106-1-34'}
EXPECTED_SHA={
  'SW-105-2-12':'6cb957f74ae14d66bb2c0d83a8a61ec741d520e9c5cec08e0c008eb5a0238332',
  'R-105-2-07':'6afea97bde8d58d00358d23bc5a31a0372a47f98d60b99ebc8f04495e3e9d836',
  'DS-106-1-34':'9f6d1a64364b25387606e32b8f0a89142ad42fa8e1474c64f712b7e3fad9179c',
}
ENRICH=('major','topic','keywords','exp_why','exp_others','exp_trap','exp_raw',
        'mnemonic','extension','law','mistake')
def digest(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def validate_overlay(p,rows,lock,manifest_raw):
  assert p['schema_version']==1 and p['status']=='NO_GO_SOURCE_BACKED_CANDIDATE'
  assert p['base_integrated_head']=='e956a1595a7344404d23ba7e36346853dd37f678'
  assert p['base_parent_pr']==499
  assert all(p[k] is False for k in ('human_source_approval','production_written','backup_site_changed','source_review_queue_cleared'))
  assert p['all_official_answers_unchanged'] and p['all_grading_tuples_unchanged'] and p['all_other_rows_unchanged']
  assert digest(manifest_raw)==p['new_manifest_sha256']
  previous_manifest_raw=p['old_manifest_raw'].encode('utf-8')
  assert digest(previous_manifest_raw)==p['old_manifest_sha256']
  m=json.loads(manifest_raw);prev_m=json.loads(previous_manifest_raw)
  assert m['dataset_revision']==p['dataset_revision_after'] and len(m['shards'])==24
  assert m['total_questions']==prev_m['total_questions']==4800
  assert m['total_uncompressed_bytes']==sum(meta['bytes'] for meta in m['shards'])
  before_map={x['file']:x for x in prev_m['shards']}
  after_map={x['file']:x for x in m['shards']}
  assert {x for x in before_map if before_map[x]!=after_map[x]}=={'105-2.json','106-1.json'}
  assert len(rows)==len({x['id'] for x in rows})==4800
  assert len(lock['mcq'])==4800 and len(lock['essays'])==240
  assert len(p['changed_rows'])==3 and {x['id'] for x in p['changed_rows']}==IDS
  assert set(p['shards'])=={'cdn/question-shards/105-2.json','cdn/question-shards/106-1.json'}
  indexed={x['id']:x for x in rows}
  ancestor=copy.deepcopy(rows)
  ancestor_index={x['id']:x for x in ancestor}
  ancestor_lock=copy.deepcopy(lock)

  for item in p['changed_rows']:
    id=item['id'];old=item['published_before'];new=item['published_after']
    assert item['source_pdf_sha256']==EXPECTED_SHA[id]
    assert item['printed_pdf_page']==(4 if id=='DS-106-1-34' else 2)
    assert old['id']==new['id']==id and indexed[id]==new
    assert row_hash(canonical_row(old,MCQ_FIELDS))==item['old_core_sha256']
    assert row_hash(canonical_row(new,MCQ_FIELDS))==item['new_core_sha256']==lock['mcq'][id]
    assert old['question']!=new['question'] if id=='R-105-2-07' else old['question']==new['question']
    assert all(old[k]==new[k] for k in ('id','subject','year','round','qno','answer','accepted_answers','grading_mode','source_url','source_exam_code'))
    allowed={'opt_a','opt_b','opt_c','opt_d','question'}
    assert set(item['changed_official_core_fields'])<=allowed
    assert set(item['changed_official_core_fields'])=={key for key in allowed if old[key]!=new[key]}
    expected=copy.deepcopy(old)
    for f in item['changed_official_core_fields']:expected[f]=new[f]
    for f in ENRICH:expected[f]=None
    expected['analysis_status']='review'
    assert expected==new
    assert new['analysis_status']=='review' and all(new[k] is None for k in ENRICH)
    ancestor_index[id].clear();ancestor_index[id].update(old)
    ancestor_lock['mcq'][id]=item['old_core_sha256']

  for meta in m['shards']:
    file=ROOT/'cdn/question-shards'/meta['file']
    raw=file.read_bytes()
    assert digest(raw)==meta['sha256'] and len(raw)==meta['bytes']
    assert len(json.loads(raw)['questions'])==meta['question_count']
    for q in json.loads(raw)['questions']:
      assert q==indexed[q['id']]
  for name in ('105-2.json','106-1.json'):
    current=(ROOT/'cdn/question-shards'/name).read_bytes()
    pair=p['shards']['cdn/question-shards/'+name]
    assert digest(current)==pair['new_sha256'] and len(current)==pair['new_bytes']
    doc=json.loads(current)
    for q in doc['questions']:
      if q['id'] in IDS:
        before=next(x['published_before'] for x in p['changed_rows'] if x['id']==q['id'])
        q.clear();q.update(before)
    old_bytes=(json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
    assert digest(old_bytes)==pair['old_sha256']==before_map[name]['sha256']
    assert len(old_bytes)==pair['old_bytes']==before_map[name]['bytes']
  assert ancestor_lock['essays']==lock['essays']
  assert all(a['answer']==b['answer'] and a['accepted_answers']==b['accepted_answers']
             and a['grading_mode']==b['grading_mode'] for a,b in zip(ancestor,rows))
  return ancestor,ancestor_lock,previous_manifest_raw

def main():
  proof=json.loads(PROOF_FILE.read_text())
  manifest_raw=(ROOT/'cdn/question-shards/manifest.json').read_bytes()
  m=json.loads(manifest_raw);rows=[]
  for meta in m['shards']:
    raw=(ROOT/'cdn/question-shards'/meta['file']).read_bytes()
    assert len(raw)==meta['bytes'] and digest(raw)==meta['sha256']
    rows.extend(json.loads(raw)['questions'])
  lock=json.loads((ROOT/'data/official_exam_readonly.lock.json').read_text())
  validate_overlay(proof,rows,lock,manifest_raw)
  for kind in ('source','answer','target','other-row','lock','approval','manifest','enrichment'):
    p,rs,lk=copy.deepcopy((proof,rows,lock))
    target=next(x for x in rs if x['id']=='SW-105-2-12')
    if kind=='source':p['changed_rows'][0]['source_pdf_sha256']='0'*64
    elif kind=='answer':target['answer']='A'
    elif kind=='target':target['opt_a']+='tamper'
    elif kind=='other-row':next(x for x in rs if x['id'] not in IDS)['question']+='tamper'
    elif kind=='lock':lk['mcq'][target['id']]='0'*64
    elif kind=='approval':p['human_source_approval']=True
    elif kind=='manifest':p['new_manifest_sha256']='0'*64
    else:target['analysis_status']='ready'
    try:validate_overlay(p,rs,lk,manifest_raw)
    except AssertionError:pass
    else:raise AssertionError('Invalid official-core tamper accepted: '+kind)
  print('MOEX THREE-ROW OCR QA PASS: 3 original PDFs source-SHA-bound, 4797 unrelated full rows unchanged, 4800 grading tuples, 240 essay locks, 8 tamper cases rejected; human approval HOLD')

if __name__=='__main__':main()

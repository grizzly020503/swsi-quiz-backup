#!/usr/bin/env python3
"""Fail-closed two-question owner-approved MOEX release guard (NO DB WRITES).

The approval is for five exact original PDF option text fields, not for other
104-1 source holds, answers, essays, AI scoring or any backup repository.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash

ROOT=Path(__file__).resolve().parents[1]
SHARDS=ROOT/'cdn/question-shards'
M=SHARDS/'manifest.json'
LOCK=ROOT/'data/official_exam_readonly.lock.json'
BACKUP=ROOT/'audit/official_two_owner_authorization_and_37_column_preimages_20261105.json'
PAPER=ROOT/'data/moex_source_subjects.v1.json'
HTML=ROOT/'cdn/index.html'
RELEASED={
 'R-107-2-40':{'file':'107-2.json','answer':'D','options':{'opt_d':'兩個變項間有高度相關，則非常可能有因果關係'},'core':'e8b9b605905e6a58de81aec57fcda9ff593e7c146f662d3b39c34b340c08b418','source':'65fc5955c9a6190db3a4792eb0889678d958e856e544ecaa8c22c86cf952468d'},
 'SP111-2-34':{'file':'111-2.json','answer':'C','options':{'opt_a':'1 至 3 個月','opt_b':'2 至 4 個月','opt_c':'3 至 6 個月','opt_d':'4 至 6 個月'},'core':'fd5542b3d9c391f96bb9345855fc7002c6ab40c9279a7a732ec4fa477df91f5d','source':'9a4afe4df13a7b88582efa0bb3950ccdb3780ec5c7e3380afabe8b0e8f2e3a0d'}
}
REMAIN=('DS-104-1-22','DS-104-1-27','DS-104-1-29')
META=('major','topic','keywords','exp_why','exp_others','exp_trap','exp_raw','mnemonic','extension','law','mistake')
EXACT_RELEASE_SHARDS={'107-2.json':'d946241685411c3c2303ab28be2ad17f362af2fbbd8221946b6e9ca90311341f','111-2.json':'105c1e38104dbc28aa34d3501496132f53caa4f739ab4c9fa7a43bbe19b17bed'}
BASE_4798='a4a2a7c6f52ec7da45523071a209d420931faf1ce0051c4d6f08de1e509f7ed7'
ESSAYS_240='9f4067690e856f54bef439e806f05f64ebb1e0c7b90e59f0c0798fa779c6870d'
UNTOUCHED_SHARDS='6f0cfcc8988972a9513841d7e27ed7192879be13ddea938e4c47a80f6c24799f'

def require(test,reason):
 if not test: raise AssertionError('OWNER-APPROVED TWO-MOEX RELEASE NO-GO: '+reason)
def digest(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def inventory_digest(items):
 return digest('\n'.join(f'{k}:{v}' for k,v in sorted(items.items())).encode('utf-8'))
def verify():
 approval=json.loads(BACKUP.read_text(encoding='utf-8'))
 require(approval.get('owner_authorization_recorded_in_chat') is True,'owner scope authorization missing')
 require(approval.get('student_user_data_saved') is False and approval.get('netlify_backup_touched') is False,'student/backup protection')
 require(approval.get('grade_tuple_must_not_change') is True,'grading gate removed')
 require(set(approval.get('owner_authorized_fields',{}))==set(RELEASED),'exact release scope')
 require(len(approval.get('preimages',[]))==2,'exact full DB rollback snapshots')
 registry=json.loads(PAPER.read_text(encoding='utf-8'))['records']
 for id,meta in RELEASED.items():
  b=next((x for x in approval['preimages'] if x['id']==id),None)
  require(b and len(b['before_row'])==37,'37-column rollback snapshot '+id)
  require(b['before_row']['answer']==meta['answer'] and
          approval['owner_authorized_fields'][id]==sorted(meta['options']), 'scope/grading mismatch '+id)
  paper=next((x for x in registry if x['url'].split('?')[0] ==
      approval['source_pdf_urls'][0].split('?')[0] and x['pdf_sha256']==meta['source']),None)
  require(paper is not None,'original MOEX PDF registry identity '+id)
 m=json.loads(M.read_text(encoding='utf-8'))
 require(m['dataset_revision']=='cf421a2ab378b68322f7' and m['total_questions']==4800 and
         len(m['shards'])==24 and m['total_uncompressed_bytes']==7623799,'release manifest/version')
 require('owner-approved' in m['source'],'source release provenance')
 allrows={}
 others={}
 sizes=0
 for f in m['shards']:
  name=f['file'];data=(SHARDS/name).read_bytes()
  require(len(data)==f['bytes'] and digest(data)==f['sha256'],'physical shard mismatch '+name)
  sizes+=len(data)
  rows=json.loads(data)['questions']
  require(len(rows)==f['question_count']==200,'incorrect 200-row session '+name)
  if name in EXACT_RELEASE_SHARDS:
   require(f['sha256']==EXACT_RELEASE_SHARDS[name],'two source physical SHA drift '+name)
  else: others[name]=f['sha256']
  for row in rows:
   id=row['id'];require(id not in allrows,'duplicate id '+id);allrows[id]=row
 require(len(allrows)==4800 and sizes==7623799,'all 4800 rows total')
 require(inventory_digest(others)==UNTOUCHED_SHARDS,'unrelated 22 source shards changed')
 lock=json.loads(LOCK.read_text(encoding='utf-8'))
 require(lock['mcq_count']==4800 and lock['essay_count']==240 and len(lock['mcq'])==4800 and len(lock['essays'])==240,'Official Core count')
 require(inventory_digest({k:v for k,v in lock['mcq'].items() if k not in RELEASED})==BASE_4798,'other 4798 official MCQ hashes changed')
 require(inventory_digest(lock['essays'])==ESSAYS_240,'240 original essay locks changed')
 for id,row in allrows.items():
  require(row_hash(canonical_row(row,MCQ_FIELDS))==lock['mcq'].get(id),'official core lock drift '+id)
 for id,meta in RELEASED.items():
  q=allrows[id]
  require(lock['mcq'][id]==meta['core'] and q['answer']==meta['answer'] and
          q['accepted_answers'] is None and q['grading_mode']=='standard' and
          q['analysis_status']=='review','unapproved grade/review state '+id)
  require(all(q[key]==val for key,val in meta['options'].items()),'original MOEX option mismatch '+id)
  require(all(q.get(key) is None for key in META),'stale AI enrichment exposed '+id)
  before=next(x['before_row'] for x in approval['preimages'] if x['id']==id)
  for field in q:
   if field in meta['options'] or field in META or field=='analysis_status':continue
   require(q[field]==before[field],'unapproved original field drift '+id+'/'+field)
 html=HTML.read_text(encoding='utf-8')
 hold="const SWSI_SOURCE_HOLD_IDS=Object.freeze(['DS-104-1-22','DS-104-1-27','DS-104-1-29']);"
 require(html.count(hold)==1,'only three unapproved holds may remain')
 for id in REMAIN:
  require(id in allrows and allrows[id]['analysis_status'] in ('ready','review'),'original three sources unexpectedly changed')
 print('MOEX TWO-SOURCE OWNER RELEASE STATIC QA PASS: 2 approved/3 held; 4798 other MCQ locks and 240 essays frozen; 22 unrelated shards untouched; no DB writes')
if __name__=='__main__':verify()

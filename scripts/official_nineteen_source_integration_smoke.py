#!/usr/bin/env python3
"""NO-GO: prove 8 new MOEX rows over 11 previous; run inherited QA on exact restored parent."""
import copy,hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
from official_exam_readonly_guard import canonical_row,row_hash,MCQ_FIELDS
ROOT=Path(__file__).resolve().parents[1]
FILES=('104-1.json','106-1.json','108-2.json','109-2.json')
def h(b):return hashlib.sha256(b).hexdigest()
def bjson(x,indent=None):return (json.dumps(x,ensure_ascii=False,indent=indent,separators=(',',':') if indent is None else None)+'\n').encode()
def main():
 p=json.loads((ROOT/'audit/official_nineteen_row_integration_20261031.json').read_bytes())
 assert p['scope']=='SWSI_OFFICIAL_NINETEEN_SOURCE_CANDIDATE' and p['parent_head_sha']=='ad9d0b711170dfdcb0a72496cf4b8f8da6670a5e'
 assert p['source_prs']==[503,502,500] and len(p['eight_ids'])==8
 assert all(v is False for k,v in p.items() if k in ('answers_changed','essay_changed','backup_changed','release_approved','production_committed','review_428_cleared'))
 audits={}
 for path,sha in p['source_hashes'].items():
  raw=(ROOT/path).read_bytes();assert h(raw)==sha,path;audits[path]=json.loads(raw)
 f=audits['audit/official_five_source_corrections_20261031.json'];t=audits['audit/official_three_truncations_20261031.json']
 assert len(f['rows'])==5 and len(t['records'])==3
 assert not f['human_approval'] and not t['human_approval'] and not f['release_approved'] and not t['release_approved']
 edits=[(x['id'],x['file'],x['published_before'],x['published_after'],x['before_core_lock_sha256'],x['after_core_lock_sha256']) for x in f['rows']]
 edits.extend((x['id'],'109-2.json' if x['id']=='DS-109-2-26' else '108-2.json',x['published_before'],x['published_after'],x['before_core_sha256'],x['after_core_sha256']) for x in t['records'])
 assert sorted(x[0] for x in edits)==p['eight_ids'] and len(set(p['eight_ids']))==8
 mraw=(ROOT/'cdn/question-shards/manifest.json').read_bytes();assert h(mraw)==p['final_manifest_sha256']
 manifest=json.loads(mraw);base_raw=p['base_manifest'].encode();assert h(base_raw)==p['base_manifest_sha256']
 base=json.loads(base_raw);assert len(manifest['shards'])==len(base['shards'])==24 and manifest['total_questions']==base['total_questions']==4800
 current={q['file']:q for q in manifest['shards']};older={q['file']:q for q in base['shards']}
 assert {n for n in older if older[n]!=current[n]}==set(FILES)
 assert manifest['total_uncompressed_bytes']==sum(q['bytes'] for q in manifest['shards'])
 lockbytes=(ROOT/'data/official_exam_readonly.lock.json').read_bytes();assert h(lockbytes)==p['final_lock_sha256']
 lock=json.loads(lockbytes);assert len(lock['mcq'])==4800 and len(lock['essays'])==240
 rows={};shards={}
 for ent in manifest['shards']:
  name=ent['file'];raw=(ROOT/'cdn/question-shards'/name).read_bytes();assert h(raw)==ent['sha256'] and len(raw)==ent['bytes']
  obj=json.loads(raw);assert len(obj['questions'])==200
  shards[name]=obj
  for q in obj['questions']:
   assert q['id'] not in rows;rows[q['id']]=q
   assert row_hash(canonical_row(q,MCQ_FIELDS))==lock['mcq'][q['id']]
 assert len(rows)==4800
 previous_lock=copy.deepcopy(lock);previous_rows={}
 for ident,name,before,after,oldsha,newsha in edits:
  assert rows[ident]==after and name in FILES
  assert row_hash(canonical_row(before,MCQ_FIELDS))==oldsha
  assert row_hash(canonical_row(after,MCQ_FIELDS))==newsha==lock['mcq'][ident]
  assert all(before[k]==after[k] for k in ('answer','accepted_answers','grading_mode','source_url','source_exam_code','id'))
  assert after['analysis_status']=='review'
  previous_rows[ident]=before;previous_lock['mcq'][ident]=oldsha
 assert h(bjson(previous_lock,2))==p['base_lock_sha256']
 restored={}
 for name in FILES:
  assert p['previous_shards'][name]=={'sha256':older[name]['sha256'],'bytes':older[name]['bytes']}
  assert p['final_shards'][name]=={'sha256':current[name]['sha256'],'bytes':current[name]['bytes']}
  obj=copy.deepcopy(shards[name])
  for n,q in enumerate(obj['questions']):
   if q['id'] in previous_rows:obj['questions'][n]=previous_rows[q['id']]
  raw=bjson(obj);assert h(raw)==older[name]['sha256'] and len(raw)==older[name]['bytes']
  restored[name]=raw
 with tempfile.TemporaryDirectory(prefix='swsi_moex19_') as td:
  dest=Path(td)/'repo';shutil.copytree(ROOT,dest,ignore=shutil.ignore_patterns('.git','node_modules','.venv','_site','__pycache__'))
  for name,raw in restored.items():(dest/'cdn/question-shards'/name).write_bytes(raw)
  (dest/'cdn/question-shards/manifest.json').write_bytes(base_raw)
  (dest/'data/official_exam_readonly.lock.json').write_bytes(bjson(previous_lock,2))
  for f in ('official_next_three_p0_source_smoke.py','official_eight_p0_pdf_review_crosswalk_smoke.py','official_428_review_priority_queue_smoke.py','official_r105138_pdf_visual_nochange_smoke.py','official_111_2_shared_context_six_smoke.py','official_two_row_p0_candidate_smoke.py','official_shared_context_13row_integration_smoke.py','official_figure_ui_qa.py','official_exam_readonly_guard.py'):
   r=subprocess.run([sys.executable,'scripts/'+f],cwd=dest,text=True,capture_output=True,timeout=80)
   if r.returncode:raise AssertionError('Inherited QA failure '+f+': '+r.stdout+' '+r.stderr)
 print('MOEX 19 ROW INTEGRATION PASS: 8 additional source-locked, 11 prior unchanged, 4800 grades/240 essays intact; inherited 428-review HOLD verified')
if __name__=='__main__':main()

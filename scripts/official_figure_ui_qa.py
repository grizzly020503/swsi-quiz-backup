#!/usr/bin/env python3
"""Offline source-backed official graphic integration guard. No network access."""
import hashlib, json, struct
from pathlib import Path
R=Path(__file__).resolve().parents[1]
j=json.loads((R/'data/official_figure_assets.v1.json').read_text())
assert j['schema_version']==1 and len(j['figures'])==2
assert j['official_core_modified'] is False and j['answer_grading_modified'] is False
assert j['release_approved'] is False
for row in j['figures']:
    raw=(R/row['path']).read_bytes()
    assert raw.startswith(b'\x89PNG\r\n\x1a\n'),row['id']+' missing PNG magic'
    assert hashlib.sha256(raw).hexdigest()==row['published_png_sha256'],row['id']+' hash mismatch'
    assert struct.unpack('>II',raw[16:24])==(row['width'],row['height']),row['id']+' dimensions mismatch'
    for tree in ('', 'cdn/'):
        twin=(R/tree/row['path']).read_bytes()
        assert twin==raw,row['id']+' root/CDN visual mismatch'
for html in ('index.html','cdn/index.html'):
    s=(R/html).read_text()
    for needle in ("function swsiOfficialFigureMarkup", "swsiOfficialFigureMarkup(item)",
                   "swsiOfficialFigureMarkup(q)", "swsiOfficialFigureReady(Q[idx])",
                   "var gradedTotal=Q.length-excluded", "swsiOfficialFigureQuestion(q)"):
        assert needle in s,html+' missing '+needle
    for row in j['figures']:
        assert s.count("'"+row['id']+"'")>=1,html+' missing '+row['id']
# The maintained runtime overrides the legacy HTML renderer. Guard that owner too.
runtime=(R/'monthly_patch_parts/00.part').read_text()
for needle in ("const figureReady=swsiOfficialFigureReady(item)",
               "swsiOfficialFigureMarkup(item)", "if(!figureReady)optHTML=",
               "if(!selected || !swsiOfficialFigureReady(queue[idx])) return;"):
    assert needle in runtime,'canonical runtime missing '+needle
mock=(R/'monthly_patch_parts/zzzzzzzzzzzzzzzzzzzzzzzzzzz_mk_grading_contract.part').read_text()
for needle in ("function figureReady(q)", "figureMarkup(q)+options", "total:rows.length-excluded", "if(!figureReady(q))return;"):
    assert needle in mock,'effective mock runtime missing '+needle
for name in ('sw.js','cdn/sw.js'):
    sw=(R/name).read_text()
    for row in j['figures']:
        assert "./"+row['path'] in sw,name+' does not precache '+row['id']
# Owner froze the backup site: candidate must retain the exact main config.
assert hashlib.sha256((R/'netlify.toml').read_bytes()).hexdigest()=='3ae451ea75b48614db95e7438e675deb7a43354cb0324711150754cd805483a5','backup configuration must remain frozen'
# Primary Workers assets are the tracked CDN tree; no preview/deploy action.
assert '"directory": "./cdn"' in (R/'wrangler.jsonc').read_text()
# The CI local _site build must include assets used by the service worker's
# atomic cache.addAll; a missing file otherwise blocks SW installation.
launch=(R/'.github/workflows/launch-readiness-qa.yml').read_text()
assert 'mkdir -p _site/icons _site/official-figures' in launch
assert 'cp official-figures/*.png _site/official-figures/' in launch

# One independently source-backed raw question correction follows the released
# figure UI. Keep the other 4,799 full rows, all answers and all essay locks exact.
import copy
from official_exam_readonly_guard import canonical_row, row_hash, MCQ_FIELDS
def canonical_digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def validate_core_transition(proof, rows, lock):
    ident='DS-113-2-13'
    assert proof['id']==ident and proof['base_main']=='12b84b4adeca779b38fbc5fb6da71a5ab11f9c87'
    assert proof['source']['pdf_sha256']=='21b47d133e072b34eab4f07fa95ffab1601d54768eb8cedf680a9471fc9bfbc3'
    stem='有關下圖案母與案主之間的關係狀況，下列何者正確？'
    assert proof['source']['official_stem']==stem and proof['source']['pdf_page_number']==3
    before,after=proof['published_before'],proof['published_after']
    assert before['question']==stem+'（圖示：62 歲男性與 24 歲女兒之間以鋸齒線連結）'
    assert after['question']==stem
    assert proof['before_core_lock_sha256']=='76ca5f940cd3d9dc7e6eae1a773ccc323f46fa9e4ea879fa0091082dc940c739'
    assert row_hash(canonical_row(before,MCQ_FIELDS))==proof['before_core_lock_sha256']
    assert row_hash(canonical_row(after,MCQ_FIELDS))==proof['after_core_lock_sha256']
    assert all(before[k]==after[k] for k in MCQ_FIELDS if k!='question')
    assert all(before[k]==after[k] for k in ('answer','accepted_answers','grading_mode','source_exam_code','source_url'))
    assert after['analysis_status']=='review'
    assert all(after[k] is None for k in ('major','topic','keywords','exp_why','exp_others','exp_trap','exp_raw','mnemonic','extension','law','mistake'))
    assert proof['official_answer_changed'] is False and proof['independent_human_approval'] is False
    assert proof['whole_platform_release_approved'] is False
    indexed={r['id']:r for r in rows}
    assert len(rows)==len(indexed)==4800 and indexed[ident]==after
    assert canonical_digest(sorted([r for r in rows if r['id']!=ident],key=lambda x:x['id']))==proof['unchanged_other_rows_sha256']
    assert canonical_digest(sorted([[r['id'],r['answer'],r['accepted_answers'],r['grading_mode']] for r in rows]))==proof['grading_tuples_sha256']
    assert lock['mcq'][ident]==proof['after_core_lock_sha256']
    assert canonical_digest({k:v for k,v in lock['mcq'].items() if k!=ident})==proof['unchanged_other_mcq_locks_sha256']
    assert canonical_digest(lock['essays'])==proof['unchanged_essay_locks_sha256']

proof_path=R/'audit/official_genogram_core_transition_20261031.json'
proof=json.loads(proof_path.read_text())
manifest_raw=(R/'cdn/question-shards/manifest.json').read_bytes()
manifest=json.loads(manifest_raw)
all_rows=[]
for meta in manifest['shards']:
    raw=(R/'cdn/question-shards'/meta['file']).read_bytes()
    assert len(raw)==meta['bytes'] and hashlib.sha256(raw).hexdigest()==meta['sha256']
    all_rows.extend(json.loads(raw)['questions'])
lock=json.loads((R/'data/official_exam_readonly.lock.json').read_text())
# Validate the newer, explicitly source-backed transition and reverse only its
# thirteen exact rows/locks before running the unchanged historical guard.
# No unrelated-row allowance or old-genogram quarantine is weakened.
from official_shared_context_13row_integration_smoke import validate_transition
shared_proof=json.loads((R/'audit/official_shared_context_release_transition_20261031.json').read_text())
from official_two_row_p0_candidate_smoke import validate_overlay
p0_proof=json.loads((R/'audit/official_two_row_p0_candidate_20261031.json').read_text())
from official_111_2_shared_context_six_smoke import validate_overlay as reverse_six
six_proof=json.loads((R/'audit/official_111_2_shared_context_six_20261031.json').read_text())
all_rows,lock,manifest_raw=reverse_six(six_proof,all_rows,lock,manifest_raw)
all_rows,lock,manifest_raw=validate_overlay(p0_proof,all_rows,lock,manifest_raw)
all_rows,lock,manifest_raw=validate_transition(shared_proof,all_rows,lock,manifest_raw)
assert hashlib.sha256(manifest_raw).hexdigest()==proof['manifest_after_sha256']
assert json.loads(manifest_raw)['dataset_revision']==proof['dataset_revision_after']
validate_core_transition(proof,all_rows,lock)
for kind in ('question','answer','unrelated-row','unrelated-lock','source'):
    p,rs,lk=copy.deepcopy((proof,all_rows,lock))
    target=next(r for r in rs if r['id']==p['id'])
    if kind=='question': target['question']+='tamper'
    elif kind=='answer': target['answer']='A'
    elif kind=='unrelated-row': next(r for r in rs if r['id']!=p['id'])['question']+='tamper'
    elif kind=='unrelated-lock': lk['mcq'][next(k for k in lk['mcq'] if k!=p['id'])]='0'*64
    else: p['source']['pdf_sha256']='0'*64
    try:
        validate_core_transition(p,rs,lk)
    except AssertionError:
        pass
    else:
        raise AssertionError('controlled correction accepted tamper: '+kind)
print('GENOGRAM CORE TRANSITION QA OK: 1 official stem; 4,799 full rows / 4,800 grading tuples / 240 essays preserved; 5 negative cases rejected')
print('OFFICIAL FIGURES UI QA OK: source-backed 2 image assets, root/CDN parity, grading guard, mock/quiz image gates and PWA pre-cache; human approval pending')

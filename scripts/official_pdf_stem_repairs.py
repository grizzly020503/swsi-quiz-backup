#!/usr/bin/env python3
"""Validate/reproduce two PDF-backed stem repairs and project the prior41 audit.

Projection is in memory only; original proofs and release holds remain enforced.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from official_exam_readonly_guard import canonical_row, row_hash, MCQ_FIELDS
from official_essay_pdf_audit import normalize

ROOT = Path(__file__).resolve().parents[1]
PROOF_PATH = 'audit/official_pdf_stem_repairs_20261029.json'
PROOF_SHA256 = '682f9c19efd70464954754ab9885ed3d69750f056358d5c404bcc262bc34377d'
REPAIR_IDS = {'R-106-2-01', 'SW-110-1-33'}
MANIFEST = 'cdn/question-shards/manifest.json'
LOCK = 'data/official_exam_readonly.lock.json'
QUARANTINE_FIELDS = ('major','topic','keywords','exp_why','exp_others','exp_trap','exp_raw','mnemonic','extension','law','mistake')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def stable(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n').encode()


def fingerprint(value):
    return digest(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())


def load_proof(root=ROOT):
    raw = (Path(root) / PROOF_PATH).read_bytes()
    require(digest(raw) == PROOF_SHA256, 'stem repair proof drift')
    proof = json.loads(raw)
    require(proof['count'] == len(proof['rows']) == 2 and {r['id'] for r in proof['rows']} == REPAIR_IDS, 'stem repair scope drift')
    require(all(proof[k] is False for k in ('human_approval','release_approved','production_write','backup_operation')), 'stem repair approval drift')
    return proof


def validate_item(item, observed, current, registry, transport):
    ident = item['id']; before = item['before']; after = item['after']
    require(ident in REPAIR_IDS and ident == before['id'] == after['id'] == observed['id'], 'repair identity drift')
    require(observed['status'] == 'review' and observed['answer_comparison_completed'] is True and observed.get('answer_difference') is None, 'unresolved official answer')
    require(fingerprint(observed) == item['baseline_comparison_row_sha256'] and observed['text_differences'] == item['baseline_differences'], 'repair baseline drift')
    require(current == after and before != after, 'repair current row drift')
    allowed = {'question', 'analysis_status'} | set(QUARANTINE_FIELDS)
    require({f for f in before.keys() | after.keys() if before.get(f) != after.get(f)} <= allowed, 'unapproved repair field')
    require({f for f in MCQ_FIELDS if before.get(f) != after.get(f)} == {'question'}, 'repair core scope')
    require(all(before.get(f) == after.get(f) == item['official_answer_rule'][f] for f in ('answer','accepted_answers','grading_mode')), 'repair grading drift')
    require(all(after[f] is None for f in QUARANTINE_FIELDS) and after['analysis_status'] == 'review', 'stale repair explanation')
    require(row_hash(canonical_row(before,MCQ_FIELDS)) == item['before_lock_sha256'] and row_hash(canonical_row(after,MCQ_FIELDS)) == item['after_lock_sha256'], 'repair lock drift')
    require(item['human_approval'] is False and item['official_transcription'] == after['question'], 'repair approval/transcription drift')
    expected_pages = {'R-106-2-01':('4-1',1), 'SW-110-1-33':('4-4',4)}
    require((item['printed_page'],item['pdf_page_number']) == expected_pages[ident] and item['answer_page'] == 1, 'repair page drift')
    from audit_moex_source_subjects import require_source
    source = require_source(registry, after['source_exam_code'], after['subject'], item['question_source_url'])
    require(source['pdf_sha256'] == item['question_pdf_sha256'] == observed['question_pdf_sha256'] and item['question_source_url'] == observed['question_source_url'], 'repair question PDF mismatch')
    candidates = [r for r in transport if r['exam_code'] == after['source_exam_code'] and r['subject'] == after['subject']]
    final = next((r for r in candidates if r['kind']=='M'), next(r for r in candidates if r['kind']=='S'))
    require(final['status']=='downloaded' and final['http_status']==200 and 'pdf' in final['mime'].lower() and final['sha256']==item['answer_pdf_sha256']==observed['answer_pdf_sha256'] and final['url']==item['answer_source_url']==observed['answer_source_url'], 'repair answer PDF mismatch')
    diffs = observed['text_differences']
    require(set(diffs) == {'question'} and diffs['question']['stored'] == before['question'], 'repair original text mismatch')
    require(normalize(after['question']) == normalize(diffs['question']['official_extraction']), 'repair not official extracted text')
    if ident == 'R-106-2-01':
        prefix = '在研究過程中，透過研究工具如問卷或訪問稿蒐集資料，這是一系列從無到有的過程，如果要測量一些'
        require(item['classification']=='missing_opening_clause' and after['question'] == prefix + before['question'], 'unverified opening clause')
    else:
        expected = before['question'].replace('19 ④世紀','④19 世紀').replace('1950 ⑤年代','⑤1950 年代')
        require(item['classification']=='circled_marker_numeric_order' and after['question'] == expected and '④19 世紀' in after['question'] and '⑤1950 年代' in after['question'], 'unverified numeric marker order')


def validated_ids(report, root=ROOT):
    root = Path(root); proof = load_proof(root)
    require(digest((root / 'audit/official_mcq_pdf_comparison_20261025.json').read_bytes()) == proof['baseline_comparison_sha256'], 'stem baseline report drift')
    from audit_moex_source_subjects import load_registry
    registry = load_registry()
    transport = json.loads((root / 'data/moex_answer_sources.v1.json').read_text())['records']
    observed = {r['id']:r for r in report['rows']}
    for item in proof['rows']:
        after = item['after']; name = str(after['year']) + ('-1.json' if after['round']=='第一次' else '-2.json')
        current = next(q for q in json.loads((root / 'cdn/question-shards' / name).read_text())['questions'] if q['id']==item['id'])
        validate_item(item, observed[item['id']], current, registry, transport)
    return set(REPAIR_IDS)


def previous_bytes(root, previous_report):
    """Verify current43 bytes and return the four exact prior41 byte streams."""
    root = Path(root); proof = load_proof(root)
    require(set(proof['output_sha256']) == set(previous_report['output_sha256']), 'repair output scope drift')
    for path, expected in proof['output_sha256'].items():
        require(digest((root / path).read_bytes()) == expected, 'combined payload drift: ' + path)
    report = json.loads((root / 'audit/official_mcq_pdf_comparison_20261025.json').read_text())
    validated_ids(report, root)
    manifest = json.loads((root / MANIFEST).read_text())
    require(manifest == proof['manifest_after'], 'repair manifest drift')
    payloads = {e['file']:json.loads((root / 'cdn/question-shards' / e['file']).read_text()) for e in manifest['shards']}
    rows = {q['id']:q for p in payloads.values() for q in p['questions']}
    require(len(rows)==4800 and sum(len(p['questions']) for p in payloads.values())==4800, 'repair coverage drift')
    require(fingerprint({i:q for i,q in rows.items() if i not in REPAIR_IDS}) == proof['unchanged_other_rows_sha256'], 'other4798 rows changed')
    require(fingerprint({i:{f:q.get(f) for f in ('answer','accepted_answers','grading_mode')} for i,q in rows.items()}) == proof['grading_map_sha256'], 'all4800 grading drift')
    lock = json.loads((root / LOCK).read_text())
    require(fingerprint(lock['essays']) == proof['essay_locks_sha256'], 'essay locks changed')
    projected = {MANIFEST:stable(proof['manifest_before'])}
    for item in proof['rows']:
        ident = item['id']; after = item['after']; name = str(after['year']) + ('-1.json' if after['round']=='第一次' else '-2.json')
        require(lock['mcq'][ident] == item['after_lock_sha256'], 'repair actual lock drift')
        payload = payloads[name]
        payload['questions'] = [deepcopy(item['before']) if q['id']==ident else q for q in payload['questions']]
        projected['cdn/question-shards/' + name] = stable(payload)
        lock['mcq'][ident] = item['before_lock_sha256']
    projected[LOCK] = (json.dumps(lock,ensure_ascii=False,indent=2)+'\n').encode()
    for path, raw in projected.items():
        require(digest(raw)==previous_report['output_sha256'][path], 'repair preimage bytes drift: '+path)
    return projected


def reproduce(out):
    out=Path(out).resolve()
    require(out!=ROOT and ROOT not in out.parents and not out.exists(), 'fresh output outside repository required')
    proof=load_proof(); output={}
    for path in proof['output_sha256']:
        output[path]=subprocess.run(['git','show',proof['base_commit']+':'+path],cwd=ROOT,check=True,capture_output=True,timeout=30).stdout
    lock=json.loads(output[LOCK]); changed={}
    for item in proof['rows']:
        after=item['after'];name='cdn/question-shards/'+str(after['year'])+('-1.json' if after['round']=='第一次' else '-2.json')
        payload=changed.setdefault(name,json.loads(output[name]))
        prior=next(q for q in payload['questions'] if q['id']==item['id'])
        require(prior==item['before'] and lock['mcq'][item['id']]==item['before_lock_sha256'], 'reproduce stale preimage')
        payload['questions']=[deepcopy(after) if q['id']==item['id'] else q for q in payload['questions']]
        lock['mcq'][item['id']]=item['after_lock_sha256']
    for path,payload in changed.items():output[path]=stable(payload)
    output[MANIFEST]=stable(proof['manifest_after']);output[LOCK]=(json.dumps(lock,ensure_ascii=False,indent=2)+'\n').encode()
    require({p:digest(raw) for p,raw in output.items()}==proof['output_sha256'], 'reproduce output drift')
    for path,raw in output.items():
        target=out/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    return {'mcq':4800,'cumulative_core_changes':43,'grading_preserved':4800,'dataset_revision':proof['manifest_after']['dataset_revision'],'release_approved':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reproduce',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(reproduce(args.reproduce)))

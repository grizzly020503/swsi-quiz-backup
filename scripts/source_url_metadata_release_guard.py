#!/usr/bin/env python3
"""PR-only fail-closed validation for SWSI's 3,920 MOEX source URL metadata patch.

Does not update database or authorize production deployment. Runs with no network access.
Expected: 22 historical CDN JSON files, exactly 3,920 URL-only changes,
all other 4,800 question fields unchanged, manifest integrity preserved.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, subprocess, sys
from urllib.parse import urlsplit, parse_qs

ROOT = pathlib.Path(__file__).resolve().parents[1]
RECEIPT = ROOT / 'data' / 'source_url_3920_release_receipt.json'
SHARDS = ROOT / 'cdn' / 'question-shards'

def blob(raw: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()

def fail(message: str) -> None:
    raise ValueError(message)

def old_file(path: str, base_ref: str | None, before_dir: pathlib.Path | None) -> bytes:
    if before_dir is not None:
        return (before_dir / path).read_bytes()
    if not base_ref:
        fail('missing before revision')
    return subprocess.check_output(['git', 'show', f'{base_ref}:{path}'], cwd=ROOT)

def identity(value: str, expected_code: str) -> None:
    p = urlsplit(value)
    if p.scheme != 'https' or p.netloc != 'wwwq.moex.gov.tw' or p.path != '/exam/wHandExamQandA_File.ashx':
        fail('unexpected official source origin')
    query = parse_qs(p.query, strict_parsing=True)
    if set(query) != {'c', 's', 't', 'q', 'code'} or any(len(v)!=1 for v in query.values()):
        fail('duplicate/extra URL parameter')
    if query['code'][0] != expected_code or query['t'] != ['Q'] or query['q'] != ['1']:
        fail('unexpected exam/question source identity')
    if not (query['c'][0].isdigit() and query['s'][0].isdigit()):
        fail('bad class/subject code')

def check(base_ref: str | None, before_dir: pathlib.Path | None) -> dict:
    receipt = json.loads(RECEIPT.read_text(encoding='utf-8'))
    if receipt['status'] != 'REVIEW_ONLY_DB_CDN_NOT_SYNCHRONIZED':
        fail('release still requires synchronized DB/CDN review')
    if receipt['baseline_manifest_revision'] != 'f31eaa32ada9649cc289' or receipt['candidate_manifest_revision'] != 'ceda1d399abaecec5ff6':
        fail('receipt revision drift')
    expected = receipt['files']; assert len(expected) == 23
    changed, scanned, unchanged, changes_by_file = 0, 0, 0, {}
    for path, pins in sorted(expected.items()):
        original = old_file(path, base_ref, before_dir)
        new = (ROOT / path).read_bytes()
        if blob(original) != pins['before_git_blob'] or blob(new) != pins['after_git_blob']:
            fail('Git blob digest mismatch at '+path)
        if hashlib.sha256(new).hexdigest() != pins['after_sha256']:
            fail('SHA256 mismatch at '+path)
        if path.endswith('manifest.json'):
            a, b = json.loads(original), json.loads(new)
            continue
        old, current = json.loads(original), json.loads(new)
        if len(old['questions'])!=200 or len(current['questions'])!=200:
            fail('shard size changed at '+path)
        if {k:v for k,v in old.items() if k != 'questions'} != {k:v for k,v in current.items() if k != 'questions'}:
            fail('shard envelope changed at '+path)
        delta=0
        for x,y in zip(old['questions'],current['questions']):
            scanned+=1
            if x['id']!=y['id'] or {k:v for k,v in x.items() if k!='source_url'} != {k:v for k,v in y.items() if k!='source_url'}:
                fail('non-source-url Official Core or metadata changed at '+path)
            identity(x['source_url'],x['source_exam_code']);identity(y['source_url'],y['source_exam_code'])
            if x['source_url'] != y['source_url']:
                delta+=1;changed+=1
            else: unchanged+=1
        changes_by_file[path.split('/')[-1]]=delta
    if changed != 3920 or scanned != 4400 or unchanged != 480:
        fail(f'unexpected count changed={changed}, scanned={scanned}, unchanged={unchanged}')
    if a['shard_count']!=b['shard_count'] or a['total_questions']!=b['total_questions'] or a['total_questions']!=4800:
        fail('manifest count change')
    if b['dataset_revision'] != receipt['candidate_manifest_revision']:
        fail('manifest dataset revision does not match pinned receipt')
    files = {s['file']:s for s in b['shards']}
    if len(files)!=24 or len(b['shards'])!=24:fail('24-shard manifest altered')
    for name in changes_by_file:
        s=files[name];raw=(SHARDS/name).read_bytes()
        if s['bytes'] != len(raw) or s['sha256'] != hashlib.sha256(raw).hexdigest():
            fail('manifest SHA256/bytes mismatch '+name)
    a_115={s['file']:s for s in a['shards'] if s['year']=='115'}
    b_115={s['file']:s for s in b['shards'] if s['year']=='115'}
    if a_115!=b_115 or len(a_115)!=2:fail('115 year must be unchanged')
    for name,s in b_115.items():
        raw=(SHARDS/name).read_bytes()
        if s['sha256']!=hashlib.sha256(raw).hexdigest() or s['bytes']!=len(raw):
            fail('115 baseline manifest mismatch')
    return {'status':'QA_PASS_DEPLOY_BLOCKED','metadata_only_changes':changed,'unchanged_historical_questions':unchanged,'historical_rows_verified':scanned,'manifest_total_questions':b['total_questions'],'unchanged_latest_exam_shards':len(a_115),'release_authorized':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base-ref');p.add_argument('--before-dir',type=pathlib.Path);args=p.parse_args()
    try:
        result=check(args.base_ref,args.before_dir)
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    except Exception as ex:
        print('SOURCE URL METADATA PR QA REFUSED: '+str(ex),file=sys.stderr)
        sys.exit(1)
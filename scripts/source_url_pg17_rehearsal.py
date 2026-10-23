#!/usr/bin/env python3
"""Native PG17 transaction rehearsal for 3,920 URL-only changes in disposable TEMP tables.

Uses public repo-owned question shard data ONLY, never connects to Supabase production.
No actual edits to CDN, DB, GitHub or release infrastructure; always ROLLBACK.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from source_url_promotion_stage import stage

ROOT = Path(__file__).resolve().parents[1]

def q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"

def generate_sql(repo: Path) -> tuple[str, dict]:
    cfg=json.loads((repo/'data/source_url_promotion_config.json').read_text())
    outputs, report=stage(repo,cfg)
    fixture=[]; patch=[]; expected={}
    for session in sorted(cfg['expected_sessions_before_git_blobs']):
        orig=json.loads((repo/f'cdn/question-shards/{session}.json').read_text())
        after=json.loads(outputs[f'{session}.json'])
        expected[session]={}
        for a,b in zip(orig['questions'], after['questions']):
            if a['id']!=b['id'] or {k:v for k,v in a.items() if k!='source_url'}!={k:v for k,v in b.items() if k!='source_url'}:
                raise ValueError('Official Core changed!')
            digest=hashlib.sha256(json.dumps({k:v for k,v in a.items() if k!='source_url'},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            fixture.append((a['id'],session,a['source_url'],digest))
            if a['source_url']!=b['source_url']:
                patch.append((a['id'],a['source_url'],b['source_url']))
        expected[session]['post']=hashlib.md5(chr(30).join(b['id']+chr(31)+b['source_url'] for b in sorted(after['questions'],key=lambda x:x['id'])).encode()).hexdigest()
        expected[session]['pre']=hashlib.md5(chr(30).join(a['id']+chr(31)+a['source_url'] for a in sorted(orig['questions'],key=lambda x:x['id'])).encode()).hexdigest()
    if len(fixture)!=4400 or len(patch)!=3920:
        raise ValueError('Unexpected fixture dimensions')
    lines=[
        'BEGIN;',
        'SET LOCAL default_transaction_read_only = off;',
        'CREATE TEMP TABLE swsi_fixture (id text PRIMARY KEY, session text NOT NULL, source_url text NOT NULL, core_sha text NOT NULL) ON COMMIT DROP;',
        'CREATE TEMP TABLE swsi_patch (id text PRIMARY KEY, before_url text NOT NULL, after_url text NOT NULL) ON COMMIT DROP;',
        'INSERT INTO pg_temp.swsi_fixture (id,session,source_url,core_sha) VALUES',
        ',\n'.join('('+','.join(map(q,row))+')' for row in fixture)+';',
        'INSERT INTO pg_temp.swsi_patch (id,before_url,after_url) VALUES',
        ',\n'.join('('+','.join(map(q,row))+')' for row in patch)+';',
        "DO $pg$ DECLARE expected_count integer; matches integer; bad integer; BEGIN",
        'SELECT count(*) INTO expected_count FROM pg_temp.swsi_patch;',
        'IF expected_count <> 3920 THEN RAISE EXCEPTION \'Patch item count mismatch\'; END IF;',
        'SELECT count(*) INTO matches FROM pg_temp.swsi_fixture f JOIN pg_temp.swsi_patch p ON p.id=f.id AND p.before_url=f.source_url;',
        'IF matches <> 3920 THEN RAISE EXCEPTION \'Exact old value mismatch %\', matches; END IF;',
        'SELECT count(*) INTO bad FROM pg_temp.swsi_fixture WHERE source_url IS NULL OR core_sha IS NULL;',
        "IF bad <> 0 THEN RAISE EXCEPTION 'NULL fixture field'; END IF;",
        'END $pg$;',
        # Verify 22 per-session BEFORE hashes over real PostgreSQL expressions
        'CREATE TEMP TABLE swsi_expected(session text PRIMARY KEY, before_md5 text, after_md5 text) ON COMMIT DROP;',
        'INSERT INTO pg_temp.swsi_expected(session,before_md5,after_md5) VALUES',
        ',\n'.join('('+','.join(map(q,(s,v['pre'],v['post'])))+')' for s,v in expected.items())+';',
        'DO $pg$ DECLARE bad integer; BEGIN',
        "SELECT count(*) INTO bad FROM (SELECT session, md5(string_agg(id||chr(31)||source_url,chr(30) ORDER BY id)) h FROM pg_temp.swsi_fixture GROUP BY session) a JOIN pg_temp.swsi_expected b USING(session) WHERE a.h <> b.before_md5;",
        "IF bad <> 0 THEN RAISE EXCEPTION 'Initial PostgreSQL URL session MD5 mismatch'; END IF; END $pg$;",
        'CREATE TEMP TABLE swsi_original_core AS SELECT id,core_sha FROM pg_temp.swsi_fixture;',
        'DO $pg$ DECLARE affected integer; bad integer; BEGIN',
        'UPDATE pg_temp.swsi_fixture f SET source_url=p.after_url FROM pg_temp.swsi_patch p WHERE f.id=p.id AND f.source_url=p.before_url;',
        'GET DIAGNOSTICS affected = ROW_COUNT;',
        "IF affected <> 3920 THEN RAISE EXCEPTION 'Wrong updated row count %', affected; END IF;",
        "SELECT count(*) INTO bad FROM pg_temp.swsi_fixture f JOIN pg_temp.swsi_original_core a USING(id) WHERE f.core_sha <> a.core_sha;",
        "IF bad <> 0 THEN RAISE EXCEPTION 'Official Core metadata changed'; END IF;",
        "SELECT count(*) INTO bad FROM (SELECT session,md5(string_agg(id||chr(31)||source_url,chr(30) ORDER BY id)) h FROM pg_temp.swsi_fixture GROUP BY session) a JOIN pg_temp.swsi_expected b USING(session) WHERE a.h <> b.after_md5;",
        "IF bad <> 0 THEN RAISE EXCEPTION 'Final PostgreSQL URL session MD5 mismatch'; END IF;",
        'END $pg$;',
        "SELECT 'PG17 EXACT URL PATCH TX OK rows=3920 shards=22 official_core_unchanged=true';",
        'ROLLBACK;',
        "SELECT CASE WHEN to_regclass('pg_temp.swsi_fixture') IS NULL AND to_regclass('pg_temp.swsi_patch') IS NULL THEN 'PG17 ROLLBACK VERIFIED' ELSE 'ROLLBACK FAILED' END;",
    ]
    sql='\n'.join(lines)+'\n'
    if 'UPDATE public.' in sql or '\nCOMMIT;' in sql or 'ALTER TABLE public.' in sql:
        raise ValueError('Potential production writes prohibited')
    return sql, report

def main():
    if os.getenv('SWSI_SYNTHETIC_PG17_CI') != 'I_CONFIRM_DISPOSABLE_FIXTURE':
        raise SystemExit('REFUSED: disposable PG17 fixture guard is required')
    if (os.getenv('PGHOST'),os.getenv('PGDATABASE'),os.getenv('PGUSER'))!=('127.0.0.1','swsi_fixture','swsi_fixture'):
        raise SystemExit('REFUSED: only synthetic local fixture connection is permitted')
    sql,report=generate_sql(ROOT)
    p=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input=sql,text=True,capture_output=True,timeout=90)
    if p.returncode!=0 or 'PG17 EXACT URL PATCH TX OK rows=3920 shards=22' not in p.stdout or 'PG17 ROLLBACK VERIFIED' not in p.stdout:
        raise SystemExit('PG17 REHEARSAL FAILED: expected transactional SQL + rollback markers missing; '+p.stderr[-750:])
    print('PG17 REHEARSAL PASS: 3920 exact source_url edits in TEMP tables, 22/22 pre/post hashes, ROLLBACK verified')
    print(json.dumps(report,ensure_ascii=False,sort_keys=True))

if __name__=='__main__':
    main()
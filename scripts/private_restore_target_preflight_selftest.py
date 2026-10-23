#!/usr/bin/env python3
"""Synthetic preflight tests: does not connect to a real database."""
import json
import os
import pathlib
import subprocess
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from private_backup_counts_guard import REQUIRED_COUNTS, OPTIONAL_COUNTS
from private_restore_target_preflight import REQUIRED_EMPTY, validate

base={'count_schema_version':3,'captured_at_utc':'2026-10-23T00:00:00Z',
      **{k:0 for k in REQUIRED_COUNTS},**{k:None for k in OPTIONAL_COUNTS},
      **{k+'_present':False for k in OPTIONAL_COUNTS}}
checks=[]
def check(name,fn,expected):
    try:
        fn();got=True
    except ValueError:
        got=False
    assert got==expected,name
    checks.append(name)
check('empty, optional absent succeeds',lambda:validate(base),True)
for k in REQUIRED_EMPTY:
    check('nonzero '+k,lambda k=k:validate({**base,k:1}),False)
for k in OPTIONAL_COUNTS:
    check('empty, optional present '+k,lambda k=k:validate({**base,k+'_present':True,k:0}),True)
    check('nonempty optional '+k,lambda k=k:validate({**base,k+'_present':True,k:1}),False)
    check('optional missing count '+k,lambda k=k:validate({**base,k+'_present':False,k:0}),False)
    check('optional missing flag '+k,lambda k=k:validate({k2:v for k2,v in base.items() if k2 !=k+'_present'}),False)
for k in [*REQUIRED_COUNTS,*OPTIONAL_COUNTS]:
    check('missing count '+k,lambda k=k:validate({k2:v for k2,v in base.items() if k2!=k}),False)
check('legacy rejected',lambda:validate({**base,'count_schema_version':2}),False)
check('none rejected',lambda:validate(None),False)
path=pathlib.Path(__file__).with_name('private_restore_target_preflight.py')
for bad in ('','[]','{}','{','{"auth_users":0}'):
    e={**os.environ,'SWSI_RESTORE_PREFLIGHT':bad}
    r=subprocess.run([sys.executable,str(path)],env=e,capture_output=True,text=True)
    assert r.returncode!=0,bad
    checks.append('CLI rejects malformed '+str(len(bad)))
r=subprocess.run([sys.executable,str(path)],env={**os.environ,'SWSI_RESTORE_PREFLIGHT':json.dumps(base)},capture_output=True,text=True)
assert r.returncode==0,r.stderr
checks.append('CLI success only complete empty snapshot')
print('PRIVATE RESTORE TARGET PREFLIGHT TESTS OK',len(checks),'/',len(checks))
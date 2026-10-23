#!/usr/bin/env python3
"""Purely synthetic negative cases. Does NOT connect to Supabase/PostgreSQL."""
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from private_restore_target_preflight import REQUIRED_EMPTY, validate


def raises(payload):
    try:
        validate(payload)
    except ValueError:
        return True
    return False

base = {key: 0 for key in REQUIRED_EMPTY}
checks = []

def check(name, cond):
    assert cond, name
    checks.append(name)

check("all required tables empty passes", not raises(base))
check("missing entire JSON rejected", raises(None))
check("list is rejected", raises([]))
check("empty dict rejected", raises({}))
for key in REQUIRED_EMPTY:
    mutated = dict(base)
    mutated[key] = 1
    check(f"nonempty {key} rejected", raises(mutated))
    missing = dict(base)
    missing.pop(key)
    check(f"missing {key} rejected", raises(missing))
for bad in ("0", 0.0, False, True, None, -1, 0.1):
    mutated = dict(base)
    mutated["auth_users"] = bad
    check(f"ambiguous count {bad!r} rejected", raises(mutated))
check("unrecognized fields do not bypass checks", raises({**base, "feedback_reports": 12, "untrusted_green": True}))

path = pathlib.Path(__file__).with_name("private_restore_target_preflight.py")
env = {**os.environ, "SWSI_RESTORE_PREFLIGHT": json.dumps(base)}
p = subprocess.run([sys.executable, str(path)], env=env, capture_output=True, text=True)
check("CLI returns success only on all-empty count snapshot", p.returncode == 0)

for broken in ("", "[]", "{", '{"auth_users": 0}', "{" + 'x'*9000 + "}"):
    env["SWSI_RESTORE_PREFLIGHT"] = broken
    p = subprocess.run([sys.executable, str(path)], env=env, capture_output=True, text=True)
    check(f"CLI malformed input ({len(broken)} bytes) fails closed", p.returncode != 0)

print(f"PRIVATE RESTORE TARGET PREFLIGHT TESTS OK {len(checks)}/{len(checks)}")

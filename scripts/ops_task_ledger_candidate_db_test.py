#!/usr/bin/env python3
"""Run #269 candidate ledger SQL only against an explicitly local disposable PostgreSQL.

This helper is intentionally incapable of targeting hosted/production databases: PGHOST
must resolve to a loopback literal/name. It loads the candidate DDL, executes the
rollback-only behavior fixture, and verifies RLS/privilege boundaries.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "supabase" / "candidates" / "ops_task_ledger_v1.sql"
BEHAVIOR = ROOT / "supabase" / "candidates" / "ops_task_ledger_v1_test.sql"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def env_guard() -> None:
    host = str(os.getenv("PGHOST", "") or "").strip().lower()
    database = str(os.getenv("PGDATABASE", "") or "").strip().lower()
    if host not in LOOPBACK_HOSTS:
        raise SystemExit(
            f"refusing non-local PostgreSQL target PGHOST={host!r}; use one of {sorted(LOOPBACK_HOSTS)}"
        )
    if not database or database in {"postgres", "template0", "template1"}:
        raise SystemExit("PGDATABASE must name a disposable non-system test database")
    if not CANDIDATE.is_file() or not BEHAVIOR.is_file():
        raise SystemExit("candidate SQL or behavior fixture is missing")
    if shutil.which("psql") is None:
        raise SystemExit("psql is required; use the repository disposable PostgreSQL DR harness")


def psql(*, sql: str | None = None, file: Path | None = None, capture: bool = False) -> str:
    if (sql is None) == (file is None):
        raise ValueError("provide exactly one of sql or file")
    cmd = ["psql", "-X", "-v", "ON_ERROR_STOP=1"]
    if capture:
        cmd += ["-A", "-t", "-F", "|"]
    if sql is not None:
        cmd += ["-c", sql]
    else:
        cmd += ["-f", str(file)]
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        env=os.environ.copy(),
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        check=True,
    )
    return (result.stdout or "").strip()


def setup_roles() -> None:
    psql(
        sql="""
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
    EXECUTE 'CREATE ROLE anon NOLOGIN';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
    EXECUTE 'CREATE ROLE authenticated NOLOGIN';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN
    EXECUTE 'CREATE ROLE service_role NOLOGIN';
  END IF;
END
$$;
"""
    )


def verify_security() -> None:
    result = psql(
        sql="""
select
  (select relrowsecurity from pg_class c join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname='swsi_ops_task_runs'),
  (select relrowsecurity from pg_class c join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname='swsi_ops_review_items'),
  has_table_privilege('anon','public.swsi_ops_task_runs','SELECT'),
  has_table_privilege('authenticated','public.swsi_ops_task_runs','SELECT'),
  has_table_privilege('service_role','public.swsi_ops_task_runs','SELECT'),
  has_table_privilege('service_role','public.swsi_ops_task_runs','UPDATE'),
  has_table_privilege('service_role','public.swsi_ops_task_runs','DELETE'),
  has_function_privilege('anon','public.swsi_ops_claim_task(text,text,text,timestamptz,integer,integer)','EXECUTE'),
  has_function_privilege('authenticated','public.swsi_ops_claim_task(text,text,text,timestamptz,integer,integer)','EXECUTE'),
  has_function_privilege('service_role','public.swsi_ops_claim_task(text,text,text,timestamptz,integer,integer)','EXECUTE');
""",
        capture=True,
    )
    expected = "t|t|f|f|t|t|f|f|f|t"
    if result != expected:
        raise AssertionError(f"ledger RLS/privilege boundary mismatch: expected={expected} actual={result}")


def main() -> int:
    env_guard()
    setup_roles()
    psql(file=CANDIDATE)
    psql(file=BEHAVIOR)
    verify_security()
    print("OPS TASK LEDGER CANDIDATE DB TEST OK (local disposable PostgreSQL only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

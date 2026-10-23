#!/usr/bin/env python3
"""Safe count-only snapshot for SWSI hosted mutable-data backup and isolated restore.

Optional future Ops relations are recorded as PRESENT/ABSENT; missing is NEVER
reported as a successful zero-row count. Only fixed table names enter the SQL.
Refuses shared CI execution. Does not dump or log private table data or secrets.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

OPTIONAL = {
    "ops_task_runs": "public.swsi_ops_task_runs",
    "ops_review_items": "public.swsi_ops_review_items",
}
MANDATORY = {
    "auth_users": "auth.users",
    "feedback_reports": "public.swsi_feedback_reports",
    "usage_daily_rows": "public.swsi_usage_daily",
    "ai_telemetry_client_daily_rows": "public.swsi_ai_telemetry_client_daily",
    "ai_telemetry_5m_rows": "public.swsi_ai_telemetry_5m",
    "admin_allowlist_rows": "public.swsi_admin_users",
    "storage_buckets": "storage.buckets",
    "storage_objects": "storage.objects",
}
CONNECTION_VARS = ("SWSI_SUPABASE_DB_URL", "SWSI_RESTORE_TARGET_DB_URL")


def detect_sql() -> str:
    fields = [f"'{key}', (SELECT CASE WHEN c.relkind IN ('r','p') THEN 'table' "
              f"WHEN c.relkind IS NULL THEN 'absent' ELSE 'unsupported' END "
              f"FROM (SELECT (SELECT relkind FROM pg_class WHERE oid=to_regclass('{table}')) AS relkind) c)"
              for key, table in OPTIONAL.items()]
    return "SELECT json_build_object(" + ", ".join(fields) + ");\n"


def build_count_sql(status: object) -> str:
    if not isinstance(status, dict) or set(status) != set(OPTIONAL):
        raise ValueError("unexpected optional table registry")
    for value in status.values():
        if value not in ("absent", "table"):
            raise ValueError("unexpected relation kind: optional table is neither absent nor a table")
    fields = ["'count_schema_version', 3",
              "'captured_at_utc', to_char((now() AT TIME ZONE 'utc'), 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"')"]
    for name, rel in MANDATORY.items():
        fields.append(f"'{name}', (SELECT count(*) FROM {rel})")
    for name, rel in OPTIONAL.items():
        present = status[name] == "table"
        fields.append(f"'{name}_present', {'true' if present else 'false'}")
        fields.append(f"'{name}', {'(SELECT count(*) FROM ' + rel + ')' if present else 'NULL::bigint'}")
    return "SELECT json_build_object(\n  " + ",\n  ".join(fields) + "\n);\n"


def parse_one_json(raw: str) -> dict:
    if len(raw) > 16384 or not raw.strip():
        raise ValueError("invalid count-only JSON size")
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError("duplicate JSON count field")
            out[k] = v
        return out
    value = json.loads(raw, object_pairs_hook=unique)
    if type(value) is not dict:
        raise ValueError("count-only output must be a JSON object")
    return value


def run_psql(db_url: str, query: str) -> dict:
    if not db_url or len(db_url) > 8192 or not db_url.startswith(("postgres://", "postgresql://")):
        raise ValueError("database URL is missing or invalid")
    env = dict(os.environ)
    # Require only one explicit database URI; inherited libpq variables may override routing.
    if any(k.upper().startswith("PG") for k in env):
        raise ValueError("inherited PG environment variables are not supported")
    env["PGOPTIONS"] = "-c default_transaction_read_only=on"
    p = subprocess.run(["psql", "-X", "-qAt", "--set=ON_ERROR_STOP=1", "--dbname", db_url],
                       input=query, text=True, capture_output=True, env=env, timeout=60)
    if p.returncode:
        # Never reflect libpq error text which might reveal connection details.
        raise RuntimeError("read-only count query failed")
    return parse_one_json(p.stdout)


def capture(db_url: str) -> dict:
    kinds = run_psql(db_url, detect_sql())
    snapshot = run_psql(db_url, build_count_sql(kinds))
    from private_backup_counts_guard import validate_counts
    return validate_counts(snapshot)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-env", required=True, choices=CONNECTION_VARS)
    args = parser.parse_args()
    try:
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS") == "true":
            raise ValueError("private count probe refuses shared CI")
        data = capture(os.environ.get(args.connection_env, ""))
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.TimeoutExpired):
        print("PRIVATE BACKUP COUNT CAPTURE REFUSED: configuration, schema or read-only query failed", file=sys.stderr)
        return 64
    print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
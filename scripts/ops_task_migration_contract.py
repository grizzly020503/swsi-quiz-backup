#!/usr/bin/env python3
"""Static #274 promotion checks for candidate -> migration + DR wiring."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAIRS = [
    (
        ROOT / "supabase/candidates/ops_task_ledger_v1.sql",
        ROOT / "supabase/migrations/20261002112000_create_ops_task_ledger.sql",
    ),
    (
        ROOT / "supabase/candidates/ops_task_review_rpc_v1.sql",
        ROOT / "supabase/migrations/20261002112100_add_ops_review_rpcs.sql",
    ),
]
MANIFEST = ROOT / "supabase/recovery/recovery_manifest.json"
RUNTIME = ROOT / "supabase/recovery/postgres_runtime_contract.sql"
OPS_RUNTIME = ROOT / "supabase/recovery/ops_ledger_runtime_contract.sql"
ACL_ALIGNMENT = ROOT / "supabase/recovery/production_acl_alignment.sql"


def sql_body(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    while lines and (not lines[0].strip() or lines[0].lstrip().startswith("--")):
        lines.pop(0)
    return "\n".join(lines).strip() + "\n"


def validate() -> dict[str, object]:
    for candidate, migration in PAIRS:
        if not candidate.is_file() or not migration.is_file():
            raise AssertionError(f"missing candidate/migration pair: {candidate.name} -> {migration.name}")
        if sql_body(candidate) != sql_body(migration):
            raise AssertionError(f"migration SQL body drifted from reviewed candidate: {migration.name}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    order = manifest.get("migration_order") or []
    ledger = "supabase/migrations/20261002112000_create_ops_task_ledger.sql"
    review = "supabase/migrations/20261002112100_add_ops_review_rpcs.sql"
    alignment = "supabase/recovery/production_acl_alignment.sql"
    for required in (ledger, review, alignment):
        if required not in order:
            raise AssertionError(f"recovery manifest missing {required}")
    if not (order.index(ledger) < order.index(review) < order.index(alignment)):
        raise AssertionError("ops ledger/review/alignment recovery order is invalid")

    expected_tables = set((manifest.get("expected") or {}).get("public_tables") or [])
    if not {"swsi_ops_task_runs", "swsi_ops_review_items"}.issubset(expected_tables):
        raise AssertionError("recovery expected public tables missing ops ledger tables")

    runtime = RUNTIME.read_text(encoding="utf-8")
    if "\\ir ops_ledger_runtime_contract.sql" not in runtime:
        raise AssertionError("postgres_runtime_contract.sql does not include ops ledger runtime checks")
    if not OPS_RUNTIME.is_file():
        raise AssertionError("ops ledger runtime contract file is missing")

    acl = ACL_ALIGNMENT.read_text(encoding="utf-8").lower()
    if "alter role service_role bypassrls" not in acl:
        raise AssertionError("portable recovery service_role does not match production BYPASSRLS")

    return {
        "ok": True,
        "migration_pairs": len(PAIRS),
        "recovery_order": True,
        "expected_tables": True,
        "runtime_include": True,
        "service_role_bypassrls": True,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))

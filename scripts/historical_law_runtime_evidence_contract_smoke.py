#!/usr/bin/env python3
"""Zero-network static contract for historical-law runtime evidence.

Does not apply migrations, call Supabase, or deploy Edge Functions.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261005050000_historical_law_runtime_evidence.sql"
LEAST_PRIVILEGE_MIGRATION = ROOT / "supabase/migrations/20261005062000_historical_law_runtime_evidence_least_privilege.sql"
INDEX = ROOT / "supabase/functions/sync-historical-law-evidence/index.ts"
MODULE = ROOT / "supabase/functions/sync-historical-law-evidence/runtime_evidence.ts"
INVENTORY = ROOT / "supabase/recovery/edge_functions.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    least_privilege = LEAST_PRIVILEGE_MIGRATION.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    module = MODULE.read_text(encoding="utf-8")
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    for marker in (
        "create table if not exists public.historical_law_runtime_evidence",
        "create table if not exists public.historical_law_runtime_evidence_snapshot",
        "historical_version_checked = true",
        "machine_verified_historical_v1",
        "evidence_adjudicated_historical_v1",
        "enable row level security",
        "revoke all on table public.historical_law_runtime_evidence from public, anon, authenticated",
        "grant select, insert, update on table public.historical_law_runtime_evidence to service_role",
    ):
        require(marker in migration, f"migration contract missing: {marker}")

    for marker in (
        "revoke all on table public.historical_law_runtime_evidence\n  from public, anon, authenticated, service_role",
        "grant select, insert, update on table public.historical_law_runtime_evidence\n  to service_role",
        "revoke all on table public.historical_law_runtime_evidence_snapshot\n  from public, anon, authenticated, service_role",
        "grant select, insert, update on table public.historical_law_runtime_evidence_snapshot\n  to service_role",
    ):
        require(marker in least_privilege, f"least-privilege migration missing: {marker}")
    for forbidden in ("grant delete", "grant truncate", "grant references", "grant trigger"):
        require(forbidden not in least_privilege.lower(), f"forbidden privilege re-grant found: {forbidden}")

    for marker in (
        "normalizeRegistry(body)",
        "materializeRegistry(normalized)",
        "assertMonotonic(existing, materialized.rows)",
        "assertQuestionIdsExist",
        'sync_status: "syncing"',
        'sync_status: "failed"',
        'sync_status: "complete"',
        'onConflict: "question_id,law_name"',
    ):
        require(marker in index, f"sync candidate contract missing: {marker}")
    require(".delete(" not in index, "sync candidate must not delete verified evidence")

    for marker in (
        "PROTECTED_CORE_FIELDS",
        "protected Official Core field rejected",
        "verified registry shrank",
        "verified evidence key disappeared",
        "verified evidence drift",
        "historical_version_checked must be true",
    ):
        require(marker in module, f"runtime evidence fail-closed marker missing: {marker}")

    candidates = [
        row for row in inventory.get("functions") or []
        if row.get("slug") == "sync-historical-law-evidence"
    ]
    require(len(candidates) == 1, "recovery inventory must include exactly one historical-law sync candidate")
    require(
        candidates[0].get("status") == "source-only-candidate-not-deployed",
        "historical-law sync must remain explicitly not deployed",
    )

    print("HISTORICAL LAW RUNTIME EVIDENCE CONTRACT OK")


if __name__ == "__main__":
    main()

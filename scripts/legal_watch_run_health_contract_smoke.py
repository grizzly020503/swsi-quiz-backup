#!/usr/bin/env python3
"""Static fail-closed contract for legal-watch run health evidence.

This is intentionally zero-network and does not apply migrations or call Supabase.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261005033000_legal_watch_run_health.sql"
INDEX = ROOT / "supabase/functions/sync-legal-watch/index.ts"
RUN_HEALTH = ROOT / "supabase/functions/sync-legal-watch/run_health.ts"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    health = RUN_HEALTH.read_text(encoding="utf-8")

    for marker in (
        "create table if not exists public.legal_watch_run_health",
        "sync_status in ('syncing','complete','failed')",
        "lookup_error_count integer not null",
        "alter table public.legal_watch_run_health enable row level security",
        "revoke all on table public.legal_watch_run_health from public, anon, authenticated",
        "grant select, insert, update on table public.legal_watch_run_health to service_role",
    ):
        require(marker in migration, f"migration contract missing: {marker}")

    require('source: "github_actions"' in health, "run health source must remain explicit")
    require('id: true' in health, "run health must remain singleton")
    require('lookup_error_count exceeds watch_count' in health, "lookup-error bounds missing")

    for marker in (
        '.from("legal_watch_run_health")',
        'normalizeRunHealth(body as Record<string, unknown>, records, "syncing")',
        'withSyncStatus(runHealth, "failed")',
        'withSyncStatus(runHealth, "complete")',
        'last_checked_at: checkedAt',
    ):
        require(marker in index, f"sync function run-health wiring missing: {marker}")

    # Runtime trust must never be inferred merely from one per-law registry row.
    # This smoke test only proves the evidence primitive; analyzer consumption is
    # a separate activation change and must be reviewed independently.
    require("analyze-pending-questions" not in index, "legal sync must not activate analyzer")

    print("LEGAL WATCH RUN HEALTH CONTRACT OK")


if __name__ == "__main__":
    main()

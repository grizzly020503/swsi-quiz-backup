#!/usr/bin/env python3
"""Static fail-closed checks for the #269 candidate persistence SQL."""
from __future__ import annotations

import argparse
from pathlib import Path


def require(text: str, needle: str) -> None:
    if needle.lower() not in text.lower():
        raise AssertionError(f"missing required SQL contract: {needle}")


def reject(text: str, needle: str) -> None:
    if needle.lower() in text.lower():
        raise AssertionError(f"forbidden SQL contract present: {needle}")


def validate(path: Path) -> dict[str, int | bool]:
    text = path.read_text(encoding="utf-8")
    for needle in [
        "create table if not exists public.swsi_ops_task_runs",
        "primary key (task_id, idempotency_key)",
        "alter table public.swsi_ops_task_runs enable row level security",
        "alter table public.swsi_ops_review_items enable row level security",
        "revoke all on table public.swsi_ops_task_runs from public, anon, authenticated",
        "revoke all on table public.swsi_ops_review_items from public, anon, authenticated",
        "grant select, insert, update on table public.swsi_ops_task_runs to service_role",
        "grant select, insert, update on table public.swsi_ops_review_items to service_role",
        "create or replace function public.swsi_ops_claim_task",
        "create or replace function public.swsi_ops_checkpoint_task",
        "create or replace function public.swsi_ops_heartbeat_task",
        "create or replace function public.swsi_ops_complete_task",
        "security invoker",
        "for update",
        "on conflict (task_id, idempotency_key) do nothing",
        "p_processed_count >= processed_count",
        "last_success_at = case",
    ]:
        require(text, needle)
    reject(text, "security definer")
    reject(text, "grant delete")
    reject(text, "grant all")
    # No direct client grants; all access must remain backend/service-role only.
    reject(text, "to anon;")
    reject(text, "to authenticated;")
    return {"ok": True, "bytes": len(text.encode("utf-8")), "functions": text.lower().count("create or replace function")}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("path", type=Path)
    args = p.parse_args()
    print(validate(args.path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Static safety contract for the undeployed #274 ops-ledger gateway candidate."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "supabase/candidates/edge-functions/swsi-ops-ledger/index.ts"
PRODUCTION = ROOT / "supabase/functions/swsi-ops-ledger/index.ts"
INVENTORY = ROOT / "supabase/recovery/edge_functions.json"

REQUIRED_ACTIONS = {
    "claim",
    "checkpoint",
    "heartbeat",
    "complete",
    "review_upsert",
    "review_touch",
    "review_resolve",
    "get_run",
    "open_reviews",
}
REQUIRED_TASKS = {
    "full-corpus-question-qa",
    "moex-social-worker-sync",
    "historical-law-guardian-queue",
}


def validate() -> dict[str, object]:
    if not CANDIDATE.is_file():
        raise AssertionError("ops-ledger gateway candidate source is missing")
    if PRODUCTION.exists():
        raise AssertionError(
            "candidate unexpectedly exists in production function tree before deploy authorization"
        )

    text = CANDIDATE.read_text(encoding="utf-8")
    for token in [
        'const REPO = "grizzly020503/swsi-quiz-backup"',
        "verifyGitHubRepoToken",
        'Deno.env.get("SUPABASE_URL")',
        'Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")',
        'repo?.private === true',
        "requireGuardianTask",
        "requireReviewItem",
    ]:
        if token not in text:
            raise AssertionError(f"gateway contract missing: {token}")

    for task in REQUIRED_TASKS:
        if f'"{task}"' not in text:
            raise AssertionError(f"gateway task allowlist missing: {task}")
    for action in REQUIRED_ACTIONS:
        if f'action === "{action}"' not in text:
            raise AssertionError(f"gateway action missing: {action}")

    forbidden = [
        '.delete(',
        '.from("questions")',
        '.from("essays")',
        '.from("swsi_admin_users")',
        "eval(",
        "Deno.Command",
    ]
    for token in forbidden:
        if token in text:
            raise AssertionError(f"forbidden gateway capability present: {token}")

    allowed_rpc = {
        "swsi_ops_claim_task",
        "swsi_ops_checkpoint_task",
        "swsi_ops_heartbeat_task",
        "swsi_ops_complete_task",
        "swsi_ops_upsert_review_item",
        "swsi_ops_touch_review_item",
        "swsi_ops_resolve_review_item",
    }
    rpc_markers = set()
    needle = 'sb.rpc("'
    start = 0
    while True:
        pos = text.find(needle, start)
        if pos < 0:
            break
        begin = pos + len(needle)
        end = text.find('"', begin)
        if end < 0:
            raise AssertionError("malformed sb.rpc marker")
        rpc_markers.add(text[begin:end])
        start = end + 1
    if rpc_markers != allowed_rpc:
        raise AssertionError(
            f"gateway RPC allowlist drift: expected={sorted(allowed_rpc)} actual={sorted(rpc_markers)}"
        )

    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    production_slugs = {str(row.get("slug") or "") for row in inventory.get("functions") or []}
    if "swsi-ops-ledger" in production_slugs:
        raise AssertionError(
            "recovery inventory must not claim undeployed swsi-ops-ledger is production"
        )

    return {
        "ok": True,
        "candidate_only": True,
        "github_repo_token_gate": True,
        "task_allowlist": sorted(REQUIRED_TASKS),
        "action_count": len(REQUIRED_ACTIONS),
        "rpc_count": len(rpc_markers),
        "production_inventory_unchanged": True,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))

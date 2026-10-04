#!/usr/bin/env python3
"""Static safety contract for the undeployed #274 ops-ledger gateway candidate."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "supabase/candidates/edge-functions/swsi-ops-ledger/index.ts"
PRODUCTION = ROOT / "supabase/functions/swsi-ops-ledger/index.ts"
INVENTORY = ROOT / "supabase/recovery/edge_functions.json"
REVIEW_POLICY = ROOT / "data/ops_review_namespace.v1.json"
MOEX_EVENT_CONTRACT = ROOT / "scripts/moex_ops_event_contract.py"

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
EXPECTED_REVIEW_NAMESPACES = {
    "historical-law-guardian-queue": "historical-law:",
    "moex-social-worker-sync": "moex:",
}
EXPECTED_REVIEW_DENY = {"full-corpus-question-qa"}


def _extract_ts_review_namespaces(text: str) -> dict[str, str]:
    match = re.search(
        r"const REVIEW_NAMESPACE_BY_TASK = new Map<string, string>\(\[(.*?)\]\);",
        text,
        flags=re.DOTALL,
    )
    if not match:
        raise AssertionError("gateway REVIEW_NAMESPACE_BY_TASK declaration missing")
    pairs = re.findall(r'\["([^"]+)",\s*"([^"]+)"\]', match.group(1))
    return dict(pairs)


def _extract_ts_moex_reasons(text: str) -> set[str]:
    match = re.search(
        r"const MOEX_REVIEW_REASONS = new Set\(\[(.*?)\]\);",
        text,
        flags=re.DOTALL,
    )
    if not match:
        raise AssertionError("gateway MOEX_REVIEW_REASONS declaration missing")
    return set(re.findall(r'"([a-z][a-z0-9_]+)"', match.group(1)))


def _extract_python_moex_reasons(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    reasons: set[str] = set()

    def add_strings(node: ast.AST | None) -> None:
        if node is None:
            return
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            reasons.add(node.value)
            return
        if isinstance(node, ast.Dict):
            for value in node.values:
                add_strings(value)
            return
        if isinstance(node, ast.Subscript):
            add_strings(node.value)
            return
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                add_strings(node.func.value)
                if len(node.args) >= 2:
                    add_strings(node.args[1])
            return

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "reason" for target in node.targets):
                add_strings(node.value)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "reason":
                add_strings(node.value)
        elif isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "reason":
                    add_strings(keyword.value)
    return reasons


def _load_review_policy() -> tuple[dict[str, str], set[str], set[str]]:
    payload = json.loads(REVIEW_POLICY.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("unknown_task_policy") != "deny":
        raise AssertionError("review namespace policy must be schema_version=1 and fail closed")
    namespaces: dict[str, str] = {}
    moex_reasons: set[str] = set()
    for row in payload.get("task_namespaces") or []:
        task_id = str(row.get("task_id") or "").strip()
        prefix = str(row.get("item_prefix") or "").strip()
        if not task_id or not prefix or task_id in namespaces:
            raise AssertionError("review namespace policy has missing/duplicate task or prefix")
        namespaces[task_id] = prefix
        if task_id == "moex-social-worker-sync":
            if row.get("reason_policy") != "explicit_allowlist":
                raise AssertionError("MOEX review reasons must use explicit_allowlist")
            moex_reasons = {str(value) for value in row.get("allowed_reasons") or []}
    denied = {str(value) for value in payload.get("explicitly_denied_review_tasks") or []}
    security = payload.get("security") or {}
    if security.get("cross_namespace_item_ids_allowed") is not False:
        raise AssertionError("cross-namespace review item ids must remain denied")
    if security.get("unknown_reasons_for_moex_allowed") is not False:
        raise AssertionError("unknown MOEX review reasons must remain denied")
    if security.get("production_write_enabled_by_this_file") is not False:
        raise AssertionError("static policy must never enable production writes")
    return namespaces, moex_reasons, denied


def validate() -> dict[str, object]:
    if not CANDIDATE.is_file():
        raise AssertionError("ops-ledger gateway candidate source is missing")
    if PRODUCTION.exists():
        raise AssertionError(
            "candidate unexpectedly exists in production function tree before deploy authorization"
        )
    if not REVIEW_POLICY.is_file():
        raise AssertionError("durable review namespace policy is missing")
    if not MOEX_EVENT_CONTRACT.is_file():
        raise AssertionError("MOEX ops event contract is missing")

    policy_namespaces, policy_moex_reasons, policy_denied = _load_review_policy()
    if policy_namespaces != EXPECTED_REVIEW_NAMESPACES:
        raise AssertionError(
            f"review namespace policy drift: expected={EXPECTED_REVIEW_NAMESPACES} actual={policy_namespaces}"
        )
    if policy_denied != EXPECTED_REVIEW_DENY:
        raise AssertionError(
            f"review deny policy drift: expected={EXPECTED_REVIEW_DENY} actual={policy_denied}"
        )
    if not policy_moex_reasons:
        raise AssertionError("MOEX review reason allowlist must not be empty")

    text = CANDIDATE.read_text(encoding="utf-8")
    for token in [
        'const REPO = "grizzly020503/swsi-quiz-backup"',
        'const REPO_ID = 1345053575',
        "verifyGitHubRepoWriteToken",
        'Number(repo?.id) === REPO_ID',
        'repo?.permissions?.push === true',
        'Deno.env.get("SUPABASE_URL")',
        'Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")',
        "requireReviewTask",
        "requireReviewItem",
        "requireReviewReason",
        "!itemId.startsWith(prefix)",
        '.eq("task_id", taskId)',
    ]:
        if token not in text:
            raise AssertionError(f"gateway contract missing: {token}")
    if "requireGuardianTask" in text:
        raise AssertionError("legacy single-namespace Guardian review gate must be removed")
    if '.eq("task_id", "historical-law-guardian-queue")' in text:
        raise AssertionError("open_reviews must be task-scoped, not hard-coded to Guardian")
    if 'repo?.private === true' in text:
        raise AssertionError("private-repo readability must not be used as gateway authentication")

    ts_namespaces = _extract_ts_review_namespaces(text)
    if ts_namespaces != policy_namespaces:
        raise AssertionError(
            f"gateway review namespace allowlist drift: policy={policy_namespaces} gateway={ts_namespaces}"
        )
    ts_moex_reasons = _extract_ts_moex_reasons(text)
    if ts_moex_reasons != policy_moex_reasons:
        raise AssertionError(
            "gateway MOEX reason allowlist drift: "
            f"policy={sorted(policy_moex_reasons)} gateway={sorted(ts_moex_reasons)}"
        )
    emitted_moex_reasons = _extract_python_moex_reasons(MOEX_EVENT_CONTRACT)
    if emitted_moex_reasons != policy_moex_reasons:
        raise AssertionError(
            "MOEX event reasons and gateway policy disagree: "
            f"event={sorted(emitted_moex_reasons)} policy={sorted(policy_moex_reasons)}"
        )

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
        "github_repo_write_token_gate": True,
        "task_allowlist": sorted(REQUIRED_TASKS),
        "review_namespaces": policy_namespaces,
        "moex_review_reason_count": len(policy_moex_reasons),
        "review_denied_tasks": sorted(policy_denied),
        "action_count": len(REQUIRED_ACTIONS),
        "rpc_count": len(rpc_markers),
        "production_inventory_unchanged": True,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))

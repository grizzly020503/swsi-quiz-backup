#!/usr/bin/env python3
"""Deterministic bounded recovery / degradation / release decision contract for SWSI.

This helper consumes the repo-owned policy only. It never executes retries,
rollbacks, deployments, migrations, payments, or credential changes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

POLICY_PATH = "data/bounded_recovery_policy.v1.json"

REQUIRED_FAILURES = {
    "transient_timeout",
    "rate_limited_429",
    "upstream_5xx",
    "source_unavailable",
    "stale_job",
    "candidate_validation_failed",
    "preview_failed",
    "post_deploy_smoke_failed",
    "quota_exhausted",
    "ai_unavailable",
    "official_core_change",
    "auth_rls_secret_change",
    "destructive_schema_change",
    "paid_service_change",
    "unknown_migration_state",
}

OWNER_REQUIRED = {
    "official_core_change",
    "auth_rls_secret_change",
    "destructive_schema_change",
    "paid_service_change",
    "unknown_migration_state",
}

REQUIRED_GLOBAL = {
    "preserve_last_known_good": True,
    "production_publish_requires_external_authorization": True,
    "contract_may_self_authorize_publish": False,
    "automatic_blind_database_rollback": False,
    "automatic_paid_service_activation": False,
    "automatic_qa_lowering": False,
    "automatic_official_core_mutation": False,
}

NORMAL_PATH = [
    "candidate",
    "isolated_verified",
    "preview_verified",
    "publish_authorized",
    "published",
    "postcheck_verified",
]

FAILURE_TERMINALS = {
    "quarantine",
    "preserve_last_known_good",
    "rollback_required",
    "manual_required",
}


class ContractError(ValueError):
    pass


def load_policy(root: Path) -> dict[str, Any]:
    path = root / POLICY_PATH
    if not path.is_file():
        raise ContractError(f"missing policy: {POLICY_PATH}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    if policy.get("schema_version") != 1:
        raise ContractError("schema_version must be 1")

    global_policy = policy.get("global")
    if not isinstance(global_policy, dict):
        raise ContractError("global policy missing")
    for key, expected in REQUIRED_GLOBAL.items():
        if global_policy.get(key) is not expected:
            raise ContractError(f"global invariant changed: {key}")

    failures = policy.get("failure_classes")
    if not isinstance(failures, dict):
        raise ContractError("failure_classes missing")
    missing = REQUIRED_FAILURES - set(failures)
    if missing:
        raise ContractError(f"required failure classes missing: {sorted(missing)}")

    retryable_count = 0
    owner_required_count = 0
    for name, row in failures.items():
        if not isinstance(row, dict):
            raise ContractError(f"failure class must be object: {name}")
        for field in (
            "retryable", "max_attempts", "backoff_class", "scope", "cost_class",
            "exhausted_action", "core_status", "enhancement_status"
        ):
            if field not in row:
                raise ContractError(f"{name} missing {field}")
        if row["cost_class"] not in {"low", "medium", "high"}:
            raise ContractError(f"invalid cost_class for {name}")
        if row["retryable"] is True:
            retryable_count += 1
            if not isinstance(row["max_attempts"], int) or not 1 <= row["max_attempts"] <= 5:
                raise ContractError(f"retryable {name} must have bounded max_attempts 1..5")
            if row["backoff_class"] == "none":
                raise ContractError(f"retryable {name} must define backoff")
        else:
            if row["max_attempts"] != 0:
                raise ContractError(f"non-retryable {name} must use max_attempts=0")

        if name in OWNER_REQUIRED:
            owner_required_count += 1
            if row.get("owner_required") is not True:
                raise ContractError(f"owner_required must remain true for {name}")
            if row["exhausted_action"] != "manual_required":
                raise ContractError(f"high-risk {name} must stop at manual_required")

    machine = policy.get("release_state_machine")
    if not isinstance(machine, dict):
        raise ContractError("release_state_machine missing")
    states = set(machine.get("states", []))
    if not set(NORMAL_PATH).issubset(states) or not FAILURE_TERMINALS.issubset(states):
        raise ContractError("release state machine is missing required states")
    if machine.get("normal_path") != NORMAL_PATH:
        raise ContractError("normal release path changed")
    if set(machine.get("failure_terminals", [])) != FAILURE_TERMINALS:
        raise ContractError("failure terminals changed")

    auth = machine.get("publish_authorization_transition", {})
    if auth.get("from") != "preview_verified" or auth.get("to") != "publish_authorized":
        raise ContractError("publish authorization transition changed")
    if auth.get("requires_external_authorization") is not True:
        raise ContractError("publish authorization must remain external")
    if not auth.get("authorization_source"):
        raise ContractError("publish authorization source missing")

    rollback = policy.get("rollback_boundaries", {})
    if "previous_known_good_static_release" not in rollback.get("static_release", ""):
        raise ContractError("static rollback boundary missing previous known-good release")
    database_rule = rollback.get("database", "")
    if "no_blind_automatic_downgrade" not in database_rule:
        raise ContractError("database boundary must forbid blind automatic downgrade")
    if "official_evidence" not in rollback.get("official_answer_correction", ""):
        raise ContractError("official correction boundary must require official evidence")

    return {
        "failure_class_count": len(failures),
        "retryable_count": retryable_count,
        "owner_required_count": owner_required_count,
        "state_count": len(states),
    }


def decide(policy: dict[str, Any], failure_class: str, attempt: int = 0) -> dict[str, Any]:
    if attempt < 0:
        raise ContractError("attempt must be >= 0")
    failures = policy["failure_classes"]
    row = failures.get(failure_class)
    if row is None:
        return {
            "failure_class": failure_class,
            "action": "manual_required",
            "retry_allowed": False,
            "max_attempts": 0,
            "next_attempt": None,
            "backoff_class": "none",
            "cost_class": "unknown",
            "scope": "unknown",
            "preserve_last_known_good": True,
            "core_status": "preserve_last_known_good",
            "enhancement_status": "paused",
            "owner_required": True,
            "production_publish_allowed": False,
            "reason": "unknown failure class fails closed",
        }

    retry_allowed = bool(row["retryable"] and attempt < row["max_attempts"])
    action = "retry_bounded" if retry_allowed else row["exhausted_action"]
    return {
        "failure_class": failure_class,
        "action": action,
        "retry_allowed": retry_allowed,
        "max_attempts": row["max_attempts"],
        "next_attempt": attempt + 1 if retry_allowed else None,
        "backoff_class": row["backoff_class"],
        "cost_class": row["cost_class"],
        "scope": row["scope"],
        "preserve_last_known_good": policy["global"]["preserve_last_known_good"],
        "core_status": row["core_status"],
        "enhancement_status": row["enhancement_status"],
        "owner_required": row.get("owner_required", False) or action == "manual_required",
        "production_publish_allowed": False,
        "reason": "bounded policy decision; execution is outside this helper",
    }


def transition(policy: dict[str, Any], stage: str, event: str, *, external_authorization: bool = False) -> dict[str, Any]:
    allowed = {
        ("candidate", "isolated_pass"): "isolated_verified",
        ("isolated_verified", "preview_pass"): "preview_verified",
        ("preview_verified", "publish_authorization"): "publish_authorized",
        ("publish_authorized", "publish_success"): "published",
        ("published", "postcheck_pass"): "postcheck_verified",
        ("candidate", "validation_fail"): "quarantine",
        ("isolated_verified", "preview_fail"): "quarantine",
        ("preview_verified", "preview_fail"): "quarantine",
        ("published", "postcheck_fail"): "rollback_required",
    }
    target = allowed.get((stage, event))
    if target is None:
        return {
            "ok": False,
            "state": stage,
            "production_publish_allowed": False,
            "reason": "transition is not allowlisted",
        }
    if target == "publish_authorized":
        auth = policy["release_state_machine"]["publish_authorization_transition"]
        if auth["requires_external_authorization"] and not external_authorization:
            return {
                "ok": False,
                "state": stage,
                "production_publish_allowed": False,
                "reason": "explicit external publish authorization is required",
            }
    return {
        "ok": True,
        "state": target,
        "production_publish_allowed": target == "publish_authorized" and external_authorization,
        "reason": "allowlisted transition",
    }


def self_test(policy: dict[str, Any]) -> dict[str, Any]:
    summary = validate_policy(policy)
    cases = 0

    for failure in ("transient_timeout", "rate_limited_429", "upstream_5xx"):
        row = policy["failure_classes"][failure]
        first = decide(policy, failure, 0)
        assert first["retry_allowed"] and first["action"] == "retry_bounded"
        assert first["next_attempt"] == 1
        exhausted = decide(policy, failure, row["max_attempts"])
        assert not exhausted["retry_allowed"]
        assert exhausted["action"] == row["exhausted_action"]
        cases += 2

    source = decide(policy, "source_unavailable")
    assert source["action"] == "preserve_last_known_good"
    assert source["preserve_last_known_good"] is True
    cases += 1

    ai = decide(policy, "ai_unavailable")
    assert ai["action"] == "degrade_enhancement"
    assert ai["core_status"] == "available"
    assert ai["enhancement_status"] == "paused"
    cases += 1

    assert decide(policy, "candidate_validation_failed")["action"] == "quarantine"
    assert decide(policy, "preview_failed")["action"] == "quarantine"
    cases += 2

    post = decide(policy, "post_deploy_smoke_failed")
    assert post["action"] == "rollback_required"
    assert "restore_previous_known_good_static_release" in post["core_status"]
    cases += 1

    for failure in sorted(OWNER_REQUIRED):
        result = decide(policy, failure)
        assert result["action"] == "manual_required"
        assert result["owner_required"] is True
        assert result["production_publish_allowed"] is False
        cases += 1

    unknown = decide(policy, "future_unknown_failure")
    assert unknown["action"] == "manual_required" and unknown["owner_required"]
    cases += 1

    stage = transition(policy, "candidate", "isolated_pass")
    assert stage["state"] == "isolated_verified"
    stage = transition(policy, stage["state"], "preview_pass")
    assert stage["state"] == "preview_verified"
    denied = transition(policy, stage["state"], "publish_authorization", external_authorization=False)
    assert denied["ok"] is False and denied["state"] == "preview_verified"
    approved = transition(policy, stage["state"], "publish_authorization", external_authorization=True)
    assert approved["state"] == "publish_authorized" and approved["production_publish_allowed"] is True
    published = transition(policy, approved["state"], "publish_success", external_authorization=True)
    assert published["state"] == "published"
    assert transition(policy, "published", "postcheck_pass")["state"] == "postcheck_verified"
    assert transition(policy, "published", "postcheck_fail")["state"] == "rollback_required"
    cases += 7

    return {
        "status": "pass",
        "cases": cases,
        **summary,
        "invariants": {
            "no_self_publish": True,
            "bounded_retry": True,
            "cost_aware": True,
            "last_known_good_preserved": True,
            "core_and_enhancement_separated": True,
            "database_no_blind_rollback": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--failure-class")
    parser.add_argument("--attempt", type=int, default=0)
    parser.add_argument("--stage")
    parser.add_argument("--event")
    parser.add_argument("--external-authorization", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy = load_policy(root)

    if args.self_test:
        print(json.dumps(self_test(policy), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.validate:
        print(json.dumps(validate_policy(policy), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.stage or args.event:
        if not args.stage or not args.event:
            raise SystemExit("--stage and --event must be supplied together")
        print(json.dumps(
            transition(policy, args.stage, args.event, external_authorization=args.external_authorization),
            ensure_ascii=False, indent=2, sort_keys=True,
        ))
        return 0
    if not args.failure_class:
        raise SystemExit("choose --validate, --self-test, --failure-class, or --stage/--event")
    validate_policy(policy)
    print(json.dumps(decide(policy, args.failure_class, args.attempt), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

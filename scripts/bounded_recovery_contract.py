#!/usr/bin/env python3
"""Acceptance validator/self-test for the SWSI bounded-recovery policy.

Decision logic lives in bounded_recovery_decision.py. This file deliberately
imports that engine instead of maintaining a second copy of recovery logic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from bounded_recovery_decision import (
    OWNER_REQUIRED,
    REQUIRED_FAILURES,
    can_transition,
    decide_failure,
    load_policy,
    validate_policy,
)

RETRYABLE_REQUIRED = {
    "transient_timeout",
    "rate_limited_429",
    "upstream_5xx",
    "source_unavailable",
    "stale_job",
}


def validate_acceptance(policy: dict) -> dict:
    """Apply issue #279 invariants on top of the engine's schema checks."""
    validate_policy(policy)
    failures = policy["failure_classes"]

    if not REQUIRED_FAILURES.issubset(failures):
        raise ValueError("required failure classes missing")

    retryable_count = 0
    for name, row in failures.items():
        if row["retryable"]:
            retryable_count += 1
            if row["max_attempts"] > 5:
                raise ValueError(f"{name}: retry budget is not bounded")
            if row["backoff_class"] == "none":
                raise ValueError(f"{name}: retryable rule must define backoff")

    for name in RETRYABLE_REQUIRED:
        if not failures[name]["retryable"]:
            raise ValueError(f"{name}: expected bounded retry rule")

    for name in OWNER_REQUIRED:
        row = failures[name]
        if row.get("owner_required") is not True:
            raise ValueError(f"{name}: owner_required must remain true")
        if row["exhausted_action"] != "manual_required":
            raise ValueError(f"{name}: high-risk boundary must stop at manual_required")

    global_policy = policy["global"]
    if global_policy["contract_may_self_authorize_publish"] is not False:
        raise ValueError("contract must never self-authorize publish")
    if global_policy["automatic_blind_database_rollback"] is not False:
        raise ValueError("database blind rollback must remain disabled")
    if global_policy["automatic_paid_service_activation"] is not False:
        raise ValueError("automatic paid activation must remain disabled")
    if global_policy["automatic_qa_lowering"] is not False:
        raise ValueError("automatic QA lowering must remain disabled")
    if global_policy["automatic_official_core_mutation"] is not False:
        raise ValueError("automatic Official Core mutation must remain disabled")

    rollback = policy["rollback_boundaries"]
    if "no_blind_automatic_downgrade" not in rollback["database"]:
        raise ValueError("database rollback boundary weakened")
    if "official_evidence" not in rollback["official_answer_correction"]:
        raise ValueError("official correction must require official evidence")

    return {
        "failure_class_count": len(failures),
        "retryable_count": retryable_count,
        "owner_required_count": len(OWNER_REQUIRED),
        "release_state_count": len(policy["release_state_machine"]["states"]),
    }


def self_test(policy: dict) -> dict:
    summary = validate_acceptance(policy)
    cases = 0

    # Bounded transient retry + exhaustion.
    for failure in ("transient_timeout", "rate_limited_429", "upstream_5xx"):
        row = policy["failure_classes"][failure]
        first = decide_failure(policy, failure, 0)
        assert first["retry_allowed"] is True
        assert first["action"] == "retry"
        assert first["production_publish_authorized"] is False
        exhausted = decide_failure(policy, failure, row["max_attempts"])
        assert exhausted["retry_allowed"] is False
        assert exhausted["action"] == row["exhausted_action"]
        cases += 2

    # Source outage: preserve trusted state, not destructive replacement.
    source = decide_failure(policy, "source_unavailable", policy["failure_classes"]["source_unavailable"]["max_attempts"])
    assert source["action"] == "preserve_last_known_good"
    assert source["preserve_last_known_good"] is True
    cases += 1

    # Enhancement outage does not become core outage.
    ai = decide_failure(policy, "ai_unavailable")
    assert ai["action"] == "degrade_enhancement"
    assert ai["core_status"] == "available"
    assert ai["enhancement_status"] == "paused"
    cases += 1

    # Candidate / preview gates remain fail-closed.
    assert decide_failure(policy, "candidate_validation_failed")["action"] == "quarantine"
    assert decide_failure(policy, "preview_failed")["action"] == "quarantine"
    cases += 2

    # Static postcheck failure signals rollback-required only.
    post = decide_failure(policy, "post_deploy_smoke_failed")
    assert post["action"] == "rollback_required"
    assert post["production_publish_authorized"] is False
    cases += 1

    # DB/security/Official Core/paid-service boundaries require owner.
    for failure in sorted(OWNER_REQUIRED):
        result = decide_failure(policy, failure)
        assert result["action"] == "manual_required"
        assert result["owner_required"] is True
        assert result["production_publish_authorized"] is False
        cases += 1

    # Unknown future class must fail closed rather than invent behavior.
    try:
        decide_failure(policy, "future_unknown_failure")
    except ValueError:
        cases += 1
    else:
        raise AssertionError("unknown failure class must fail closed")

    # Release state machine cannot manufacture production authorization.
    s1 = can_transition(policy, "candidate", "isolated_verified")
    assert s1["allowed"] is True
    s2 = can_transition(policy, "isolated_verified", "preview_verified")
    assert s2["allowed"] is True
    denied = can_transition(policy, "preview_verified", "publish_authorized", False)
    assert denied["allowed"] is False
    assert denied["contract_generated_authorization"] is False
    approved = can_transition(policy, "preview_verified", "publish_authorized", True)
    assert approved["allowed"] is True
    assert approved["external_publish_authorization_consumed"] is True
    assert approved["contract_generated_authorization"] is False
    assert can_transition(policy, "publish_authorized", "published", True)["allowed"] is True
    assert can_transition(policy, "published", "postcheck_verified")["allowed"] is True
    assert can_transition(policy, "published", "rollback_required")["allowed"] is True
    cases += 7

    return {
        "status": "pass",
        "cases": cases,
        **summary,
        "invariants": {
            "single_decision_engine": True,
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
    args = parser.parse_args()

    policy = load_policy(Path(args.root).resolve())
    if args.self_test:
        result = self_test(policy)
    else:
        result = validate_acceptance(policy)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

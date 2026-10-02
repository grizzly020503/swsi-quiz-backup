#!/usr/bin/env python3
"""Deterministic bounded recovery/degradation decision contract for SWSI."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any

OWNER_REQUIRED = {
    "official_core_change", "auth_rls_secret_change", "destructive_schema",
    "paid_service_required", "unknown_migration_state",
}
STATIC_ROLLBACK = {"static_postcheck_failed"}
QUARANTINE = {"candidate_validation_failed", "preview_failed", "invalid_content"}
DEGRADE = {"ai_unavailable", "feedback_unavailable", "admin_unavailable"}
PRESERVE = {"source_unavailable", "sync_unavailable", "quota_exhausted", "stale_job"}
RETRYABLE = {"timeout", "http_429", "http_5xx"}
MAX_ATTEMPTS = {"timeout": 3, "http_429": 3, "http_5xx": 3}
BACKOFF = {
    "timeout": "exponential_short",
    "http_429": "respect_retry_after_then_exponential",
    "http_5xx": "exponential_short",
}

@dataclass(frozen=True)
class Decision:
    action: str
    retry_allowed: bool
    max_attempts: int
    next_attempt: int | None
    backoff_class: str | None
    preserve_last_known_good: bool
    core_available: bool
    enhancement_status: str
    production_publish_allowed: bool
    owner_required: bool
    rollback_mode: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def decide(failure_class: str, attempt: int = 0, *, publish_authorized: bool = False) -> Decision:
    failure = str(failure_class or "").strip()
    if not failure:
        raise ValueError("failure_class is required")
    if attempt < 0:
        raise ValueError("attempt must be >= 0")

    if failure in OWNER_REQUIRED:
        return Decision(
            "manual_required", False, 0, None, None, True, True, "paused", False, True,
            "forward_recovery_or_restore_only" if "schema" in failure or "migration" in failure else "none",
            "high-risk boundary requires explicit maintainer decision",
        )
    if failure in STATIC_ROLLBACK:
        return Decision(
            "rollback_required", False, 0, None, None, True, True, "paused", False, True,
            "restore_last_known_good_static_release",
            "post-deploy static verification failed; restore previous verified release",
        )
    if failure in QUARANTINE:
        return Decision(
            "quarantine_candidate", False, 0, None, None, True, True, "paused", False, False, "none",
            "candidate/preview evidence is not trusted enough to publish",
        )
    if failure in DEGRADE:
        return Decision(
            "degrade_enhancement", False, 0, None, None, True, True, "degraded", False, False, "none",
            "non-core enhancement is unavailable; core study must remain usable",
        )
    if failure in PRESERVE:
        return Decision(
            "preserve_last_known_good", False, 0, None, None, True, True, "stale_or_paused", False, False, "none",
            "do not replace trusted state with missing/stale/unverified output",
        )
    if failure in RETRYABLE:
        maximum = MAX_ATTEMPTS[failure]
        if attempt < maximum:
            return Decision(
                "retry_bounded", True, maximum, attempt + 1, BACKOFF[failure], True, True, "retrying",
                False, False, "none", "transient failure may retry within the bounded budget",
            )
        return Decision(
            "preserve_last_known_good", False, maximum, None, BACKOFF[failure], True, True, "stale_or_paused",
            False, False, "none", "retry budget exhausted; stop instead of looping indefinitely",
        )
    return Decision(
        "manual_required", False, 0, None, None, True, True, "paused", False, True, "none",
        "unknown failure class fails closed",
    )


def transition(stage: str, event: str, *, publish_authorized: bool = False) -> dict[str, Any]:
    allowed = {
        ("candidate", "isolated_pass"): "isolated_verified",
        ("isolated_verified", "preview_pass"): "preview_verified",
        ("preview_verified", "owner_publish_approval"): "publish_authorized",
        ("publish_authorized", "publish_success"): "published",
        ("published", "postcheck_pass"): "postcheck_verified",
        ("candidate", "validation_fail"): "quarantined",
        ("isolated_verified", "preview_fail"): "quarantined",
        ("preview_verified", "preview_fail"): "quarantined",
        ("published", "postcheck_fail"): "rollback_required",
    }
    if event == "owner_publish_approval" and not publish_authorized:
        return {"ok": False, "state": stage, "reason": "external explicit publish authorization is required", "production_publish_allowed": False}
    target = allowed.get((stage, event))
    if not target:
        return {"ok": False, "state": stage, "reason": "transition is not allowlisted", "production_publish_allowed": False}
    return {"ok": True, "state": target, "production_publish_allowed": target == "publish_authorized" and publish_authorized}


def self_test() -> dict[str, Any]:
    cases = 0
    for failure in ("timeout", "http_429", "http_5xx"):
        first = decide(failure, 0)
        assert first.retry_allowed and first.next_attempt == 1
        exhausted = decide(failure, first.max_attempts)
        assert not exhausted.retry_allowed and exhausted.action == "preserve_last_known_good"
        cases += 2
    source = decide("source_unavailable")
    assert source.preserve_last_known_good and source.core_available
    cases += 1
    ai = decide("ai_unavailable")
    assert ai.action == "degrade_enhancement" and ai.core_available and ai.enhancement_status == "degraded"
    cases += 1
    assert decide("candidate_validation_failed").action == "quarantine_candidate"
    assert decide("preview_failed").action == "quarantine_candidate"
    cases += 2
    static = decide("static_postcheck_failed")
    assert static.action == "rollback_required" and static.rollback_mode == "restore_last_known_good_static_release" and static.owner_required
    cases += 1
    for failure in ("destructive_schema", "unknown_migration_state", "auth_rls_secret_change", "official_core_change", "paid_service_required"):
        d = decide(failure)
        assert d.action == "manual_required" and d.owner_required and not d.production_publish_allowed
        cases += 1
    s1 = transition("candidate", "isolated_pass")
    s2 = transition(s1["state"], "preview_pass")
    denied = transition(s2["state"], "owner_publish_approval", publish_authorized=False)
    assert not denied["ok"] and denied["state"] == "preview_verified"
    approved = transition(s2["state"], "owner_publish_approval", publish_authorized=True)
    assert approved["state"] == "publish_authorized"
    assert transition(approved["state"], "publish_success", publish_authorized=True)["state"] == "published"
    assert transition("published", "postcheck_fail")["state"] == "rollback_required"
    cases += 5
    unknown = decide("something_new")
    assert unknown.owner_required and unknown.action == "manual_required"
    cases += 1
    return {"ok": True, "cases": cases, "invariants": {
        "no_self_publish": True,
        "bounded_retry": True,
        "last_known_good_preserved": True,
        "core_separate_from_enhancements": True,
        "db_no_blind_rollback": True,
    }}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--failure-class")
    p.add_argument("--attempt", type=int, default=0)
    p.add_argument("--publish-authorized", action="store_true")
    p.add_argument("--stage")
    p.add_argument("--event")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0
    if args.stage or args.event:
        if not args.stage or not args.event:
            raise SystemExit("--stage and --event must be supplied together")
        print(json.dumps(transition(args.stage, args.event, publish_authorized=args.publish_authorized), ensure_ascii=False, indent=2))
        return 0
    if not args.failure_class:
        raise SystemExit("--failure-class is required unless --self-test or --stage/--event is used")
    print(json.dumps(decide(args.failure_class, args.attempt, publish_authorized=args.publish_authorized).as_dict(), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

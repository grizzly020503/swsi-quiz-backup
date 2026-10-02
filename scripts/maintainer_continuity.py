#!/usr/bin/env python3
"""Validate SWSI maintainer-continuity metadata and minimum-survival behavior."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

SENSITIVE_KEY_TOKENS = {
    "password",
    "token",
    "secret",
    "email",
    "account_id",
    "user_id",
    "recovery_code",
    "mfa",
    "private_key",
    "api_key",
    "service_role_key",
    "phone",
}
CRITICALITIES = {"low", "medium", "high", "critical"}
DEPENDENCY_TYPES = {"core", "enhancement", "external_source"}
RENEWAL_TYPES = {"none", "terms_review", "manual_renewal_review"}
REQUIRED_HUMAN_DECISIONS = {
    "account_succession",
    "provider_new_terms",
    "major_security_incident",
    "new_paid_obligation",
    "disputed_official_content",
    "destructive_migration",
}
REQUIRED_CORE = {
    "home_navigation",
    "official_mcq",
    "grading_contract",
    "practice_sessions",
    "mock_exams",
    "wrong_answer_review",
    "local_learning_progress",
    "essay_library",
    "local_essay_drafts",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sensitive_keys(value: Any, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in SENSITIVE_KEY_TOKENS or any(
                normalized.endswith("_" + token) for token in SENSITIVE_KEY_TOKENS
            ):
                hits.append(f"{prefix}.{key}" if prefix else str(key))
            hits.extend(
                sensitive_keys(child, f"{prefix}.{key}" if prefix else str(key))
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(sensitive_keys(child, f"{prefix}[{index}]"))
    return hits


def validate_contract(payload: Any, root: Path | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("contract must be schema_version=1")

    hits = sensitive_keys(payload)
    if hits:
        raise ValueError("sensitive field keys are forbidden: " + ", ".join(hits[:10]))

    services = payload.get("services")
    if not isinstance(services, list) or not services:
        raise ValueError("services[] must be non-empty")
    seen: set[str] = set()
    for row in services:
        if not isinstance(row, dict):
            raise ValueError("service entry must be object")
        service_id = str(row.get("id") or "").strip()
        if not service_id or service_id in seen:
            raise ValueError(f"missing or duplicate service id: {service_id!r}")
        seen.add(service_id)
        for field in ("purpose", "owner_role", "fallback", "credentials_policy"):
            if not str(row.get(field) or "").strip():
                raise ValueError(f"{service_id}: {field} is required")
        if row.get("credentials_policy") != "external_secret_only":
            raise ValueError(
                f"{service_id}: credentials_policy must be external_secret_only"
            )
        if str(row.get("criticality") or "") not in CRITICALITIES:
            raise ValueError(f"{service_id}: invalid criticality")
        if str(row.get("dependency_type") or "") not in DEPENDENCY_TYPES:
            raise ValueError(f"{service_id}: invalid dependency_type")
        if str(row.get("renewal_type") or "") not in RENEWAL_TYPES:
            raise ValueError(f"{service_id}: invalid renewal_type")
        refs = row.get("recovery_references")
        if not isinstance(refs, list) or not refs or not all(
            isinstance(x, str) and x.strip() for x in refs
        ):
            raise ValueError(f"{service_id}: recovery_references must be non-empty")
        if root is not None:
            missing = [ref for ref in refs if not (root / ref).exists()]
            if missing:
                raise ValueError(
                    f"{service_id}: missing recovery reference(s): {missing}"
                )

    mode = payload.get("minimum_survival_mode")
    if not isinstance(mode, dict):
        raise ValueError("minimum_survival_mode is required")
    if mode.get("mode") != "last_verified_updates_paused":
        raise ValueError("minimum survival mode name mismatch")
    if mode.get("updates_paused") is not True:
        raise ValueError("minimum survival mode must pause updates")
    if mode.get("freshness_disclosure_required") is not True:
        raise ValueError("freshness disclosure is required")
    if mode.get("auto_payment") is not False:
        raise ValueError("auto_payment must remain false")
    if mode.get("auto_account_takeover") is not False:
        raise ValueError("auto_account_takeover must remain false")
    if mode.get("review_queue_policy") != "preserve_no_delete":
        raise ValueError("review queue must be preserved")
    if mode.get("qa_policy") != "no_lowering":
        raise ValueError("QA lowering is forbidden")
    core = set(mode.get("core_capabilities") or [])
    missing_core = sorted(REQUIRED_CORE - core)
    if missing_core:
        raise ValueError(
            f"minimum survival mode missing core capability: {missing_core}"
        )

    decisions = set(payload.get("human_only_decisions") or [])
    missing_decisions = sorted(REQUIRED_HUMAN_DECISIONS - decisions)
    if missing_decisions:
        raise ValueError(f"missing human-only decision(s): {missing_decisions}")

    allowed = payload.get("automation_allowlist")
    if not isinstance(allowed, list) or not allowed:
        raise ValueError("automation_allowlist must be non-empty")
    forbidden_verbs = {
        "merge",
        "deploy",
        "publish",
        "pay",
        "delete",
        "takeover",
        "downgrade_qa",
    }
    if any(str(item).strip() in forbidden_verbs for item in allowed):
        raise ValueError("automation allowlist contains privileged/destructive action")

    return {
        "ok": True,
        "services": len(services),
        "minimum_survival_mode": mode["mode"],
        "sensitive_field_keys": 0,
        "recovery_references_checked": root is not None,
    }


def evaluate_event(payload: dict[str, Any], event: str) -> dict[str, Any]:
    validate_contract(payload)
    event = str(event or "").strip()
    mode = payload["minimum_survival_mode"]
    base = {
        "event": event,
        "core_available": True,
        "auto_payment": False,
        "auto_account_takeover": False,
        "review_queue_preserved": True,
        "qa_lowering_allowed": False,
        "production_change_allowed": False,
    }
    if event == "normal":
        return {
            **base,
            "mode": "normal",
            "updates_paused": False,
            "enhancement_status": "normal",
            "human_decision_required": False,
        }
    if event == "ai_unavailable":
        return {
            **base,
            "mode": "normal_core_enhancement_degraded",
            "updates_paused": False,
            "enhancement_status": "degraded",
            "human_decision_required": False,
        }
    if event in {
        "maintainer_absent",
        "account_recovery_pending",
        "paid_decision_pending",
        "disputed_update",
    }:
        reason = {
            "maintainer_absent": "maintainer succession unresolved",
            "account_recovery_pending": "account recovery unresolved",
            "paid_decision_pending": "new paid obligation needs owner decision",
            "disputed_update": "disputed content stays quarantined",
        }[event]
        return {
            **base,
            "mode": mode["mode"],
            "updates_paused": True,
            "enhancement_status": "paused_or_degraded",
            "human_decision_required": True,
            "freshness_disclosure_required": True,
            "serve_last_verified_revision": True,
            "reason": reason,
        }
    return {
        **base,
        "mode": mode["mode"],
        "updates_paused": True,
        "enhancement_status": "paused_or_degraded",
        "human_decision_required": True,
        "freshness_disclosure_required": True,
        "serve_last_verified_revision": True,
        "reason": "unknown continuity event fails closed",
    }


def self_test() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for ref in ("RELEASE.md", "ZERO_COST_OPERATIONS.md", "docs/recovery.md"):
            path = root / ref
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n", encoding="utf-8")

        sample = {
            "schema_version": 1,
            "services": [
                {
                    "id": "source",
                    "purpose": "source of truth",
                    "owner_role": "repository_maintainer",
                    "criticality": "critical",
                    "dependency_type": "core",
                    "recovery_references": ["RELEASE.md", "docs/recovery.md"],
                    "renewal_type": "none",
                    "paid_required": False,
                    "fallback": "portable source export",
                    "credentials_policy": "external_secret_only",
                }
            ],
            "minimum_survival_mode": {
                "mode": "last_verified_updates_paused",
                "updates_paused": True,
                "freshness_disclosure_required": True,
                "auto_payment": False,
                "auto_account_takeover": False,
                "review_queue_policy": "preserve_no_delete",
                "qa_policy": "no_lowering",
                "core_capabilities": sorted(REQUIRED_CORE),
            },
            "human_only_decisions": sorted(REQUIRED_HUMAN_DECISIONS),
            "automation_allowlist": [
                "read_only_health",
                "hash_verification",
                "public_source_check",
                "diagnostic_export",
            ],
        }
        result = validate_contract(sample, root=root)
        assert result["services"] == 1

        for event in (
            "maintainer_absent",
            "account_recovery_pending",
            "paid_decision_pending",
            "disputed_update",
        ):
            out = evaluate_event(sample, event)
            assert out["mode"] == "last_verified_updates_paused"
            assert out["updates_paused"] is True
            assert out["core_available"] is True
            assert out["human_decision_required"] is True
            assert out["auto_payment"] is False
            assert out["auto_account_takeover"] is False

        ai = evaluate_event(sample, "ai_unavailable")
        assert ai["core_available"] is True
        assert ai["enhancement_status"] == "degraded"
        assert ai["updates_paused"] is False

        bad = json.loads(json.dumps(sample))
        bad["services"][0]["token"] = "forbidden-even-as-fixture"
        try:
            validate_contract(bad)
        except ValueError as exc:
            assert "sensitive field keys" in str(exc)
        else:
            raise AssertionError("sensitive key must fail closed")

        missing = json.loads(json.dumps(sample))
        missing["services"][0]["recovery_references"] = ["docs/missing.md"]
        try:
            validate_contract(missing, root=root)
        except ValueError as exc:
            assert "missing recovery reference" in str(exc)
        else:
            raise AssertionError("missing recovery reference must fail closed")

        return {
            "ok": True,
            "cases": 7,
            "sensitive_metadata_rejected": True,
            "minimum_survival_preserves_core": True,
            "ai_outage_does_not_kill_core": True,
        }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--contract",
        type=Path,
        default=Path("data/maintainer_continuity_contract.v1.json"),
    )
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--event")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()

    if args.self_test:
        payload = self_test()
    else:
        contract = read_json(args.contract)
        validation = validate_contract(contract, root=args.root.resolve())
        payload = (
            {"validation": validation, "decision": evaluate_event(contract, args.event)}
            if args.event
            else validation
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

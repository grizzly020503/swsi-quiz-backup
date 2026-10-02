#!/usr/bin/env python3
"""Fail-closed validator for SWSI maintainer succession and minimum-survival contracts."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

SENSITIVE_KEYS = {
    "name", "email", "account_id", "account_identifier", "username",
    "password", "token", "secret", "api_key", "service_role_key",
    "mfa", "mfa_code", "recovery_code", "credential", "credentials"
}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_SERVICE_FIELDS = {
    "id", "purpose", "owner_role", "criticality", "core_or_enhancement",
    "recovery_reference", "renewal_type", "fallback", "credential_policy"
}
ALLOWED_CRITICALITY = {"high", "medium", "low"}
ALLOWED_CLASS = {"core", "enhancement", "fallback"}
REQUIRED_PRESERVE = {
    "home_navigation", "official_question_corpus", "grading_contract",
    "practice_sessions", "mock_exams", "wrong_answer_review",
    "local_learning_progress", "essay_library", "local_essay_drafts"
}
REQUIRED_HUMAN_ONLY = {
    "account_succession", "provider_new_terms", "major_security_incident",
    "new_paid_obligation", "disputed_official_content", "destructive_migration"
}
REQUIRED_AUTOMATION_ALLOWLIST = {
    "read_only_health", "hash_verification",
    "public_source_change_detection", "deterministic_local_validation"
}
EXPECTED_SCENARIOS = {
    "maintainer_absent": "enter_last_verified_updates_paused",
    "account_recovery_pending": "keep_core_and_wait_for_human",
    "ai_unavailable": "degrade_ai_only_keep_core",
    "paid_decision_pending": "do_not_pay_or_accept_terms_automatically",
    "disputed_update": "hold_unverified_and_require_human_review"
}

class ContractError(ValueError):
    pass


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def walk_sensitive(value, path="$"):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in SENSITIVE_KEYS:
                raise ContractError(f"sensitive field key forbidden: {path}.{key}")
            walk_sensitive(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            walk_sensitive(child, f"{path}[{i}]")
    elif isinstance(value, str) and EMAIL_RE.match(value.strip()):
        raise ContractError(f"email-like value forbidden: {path}")


def validate_registry(registry, root: Path):
    if registry.get("schema_version") != 1:
        raise ContractError("registry schema_version must be 1")
    if registry.get("credential_policy") != "external_secret_only":
        raise ContractError("registry credential_policy must be external_secret_only")
    walk_sensitive(registry)
    services = registry.get("services")
    if not isinstance(services, list) or not services:
        raise ContractError("services must be a non-empty list")
    ids = set()
    for row in services:
        missing = REQUIRED_SERVICE_FIELDS - set(row)
        if missing:
            raise ContractError(f"service missing fields: {sorted(missing)}")
        sid = row["id"]
        if sid in ids:
            raise ContractError(f"duplicate service id: {sid}")
        ids.add(sid)
        if row["criticality"] not in ALLOWED_CRITICALITY:
            raise ContractError(f"invalid criticality for {sid}")
        if row["core_or_enhancement"] not in ALLOWED_CLASS:
            raise ContractError(f"invalid core_or_enhancement for {sid}")
        if row["credential_policy"] != "external_secret_only":
            raise ContractError(f"credential policy must be external_secret_only for {sid}")
        if not isinstance(row["owner_role"], str) or not row["owner_role"].endswith("_maintainer"):
            raise ContractError(f"owner_role must be a role, not a person, for {sid}")
        if not isinstance(row["fallback"], str) or len(row["fallback"].strip()) < 12:
            raise ContractError(f"fallback missing for {sid}")
        ref = Path(row["recovery_reference"])
        if ref.is_absolute() or ".." in ref.parts:
            raise ContractError(f"unsafe recovery reference for {sid}")
        if not (root / ref).is_file():
            raise ContractError(f"recovery reference missing for {sid}: {ref}")
    return {"service_count": len(services)}


def validate_survival(contract):
    if contract.get("schema_version") != 1:
        raise ContractError("survival schema_version must be 1")
    walk_sensitive(contract)
    if contract.get("mode") != "last_verified_updates_paused":
        raise ContractError("minimum-survival mode must be last_verified_updates_paused")
    preserve = set(contract.get("must_preserve", []))
    missing = REQUIRED_PRESERVE - preserve
    if missing:
        raise ContractError(f"survival contract missing core: {sorted(missing)}")
    human = set(contract.get("human_only_decisions", []))
    missing = REQUIRED_HUMAN_ONLY - human
    if missing:
        raise ContractError(f"human-only decisions missing: {sorted(missing)}")
    allowed = set(contract.get("automation_allowlist", []))
    if allowed != REQUIRED_AUTOMATION_ALLOWLIST:
        raise ContractError("automation allowlist must stay read-only and exact")
    disclosure = contract.get("freshness_disclosure", {})
    if disclosure.get("required") is not True or disclosure.get("updates_paused_value") is not True:
        raise ContractError("freshness disclosure must be required with updates_paused=true")
    required_fields = set(disclosure.get("required_fields", []))
    for field in {"last_verified_revision", "last_verified_at", "updates_paused", "freshness_notice"}:
        if field not in required_fields:
            raise ContractError(f"freshness disclosure missing field: {field}")
    safety = contract.get("safety", {})
    forbidden_true = {
        "auto_payment", "auto_account_takeover", "delete_review_queue",
        "lower_qa_gate", "promote_unverified_content", "destructive_migration"
    }
    for key in forbidden_true:
        if safety.get(key) is not False:
            raise ContractError(f"safety invariant must be false: {key}")
    scenarios = contract.get("scenario_expectations", {})
    if scenarios != EXPECTED_SCENARIOS:
        raise ContractError("scenario expectations changed from fail-safe contract")
    return {
        "mode": contract["mode"],
        "preserved_core_count": len(preserve),
        "human_only_decision_count": len(human)
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--registry", default="data/service_responsibility_registry.v1.json")
    ap.add_argument("--survival", default="data/minimum_survival_contract.v1.json")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    registry = load(root / args.registry)
    survival = load(root / args.survival)
    result = {
        "registry": validate_registry(registry, root),
        "survival": validate_survival(survival)
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print("MAINTAINER SURVIVAL CONTRACT OK")
        print(f"services={result['registry']['service_count']}")
        print(f"mode={result['survival']['mode']}")
        print(f"preserved_core={result['survival']['preserved_core_count']}")
        print(f"human_only_decisions={result['survival']['human_only_decision_count']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Synthetic regression tests for maintainer-survival contracts."""
from __future__ import annotations
import copy
import tempfile
from pathlib import Path

from maintainer_survival_validate import ContractError, validate_registry, validate_survival

BASE_REGISTRY = {
    "schema_version": 1,
    "credential_policy": "external_secret_only",
    "services": [{
        "id": "synthetic",
        "purpose": "Synthetic provider for contract tests.",
        "owner_role": "test_maintainer",
        "criticality": "medium",
        "core_or_enhancement": "enhancement",
        "recovery_reference": "recovery.md",
        "renewal_type": "manual_provider_terms",
        "fallback": "Keep the verified local core available.",
        "credential_policy": "external_secret_only"
    }]
}

BASE_SURVIVAL = {
    "schema_version": 1,
    "mode": "last_verified_updates_paused",
    "purpose": "Synthetic minimum survival.",
    "must_preserve": [
        "home_navigation", "official_question_corpus", "grading_contract",
        "practice_sessions", "mock_exams", "wrong_answer_review",
        "local_learning_progress", "essay_library", "local_essay_drafts"
    ],
    "may_degrade_or_pause": ["ai_analysis"],
    "freshness_disclosure": {
        "required": True,
        "required_fields": ["last_verified_revision", "last_verified_at", "updates_paused", "freshness_notice"],
        "updates_paused_value": True
    },
    "automation_allowlist": [
        "read_only_health", "hash_verification",
        "public_source_change_detection", "deterministic_local_validation"
    ],
    "human_only_decisions": [
        "account_succession", "provider_new_terms", "major_security_incident",
        "new_paid_obligation", "disputed_official_content", "destructive_migration"
    ],
    "safety": {
        "auto_payment": False,
        "auto_account_takeover": False,
        "delete_review_queue": False,
        "lower_qa_gate": False,
        "promote_unverified_content": False,
        "destructive_migration": False
    },
    "scenario_expectations": {
        "maintainer_absent": "enter_last_verified_updates_paused",
        "account_recovery_pending": "keep_core_and_wait_for_human",
        "ai_unavailable": "degrade_ai_only_keep_core",
        "paid_decision_pending": "do_not_pay_or_accept_terms_automatically",
        "disputed_update": "hold_unverified_and_require_human_review"
    }
}


def must_fail(fn, label):
    try:
        fn()
    except ContractError:
        return
    raise AssertionError(f"expected failure: {label}")


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / "recovery.md").write_text("synthetic", encoding="utf-8")
    assert validate_registry(copy.deepcopy(BASE_REGISTRY), root)["service_count"] == 1
    assert validate_survival(copy.deepcopy(BASE_SURVIVAL))["mode"] == "last_verified_updates_paused"

    bad = copy.deepcopy(BASE_REGISTRY)
    bad["services"][0]["email"] = "maintainer@example.invalid"
    must_fail(lambda: validate_registry(bad, root), "sensitive email field")

    bad = copy.deepcopy(BASE_REGISTRY)
    del bad["services"][0]["owner_role"]
    must_fail(lambda: validate_registry(bad, root), "missing owner role")

    bad = copy.deepcopy(BASE_REGISTRY)
    bad["services"][0]["recovery_reference"] = "missing.md"
    must_fail(lambda: validate_registry(bad, root), "missing recovery reference")

    for key in ["auto_payment", "auto_account_takeover", "delete_review_queue", "lower_qa_gate", "promote_unverified_content"]:
        bad = copy.deepcopy(BASE_SURVIVAL)
        bad["safety"][key] = True
        must_fail(lambda b=bad: validate_survival(b), key)

    bad = copy.deepcopy(BASE_SURVIVAL)
    bad["human_only_decisions"].remove("disputed_official_content")
    must_fail(lambda: validate_survival(bad), "disputed official content must remain human-only")

    bad = copy.deepcopy(BASE_SURVIVAL)
    bad["scenario_expectations"]["ai_unavailable"] = "disable_core"
    must_fail(lambda: validate_survival(bad), "AI outage cannot disable core")

print("MAINTAINER SURVIVAL SELFTEST OK")

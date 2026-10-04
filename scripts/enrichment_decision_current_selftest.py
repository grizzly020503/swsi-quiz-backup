#!/usr/bin/env python3
"""Zero-network fixtures for current-intake legal-watch enrichment projection."""
from __future__ import annotations

import copy

from enrichment_decision import ROOT, build_report, read_json
from enrichment_decision_current import apply_trusted_current_legal_watch

POLICY = read_json(ROOT / "data/enrichment_decision_policy.v1.json")
QUESTION_POLICY = read_json(ROOT / "data/question_qa_policy_v1.json")


def legal_row() -> dict:
    return {
        "id": "SP-116-1-001",
        "subject": "社會政策與社會立法",
        "year": "116",
        "round": "第一次",
        "qno": "1",
        "question": "依社會救助法規定，下列何者正確？",
        "opt_a": "應依法律規定辦理",
        "opt_b": "可完全忽略法律規定",
        "opt_c": "不需要依法行政",
        "opt_d": "所有規定都可任意變更",
        "answer": "A",
        "accepted_answers": None,
        "grading_mode": "standard",
        "major": "社會救助",
        "topic": "社會救助 > 法規原則",
        "keywords": "社會救助法,依法行政",
        "exp_why": "正確選項符合社會救助法的法律規定。",
        "exp_others": "B選項：不能忽略法律規定。C選項：仍須依法行政。D選項：規定不能任意變更。",
        "exp_trap": "注意題目要求依法規判斷。",
        "mnemonic": "依法辦理。",
        "extension": "比較社會救助的法規原則。",
        "law": "社會救助法",
        "mistake": "法規混淆",
        "analysis_status": "ready",
        "legal_status": "unreviewed",
    }


def watch(*, changed: bool = False, lookup_errors: int = 0) -> dict:
    return {
        "schema_version": 3,
        "checked_at": "2026-10-05T00:00:00Z",
        "lookup_error_count": lookup_errors,
        "missing_count": 0,
        "changed_count": 1 if changed else 0,
        "records": {
            "社會救助法": {
                "canonical_name": "社會救助法",
                "found": True,
                "changed": changed,
            }
        },
    }


def base_report(row: dict) -> dict:
    return build_report(
        [row],
        policy=POLICY,
        question_policy=QUESTION_POLICY,
        source="fixture",
    )


def main() -> int:
    base = base_report(legal_row())
    assert base["summary"]["human_review_count"] == 1, base["summary"]
    assert base["items"][0]["review_reasons"] == ["ENRICHMENT_LEGAL_EVIDENCE_REQUIRED"]

    cleared = apply_trusted_current_legal_watch(base, watch=watch(), policy=POLICY)
    item = cleared["items"][0]
    assert item["enrichment_status"] == "passed", item
    assert item["automation_confidence"] == "high", item
    assert item["evidence"]["legal_watch_fresh"] is True
    assert cleared["summary"]["human_review_count"] == 0
    assert cleared["current_legal_watch"]["cleared_review_count"] == 1
    assert cleared["current_legal_watch"]["historical_version_proof"] is False

    changed = apply_trusted_current_legal_watch(base, watch=watch(changed=True), policy=POLICY)
    assert changed["items"][0]["enrichment_status"] == "needs_review", changed["items"][0]
    assert changed["current_legal_watch"]["cleared_review_count"] == 0

    failed_lookup = apply_trusted_current_legal_watch(
        base, watch=watch(lookup_errors=1), policy=POLICY
    )
    assert failed_lookup["items"][0]["enrichment_status"] == "needs_review"

    generic = legal_row()
    generic["id"] = "SP-116-1-002"
    generic["question"] = "近期法規修正時，下列處理原則何者正確？"
    generic["law"] = None
    generic["keywords"] = "法規修正,依法行政"
    generic["exp_why"] = "正確選項強調依法行政。"
    generic["extension"] = "比較法規修正與依法行政。"
    generic_base = base_report(generic)
    assert "ENRICHMENT_LEGAL_EVIDENCE_REQUIRED" in generic_base["items"][0]["review_reasons"]
    generic_result = apply_trusted_current_legal_watch(
        generic_base, watch=watch(), policy=POLICY
    )
    assert generic_result["items"][0]["enrichment_status"] == "needs_review"
    assert generic_result["current_legal_watch"]["cleared_review_count"] == 0

    conflict = legal_row()
    conflict["id"] = "SP-116-1-003"
    conflict["exp_others"] = "A選項：錯誤。B選項：不符規定。C選項：不符規定。D選項：不符規定。"
    conflict_base = base_report(conflict)
    assert set(conflict_base["items"][0]["review_reasons"]) == {
        "ENRICHMENT_ACCEPTED_ANSWER_IN_OTHERS",
        "ENRICHMENT_LEGAL_EVIDENCE_REQUIRED",
    }
    conflict_result = apply_trusted_current_legal_watch(
        conflict_base, watch=watch(), policy=POLICY
    )
    assert conflict_result["items"][0]["enrichment_status"] == "needs_review"
    assert conflict_result["items"][0]["review_reasons"] == [
        "ENRICHMENT_ACCEPTED_ANSWER_IN_OTHERS"
    ]
    assert conflict_result["current_legal_watch"]["cleared_review_count"] == 1

    # Projection must not mutate the base report in-place.
    assert base["items"][0]["enrichment_status"] == "needs_review"
    assert base["summary"]["human_review_count"] == 1

    print(
        "ENRICHMENT CURRENT LEGAL WATCH SELFTEST OK: "
        "unchanged canonical law clears only duplicate current-intake legal review; "
        "changed/error/unnamed law and unrelated findings remain review"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

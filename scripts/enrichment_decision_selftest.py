#!/usr/bin/env python3
"""Deterministic zero-network fixtures for enrichment_decision.py."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from enrichment_decision import (
    ROOT,
    build_report,
    extract_law_names,
    load_law_registry,
    read_json,
)

POLICY = read_json(ROOT / "data/enrichment_decision_policy.v1.json")
QUESTION_POLICY = read_json(ROOT / "data/question_qa_policy_v1.json")


def base_row() -> dict:
    return {
        "id": "SW-116-1-001",
        "subject": "社會工作",
        "year": "116",
        "round": "第一次",
        "qno": "1",
        "question": "有關社會工作專業關係的敘述，下列何者正確？",
        "opt_a": "應維持清楚的專業界線",
        "opt_b": "應完全避免與服務對象溝通",
        "opt_c": "應由服務對象決定所有專業倫理",
        "opt_d": "應忽略服務對象的自主選擇",
        "answer": "A",
        "accepted_answers": None,
        "grading_mode": "standard",
        "major": "社會工作專業",
        "topic": "專業關係 > 專業界線",
        "keywords": "專業關係,專業界線,自主",
        "exp_why": "正確敘述強調專業關係需要維持清楚的專業界線。",
        "exp_others": "B選項：完全避免溝通不符合專業關係。C選項：不能把所有專業倫理交由服務對象決定。D選項：忽略自主選擇不符合專業關係。",
        "exp_trap": "容易把尊重自主誤解成放棄專業責任。",
        "exp_raw": None,
        "mnemonic": "尊重自主也要守住專業界線。",
        "extension": "比較專業界線與服務對象自主。",
        "law": None,
        "mistake": "概念混淆",
        "analysis_status": "ready",
        "legal_status": "not_applicable",
    }


def one(row: dict) -> dict:
    report = build_report(
        [row],
        policy=POLICY,
        question_policy=QUESTION_POLICY,
        source="fixture",
    )
    assert report["safety"] == {
        "official_core_modified": False,
        "production_write_performed": False,
        "model_called": False,
        "numeric_model_confidence_claimed": False,
    }
    return report["items"][0]


def main() -> int:
    good = one(base_row())
    assert good["enrichment_status"] == "passed", good
    assert good["automation_confidence"] == "high", good
    assert good["publish_action"] == "publish", good

    pending = base_row()
    pending["analysis_status"] = "pending"
    for key in ("major", "topic", "keywords", "exp_why", "exp_others", "exp_trap", "mnemonic", "extension", "mistake"):
        pending[key] = None
    pending_result = one(pending)
    assert pending_result["enrichment_status"] == "pending_generation", pending_result
    assert pending_result["review_reasons"] == [], pending_result

    upstream_review = base_row()
    upstream_review["analysis_status"] = "review"
    review_result = one(upstream_review)
    assert review_result["enrichment_status"] == "needs_review", review_result
    assert review_result["review_reasons"] == ["UPSTREAM_ANALYSIS_REVIEW"], review_result

    missing = base_row()
    missing["exp_why"] = ""
    missing_result = one(missing)
    assert missing_result["enrichment_status"] == "blocked", missing_result
    assert "ENRICHMENT_REQUIRED_FIELDS" in missing_result["review_reasons"], missing_result

    extra_ascii = base_row()
    extra_ascii["extension"] = "比較專業界線與 GPT 判斷。"
    ascii_result = one(extra_ascii)
    assert ascii_result["enrichment_status"] == "blocked", ascii_result
    assert "ENRICHMENT_UNGROUNDED_ASCII" in ascii_result["review_reasons"], ascii_result

    extra_number = base_row()
    extra_number["extension"] = "整理第5階段的相關比較。"
    number_result = one(extra_number)
    assert number_result["enrichment_status"] == "blocked", number_result
    assert "ENRICHMENT_UNGROUNDED_NUMBER" in number_result["review_reasons"], number_result

    answer_conflict = base_row()
    answer_conflict["exp_others"] = "A選項：這個答案錯誤。B選項：不符合專業關係。C選項：不符合專業倫理。D選項：忽略自主不恰當。"
    conflict_result = one(answer_conflict)
    assert conflict_result["enrichment_status"] == "needs_review", conflict_result
    assert "ENRICHMENT_ACCEPTED_ANSWER_IN_OTHERS" in conflict_result["review_reasons"], conflict_result

    multi = base_row()
    multi["accepted_answers"] = ["A", "B"]
    multi["exp_why"] = "A與B皆為官方可接受答案。"
    multi["exp_others"] = "C選項：不符合題意。D選項：不符合題意。"
    multi_result = one(multi)
    assert multi_result["enrichment_status"] == "needs_review", multi_result
    assert multi_result["risk"] in {"medium", "high"}, multi_result
    assert "ENRICHMENT_MULTI_ANSWER_REVIEW" in multi_result["review_reasons"], multi_result

    special = base_row()
    special["grading_mode"] = "all_credit"
    special["answer"] = "一律給分"
    special_result = one(special)
    assert special_result["enrichment_status"] == "blocked", special_result
    assert "ENRICHMENT_SPECIAL_GRADING" in special_result["review_reasons"], special_result

    legal = base_row()
    legal["question"] = "依社會救助法規定，下列何者正確？"
    legal["opt_a"] = "應依法律規定辦理"
    legal["law"] = "社會救助法"
    legal["legal_status"] = "unreviewed"
    legal_result = one(legal)
    assert legal_result["enrichment_status"] == "needs_review", legal_result
    assert "ENRICHMENT_LEGAL_EVIDENCE_REQUIRED" in legal_result["review_reasons"], legal_result
    assert legal_result["field_actions"] == {}, legal_result

    legal_checked = copy.deepcopy(legal)
    legal_checked["legal_status"] = "verified_current"
    legal_checked_result = one(legal_checked)
    assert legal_checked_result["enrichment_status"] == "passed", legal_checked_result

    unsupported_law = base_row()
    unsupported_law["law"] = "社會救助法"
    unsupported_law["legal_status"] = "unreviewed"
    sanitized = one(unsupported_law)
    assert sanitized["enrichment_status"] == "passed_sanitized", sanitized
    assert sanitized["field_actions"] == {"law": "drop"}, sanitized
    assert sanitized["publish_action"] == "publish_sanitized", sanitized

    changed = copy.deepcopy(legal)
    changed["legal_status"] = "changed"
    changed_result = one(changed)
    assert changed_result["enrichment_status"] == "needs_review", changed_result
    assert "ENRICHMENT_LAW_CHANGED_REVIEW" in changed_result["review_reasons"], changed_result

    unknown = base_row()
    unknown["analysis_status"] = "future_state"
    unknown_result = one(unknown)
    assert unknown_result["enrichment_status"] == "needs_review", unknown_result
    assert "UNKNOWN_ANALYSIS_STATE" in unknown_result["review_reasons"], unknown_result

    law_names, aliases = load_law_registry(POLICY)
    assert extract_law_names("性別工作平等法", law_names, aliases) == ["性別平等工作法"]
    assert "公民與政治權利國際公約及經濟社會文化權利國際公約施行法" in extract_law_names(
        "兩公約施行法", law_names, aliases
    )
    assert extract_law_names("兒童及少年福利與權益保障法", law_names, aliases) == [
        "兒童及少年福利與權益保障法"
    ]

    report = build_report(
        [base_row(), unsupported_law, multi, special, pending],
        policy=POLICY,
        question_policy=QUESTION_POLICY,
        source="mixed-fixture",
    )
    assert report["summary"]["items"] == 5
    assert report["summary"]["status_counts"]["passed"] == 1
    assert report["summary"]["status_counts"]["passed_sanitized"] == 1
    assert report["summary"]["status_counts"]["needs_review"] == 1
    assert report["summary"]["status_counts"]["blocked"] == 1
    assert report["summary"]["status_counts"]["pending_generation"] == 1
    assert report["summary"]["human_review_count"] == 2
    assert report["summary"]["safe_sanitization_count"] == 1

    # The policy itself must remain advisory-only.
    assert POLICY["safety"]["official_core_mutation_allowed"] is False
    assert POLICY["safety"]["production_write_enabled"] is False
    assert POLICY["safety"]["numeric_confidence_score_used"] is False

    print(json.dumps({
        "ok": True,
        "passed": True,
        "safe_sanitization": True,
        "multi_answer_review": True,
        "special_grading_blocked": True,
        "legal_evidence_review": True,
        "source_token_hallucination_blocked": True,
        "official_core_mutation": False,
        "production_write": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

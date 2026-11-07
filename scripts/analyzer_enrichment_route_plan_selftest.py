#!/usr/bin/env python3
"""Zero-network contract tests for analyzer_enrichment_route_plan.py."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from analyzer_enrichment_route_plan import (
    ANALYZER_CANDIDATE_FIELDS,
    OFFICIAL_CORE_FIELDS,
    build_route_plan,
)
from enrichment_decision import ROOT, read_json

POLICY = read_json(ROOT / "data/enrichment_decision_policy.v1.json")
QUESTION_POLICY = read_json(ROOT / "data/question_qa_policy_v1.json")
ANALYZER_SOURCE = ROOT / "supabase/functions/analyze-pending-questions/index.ts"


def question() -> dict:
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
        "source_exam_code": "116030",
        "source_url": "fixture://moex/116030",
        "legal_status": "not_applicable",
        "analysis_status": "analyzing",
        "analysis_attempts": 1,
    }


def candidate() -> dict:
    return {
        "id": "SW-116-1-001",
        "major": "社會工作專業",
        "topic": "專業關係 > 專業界線",
        "keywords": "專業關係,專業界線,自主",
        "exp_why": "正確敘述強調專業關係需要維持清楚的專業界線。",
        "exp_others": "B選項：完全避免溝通不符合專業關係。C選項：不能把所有專業倫理交由服務對象決定。D選項：忽略自主選擇不符合專業關係。",
        "exp_trap": "容易把尊重自主誤解成放棄專業責任。",
        "mnemonic": "尊重自主也要守住專業界線。",
        "extension": "比較專業界線與服務對象自主。",
        "law": "",
        "mistake": "概念混淆",
    }


def plan(q: dict, c: dict, **kwargs):
    return build_route_plan(
        q,
        c,
        policy=POLICY,
        question_policy=QUESTION_POLICY,
        **kwargs,
    )


def must_fail(q: dict, c: dict, **kwargs) -> None:
    try:
        plan(q, c, **kwargs)
    except (ValueError, TypeError, AssertionError):
        return
    raise AssertionError("invalid analyzer route fixture must fail closed")


def production_fields() -> list[str]:
    text = ANALYZER_SOURCE.read_text(encoding="utf-8")
    match = re.search(r"const FIELDS = (\[[^;]+\]);", text)
    if not match:
        raise AssertionError("production analyzer FIELDS contract not found")
    fields = json.loads(match.group(1))
    if not isinstance(fields, list) or not all(isinstance(x, str) for x in fields):
        raise AssertionError("production analyzer FIELDS is not a string array")
    return fields


def assert_production_boundary() -> None:
    fields = production_fields()
    assert fields == ANALYZER_CANDIDATE_FIELDS, (fields, ANALYZER_CANDIDATE_FIELDS)
    text = ANALYZER_SOURCE.read_text(encoding="utf-8")
    # Production activation candidate must no longer write analyzeOne() output
    # directly. It must pass through current-law + Stage7 exam-time historical
    # preflight before the deterministic final publication route.
    assert 'const candidate = await analyzeOne(q, internalKey);' in text
    assert 'finalizeValidatedCandidate(q, candidate, preflight)' in text
    assert 'updateClaimedQuestion(sb, q, finalRoute.patch)' in text
    assert 'preflightQuestion(q, null, false)' in text
    assert 'preflightQuestion(q, currentTrust.decision, false)' in text
    assert 'loadHistoricalLegalTrust(sb, q)' in text
    assert 'preflightQuestion(q, currentTrust.decision, true)' in text
    assert 'historical_law_runtime_evidence_snapshot' in text
    assert 'historical_law_runtime_evidence' in text
    assert "analyzer_enrichment_route_plan" not in text
    assert "enrichment_decision" not in text


def assert_no_official_core_patch(route: dict) -> None:
    patch = route.get("proposed_update_patch") or {}
    overlap = sorted(set(patch).intersection(OFFICIAL_CORE_FIELDS))
    assert overlap == [], overlap
    safety = route["safety"]
    assert safety["official_core_modified"] is False
    assert safety["production_write_performed"] is False
    assert safety["model_called"] is False
    assert safety["production_analyzer_modified"] is False


def main() -> int:
    assert_production_boundary()

    q = question()
    c = candidate()
    q_before, c_before = copy.deepcopy(q), copy.deepcopy(c)
    good = plan(q, c)
    assert good["route"] == "ready", good
    assert good["publication_allowed"] is True
    assert good["decision"]["enrichment_status"] == "passed"
    assert good["proposed_update_patch"]["analysis_status"] == "ready"
    assert good["proposed_update_patch"]["major"] == c["major"]
    assert_no_official_core_patch(good)
    assert q == q_before and c == c_before, "dry-run planner mutated caller input"

    # Unsupported unverified law is deterministic field sanitization, not a
    # whole-question failure for a non-legal question.
    sanitize = candidate()
    sanitize["law"] = "社會救助法"
    sanitized = plan(question(), sanitize)
    assert sanitized["route"] == "sanitized_ready", sanitized
    assert sanitized["publication_allowed"] is True
    assert sanitized["decision"]["field_actions"] == {"law": "drop"}
    assert sanitized["proposed_update_patch"]["law"] is None
    assert sanitized["sanitized_candidate"]["law"] is None
    assert_no_official_core_patch(sanitized)

    # Defense in depth: if a candidate somehow contradicts the accepted answer,
    # do not publish it even if it passed an upstream model stage.
    conflict = candidate()
    conflict["exp_others"] = "A選項：錯誤。B選項：不符合專業關係。C選項：不符合專業倫理。D選項：忽略自主不恰當。"
    review = plan(question(), conflict)
    assert review["route"] == "review", review
    assert review["publication_allowed"] is False
    assert "ENRICHMENT_ACCEPTED_ANSWER_IN_OTHERS" in review["decision"]["review_reasons"]
    assert review["proposed_update_patch"]["analysis_status"] == "review"
    assert "major" not in review["proposed_update_patch"]
    assert_no_official_core_patch(review)

    special_q = question()
    special_q["grading_mode"] = "all_credit"
    special_q["answer"] = "一律給分"
    special = plan(special_q, candidate())
    assert special["route"] == "review", special
    assert special["decision"]["enrichment_status"] == "blocked"
    assert special["publication_allowed"] is False
    assert "ENRICHMENT_SPECIAL_GRADING" in special["decision"]["review_reasons"]
    assert_no_official_core_patch(special)

    # Current-law health alone must NOT prove the version effective on exam day.
    legal_q = question()
    legal_q.update(
        id="SP-116-1-001",
        subject="社會政策與社會立法",
        question="依社會救助法規定，下列何者正確？",
        opt_a="應依法律規定辦理",
        opt_b="可完全忽略法律規定",
        opt_c="不需要依法行政",
        opt_d="所有規定都可任意變更",
        legal_status="unreviewed",
    )
    legal_c = candidate()
    legal_c.update(
        id="SP-116-1-001",
        major="社會救助",
        topic="社會救助 > 法規原則",
        keywords="社會救助法,依法行政",
        exp_why="正確選項符合社會救助法的法律規定。",
        exp_others="B選項：不能忽略法律規定。C選項：仍須依法行政。D選項：規定不能任意變更。",
        exp_trap="注意題目要求依法規判斷。",
        mnemonic="依法辦理。",
        extension="比較社會救助的法規原則。",
        law="社會救助法",
        mistake="法規混淆",
    )
    watch = {
        "schema_version": 3,
        "checked_at": "2026-10-05T00:00:00Z",
        "lookup_error_count": 0,
        "missing_count": 0,
        "changed_count": 0,
        "records": {
            "社會救助法": {
                "canonical_name": "社會救助法",
                "found": True,
                "changed": False,
            }
        },
    }
    legal_base = plan(legal_q, legal_c)
    assert legal_base["route"] == "review", legal_base
    assert "ENRICHMENT_LEGAL_EVIDENCE_REQUIRED" in legal_base["decision"]["review_reasons"]

    legal_current = plan(
        legal_q,
        legal_c,
        legal_watch=watch,
        trust_current_legal_watch=True,
    )
    assert legal_current["route"] == "review", legal_current
    assert legal_current["publication_allowed"] is False
    assert legal_current["current_legal_watch"]["historical_version_proof"] is False
    assert legal_current["historical_version_checked"] is False
    assert "ENRICHMENT_LEGAL_EVIDENCE_REQUIRED" in legal_current["decision"]["review_reasons"]
    assert_no_official_core_patch(legal_current)

    legal_verified = plan(
        legal_q,
        legal_c,
        legal_watch=watch,
        trust_current_legal_watch=True,
        historical_version_checked=True,
    )
    assert legal_verified["route"] == "ready", legal_verified
    assert legal_verified["publication_allowed"] is True
    assert legal_verified["historical_version_checked"] is True
    assert legal_verified["current_legal_watch"]["historical_version_proof"] is False
    assert_no_official_core_patch(legal_verified)

    changed_watch = copy.deepcopy(watch)
    changed_watch["changed_count"] = 1
    changed_watch["records"]["社會救助法"]["changed"] = True
    legal_changed = plan(
        legal_q,
        legal_c,
        legal_watch=changed_watch,
        trust_current_legal_watch=True,
        historical_version_checked=True,
    )
    assert legal_changed["route"] == "review", legal_changed

    must_fail(legal_q, legal_c, legal_watch=watch, trust_current_legal_watch=False)

    # Candidate cannot smuggle any Official Core field into the update path.
    tampered = candidate()
    tampered["answer"] = "D"
    must_fail(question(), tampered)
    tampered = candidate()
    tampered["question"] = "改寫官方題目"
    must_fail(question(), tampered)
    tampered = candidate()
    tampered["id"] = "SW-116-1-999"
    must_fail(question(), tampered)
    tampered = candidate()
    del tampered["exp_trap"]
    must_fail(question(), tampered)

    print(json.dumps({
        "ok": True,
        "production_fields_match": True,
        "clean_candidate_route": "ready",
        "unsupported_law_route": "sanitized_ready",
        "accepted_answer_conflict_route": "review",
        "special_grading_route": "review",
        "trusted_current_named_law_route": "review",
        "historically_verified_named_law_route": "ready",
        "changed_law_route": "review",
        "official_core_tamper_rejected": True,
        "production_analyzer_modified": True,
        "production_write": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

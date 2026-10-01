#!/usr/bin/env python3
from __future__ import annotations

import historical_law_guardian_queue as q

stage2 = {
    "questions": [
        {"law_name": "A法", "question_id": "Q1", "exam_code": "115-1", "status": "article_resolution_required"},
        {"law_name": "A法", "question_id": "Q2", "exam_code": "115-1", "status": "article_resolution_required"},
        {"law_name": "B法", "question_id": "Q3", "exam_code": "115-1", "status": "current_text_equals_exam_date_candidate"},
        {"law_name": "C法", "question_id": "Q4", "exam_code": "115-1", "status": "effective_date_review"},
        {"law_name": "D法", "question_id": "Q5", "exam_code": "115-1", "status": "official_history_unavailable"},
        {"law_name": "E法", "question_id": "Q6", "exam_code": "115-1", "status": "article_resolution_required"},
        {"law_name": "F法", "question_id": "Q7", "exam_code": "115-1", "status": "article_resolution_required"},
        {"law_name": "G法", "question_id": "Q8", "exam_code": "115-1", "status": "article_resolution_required"},
        {"law_name": "H法", "question_id": "Q9", "exam_code": "115-1", "status": "article_resolution_required"},
    ]
}
stage3 = {
    "records": [
        {
            "law_name": "A法", "question_id": "Q1", "exam_code": "115-1",
            "route": "machine_candidate", "confidence": "high",
            "decision_reason": "very_strong_semantic_separation", "suggested_article": "8",
        },
        {
            "law_name": "A法", "question_id": "Q2", "exam_code": "115-1",
            "route": "ai_review", "confidence": "conflict",
            "decision_reason": "semantic_metadata_disagree", "suggested_article": "9",
        },
        {
            "law_name": "E法", "question_id": "Q6", "exam_code": "115-1",
            "route": "machine_candidate", "confidence": "high",
            "decision_reason": "very_strong_semantic_separation", "suggested_article": "6",
        },
        {
            "law_name": "F法", "question_id": "Q7", "exam_code": "115-1",
            "route": "machine_candidate", "confidence": "high",
            "decision_reason": "very_strong_semantic_separation", "suggested_article": "7",
        },
        {
            "law_name": "G法", "question_id": "Q8", "exam_code": "115-1",
            "route": "machine_candidate", "confidence": "high",
            "decision_reason": "very_strong_semantic_separation", "suggested_article": "8",
        },
        {
            "law_name": "H法", "question_id": "Q9", "exam_code": "115-1",
            "route": "machine_candidate", "confidence": "high",
            "decision_reason": "very_strong_semantic_separation", "suggested_article": "9",
        },
    ]
}
stage5 = {
    "records": [
        {
            "law_name": law, "question_id": qid, "exam_code": "115-1",
            "promotion_status": "promotion_candidate", "blockers": [],
            "historical_article_sha256": char * 64,
        }
        for law, qid, char in [
            ("A法", "Q1", "a"), ("E法", "Q6", "b"), ("F法", "Q7", "c"),
            ("G法", "Q8", "d"), ("H法", "Q9", "e"),
        ]
    ]
}
stage6 = {
    "records": [
        {"law_name": "A法", "question_id": "Q1", "status": "historical_semantic_confirmed", "source_identity_method": "moj_title", "expected_rank": 1},
        {"law_name": "E法", "question_id": "Q6", "status": "historical_semantic_support", "source_identity_method": "moj_title", "expected_rank": 1},
        {"law_name": "F法", "question_id": "Q7", "status": "source_identity_mismatch", "source_error": "MOJ page identity mismatch after HTTP success"},
        {"law_name": "G法", "question_id": "Q8", "status": "historical_semantic_conflict", "source_identity_method": "moj_title", "expected_rank": 2},
    ]
}

report = q.build_queue(stage2, stage3, stage5, stage6)
assert report["mapping_count"] == 9, report
assert report["unique_question_count"] == 9, report
assert report["human_queue_count"] == 1, report
assert report["historical_version_checked_count"] == 0
assert report["protected_core_mutation_count"] == 0
assert report["lane_counts"] == {
    "ai_article_review": 1,
    "ai_semantic_review": 1,
    "effective_date_resolution": 1,
    "human_review": 1,
    "machine_direct_source_check": 1,
    "machine_evidence_blocked": 1,
    "machine_promotion": 1,
    "source_retry": 2,
}, report["lane_counts"]

items = {row["question_id"]: row for row in report["items"]}
assert items["Q1"]["lane"] == q.LANE_MACHINE_PROMOTION
assert items["Q1"]["stage6_status"] == "historical_semantic_confirmed"
assert items["Q2"]["lane"] == q.LANE_AI_ARTICLE
assert items["Q2"]["priority"] == "high"
assert items["Q3"]["lane"] == q.LANE_DIRECT_SOURCE
assert items["Q4"]["lane"] == q.LANE_EFFECTIVE_DATE
assert items["Q5"]["lane"] == q.LANE_SOURCE_RETRY
assert items["Q6"]["lane"] == q.LANE_AI_SEMANTIC
assert items["Q7"]["lane"] == q.LANE_SOURCE_RETRY
assert items["Q7"]["priority"] == "high"
assert items["Q8"]["lane"] == q.LANE_HUMAN
assert items["Q8"]["human_review_required"] is True
assert items["Q9"]["lane"] == q.LANE_EVIDENCE_BLOCKED
assert items["Q9"]["priority"] == "high"
assert all(row["historical_version_checked"] is False for row in report["items"])
assert all("official_answer" not in row for row in report["items"])

# A Stage 5 machine candidate without a Stage 6 result fails closed instead of
# remaining in machine promotion.
report2 = q.build_queue(stage2, stage3, stage5, {"records": []})
items2 = {row["question_id"]: row for row in report2["items"]}
assert items2["Q1"]["lane"] == q.LANE_EVIDENCE_BLOCKED
assert items2["Q1"]["priority"] == "high"
assert items2["Q6"]["lane"] == q.LANE_EVIDENCE_BLOCKED

print("HISTORICAL LAW GUARDIAN QUEUE SELFTEST OK")

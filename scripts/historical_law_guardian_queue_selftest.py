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
    ]
}
stage3 = {
    "records": [
        {
            "law_name": "A法", "question_id": "Q1", "exam_code": "115-1",
            "route": "machine_candidate", "confidence": "high",
            "decision_reason": "very_strong_semantic_separation",
            "suggested_article": "8",
        },
        {
            "law_name": "A法", "question_id": "Q2", "exam_code": "115-1",
            "route": "ai_review", "confidence": "conflict",
            "decision_reason": "semantic_metadata_disagree",
            "suggested_article": "9",
        },
    ]
}
stage5 = {
    "records": [
        {
            "law_name": "A法", "question_id": "Q1", "exam_code": "115-1",
            "promotion_status": "promotion_candidate", "blockers": [],
            "historical_article_sha256": "a" * 64,
        }
    ]
}

report = q.build_queue(stage2, stage3, stage5)
assert report["mapping_count"] == 5, report
assert report["unique_question_count"] == 5, report
assert report["human_queue_count"] == 0, report
assert report["historical_version_checked_count"] == 0
assert report["protected_core_mutation_count"] == 0
assert report["lane_counts"] == {
    "ai_article_review": 1,
    "effective_date_resolution": 1,
    "machine_direct_source_check": 1,
    "machine_promotion": 1,
    "source_retry": 1,
}, report["lane_counts"]

items = {row["question_id"]: row for row in report["items"]}
assert items["Q1"]["lane"] == q.LANE_MACHINE_PROMOTION
assert items["Q2"]["lane"] == q.LANE_AI_ARTICLE
assert items["Q2"]["priority"] == "high"
assert items["Q3"]["lane"] == q.LANE_DIRECT_SOURCE
assert items["Q4"]["lane"] == q.LANE_EFFECTIVE_DATE
assert items["Q5"]["lane"] == q.LANE_SOURCE_RETRY
assert all(row["historical_version_checked"] is False for row in report["items"])
assert all("official_answer" not in row for row in report["items"])

# Missing Stage 5 evidence for a machine candidate is not sent to a human by default.
report2 = q.build_queue(stage2, stage3, {"records": []})
items2 = {row["question_id"]: row for row in report2["items"]}
assert items2["Q1"]["lane"] == q.LANE_EVIDENCE_BLOCKED
assert items2["Q1"]["priority"] == "high"
assert report2["human_queue_count"] == 0

print("HISTORICAL LAW GUARDIAN QUEUE SELFTEST OK")

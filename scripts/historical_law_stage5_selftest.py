#!/usr/bin/env python3
from __future__ import annotations

import historical_law_stage5_promotion as s5

BASE_STAGE3 = {
    "explicit_control_count": 10,
    "explicit_control_top1_match_count": 9,
    "explicit_control_top3_match_count": 9,
    "explicit_control_shadow_machine_candidate_count": 4,
    "explicit_control_false_machine_candidate_count": 0,
    "records": [{
        "law_name": "測試法",
        "question_id": "Q1",
        "exam_code": "115-1",
        "route": "machine_candidate",
        "confidence": "high",
        "decision_reason": "very_strong_semantic_separation",
        "suggested_article": "8",
        "metadata_articles": [],
    }],
}

BASE_STAGE4 = {
    "record_count": 1,
    "records": [{
        "law_name": "測試法",
        "question_id": "Q1",
        "exam_code": "115-1",
        "suggested_article": "8",
        "status": "historical_text_evidence_ready",
        "historical_article_sha256": "a" * 64,
        "historical_article_char_count": 123,
        "selected_version": {"url": "https://law.moj.gov.tw/example"},
        "official_history_url": "https://law.moj.gov.tw/history",
        "exam_date_source_url": "https://wwwc.moex.gov.tw/example",
    }],
}

report = s5.build_report(BASE_STAGE3, BASE_STAGE4)
assert report["promotion_candidate_count"] == 1, report
assert report["blocked_count"] == 0, report
assert report["historical_version_checked_count"] == 0
assert report["records"][0]["historical_version_checked"] is False
assert "official_answer" not in report["records"][0]

unsafe = dict(BASE_STAGE3)
unsafe["explicit_control_false_machine_candidate_count"] = 1
report = s5.build_report(unsafe, BASE_STAGE4)
assert report["promotion_candidate_count"] == 0, report
assert report["blocked_count"] == 1, report
assert "stage3_shadow_calibration_not_safe" in report["records"][0]["blockers"]

bad_fingerprint = {
    **BASE_STAGE4,
    "records": [{**BASE_STAGE4["records"][0], "historical_article_sha256": "bad"}],
}
report = s5.build_report(BASE_STAGE3, bad_fingerprint)
assert report["promotion_candidate_count"] == 0, report
assert "stage4_fingerprint_missing" in report["records"][0]["blockers"]

mismatch = {
    **BASE_STAGE4,
    "records": [{**BASE_STAGE4["records"][0], "suggested_article": "9"}],
}
report = s5.build_report(BASE_STAGE3, mismatch)
assert report["promotion_candidate_count"] == 0, report
assert "stage3_stage4_article_mismatch" in report["records"][0]["blockers"]

print("HISTORICAL LAW STAGE5 SELFTEST OK")

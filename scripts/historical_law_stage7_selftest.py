#!/usr/bin/env python3
from __future__ import annotations

import historical_law_stage7_materialize as s7

S5 = {
    "records": [{
        "law_name": "測試法", "question_id": "Q1", "exam_code": "115-1",
        "suggested_article": "8", "promotion_status": "promotion_candidate",
        "official_history_url": "https://law.moj.gov.tw/history",
        "exam_date_source_url": "https://wwwc.moex.gov.tw/exam",
    }]
}
S6_CONFIRMED = {
    "records": [{
        "law_name": "測試法", "question_id": "Q1", "exam_code": "115-1",
        "suggested_article": "8", "status": "historical_semantic_confirmed",
        "selected_version": {"url": "https://law.moj.gov.tw/version"},
        "historical_article_sha256": "a" * 64,
        "historical_top_article": "8", "historical_top_score": 0.72,
        "historical_second_article": "9", "historical_second_score": 0.2,
        "historical_margin": 0.52,
        "historical_decision_reason": "very_strong_semantic_separation",
    }]
}

registry, conflicts = s7.build_registry(S5, S6_CONFIRMED)
assert not conflicts
assert registry["verified_record_count"] == 1
assert registry["historical_version_checked_count"] == 1
row = registry["records"][0]
assert row["historical_version_checked"] is True
assert row["verification_level"] == s7.VERIFICATION_LEVEL
assert "official_answer" not in row

# Support/conflict rows are never materialized.
for status in ("historical_semantic_support", "historical_semantic_conflict"):
    payload = {"records": [{**S6_CONFIRMED["records"][0], "status": status}]}
    reg, err = s7.build_registry(S5, payload)
    assert not err and reg["verified_record_count"] == 0, (status, reg, err)

# Existing registry is monotonic during a source outage / empty fresh result.
reg, err = s7.build_registry(S5, {"records": []}, registry)
assert not err and reg["verified_record_count"] == 1

# Evidence drift fails closed instead of silently replacing provenance.
drift = {"records": [{**S6_CONFIRMED["records"][0], "historical_article_sha256": "b" * 64}]}
reg, err = s7.build_registry(S5, drift, registry)
assert len(err) == 1 and "historical_article_sha256" in err[0]["changed_fields"]
assert reg["records"][0]["historical_article_sha256"] == "a" * 64

print("HISTORICAL LAW STAGE7 SELFTEST OK")

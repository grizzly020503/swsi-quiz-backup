#!/usr/bin/env python3
from __future__ import annotations

import historical_law_oldver_stage4 as s4
import historical_law_stage4_snapshot_runner as snap4
import historical_law_stage6_snapshot_semantic as snap6

URL = "https://law.moj.gov.tw/LawClass/LawOldVer.aspx?pcode=D0050075&lnndate=20140129&lser=001"
HTML = """
<html><head><title>測試法 歷史法規所有條文-全國法規資料庫</title></head><body>
<div class="row"><div class="col-no">第 1 條</div><div class="col-data"><div class="law-article">
<div class="line-0000">總則規定。</div></div></div></div>
<div class="row"><div class="col-no">第 8 條</div><div class="col-data"><div class="law-article">
<div class="line-0000">緊急生活扶助每人每次補助三個月。</div></div></div></div>
</body></html>
"""
TARGET = "緊急生活扶助每人每次補助三個月。"
TARGET_SHA = s4.article_fingerprint(TARGET)

base_report = {
    "schema_version": 3,
    "method": "test",
    "records": [{
        "law_name": "測試法",
        "question_id": "Q1",
        "exam_code": "115-1",
        "suggested_article": "8",
        "status": "historical_text_evidence_ready",
        "eligible_for_historical_version_checked": True,
        "selected_version": {"url": URL},
        "historical_article_sha256": TARGET_SHA,
        "historical_version_checked": False,
    }],
    "historical_version_checked_count": 0,
    "protected_core_mutation_count": 0,
}
report = snap4.attach_verified_snapshots(base_report, {URL: HTML})
row4 = report["records"][0]
assert report["schema_version"] == 4
assert report["verified_snapshot_count"] == 1
assert row4["status"] == "historical_text_evidence_ready"
snapshot = row4["historical_version_snapshot"]
assert snapshot["source_url"] == URL
assert snapshot["source_identity_method"] == "stage4_moj_title"
assert snapshot["article_count"] == 2
assert len(snapshot["page_sha256"]) == 64
assert len(snapshot["snapshot_id"]) == 64
assert next(a for a in snapshot["articles"] if a["article_no"] == "8")["sha256"] == TARGET_SHA

row5 = {
    "law_name": "測試法",
    "question_id": "Q1",
    "exam_code": "115-1",
    "suggested_article": "8",
    "promotion_status": "promotion_candidate",
    "selected_version": {"url": URL},
    "historical_article_sha256": TARGET_SHA,
}
articles, error = snap6.verified_snapshot_articles(row4, row5)
assert error is None
assert articles and {a["article_no"] for a in articles} == {"1", "8"}

bad_url = dict(row5)
bad_url["selected_version"] = {"url": "https://example.com/fake"}
articles, error = snap6.verified_snapshot_articles(row4, bad_url)
assert articles is None and "URL mismatch" in (error or "")

bad_hash = dict(row5)
bad_hash["historical_article_sha256"] = "0" * 64
articles, error = snap6.verified_snapshot_articles(row4, bad_hash)
assert articles is None and "fingerprint mismatch" in (error or "")

bad_row4 = dict(row4)
bad_snapshot = dict(snapshot)
bad_articles = [dict(a) for a in snapshot["articles"]]
bad_articles[0]["text"] += "被竄改"
bad_snapshot["articles"] = bad_articles
bad_row4["historical_version_snapshot"] = bad_snapshot
articles, error = snap6.verified_snapshot_articles(bad_row4, row5)
assert articles is None and "snapshot article fingerprint mismatch" in (error or "")

# If capture integrity is broken, Stage 4 snapshot attachment fails closed.
missing = {
    "schema_version": 3,
    "method": "test",
    "records": [{
        "law_name": "測試法", "question_id": "Q2", "suggested_article": "8",
        "status": "historical_text_evidence_ready",
        "eligible_for_historical_version_checked": True,
        "selected_version": {"url": URL},
        "historical_article_sha256": TARGET_SHA,
        "historical_version_checked": False,
    }],
}
missing = snap4.attach_verified_snapshots(missing, {})
assert missing["records"][0]["status"] == "source_snapshot_unavailable"
assert missing["verified_snapshot_count"] == 0

print("HISTORICAL LAW SNAPSHOT PIPELINE SELFTEST OK")

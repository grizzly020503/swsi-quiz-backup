#!/usr/bin/env python3
from __future__ import annotations

import historical_law_oldver_stage4 as s4
import historical_law_stage4_snapshot_runner as snap4
import historical_law_stage6_snapshot_semantic as snap6

OLD_URL = "https://law.moj.gov.tw/LawClass/LawOldVer.aspx?pcode=D0050075&lnndate=20140129&lser=001"
CURRENT_URL = "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050075"
API_ENDPOINT = "https://law.moj.gov.tw/api/ch/law/json"
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
EXAM = {"source_url": "https://wwwc.moex.gov.tw/example"}
BASE = {
    "law_name": "測試法",
    "question_id": "Q1",
    "exam_code": "115-1",
    "suggested_article": "8",
    "stage3_confidence": "high",
    "stage3_decision_reason": "test",
    "historical_version_checked": False,
}

# ---- Old-version HTML snapshot ----
old_selected = {"kind": "oldver", "url": OLD_URL, "version_date": "2014-01-29"}
old_row4 = snap4._oldver_ready_record(
    BASE, old_selected, "https://law.moj.gov.tw/LawClass/LawHistory.aspx?pcode=D0050075",
    HTML, EXAM, "2015-02-07", "2015-02-08"
)
assert old_row4["status"] == "historical_text_evidence_ready"
old_snapshot = old_row4["historical_version_snapshot"]
assert old_snapshot["source_identity_method"] == "stage4_moj_title"
assert old_snapshot["article_count"] == 2
assert len(old_snapshot["page_sha256"]) == 64
assert len(old_snapshot["evidence_sha256"]) == 64
assert len(old_snapshot["snapshot_id"]) == 64
assert next(a for a in old_snapshot["articles"] if a["article_no"] == "8")["sha256"] == TARGET_SHA

old_row5 = {
    "law_name": "測試法", "question_id": "Q1", "exam_code": "115-1",
    "suggested_article": "8", "promotion_status": "promotion_candidate",
    "selected_version": old_selected, "historical_article_sha256": TARGET_SHA,
}
articles, error = snap6.verified_snapshot_articles(old_row4, old_row5)
assert error is None, error
assert articles and {a["article_no"] for a in articles} == {"1", "8"}

# Tampering with one old-version article invalidates both per-article and aggregate evidence.
tampered_old = dict(old_row4)
tampered_old_snapshot = dict(old_snapshot)
tampered_old_articles = [dict(a) for a in old_snapshot["articles"]]
tampered_old_articles[0]["text"] += "被竄改"
tampered_old_snapshot["articles"] = tampered_old_articles
tampered_old["historical_version_snapshot"] = tampered_old_snapshot
articles, error = snap6.verified_snapshot_articles(tampered_old, old_row5)
assert articles is None and "aggregate evidence fingerprint mismatch" in (error or "")

# ---- Current MOJ Open API target snapshot ----
api_articles = [
    {"article_no": "1", "text": "總則規定。", "sha256": snap4._sha256_text("總則規定。")},
    {"article_no": "8", "text": TARGET, "sha256": TARGET_SHA},
]
api_identity = {
    "endpoint": API_ENDPOINT,
    "collection": "law",
    "update_date": "2026-10-01",
    "pcode": "D0050075",
    "law_name": "測試法",
    "law_url": CURRENT_URL,
    "modified_date": "2025-01-01",
    "article_count": 2,
    "articles_sha256": snap4._payload_sha256(api_articles),
}
api_snapshot_payload = {
    "schema_version": 1,
    "records": [{
        **api_identity,
        "source_identity_sha256": snap4._payload_sha256(api_identity),
        "articles": api_articles,
    }],
}
api_targets = snap4.verified_api_targets(api_snapshot_payload)
assert set(api_targets) == {"D0050075"}
api_selected = {"kind": "current", "url": CURRENT_URL, "version_date": "2025-01-01"}
api_row4 = snap4._api_ready_record(
    BASE, api_selected, "https://law.moj.gov.tw/LawClass/LawHistory.aspx?pcode=D0050075",
    "D0050075", "測試法", api_targets["D0050075"], EXAM, "2026-02-07", "2026-02-08"
)
assert api_row4["status"] == "historical_text_evidence_ready", api_row4
api_snapshot = api_row4["historical_version_snapshot"]
assert api_snapshot["source_identity_method"] == "moj_open_api_current"
assert api_snapshot["api_endpoint"] == API_ENDPOINT
assert api_snapshot["article_count"] == 2
assert len(api_snapshot["api_source_identity_sha256"]) == 64
assert len(api_snapshot["evidence_sha256"]) == 64

api_row5 = {
    "law_name": "測試法", "question_id": "Q1", "exam_code": "115-1",
    "suggested_article": "8", "promotion_status": "promotion_candidate",
    "selected_version": api_selected, "historical_article_sha256": TARGET_SHA,
}
articles, error = snap6.verified_snapshot_articles(api_row4, api_row5)
assert error is None, error
assert articles and {a["article_no"] for a in articles} == {"1", "8"}

# Open API evidence may only represent a current selected version.
wrong_kind = dict(api_row5)
wrong_kind["selected_version"] = {"kind": "oldver", "url": CURRENT_URL}
articles, error = snap6.verified_snapshot_articles(api_row4, wrong_kind)
assert articles is None and "non-current" in (error or "")

# A non-official/unknown API endpoint is rejected at Stage 4 snapshot validation.
bad_api_payload = {
    "schema_version": 1,
    "records": [{
        **api_identity,
        "endpoint": "https://example.com/api",
        "source_identity_sha256": "0" * 64,
        "articles": api_articles,
    }],
}
try:
    snap4.verified_api_targets(bad_api_payload)
    raise AssertionError("untrusted API endpoint was accepted")
except ValueError as exc:
    assert "invalid MOJ API target identity" in str(exc)

# Stage4/5 URL mismatch and target-hash mismatch remain fail closed for both sources.
bad_url = dict(api_row5)
bad_url["selected_version"] = {"kind": "current", "url": "https://example.com/fake"}
articles, error = snap6.verified_snapshot_articles(api_row4, bad_url)
assert articles is None and "URL mismatch" in (error or "")

bad_hash = dict(api_row5)
bad_hash["historical_article_sha256"] = "0" * 64
articles, error = snap6.verified_snapshot_articles(api_row4, bad_hash)
assert articles is None and "fingerprint mismatch" in (error or "")

assert api_row4["historical_version_checked"] is False
assert old_row4["historical_version_checked"] is False
assert "official_answer" not in api_row4 and "official_answer" not in old_row4

print("HISTORICAL LAW HYBRID SNAPSHOT PIPELINE SELFTEST OK")

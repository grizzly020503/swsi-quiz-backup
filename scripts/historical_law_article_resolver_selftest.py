#!/usr/bin/env python3
from __future__ import annotations

import historical_law_article_resolver as r

LAW = "測試扶助法"
HTML = """
<html><body>
<h3>第 4 條</h3>
<p>本法所稱特殊家庭，指家庭總收入及家庭財產符合主管機關公告標準，並具有特定生活困難情形者。</p>
<h3>第 6 條</h3>
<p>符合規定者得申請緊急生活扶助。申請緊急生活扶助，應於事實發生後六個月內提出申請；每人每次以補助三個月為原則。</p>
<h3>第 8 條</h3>
<p>特殊家庭之子女就讀國內公立或立案之私立高級中等以上學校，得申請教育補助及學雜費減免。</p>
<h3>第 12 條</h3>
<p>依第 6 條領取緊急生活扶助之權利，不得扣押、讓與或供擔保。</p>
</body></html>
"""

articles = r.parse_law_articles(HTML)
assert [x["article_no"] for x in articles] == ["4", "6", "8", "12"], articles
assert "第 6 條" in articles[-1]["text"], "cross-reference inside article 12 must remain body text, not become a heading"

# Explicit article references must be recognized as already explicit and never
# become a machine-inferred mapping.
explicit = {
    "question_id": "Q-explicit",
    "exam_code": "115-1",
    "stem": "依測試扶助法第8條規定，下列何者可領取教育補助？",
}
result = r.resolve_question(explicit, LAW, articles, "https://law.moj.gov.tw/test")
assert result["route"] == "already_explicit", result
assert result["explicit_articles"] == ["8"], result
assert result["historical_version_checked"] is False

# A distinctive non-numbered stem should rank the matching official article first.
q6 = "依測試扶助法，申請緊急生活扶助應於事實發生後多久內提出申請？"
ranked6 = r.rank_articles(q6, LAW, articles)
assert ranked6 and ranked6[0]["article_no"] == "6", ranked6

q8 = "測試扶助法有關子女就讀高級中等以上學校之教育補助與學雜費減免，下列敘述何者正確？"
ranked8 = r.rank_articles(q8, LAW, articles)
assert ranked8 and ranked8[0]["article_no"] == "8", ranked8

# Very generic language must not be promoted as a high-confidence machine result.
generic = r.resolve_question(
    {"question_id": "Q-generic", "exam_code": "115-1", "stem": "依測試扶助法，下列何者正確？"},
    LAW,
    articles,
    "https://law.moj.gov.tw/test",
)
assert generic["route"] == "ai_review", generic
assert generic["historical_version_checked"] is False

# Even a high-confidence route is still only a candidate and cannot claim
# historical verification.
resolved = r.resolve_question(
    {"question_id": "Q6", "exam_code": "115-1", "stem": q6},
    LAW,
    articles,
    "https://law.moj.gov.tw/test",
)
assert resolved["suggested_article"] == "6", resolved
assert resolved["historical_version_checked"] is False
assert resolved["route"] in {"machine_candidate", "ai_review"}

# Source failure stays visible and is not silently converted into a result.
links = {"cards": [{"law_name": LAW, "questions": [{"question_id": "Q", "stem": q6}]}]}
orig = r.fetch_law_articles
try:
    r.fetch_law_articles = lambda _watch, _cards: ({LAW: []}, {LAW: "https://law.moj.gov.tw/test"}, {LAW: "offline"})
    report = r.build_report(links, {"records": []})
    assert report["target_count"] == 1
    assert report["route_counts"] == {"source_failure": 1}, report
    assert report["law_source_error_count"] == 1
    assert report["historical_version_checked_count"] == 0
finally:
    r.fetch_law_articles = orig

print("HISTORICAL LAW ARTICLE RESOLVER SELFTEST OK")

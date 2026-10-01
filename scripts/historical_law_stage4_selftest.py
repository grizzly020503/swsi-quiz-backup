#!/usr/bin/env python3
from __future__ import annotations

import historical_law_oldver_stage4 as s4

P = "D0050075"
OFFICIAL = "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050075"

# Ordinary promulgation date.
ordinary = {
    "date": "2014-01-29",
    "articles": ["13-1"],
    "all_articles": False,
    "special_effective_date": False,
    "summary": "中華民國 103 年 1 月 29 日 修正第 13-1 條",
}
assert s4.effective_date_from_entry(ordinary) == "2014-01-29"

# Delayed but deterministic: promulgated in 2006, effective next Jan 1.
next_year = {
    "date": "2006-05-17",
    "articles": ["4"],
    "all_articles": False,
    "special_effective_date": True,
    "summary": "中華民國 95 年 5 月 17 日修正第 4 條；自公布後次年一月一日施行",
}
assert s4.effective_date_from_entry(next_year) == "2007-01-01"

# Explicit effective date published by the Executive Yuan.
announcement = {
    "date": "2009-02-19",
    "articles": [],
    "all_articles": False,
    "special_effective_date": True,
    "summary": "中華民國 98 年 2 月 19 日行政院發布定自中華民國九十八年三月一日施行",
}
assert s4.effective_date_from_entry(announcement) == "2009-03-01"

# A separately-prescribed amendment can be paired with that later MOJ announcement.
separate = {
    "date": "2009-01-23",
    "articles": ["3", "4"],
    "all_articles": False,
    "special_effective_date": True,
    "summary": "中華民國 98 年 1 月 23 日修正第 3、4 條；施行日期，由行政院定之",
}
resolved = s4.resolve_effective_dates([announcement, separate])
separate_resolved = next(r for r in resolved if r["date"] == "2009-01-23")
assert separate_resolved["effective_date"] == "2009-03-01", separate_resolved
assert separate_resolved["effective_date_source"] == "later_moj_effective_announcement"

# Unknown special rule remains unresolved and therefore fail-closed.
unknown = {
    "date": "2010-01-01",
    "articles": ["9"],
    "all_articles": False,
    "special_effective_date": True,
    "summary": "中華民國 99 年 1 月 1 日修正第 9 條；施行日期另定之",
}
assert s4.effective_date_from_entry(unknown) is None

# Derived old-version URL is deterministic and uses the live-probed MOJ contract.
url = s4._canonical_oldver_url(P, "20140129")
assert url == (
    "https://law.moj.gov.tw/LawClass/LawOldVer.aspx?"
    "pcode=D0050075&lnndate=20140129&lser=001"
), url

entries = [
    {
        "date": "2000-05-24",
        "articles": [],
        "all_articles": True,
        "special_effective_date": False,
        "summary": "中華民國 89 年 5 月 24 日制定全文 20 條；自公布日施行",
    },
    separate,
    announcement,
    ordinary,
    {
        "date": "2021-01-20",
        "articles": ["12"],
        "all_articles": False,
        "special_effective_date": False,
        "summary": "中華民國 110 年 1 月 20 日修正第 12 條",
    },
]
versions = s4.versions_from_history_entries(entries, P, OFFICIAL, "2021-01-20")

# Announcement-only rows are effective-date evidence, not full-text versions.
assert not any(v["version_date"] == "2009-02-19" for v in versions), versions
v2009 = next(v for v in versions if v["version_date"] == "2009-01-23")
assert v2009["effective_date"] == "2009-03-01"
assert v2009["kind"] == "oldver"
assert "lnndate=20090123" in v2009["url"]
current = next(v for v in versions if v["version_date"] == "2021-01-20")
assert current["kind"] == "current" and current["url"] == OFFICIAL

# A 2015 exam selects the 2014 official historical version.
status, a, b = s4.select_exam_window_version(
    versions, "2015-02-07", "2015-02-08", article="13-1"
)
assert status == "ok" and a == b and a["version_date"] == "2014-01-29", (status, a, b)

# A version transition inside an exam window must not be guessed across.
synthetic_versions = [
    {"version_date": "2019-01-01", "effective_date": "2019-01-01", "url": "A"},
    {"version_date": "2019-01-20", "effective_date": "2019-01-20", "url": "B"},
]
status, a, b = s4.select_exam_window_version(
    synthetic_versions, "2019-01-19", "2019-01-20", article="1"
)
assert status == "exam_window_version_conflict", (status, a, b)

# An unresolved special-effective amendment affecting the target article blocks selection.
risky = versions + [{
    "version_date": "2015-01-01",
    "effective_date": None,
    "url": "X",
    "articles_changed": ["13-1"],
    "all_articles": False,
}]
status, a, b = s4.select_exam_window_version(
    risky, "2015-02-07", "2015-02-08", article="13-1"
)
assert status == "effective_date_review" and a is None and b is None

# Fingerprint normalizes superficial whitespace only.
assert s4.article_fingerprint(" 第 1 條 \n 測試 ") == s4.article_fingerprint("第 1 條 測試")

print("HISTORICAL LAW STAGE4 SELFTEST OK")

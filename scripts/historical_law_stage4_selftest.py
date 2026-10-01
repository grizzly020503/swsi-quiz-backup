#!/usr/bin/env python3
from __future__ import annotations

import historical_law_oldver_stage4 as s4

P = "D0050075"
OFFICIAL = "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050075"

# Common enactment wording with 起 must still resolve to promulgation day.
enactment = {
    "date": "2000-05-24",
    "articles": [],
    "all_articles": True,
    "special_effective_date": True,
    "summary": "中華民國八十九年五月二十四日制定公布全文16條；並自公布日起施行",
}
assert s4.article_effective_date(enactment, "4") == "2000-05-24"

# Delayed but deterministic next-year Jan 1 rule.
next_year = {
    "date": "2006-05-17",
    "articles": ["4"],
    "all_articles": False,
    "special_effective_date": True,
    "summary": "中華民國九十五年五月十七日修正第4條；自公布後次年一月一日施行",
}
assert s4.article_effective_date(next_year, "4") == "2007-01-01"

# National Pension 2011: article 30 has a retroactive explicit date, article 12
# falls through to the default promulgation-day clause.
nps = {
    "date": "2011-06-29",
    "articles": ["1", "2", "6", "7", "12", "13", "13-1", "14", "18-1", "30", "31", "32", "32-1"],
    "all_articles": False,
    "special_effective_date": True,
    "summary": (
        "中華民國一百年六月二十九日修正公布第1、2、6、7、12~14、30~32條；"
        "增訂第13-1、18-1、32-1條；除第7條第2款、第3款及第30條第2項第3款"
        "自九十七年十月一日施行，第6條第4款、第13條第1項及第3項修正條文之"
        "施行日期由行政院定之者外，自公布日施行；中華民國一百年八月三十一日"
        "行政院令發布第6條第4款、第13條第1項及第3項，定自一百零一年一月一日施行"
    ),
}
assert s4.article_effective_date(nps, "30") == "2008-10-01"
assert s4.article_effective_date(nps, "12") == "2011-06-29"
assert s4.article_effective_date(nps, "13") == "2012-01-01"

# NHI full rewrite: named articles take the first date; remaining articles use
# the later unscoped implementation date.
nhi = {
    "date": "2011-01-26",
    "articles": ["27", "28", "35"],
    "all_articles": True,
    "special_effective_date": True,
    "summary": (
        "中華民國一百年一月二十六日修正公布全文104條；施行日期由行政院定之；"
        "中華民國一百零一年五月二十一日行政院令發布第27、28、35條條文"
        "定自一百零一年七月一日施行；中華民國一百零一年十月九日行政院令發布"
        "除已施行之條文外，定自一百零二年一月一日施行"
    ),
}
assert s4.article_effective_date(nhi, "27") == "2012-07-01"
assert s4.article_effective_date(nhi, "10") == "2013-01-01"

# Whole-statute implementation date expressed through a final article.
crpd = {
    "date": "2014-08-20",
    "articles": ["12"],
    "all_articles": True,
    "special_effective_date": True,
    "summary": "中華民國一百零三年八月二十日制定公布全文12條；依第12條規定：自一百零三年十二月三日起施行",
}
assert s4.article_effective_date(crpd, "6") == "2014-12-03"

# Unknown target-article special effective date remains unresolved.
unknown = {
    "date": "2010-01-01",
    "articles": ["9"],
    "all_articles": False,
    "special_effective_date": True,
    "summary": "中華民國九十九年一月一日修正第9條；施行日期另定之",
}
assert s4.article_effective_date(unknown, "9") is None

# Derived historical URL uses the live-probed MOJ contract.
assert s4._canonical_oldver_url(P, "20140129") == (
    "https://law.moj.gov.tw/LawClass/LawOldVer.aspx?"
    "pcode=D0050075&lnndate=20140129&lser=001"
)

# Identity and article parsing are deliberately separate gates.
assert s4._page_identity_ok("<html><head><title>測試法 歷史法規所有條文-全國法規資料庫</title></head></html>")
assert not s4._page_identity_ok("<html><head><title>系統訊息</title></head></html>")

entries = [
    enactment,
    {
        "date": "2014-01-29",
        "articles": ["13-1"],
        "all_articles": False,
        "special_effective_date": False,
        "summary": "中華民國一百零三年一月二十九日修正第13-1條",
    },
    {
        "date": "2021-01-20",
        "articles": ["12"],
        "all_articles": False,
        "special_effective_date": False,
        "summary": "中華民國一百一十年一月二十日修正第12條",
    },
]

# The latest row affecting the target article is represented by current LawAll,
# even if the statute later changed only unrelated articles.
versions = s4.versions_for_article(entries, P, OFFICIAL, None, "13-1")
assert [v["version_date"] for v in versions] == ["2000-05-24", "2014-01-29"], versions
assert versions[0]["kind"] == "oldver" and "lnndate=20000524" in versions[0]["url"]
assert versions[-1]["kind"] == "current" and versions[-1]["url"] == OFFICIAL
assert versions[-1]["effective_date"] == "2014-01-29"

status, a, b = s4.select_exam_window_version(versions, "2015-02-07", "2015-02-08")
assert status == "ok" and a == b and a["version_date"] == "2014-01-29", (status, a, b)
assert a["url"] == OFFICIAL

# When the target article itself has a later change, an exam before that change
# must still route to the prior historical version.
versions_12 = s4.versions_for_article(entries, P, OFFICIAL, None, "12")
assert [v["version_date"] for v in versions_12] == ["2000-05-24", "2021-01-20"], versions_12
assert versions_12[0]["kind"] == "oldver" and "lnndate=20000524" in versions_12[0]["url"]
assert versions_12[-1]["kind"] == "current" and versions_12[-1]["url"] == OFFICIAL
status, a, b = s4.select_exam_window_version(versions_12, "2015-02-07", "2015-02-08")
assert status == "ok" and a == b and a["kind"] == "oldver", (status, a, b)

# Retroactivity never makes an amendment selectable before its promulgation.
retro = [{
    "version_date": "2011-06-29",
    "effective_date": "2008-10-01",
    "url": "retro",
}]
assert s4.select_version(retro, "2010-01-01") is None
assert s4.select_version(retro, "2012-01-01")["url"] == "retro"

# Version transition inside an exam window fails closed.
synthetic = [
    {"version_date": "2019-01-01", "effective_date": "2019-01-01", "url": "A"},
    {"version_date": "2019-01-20", "effective_date": "2019-01-20", "url": "B"},
]
status, a, b = s4.select_exam_window_version(synthetic, "2019-01-19", "2019-01-20")
assert status == "exam_window_version_conflict", (status, a, b)

# Unresolved effective date blocks only this target-article version chain.
risky = versions + [{
    "version_date": "2015-01-01",
    "effective_date": None,
    "url": "X",
}]
status, a, b = s4.select_exam_window_version(risky, "2015-02-07", "2015-02-08")
assert status == "effective_date_review" and a is None and b is None

assert s4.article_fingerprint(" 第 1 條 \n 測試 ") == s4.article_fingerprint("第 1 條 測試")

print("HISTORICAL LAW STAGE4 SELFTEST OK")
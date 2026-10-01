#!/usr/bin/env python3
from __future__ import annotations

import historical_law_oldver_stage4 as s4

P = "D0050078"

html = '''
<a href="/LawClass/LawOldVer.aspx?PCode=D0050078&amp;LNNDATE=20151230&amp;LSER=001">v1</a>
<a href="LawOldVer.aspx?pcode=D0050078&lnndate=20200603&lser=002">v2</a>
<a href="LawOldVer.aspx?pcode=WRONG&lnndate=20200603&lser=001">wrong</a>
'''
rows = s4.parse_oldver_links(html, P)
assert [r["version_date"] for r in rows] == ["2015-12-30", "2020-06-03"], rows
assert rows[0]["url"].startswith("https://law.moj.gov.tw/LawClass/LawOldVer.aspx?"), rows[0]

versions = s4.add_current_version(
    rows,
    "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050078",
    "2023-12-06",
)
status, a, b = s4.select_exam_window_version(versions, "2019-01-19", "2019-01-20")
assert status == "ok" and a == b and a["version_date"] == "2015-12-30", (status, a, b)

status, a, b = s4.select_exam_window_version(versions, "2020-06-02", "2020-06-04")
assert status == "exam_window_version_conflict", (status, a, b)

status, a, b = s4.select_exam_window_version(versions, "2024-02-04", "2024-02-05")
assert status == "ok" and a["kind"] == "current" and a["version_date"] == "2023-12-06"

assert s4.article_fingerprint(" 第 1 條 \n 測試 ") == s4.article_fingerprint("第 1 條 測試")

entries = [
    {"date": "2018-01-01", "articles": ["10"], "all_articles": False, "special_effective_date": False},
    {"date": "2019-01-01", "articles": ["11"], "all_articles": False, "special_effective_date": True},
]
assert s4.has_effective_date_risk(entries, "10", "2020-01-01") is False
assert s4.has_effective_date_risk(entries, "11", "2020-01-01") is True
assert s4.has_effective_date_risk(entries, "11", "2018-12-31") is False

print("HISTORICAL LAW STAGE4 SELFTEST OK")

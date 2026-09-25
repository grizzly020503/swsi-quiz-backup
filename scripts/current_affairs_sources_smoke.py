#!/usr/bin/env python3
"""Regression contract for curated SWSI current-affairs sources."""
from __future__ import annotations

import json
from pathlib import Path

from current_affairs_watch import score_item

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "current_affairs_sources.json"

EXPECTED_NEW = {
    "勞動部新聞稿": "https://www.mol.gov.tw/1607/1632/1633/RssList",
    "教育部即時新聞": "https://www.edu.tw/Rss_News.aspx?n=9E7AC85F1954DDA8",
    "移民署新住民政策法規": "https://news.immigration.gov.tw/Rss/Content/8?lang=TW",
}


def main() -> int:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = payload.get("sources") or []
    assert payload.get("schema_version") == 1
    assert len(rows) == 11, f"expected 11 curated feeds, got {len(rows)}"

    urls = [str(x.get("url") or "") for x in rows]
    names = [str(x.get("name") or "") for x in rows]
    assert len(urls) == len(set(urls)), "duplicate feed URL"
    assert len(names) == len(set(names)), "duplicate feed name"
    assert all(url.startswith("https://") for url in urls), "all feeds must use HTTPS"

    by_name = {str(x.get("name")): x for x in rows}
    for name, url in EXPECTED_NEW.items():
        row = by_name.get(name)
        assert row, f"missing source: {name}"
        assert row.get("url") == url, (name, row.get("url"))
        assert row.get("region") == "taiwan", name
        assert row.get("source_type") == "official", name

    labor = score_item(
        "勞動部修正就業保險給付規定 強化失業勞工權益",
        "新制調整失業給付與就業服務保障。",
        "taiwan",
        "勞動部新聞稿",
        "official",
    )
    assert labor and labor[1] == "勞動與社會保障", labor
    assert labor[0] >= 5, labor

    education = score_item(
        "教育部修正學生輔導制度 強化中輟與弱勢學生支持",
        "政策聚焦學生輔導、跨專業合作及弱勢學生權益。",
        "taiwan",
        "教育部即時新聞",
        "official",
    )
    assert education and education[1] == "教育與學生輔導", education
    assert education[0] >= 5, education

    low_value = score_item(
        "教育部舉辦全國學生競賽",
        "歡迎學生踴躍參加競賽活動。",
        "taiwan",
        "教育部即時新聞",
        "official",
    )
    assert low_value is None, low_value

    print(
        "CURRENT AFFAIRS SOURCE SMOKE OK: "
        "11 unique HTTPS feeds, 3 new official feeds, "
        "labor/student-support accepted, generic competition rejected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Regression contract for curated SWSI current-affairs sources and relevance."""
from __future__ import annotations

import json
from pathlib import Path

from current_affairs_watch import score_item

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "current_affairs_sources.json"

REQUIRED = {
    "教育部即時新聞": "https://www.edu.tw/Rss_News.aspx?n=9E7AC85F1954DDA8",
    "教育部重要政策": "https://www.edu.tw/Rss_WebArchive.aspx?n=FB01D469347C76A7",
    "移民署新住民政策法規": "https://news.immigration.gov.tw/Rss/Content/8?lang=TW",
    "勞動部新聞稿": "https://www.mol.gov.tw/1607/1632/1633/RssList",
}


def scored(title: str, summary: str, source: str):
    return score_item(title, summary, "taiwan", source, "official")


def main() -> int:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = payload.get("sources") or []
    assert payload.get("schema_version") == 1
    assert len(rows) >= 12, f"expected at least 12 curated feeds, got {len(rows)}"

    urls = [str(x.get("url") or "") for x in rows]
    names = [str(x.get("name") or "") for x in rows]
    assert len(urls) == len(set(urls)), "duplicate feed URL"
    assert len(names) == len(set(names)), "duplicate feed name"
    assert all(url.startswith("https://") for url in urls), "all feeds must use HTTPS"

    by_name = {str(x.get("name")): x for x in rows}
    for name, url in REQUIRED.items():
        row = by_name.get(name)
        assert row, f"missing source: {name}"
        assert row.get("url") == url, (name, row.get("url"))
        assert row.get("region") == "taiwan", name
        assert row.get("source_type") == "official", name

    labor = scored(
        "勞動部修正就業保險給付規定 強化失業勞工權益",
        "新制調整失業給付、就業服務與社會保障。",
        "勞動部新聞稿",
    )
    assert labor and labor[1] == "勞動與社會保障", labor
    assert labor[0] >= 5, labor

    education = scored(
        "教育部修正學生輔導制度 強化中輟與弱勢學生支持",
        "政策聚焦學生輔導、跨專業合作及弱勢學生權益。",
        "教育部重要政策",
    )
    assert education and education[1] == "教育與學生輔導", education
    assert education[0] >= 5, education

    child_survey = scored(
        "敬請支持115年兒童及少年生活狀況調查",
        "依兒童及少年福利與權益保障法辦理生活狀況調查，作為社會福利政策與法規修訂依據。",
        "衛生福利部公告訊息",
    )
    assert child_survey and child_survey[1] == "兒少保護", child_survey

    childcare = scored(
        "響應0-6歲國家一起養 中央部會落實員工子女托育",
        "政策同時提到弱勢家庭、社會福利與托育支持。",
        "教育部即時新聞",
    )
    assert childcare and childcare[1] == "性別與家庭政策", childcare

    noise_cases = [
        (
            "教育部舉辦全國學生競賽",
            "歡迎學生踴躍參加競賽活動。",
            "教育部即時新聞",
        ),
        (
            "參觀國際兒童及青少年書展 鼓勵使用文化幣",
            "推動閱讀政策，邀請兒童與青少年參與文化活動。",
            "行政院本院新聞",
        ),
        (
            "外出牢記防熱4招 護兒童遠離熱傷害",
            "衛生單位提供兒童健康宣導與保護資訊。",
            "衛生福利部焦點新聞",
        ),
        (
            "燈塔引航 守護學子 大專校院專業輔導人員頒獎典禮",
            "表揚學生輔導與校園支持服務人員。",
            "教育部即時新聞",
        ),
        (
            "新住民模擬投票扎根民主",
            "新住民參與公民教育活動，推動政策宣導。",
            "移民署新住民政策法規",
        ),
        (
            "內政部伴新住民築夢 49組團隊創意發光",
            "新住民團隊成果發表與活動。",
            "內政部新聞發布",
        ),
        (
            "接見亞洲地區臺灣同鄉會回國訪問團 用新移民觀念創造投資環境",
            "接見訪問團並談新移民與投資政策。",
            "行政院本院新聞",
        ),
        (
            "教育部辦理大專校院優良校園無障礙建築物評選",
            "樹立校園無障礙環境典範。",
            "教育部即時新聞",
        ),
    ]
    for title, summary, source in noise_cases:
        result = scored(title, summary, source)
        assert result is None, (title, result)

    print(
        "CURRENT AFFAIRS SOURCE SMOKE OK: "
        f"{len(rows)} unique HTTPS feeds; labor/student-support policy accepted; "
        "observed activity, ceremony and child-health noise rejected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

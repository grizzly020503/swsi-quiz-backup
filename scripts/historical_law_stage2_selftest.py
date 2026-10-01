#!/usr/bin/env python3
from __future__ import annotations

import historical_law_exam_date_refiner as s2
import historical_law_provenance_core as hp

assert hp.chinese_integer("一百十五") == 115
assert hp.normalize_article_no("二十六之二") == "26-2"
assert hp.extract_explicit_articles("依第十條、第26條之1、第30之2條及第 41 條規定") == [
    "10", "26-1", "30-2", "41"
]
assert hp.extract_explicit_articles("依第26-1條規定") == ["26-1"]

history = """
4. 中華民國一百十五年六月一日總統令修正公布第 10、13 條條文
3. 中華民國一百十四年十二月一日總統令修正公布第 8 條條文
2. 中華民國一百零四年十二月十六日總統令修正公布第 33-2 條條文；除第 33-2 條自公布後二年施行，其餘自公布日施行
1. 中華民國一百年十一月三十日總統令修正公布名稱及全文 50 條；其餘自公布日施行
"""
entries = hp.parse_history_entries(history)
assert entries[0]["date"] == "2026-06-01"
assert entries[2]["special_effective_date"] is True

html = "<div>考試日期：115/7/25~7/27</div>"
assert s2.parse_moex_exam_dates(html) == ("2026-07-25", "2026-07-27")
assert s2.official_exam_code({"exam_code": "105-2"}) == "105090"
assert s2.official_exam_code({"exam_code": "106-2"}) == "106110"
assert s2.official_exam_code({"source_exam_code": "115100", "exam_code": "115-2"}) == "115100"

question = {"question_id": "Q1", "year": "115", "exam_code": "115-2", "stem": "依第10條規定"}
exam = {
    "status": "official_moex",
    "start_date": "2026-07-25",
    "end_date": "2026-07-27",
    "source_url": "official",
}
result = s2.refine_question(question, entries, exam)
assert result["stage2_status"] == "current_text_equals_exam_date_candidate", result
assert result["historical_version_checked"] is False

history_after = """
2. 中華民國一百十五年八月一日總統令修正公布第 10 條條文
1. 中華民國一百年一月一日總統令制定公布全文 20 條
"""
result = s2.refine_question(question, hp.parse_history_entries(history_after), exam)
assert result["stage2_status"] == "historical_text_required", result

history_during = """
2. 中華民國一百十五年七月二十六日總統令修正公布第 10 條條文
1. 中華民國一百年一月一日總統令制定公布全文 20 條
"""
result = s2.refine_question(question, hp.parse_history_entries(history_during), exam)
assert result["stage2_status"] == "exam_day_resolution_required", result

no_article = {"question_id": "Q2", "year": "115", "exam_code": "115-2", "stem": "依本法規定"}
result = s2.refine_question(no_article, entries, exam)
assert result["stage2_status"] == "article_resolution_required"

mixed = {
    "schema_version": 3,
    "records": [{
        "canonical_name": "測試法",
        "official_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0000001",
    }],
}
assert hp.pcode_from_url(hp.watch_record_map(mixed)["測試法"]["official_url"]) == "A0000001"
legacy = {
    "records": {
        "測試法": {"official_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0000001"}
    }
}
assert "測試法" in hp.watch_record_map(legacy)

# A historical question may legitimately map to more than one explicit law.
# Preserve law context instead of collapsing both mappings to one bare question ID.
original_fetch_dates = s2.fetch_exam_dates
original_fetch_histories = s2.fetch_histories
try:
    s2.fetch_exam_dates = lambda _session, _codes: {
        "115100": {
            "status": "official_moex",
            "start_date": "2026-07-25",
            "end_date": "2026-07-27",
            "source_url": "official-exam",
        }
    }
    s2.fetch_histories = lambda _watch, cards: (
        {card["law_name"]: [] for card in cards},
        {card["law_name"]: f"history://{card['law_name']}" for card in cards},
        {card["law_name"]: None for card in cards},
    )
    shared = {
        "question_id": "Q-SHARED",
        "year": "115",
        "exam_code": "115-2",
        "stem": "依本法規定，下列何者正確？",
    }
    links = {
        "cards": [
            {"law_name": "甲法", "questions": [dict(shared)]},
            {"law_name": "乙法", "questions": [dict(shared)]},
        ]
    }
    report = s2.build_live_report(links, {"records": []}, object())
    assert report["mapping_count"] == 2, report
    assert report["unique_question_count"] == 1, report
    assert report["cross_law_overlap_count"] == 1, report
    assert report["historical_version_checked_count"] == 0, report
    queued = report["exception_queue"]["article_resolution"]
    assert {(row["law_name"], row["question_id"]) for row in queued} == {
        ("甲法", "Q-SHARED"),
        ("乙法", "Q-SHARED"),
    }, queued
finally:
    s2.fetch_exam_dates = original_fetch_dates
    s2.fetch_histories = original_fetch_histories

# Source failures must remain observable and must never turn into verification.
original_fetch_dates = s2.fetch_exam_dates
original_fetch_histories = s2.fetch_histories
try:
    s2.fetch_exam_dates = lambda _session, _codes: {
        "115100": {"status": "unresolved", "source_url": "official-exam", "error": "timeout"}
    }
    s2.fetch_histories = lambda _watch, cards: (
        {card["law_name"]: [] for card in cards},
        {card["law_name"]: f"history://{card['law_name']}" for card in cards},
        {card["law_name"]: "source unavailable" for card in cards},
    )
    links = {"cards": [{"law_name": "甲法", "questions": [dict(question)]}]}
    report = s2.build_live_report(links, {"records": []}, object())
    assert report["historical_version_checked_count"] == 0
    assert report["exam_date_error_count"] == 1
    assert report["law_fetch_error_count"] == 1
    assert report["questions"][0]["history_fetch_error"] == "source unavailable"
finally:
    s2.fetch_exam_dates = original_fetch_dates
    s2.fetch_histories = original_fetch_histories

print("HISTORICAL LAW STAGE2 SELFTEST OK")

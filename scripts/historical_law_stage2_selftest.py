#!/usr/bin/env python3
from __future__ import annotations
import historical_law_provenance_core as hp
import historical_law_exam_date_refiner as s2

assert hp.chinese_integer("一百十五") == 115
assert hp.normalize_article_no("二十六之二") == "26-2"
assert hp.extract_explicit_articles("依第十條、第26條之1、第30之2條及第 41 條規定") == ["10","26-1","30-2","41"]
assert hp.extract_explicit_articles("依第26-1條規定") == ["26-1"]

history = """
4. 中華民國一百十五年六月一日總統令修正公布第 10、13 條條文
3. 中華民國一百十四年十二月一日總統令修正公布第 8 條條文
2. 中華民國一百零四年十二月十六日總統令修正公布第 33-2 條條文；除第 33-2 條自公布後二年施行，其餘自公布日施行
1. 中華民國一百年十一月三十日總統令修正公布名稱及全文 50 條；其餘自公布日施行
"""
entries=hp.parse_history_entries(history)
assert entries[0]["date"] == "2026-06-01"
assert entries[2]["special_effective_date"] is True

html="<div>考試日期：115/7/25~7/27</div>"
assert s2.parse_moex_exam_dates(html) == ("2026-07-25","2026-07-27")
assert s2.official_exam_code({"exam_code":"105-2"}) == "105090"
assert s2.official_exam_code({"exam_code":"106-2"}) == "106110"

q={"question_id":"Q1","year":"115","exam_code":"115-2","stem":"依第10條規定"}
exam={"status":"official_moex","start_date":"2026-07-25","end_date":"2026-07-27","source_url":"official"}
r=s2.refine_question(q,entries,exam)
assert r["stage2_status"] == "current_text_equals_exam_date_candidate", r
assert r["historical_version_checked"] is False

history_after="""
2. 中華民國一百十五年八月一日總統令修正公布第 10 條條文
1. 中華民國一百年一月一日總統令制定公布全文 20 條
"""
r=s2.refine_question(q,hp.parse_history_entries(history_after),exam)
assert r["stage2_status"] == "historical_text_required", r

history_during="""
2. 中華民國一百十五年七月二十六日總統令修正公布第 10 條條文
1. 中華民國一百年一月一日總統令制定公布全文 20 條
"""
r=s2.refine_question(q,hp.parse_history_entries(history_during),exam)
assert r["stage2_status"] == "exam_day_resolution_required", r

no_article={"question_id":"Q2","year":"115","exam_code":"115-2","stem":"依本法規定"}
r=s2.refine_question(no_article,entries,exam)
assert r["stage2_status"] == "article_resolution_required"

mixed={"schema_version":3,"records":[{"canonical_name":"測試法","official_url":"https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0000001"}]}
assert hp.pcode_from_url(hp.watch_record_map(mixed)["測試法"]["official_url"]) == "A0000001"
legacy={"records":{"測試法":{"official_url":"https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0000001"}}}
assert "測試法" in hp.watch_record_map(legacy)
print("HISTORICAL LAW STAGE2 SELFTEST OK")

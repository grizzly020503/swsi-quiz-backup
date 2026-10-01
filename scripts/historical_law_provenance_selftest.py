#!/usr/bin/env python3
# Intentionally stdlib-only: live MOJ HTTP dependencies must not be required by CI.
from historical_law_provenance import (
    chinese_integer,
    extract_explicit_articles,
    parse_history_entries,
    triage_question,
)


def q(year, stem, qid="SP-test"):
    return {"question_id": qid, "year": str(year), "stem": stem, "exam_code": f"{year}-1"}

assert chinese_integer("九十九") == 99
assert chinese_integer("一百零四") == 104
assert chinese_integer("一百十五") == 115
assert chinese_integer("115") == 115
assert extract_explicit_articles("依第8條及第 26-1 條規定，何者正確？") == ["8", "26-1"]
assert extract_explicit_articles("補助 3 個月，所得為最低生活費 2.5 倍") == []

history_text = """
15. 中華民國一百十年一月二十日總統令修正公布第 26 條條文
14. 中華民國一百零九年一月十五日總統令增訂公布第 23-1 條條文
13. 中華民國一百零八年四月二十四日總統令修正公布第 10、13、41、43、49、53、54、56、62～64、70、76、81 條條文；並增訂第 21-1 條條文
10. 中華民國一百零四年十二月十六日總統令修正公布第 7 條條文；並增訂第 33-1、33-2、90-2 條條文；除第 33-2 條自公布後二年施行，其餘自公布日施行
5. 中華民國一百年十一月三十日總統令修正公布名稱及全文 118 條；其餘自公布日施行
"""
entries = parse_history_entries(history_text)
assert len(entries) == 5
by_year = {e["year"]: e for e in entries}
assert {"62", "63", "64"}.issubset(set(by_year[2019]["articles"]))
assert by_year[2015]["special_effective_date"] is True
assert by_year[2011]["all_articles"] is True

r = triage_question(q(110, "依兒童及少年福利與權益保障法，下列何者正確？"), entries)
assert r["status"] == "article_resolution_required"
assert r["historical_version_checked"] is False
r = triage_question(q(108, "依第26條規定，下列何者正確？"), entries)
assert r["status"] == "historical_text_required"
assert r["post_exam_change_years"] == [2021]
r = triage_question(q(108, "依第10條規定，下列何者正確？"), entries)
assert r["status"] == "exam_date_required"
r = triage_question(q(110, "依第33-2條規定，下列何者正確？"), entries)
assert r["status"] == "effective_date_review"
r = triage_question(q(110, "依第50條規定，下列何者正確？"), entries)
assert r["status"] == "current_text_equals_exam_year_candidate"
assert r["eligible_for_historical_version_checked"] is True
assert r["historical_version_checked"] is False
r = triage_question(q(107, "依第23-1條規定，下列何者正確？"), entries)
assert r["status"] == "historical_text_required"
print("HISTORICAL LAW PROVENANCE SELFTEST OK")

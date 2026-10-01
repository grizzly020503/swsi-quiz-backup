#!/usr/bin/env python3
"""Deterministic safety tests for historical_law_provenance.py."""
from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

from historical_law_provenance import (
    build_report,
    chinese_integer,
    extract_explicit_articles,
    normalize_article_no,
    parse_history_entries,
    pcode_from_url,
    triage_question,
    watch_record_map,
)

ROOT = Path(__file__).resolve().parents[1]
LINKS = ROOT / "data/law_question_links_priority10.v1.json"
WATCH = ROOT / "data/legal_watch_report.json"


def q(year: int, stem: str, qid: str = "SP-test") -> dict:
    return {
        "question_id": qid,
        "year": str(year),
        "stem": stem,
        "exam_code": f"{year}-1",
    }


def parser_contract() -> None:
    assert chinese_integer("九十九") == 99
    assert chinese_integer("一百零四") == 104
    assert chinese_integer("一百十五") == 115
    assert chinese_integer("二十六") == 26
    assert chinese_integer("115") == 115

    assert normalize_article_no("26之1") == "26-1"
    assert normalize_article_no("二十六之一") == "26-1"
    assert extract_explicit_articles("依第8條及第 26-1 條規定，何者正確？") == ["8", "26-1"]
    assert extract_explicit_articles("依第十條、第26條之1、第30之2條及第 41 條規定") == [
        "10",
        "26-1",
        "30-2",
        "41",
    ]
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


def triage_contract() -> None:
    history_text = """
15. 中華民國一百十年一月二十日總統令修正公布第 26 條條文
14. 中華民國一百零九年一月十五日總統令增訂公布第 23-1 條條文
13. 中華民國一百零八年四月二十四日總統令修正公布第 10、13、41、43、49、53、54、56、62～64、70、76、81 條條文；並增訂第 21-1 條條文
10. 中華民國一百零四年十二月十六日總統令修正公布第 7 條條文；並增訂第 33-1、33-2、90-2 條條文；除第 33-2 條自公布後二年施行，其餘自公布日施行
5. 中華民國一百年十一月三十日總統令修正公布名稱及全文 118 條；其餘自公布日施行
"""
    entries = parse_history_entries(history_text)

    original = q(110, "依兒童及少年福利與權益保障法，下列何者正確？")
    before = deepcopy(original)
    result = triage_question(original, entries)
    assert result["status"] == "article_resolution_required"
    assert result["historical_version_checked"] is False
    assert original == before, "triage must not mutate official question content"

    result = triage_question(q(108, "依第26條規定，下列何者正確？"), entries)
    assert result["status"] == "historical_text_required"
    assert result["post_exam_change_years"] == [2021]

    result = triage_question(q(108, "依第10條規定，下列何者正確？"), entries)
    assert result["status"] == "exam_date_required"

    result = triage_question(q(110, "依第33-2條規定，下列何者正確？"), entries)
    assert result["status"] == "effective_date_review"

    result = triage_question(q(110, "依第50條規定，下列何者正確？"), entries)
    assert result["status"] == "current_text_equals_exam_year_candidate"
    assert result["eligible_for_historical_version_checked"] is True
    assert result["historical_version_checked"] is False

    result = triage_question(q(107, "依第23-1條規定，下列何者正確？"), entries)
    assert result["status"] == "historical_text_required"

    result = triage_question(q(110, "依第10條規定，下列何者正確？"), [])
    assert result["status"] == "official_history_unavailable"
    assert result["historical_version_checked"] is False


def repository_contract() -> None:
    links = json.loads(LINKS.read_text(encoding="utf-8"))
    watch = json.loads(WATCH.read_text(encoding="utf-8"))

    cards = links.get("cards") or []
    assert len(cards) == 10, len(cards)

    mappings: list[tuple[str, dict]] = []
    for card in cards:
        law = str(card.get("law_name") or "")
        card_questions = card.get("questions") or []
        card_ids = [str(row.get("question_id") or "") for row in card_questions]
        assert all(card_ids), f"missing question ID in {law}"
        assert len(card_ids) == len(set(card_ids)), f"duplicate question inside law card: {law}"
        mappings.extend((law, row) for row in card_questions)

    assert len(mappings) == 86, len(mappings)
    mapping_keys = [(law, str(row.get("question_id") or "")) for law, row in mappings]
    assert len(set(mapping_keys)) == 86, "duplicate law/question mapping"

    question_ids = [qid for _law, qid in mapping_keys]
    unique_question_count = len(set(question_ids))
    overlap_count = len(question_ids) - unique_question_count
    assert 0 < unique_question_count <= 86

    for _law, row in mappings:
        assert row.get("match_strength") == "metadata_only", row
        assert row.get("historical_version_checked") is False, row

    indexed = watch_record_map(watch)
    assert len(indexed) >= 10, len(indexed)
    for card in cards:
        law = card["law_name"]
        assert law in indexed, law
        assert pcode_from_url(indexed[law].get("official_url")), indexed[law]

    report = build_report(links, watch, live=False)
    assert report["question_count"] == 86, report
    assert sum(report["status_counts"].values()) == 86, report
    assert all(row["historical_version_checked"] is False for row in report["questions"])
    assert all(row.get("official_history_url") for row in report["questions"])
    assert set(report["status_counts"]).issubset(
        {"article_resolution_required", "official_history_unavailable"}
    ), report["status_counts"]

    repeated = {qid: count for qid, count in Counter(question_ids).items() if count > 1}
    print(
        "PRIORITY LAW REAL-DATA CONTRACT:",
        f"mappings=86 unique_questions={unique_question_count} cross_law_overlap={overlap_count}",
        f"repeated_question_ids={repeated}",
    )


def main() -> int:
    parser_contract()
    triage_contract()
    repository_contract()
    print("HISTORICAL LAW PROVENANCE SELFTEST OK: parsers + fail-closed triage + 86-mapping repository contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

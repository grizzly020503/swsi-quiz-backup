#!/usr/bin/env python3
"""Deterministic safety tests for historical_law_provenance.py."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import historical_law_provenance as hp

ROOT = Path(__file__).resolve().parents[1]
LINKS = ROOT / "data/law_question_links_priority10.v1.json"
WATCH = ROOT / "data/legal_watch_report.json"


def q(stem: str, year: str = "110") -> dict:
    return {
        "question_id": "Q-TEST",
        "exam_code": f"{year}-1",
        "year": year,
        "stem": stem,
        "official_answer": "B",
        "grading_mode": "standard",
    }


def entry(year: int, *, articles=None, all_articles=False, special=False) -> dict:
    return {
        "year": year,
        "articles": articles or [],
        "all_articles": all_articles,
        "special_effective_date": special,
        "summary": "fixture",
    }


def parser_contract() -> None:
    assert hp.chinese_integer("一百十五") == 115
    assert hp.chinese_integer("九十九") == 99
    assert hp.normalize_article_no("26之1") == "26-1"
    assert hp.normalize_article_no("二十六之二") == "26-2"
    got = hp.extract_explicit_articles("依第十條、第26條之1、第30之2條及第 41 條規定")
    assert got == ["10", "26-1", "30-2", "41"], got

    history_text = """
15. 中華民國一百十五年六月一日修正第 10、13、26-1 條
14. 中華民國一百十二年五月一日修正全文 20 條
13. 中華民國一百零八年一月一日修正第 7 條並自公布日施行
"""
    parsed = hp.parse_history_entries(history_text)
    assert [x["year"] for x in parsed] == [2026, 2023, 2019], parsed
    assert {"10", "13", "26-1"}.issubset(set(parsed[0]["articles"])), parsed[0]
    assert parsed[1]["all_articles"] is True, parsed[1]
    assert parsed[2]["special_effective_date"] is False, parsed[2]


def triage_contract() -> None:
    original = q("依第10條規定，下列何者正確？", "110")
    before = deepcopy(original)

    out = hp.triage_question(original, [entry(2020, articles=["10"])])
    assert out["status"] == "current_text_equals_exam_year_candidate", out
    assert out["eligible_for_historical_version_checked"] is True, out
    assert out["historical_version_checked"] is False, out
    assert original == before, "triage must never mutate official question content"

    out = hp.triage_question(q("依第10條規定", "110"), [entry(2020, articles=["10"]), entry(2023, articles=["10"])])
    assert out["status"] == "historical_text_required", out
    assert out["post_exam_change_years"] == [2023], out

    out = hp.triage_question(q("依第10條規定", "110"), [entry(2021, articles=["10"])])
    assert out["status"] == "exam_date_required", out

    out = hp.triage_question(q("依第10條規定", "110"), [entry(2020, articles=["10"], special=True)])
    assert out["status"] == "effective_date_review", out

    out = hp.triage_question(q("依本法規定，下列何者正確？", "110"), [entry(2020, articles=["10"])])
    assert out["status"] == "article_resolution_required", out

    out = hp.triage_question(q("依第10條規定", "110"), [])
    assert out["status"] == "official_history_unavailable", out


def repository_contract() -> None:
    links = json.loads(LINKS.read_text(encoding="utf-8"))
    watch = json.loads(WATCH.read_text(encoding="utf-8"))
    cards = links.get("cards") or []
    assert len(cards) == 10, len(cards)

    rows = [question for card in cards for question in (card.get("questions") or [])]
    assert len(rows) == 86, len(rows)
    ids = [str(row.get("question_id") or "") for row in rows]
    assert len(set(ids)) == 86 and all(ids), "priority-law question IDs must be unique"
    for row in rows:
        assert row.get("match_strength") == "metadata_only", row
        assert row.get("historical_version_checked") is False, row
        assert row.get("official_answer") in {"A", "B", "C", "D"}, row

    indexed = hp.watch_record_map(watch)
    assert len(indexed) >= 10, len(indexed)
    for card in cards:
        law = card["law_name"]
        assert law in indexed, law
        assert hp.pcode_from_url(indexed[law].get("official_url")), indexed[law]

    report = hp.build_report(links, watch, live=False)
    assert report["question_count"] == 86, report
    assert sum(report["status_counts"].values()) == 86, report
    assert all(row["historical_version_checked"] is False for row in report["questions"])
    allowed = {"article_resolution_required", "official_history_unavailable"}
    assert set(report["status_counts"]).issubset(allowed), report["status_counts"]
    assert all(row.get("official_history_url") for row in report["questions"]), "every priority law must have an MOJ history URL"


def main() -> int:
    parser_contract()
    triage_contract()
    repository_contract()
    print("historical-law provenance selftest: PASS (parsers + fail-closed triage + 86-question contract)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

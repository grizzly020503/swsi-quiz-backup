#!/usr/bin/env python3
"""Synthetic self-test for scripts/unified_question_qa.py.

Key invariant: generation backlog must not become human-review backlog.
A future exam may have hundreds of pending explanations while the manual queue
remains near zero when Official Core and current-law watch are healthy.
"""

from __future__ import annotations

import json
from pathlib import Path

from unified_question_qa import summarize, validate_essays, validate_mcq

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "data" / "question_qa_policy_v1.json").read_text(encoding="utf-8"))
SUBJECTS = POLICY["subjects"]
YEAR = "116"
ROUND = "第一次"


def make_mcqs(analysis_status: str = "done") -> list[dict]:
    rows = []
    idx = 0
    for subject in SUBJECTS:
        for qno in range(1, 41):
            idx += 1
            rows.append(
                {
                    "id": f"Q-{YEAR}-1-{idx:03d}",
                    "subject": subject,
                    "year": YEAR,
                    "round": ROUND,
                    "qno": str(qno),
                    "question": f"測試題目 {idx}",
                    "opt_a": "選項A",
                    "opt_b": "選項B",
                    "opt_c": "選項C",
                    "opt_d": "選項D",
                    "answer": "A",
                    "accepted_answers": None,
                    "grading_mode": "standard",
                    "source_exam_code": "116100",
                    "analysis_status": analysis_status,
                    "legal_status": "",
                    "law": "",
                    "extension": "",
                    "exp_why": "",
                    "exp_raw": "",
                }
            )
    return rows


def make_essays(analysis_status: str = "pending") -> list[dict]:
    rows = []
    idx = 0
    for subject in SUBJECTS:
        for qno in (1, 2):
            idx += 1
            rows.append(
                {
                    "id": f"E-{YEAR}-1-{idx:02d}",
                    "subject": subject,
                    "year": YEAR,
                    "round": ROUND,
                    "qno": str(qno),
                    "q": f"請說明第 {idx} 題的核心概念並舉例。",
                    "points": "20",
                    "source_exam_code": "116100",
                    "source_url": f"https://example.invalid/moex/{idx}",
                    "analysis_status": analysis_status,
                }
            )
    return rows


def make_watch(changed: bool = False) -> dict:
    return {
        "checked_at": "2027-02-01T12:00:00+08:00",
        "lookup_error_count": 0,
        "missing_count": 0,
        "records": {
            "老人福利法": {
                "canonical_name": "老人福利法",
                "found": True,
                "changed": changed,
                "official_modified_date": "2026-12-01",
            }
        },
    }


def assert_eq(got, expected, label: str) -> None:
    if got != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {got!r}")


def run() -> None:
    # 1. Completely healthy MCQ official core.
    mcq_items, mcq_session = validate_mcq(make_mcqs("done"), YEAR, ROUND, POLICY)
    mcq_summary = summarize(mcq_items, mcq_session)
    assert_eq(mcq_summary["official_core"]["passed"], 200, "healthy mcq passed")
    assert_eq(mcq_summary["official_core"]["blocked"], 0, "healthy mcq blocked")
    assert_eq(mcq_summary["manual_review_queue_count"], 0, "healthy mcq manual queue")
    assert_eq(mcq_summary["enrichment"]["pending_generation"], 0, "healthy mcq generation pending")

    # 2. All 200 explanations pending generation must NOT create 200 human tasks.
    pending_items, pending_session = validate_mcq(make_mcqs("pending"), YEAR, ROUND, POLICY)
    pending_summary = summarize(pending_items, pending_session)
    assert_eq(pending_summary["official_core"]["passed"], 200, "pending mcq official passed")
    assert_eq(pending_summary["enrichment"]["pending_generation"], 200, "pending mcq generation backlog")
    assert_eq(pending_summary["manual_review_queue_count"], 0, "pending mcq manual queue")

    # 3. Special grading without explicit grading_mode must fail closed.
    broken = make_mcqs("done")
    broken[15]["answer"] = "一律給分"
    broken[15]["grading_mode"] = ""
    broken_items, broken_session = validate_mcq(broken, YEAR, ROUND, POLICY)
    broken_summary = summarize(broken_items, broken_session)
    assert_eq(broken_summary["official_core"]["blocked"], 1, "special grading blocked")
    if broken_summary["manual_review_queue_count"] < 1:
        raise AssertionError("special grading anomaly must enter human queue")

    # 4. "第三條路" is a welfare-policy theory, NOT legal article 3.
    third_way = make_mcqs("done")
    third_way[0]["question"] = "下列何者不是第三條路所重視的特性？"
    third_items, third_session = validate_mcq(third_way, YEAR, ROUND, POLICY)
    third_summary = summarize(third_items, third_session)
    assert_eq(third_summary["manual_review_queue_count"], 0, "third-way false legal positive")
    assert_eq(third_items[0]["signals"]["legal_or_policy"], [], "third-way legal signals")

    # 5. Ten normal essays may wait for guide generation with zero human tasks.
    essay_items, essay_session = validate_essays(make_essays("pending"), YEAR, ROUND, POLICY)
    essay_summary = summarize(essay_items, essay_session)
    assert_eq(essay_summary["official_core"]["passed"], 10, "healthy essay official passed")
    assert_eq(essay_summary["enrichment"]["pending_generation"], 10, "essay generation backlog")
    assert_eq(essay_summary["manual_review_queue_count"], 0, "healthy essay manual queue")

    # 6. A law essay defaults to review: this is the safe historical/default mode.
    legal = make_essays("pending")
    legal[0]["q"] = "依老人福利法第 32 條規定，說明住宅扶助措施。"
    legal_items, legal_session = validate_essays(legal, YEAR, ROUND, POLICY)
    legal_summary = summarize(legal_items, legal_session)
    assert_eq(legal_summary["manual_review_queue_count"], 1, "default law essay manual queue")

    # 7. For a CURRENT intake only, a healthy unchanged legal watch clears that
    # duplicate manual task. Official Core remains untouched.
    watched_items, watched_session = validate_essays(
        legal,
        YEAR,
        ROUND,
        POLICY,
        legal_watch=make_watch(changed=False),
        trust_current_legal_watch=True,
    )
    watched_summary = summarize(watched_items, watched_session)
    assert_eq(watched_summary["manual_review_queue_count"], 0, "fresh current legal watch queue")
    assert_eq(watched_items[0]["signals"]["legal_watch_fresh"], True, "fresh watch signal")

    # 8. If the watched law changed, it must re-enter manual review.
    changed_items, changed_session = validate_essays(
        legal,
        YEAR,
        ROUND,
        POLICY,
        legal_watch=make_watch(changed=True),
        trust_current_legal_watch=True,
    )
    changed_summary = summarize(changed_items, changed_session)
    assert_eq(changed_summary["manual_review_queue_count"], 1, "changed law queue")

    print("UNIFIED QUESTION QA SELFTEST OK")
    print("- 200 pending MCQ explanations -> manual queue 0")
    print("- 10 pending essay guides -> manual queue 0")
    print("- explicit special-grading anomaly -> blocked")
    print("- '第三條路' -> not misclassified as 第三條")
    print("- current unchanged legal watch -> duplicate law review cleared")
    print("- changed law -> review restored")


if __name__ == "__main__":
    run()

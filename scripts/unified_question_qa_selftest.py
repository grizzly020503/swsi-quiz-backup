#!/usr/bin/env python3
"""Synthetic self-test for scripts/unified_question_qa.py.

The important invariant is that generation backlog must not become human-review
backlog. A future 200-question exam may have 200 pending explanations while the
manual queue remains zero if Official Core is healthy.
"""

from __future__ import annotations

import copy
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


def assert_eq(got, expected, label: str) -> None:
    if got != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {got!r}")


def run() -> None:
    # Case 1: completely healthy MCQ official core.
    mcq_items, mcq_session = validate_mcq(make_mcqs("done"), YEAR, ROUND, POLICY)
    mcq_summary = summarize(mcq_items, mcq_session)
    assert_eq(mcq_summary["official_core"]["passed"], 200, "healthy mcq passed")
    assert_eq(mcq_summary["official_core"]["blocked"], 0, "healthy mcq blocked")
    assert_eq(mcq_summary["manual_review_queue_count"], 0, "healthy mcq manual queue")
    assert_eq(mcq_summary["enrichment"]["pending_generation"], 0, "healthy mcq generation pending")

    # Case 2: all 200 explanations are still pending generation.
    # This MUST NOT create 200 human-review tasks.
    pending_items, pending_session = validate_mcq(make_mcqs("pending"), YEAR, ROUND, POLICY)
    pending_summary = summarize(pending_items, pending_session)
    assert_eq(pending_summary["official_core"]["passed"], 200, "pending mcq official passed")
    assert_eq(pending_summary["enrichment"]["pending_generation"], 200, "pending mcq generation backlog")
    assert_eq(pending_summary["manual_review_queue_count"], 0, "pending mcq manual queue")

    # Case 3: special grading marker without explicit grading_mode must fail closed.
    broken = make_mcqs("done")
    broken[15]["answer"] = "一律給分"
    broken[15]["grading_mode"] = ""
    broken_items, broken_session = validate_mcq(broken, YEAR, ROUND, POLICY)
    broken_summary = summarize(broken_items, broken_session)
    assert_eq(broken_summary["official_core"]["blocked"], 1, "special grading blocked")
    if broken_summary["manual_review_queue_count"] < 1:
        raise AssertionError("special grading anomaly must enter human queue")

    # Case 4: ten normal essays may wait for automatic guide generation without
    # creating ten human-review tasks.
    essay_items, essay_session = validate_essays(make_essays("pending"), YEAR, ROUND, POLICY)
    essay_summary = summarize(essay_items, essay_session)
    assert_eq(essay_summary["official_core"]["passed"], 10, "healthy essay official passed")
    assert_eq(essay_summary["enrichment"]["pending_generation"], 10, "essay generation backlog")
    assert_eq(essay_summary["manual_review_queue_count"], 0, "healthy essay manual queue")

    # Case 5: only the law/policy essay enters enrichment human review.
    legal = make_essays("pending")
    legal[0]["q"] = "依老人福利法第 32 條規定，說明住宅扶助措施。"
    legal_items, legal_session = validate_essays(legal, YEAR, ROUND, POLICY)
    legal_summary = summarize(legal_items, legal_session)
    assert_eq(legal_summary["official_core"]["passed"], 10, "legal essay official passed")
    assert_eq(legal_summary["manual_review_queue_count"], 1, "legal essay manual queue")

    print("UNIFIED QUESTION QA SELFTEST OK")
    print("- 200 pending MCQ explanations -> manual queue 0")
    print("- 10 pending essay guides -> manual queue 0")
    print("- explicit special-grading anomaly -> blocked")
    print("- one legal essay -> one enrichment review")


if __name__ == "__main__":
    run()

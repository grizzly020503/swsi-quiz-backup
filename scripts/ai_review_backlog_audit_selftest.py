#!/usr/bin/env python3
"""Synthetic fail-closed tests for read-only AI review backlog triage."""
from __future__ import annotations

from copy import deepcopy
from ai_review_backlog_audit import audit, validate_scope, review_category


def corpus() -> list[dict]:
    rows = []
    for year in range(104, 116):
        for rnd in ("第一次", "第二次"):
            for subject in (
                "社會工作", "社會工作直接服務", "社會政策與社會立法",
                "人類行為與社會環境", "社會工作研究方法",
            ):
                for qno in range(1, 41):
                    rows.append({
                        "id": f"TEST-{year}-{rnd}-{subject}-{qno:02d}",
                        "year": str(year), "round": rnd, "subject": subject,
                        "qno": str(qno), "analysis_status": "ready",
                        "analysis_error": None, "grading_mode": "standard",
                        "accepted_answers": None, "answer": "A",
                    })
    return rows


def require_fail(rows: list[dict], expected_message: str) -> None:
    try:
        audit(rows)
    except ValueError as exc:
        assert expected_message in str(exc), str(exc)
    else:
        raise AssertionError("audit accepted malformed historical source")


def main() -> None:
    rows = corpus()
    validate_scope(rows)
    assert audit(rows)["analysis_status"] == {
        "ready": 4800, "review": 0, "pending": 0, "analyzing": 0,
    }
    for row in rows[:7]:
        row["analysis_status"] = "review"
    rows[0]["analysis_error"] = "AI qwen/qwen3.6-27b HTTP 405"
    rows[1]["analysis_error"] = "AI qwen/qwen3.6-27b HTTP 405 legacy"
    rows[1]["accepted_answers"] = ["A"]  # valid populated single-answer set
    rows[2]["analysis_error"] = None
    rows[3]["analysis_error"] = "v12 dedicated validation"
    rows[4]["accepted_answers"] = ["A", "B"]
    rows[4]["analysis_error"] = "AI qwen/qwen3.6-27b HTTP 405"  # multi takes priority
    rows[5]["grading_mode"] = "all_credit"
    rows[5]["answer"] = "一律給分"  # Official MOEX marker, not A-D
    rows[6]["grading_mode"] = "any_answer"
    rows[6]["answer"] = "一律給分"  # Both special modes use this sentinel
    result = audit(rows)
    assert result["total_historical_mcq"] == 4800
    assert result["analysis_status"]["review"] == 7
    assert result["review_categories"] == {
        "legacy_http_405_single_answer": 2,
        "missing_reason_single_answer": 1,
        "other_manual_single_answer": 1,
        "multi_answer_requires_separate_review": 1,
        "special_grading_requires_separate_review": 2,
    }, result
    assert not result["automatic_change"] and not result["bulk_requeue_allowed"]
    assert not result["release_approval"] and not result["ready_means_human_verified"]
    assert result["legacy_http_405_is_historical_annotation"]
    assert review_category(rows[4]) == "multi_answer_requires_separate_review"
    assert review_category(rows[5]) == "special_grading_requires_separate_review"

    require_fail(rows[:-1], "4800")
    bad = deepcopy(rows); bad[0]["id"] = bad[1]["id"]
    require_fail(bad, "duplicate question ID")
    bad = deepcopy(rows); bad[0]["qno"] = "41"
    require_fail(bad, "question number")
    bad = deepcopy(rows); bad[0]["analysis_status"] = "verified"
    require_fail(bad, "unknown analysis status")
    bad = deepcopy(rows); bad[0]["grading_mode"] = "auto_credit"
    require_fail(bad, "unknown analysis status or grading mode")
    bad = deepcopy(rows); bad[4]["accepted_answers"] = ["A", "A"]
    require_fail(bad, "invalid accepted_answers")
    bad = deepcopy(rows); bad[4]["accepted_answers"] = ["B", "C"]
    require_fail(bad, "standard grading conflicts")
    bad = deepcopy(rows); bad[0]["answer"] = "一律給分"
    require_fail(bad, "invalid standard official answer")
    bad = deepcopy(rows); bad[5]["answer"] = "A"
    require_fail(bad, "invalid special-credit official answer")
    bad = deepcopy(rows); bad[6]["accepted_answers"] = ["A"]
    require_fail(bad, "invalid special-credit official answer")
    bad = deepcopy(rows); bad[0]["analysis_error"] = ["unexpected"]
    require_fail(bad, "invalid analysis error type")
    bad = deepcopy(rows); bad[0].pop("analysis_error")
    require_fail(bad, "malformed or incomplete")
    bad = deepcopy(rows); bad[0]["year"] = "116"
    require_fail(bad, "unexpected historic")
    print("AI REVIEW BACKLOG TRIAGE SELFTEST PASS: 4800 historical, 7 review cases, 13 fail-closed variants; no writes")


if __name__ == "__main__":
    main()

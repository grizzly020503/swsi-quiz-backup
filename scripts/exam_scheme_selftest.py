#!/usr/bin/env python3
"""Synthetic acceptance tests for versioned exam-scheme intake.

These fixtures are deliberately synthetic. They do NOT claim ROC 116 or any
later examination will actually use these structures.
"""

from __future__ import annotations

from copy import deepcopy

from exam_scheme import compare_payload, load_registry


def build_payload(
    year: str,
    round_name: str,
    *,
    subject_limit: int | None = None,
    essays_per_subject: int = 2,
    special_grading: bool = False,
) -> dict:
    registry = load_registry()
    profile = registry["profiles"][0]
    subjects = profile["subjects"]
    if subject_limit is not None:
        subjects = subjects[:subject_limit]
    suffix = profile["exam_code_suffixes"][round_name]
    code = f"{year}{suffix}"
    questions = []
    essays = []
    for subject in subjects:
        for qno in range(1, 41):
            row = {
                "id": f"{subject['prefix']}-{year}-{'1' if round_name == '第一次' else '2'}-{qno:03d}",
                "subject": subject["name"],
                "year": year,
                "round": round_name,
                "qno": str(qno),
                "question": f"SYNTHETIC {subject['name']} question {qno}",
                "opt_a": "A",
                "opt_b": "B",
                "opt_c": "C",
                "opt_d": "D",
                "answer": "A",
                "grading_mode": "standard",
                "source_exam_code": code,
                "source_url": "https://example.invalid/synthetic",
            }
            questions.append(row)
        for qno in range(1, essays_per_subject + 1):
            essays.append(
                {
                    "id": f"E-{year}-{'1' if round_name == '第一次' else '2'}-{subject['prefix']}-{qno}",
                    "subject": subject["name"],
                    "year": year,
                    "round": round_name,
                    "qno": str(qno),
                    "q": f"SYNTHETIC {subject['name']} essay {qno}（20 分）",
                    "points": "20",
                    "source_exam_code": code,
                    "source_url": "https://example.invalid/synthetic",
                }
            )

    if special_grading:
        questions[0]["answer"] = "一律給分"
        questions[0]["grading_mode"] = "all_credit"
        questions[1]["answer"] = "一律給分"
        questions[1]["grading_mode"] = "any_answer"

    return {
        "exam_type": registry["exam_type"],
        "exam_code": code,
        "roc_year": year,
        "round": round_name,
        "source_page": "https://example.invalid/synthetic",
        "questions": questions,
        "essays": essays,
    }


def assert_status(payload: dict, expected: str) -> dict:
    result = compare_payload(payload)
    assert result["status"] == expected, result
    return result


def main() -> int:
    # Same approved shape in a future year: no code change should be required.
    normal_116_1 = build_payload("116", "第一次")
    normal = assert_status(normal_116_1, "match")
    assert normal["profile_id"] == "social-worker-five-subjects-v1"

    # A much later year with the same shape still inherits the latest approved profile.
    assert_status(build_payload("130", "第二次"), "match")

    # Special grading is a grading semantic, not an exam-structure change.
    special = assert_status(build_payload("116", "第一次", special_grading=True), "match")
    assert special["observed"]["grading_modes"]["all_credit"] == 1
    assert special["observed"]["grading_modes"]["any_answer"] == 1

    # Synthetic future reform: one subject disappears. Must be quarantined.
    fewer_subjects = assert_status(
        build_payload("117", "第一次", subject_limit=4),
        "candidate_change",
    )
    assert any(d["field"] == "mcq.subjects" for d in fewer_subjects["diffs"])
    assert fewer_subjects["candidate_profile"]["auto_approved"] is False

    # Synthetic future reform: essays disappear. Must NOT be treated as complete.
    no_essays = assert_status(
        build_payload("117", "第二次", essays_per_subject=0),
        "candidate_change",
    )
    assert any(d["field"] == "essay.total" for d in no_essays["diffs"])

    # Identity mismatch is not a candidate reform; it is bad session metadata.
    bad_identity = deepcopy(normal_116_1)
    bad_identity["exam_code"] = "116100"
    invalid = assert_status(bad_identity, "invalid_identity")
    assert invalid["identity_issues"]

    print("EXAM SCHEME SELFTEST OK")
    print("- synthetic 116-1 same shape -> match")
    print("- synthetic future same shape -> match")
    print("- special grading -> match (not a structure change)")
    print("- synthetic fewer subjects -> candidate_change / quarantined")
    print("- synthetic no essays -> candidate_change / quarantined")
    print("- mismatched exam identity -> invalid_identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

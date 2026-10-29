#!/usr/bin/env python3
"""Deterministic exact-hash, no-network tests for candidate/live release parity."""
from __future__ import annotations

import argparse
from copy import deepcopy

from official_exam_readonly_guard import MCQ_FIELDS, canonical_row, row_hash
from official_candidate_live_core_preflight import (
    EXPECTED_CHANGED, check, current_lock, read_pinned_lock,
)
from official_option_scenario_guard import read_rows


def run(check_real_baseline: bool) -> None:
    candidate_rows = read_rows()
    candidate = current_lock()
    assert len(candidate_rows) == 4800 and len(candidate["essays"]) == 240
    base = deepcopy(candidate)
    before_rows = [dict(r) for r in candidate_rows]
    changed_ids = sorted(candidate["mcq"])[:EXPECTED_CHANGED]
    changed = set(changed_ids)
    for row in before_rows:
        if row["id"] in changed:
            row["question"] += "【synthetic preimage for no-network tests】"
            base["mcq"][row["id"]] = row_hash(canonical_row(row, MCQ_FIELDS))

    clean_old = check(base, candidate, candidate_rows, before_rows)
    assert clean_old["candidate_changed_official_core"] == 43
    assert clean_old["live_state"] == "BEFORE_ONLY" and clean_old["live_pending_exact_core"] == 43
    assert clean_old["live_unexpected_core_drift"] == 0 and clean_old["live_grading_difference"] == 0
    assert not clean_old["production_written"] and not clean_old["release_approved"]

    clean_new = check(base, candidate, candidate_rows, candidate_rows)
    assert clean_new["live_state"] == "AFTER_ONLY" and clean_new["live_already_at_candidate_core"] == 43
    mixed = [dict(r) for r in before_rows]
    repaired = next(i for i, row in enumerate(mixed) if row["id"] in changed)
    mixed[repaired] = dict(candidate_rows[repaired])
    mixed_report = check(base, candidate, candidate_rows, mixed)
    assert mixed_report["live_state"] == "MIXED_PARTIAL"
    assert mixed_report["live_pending_exact_core"] == 42
    assert mixed_report["live_already_at_candidate_core"] == 1

    unknown = [dict(r) for r in before_rows]
    item = next(r for r in unknown if r["id"] not in changed)
    item["question"] += "UNAUTHORIZED DRIFT"
    drift_report = check(base, candidate, candidate_rows, unknown)
    assert drift_report["live_state"] == "DRIFT"
    assert item["id"] in drift_report["unexpected_ids"]

    bad_grade = [dict(r) for r in before_rows]
    bad_grade[0]["grading_mode"] = "unapproved_grade"
    grade_report = check(base, candidate, candidate_rows, bad_grade)
    assert grade_report["live_state"] == "DRIFT"
    assert grade_report["live_grading_difference"] == 1

    bad_scope = deepcopy(base)
    bad_scope["mcq"][changed_ids[0]] = candidate["mcq"][changed_ids[0]]
    try:
        check(bad_scope, candidate, candidate_rows, before_rows)
    except ValueError as exc:
        assert "unreviewed Official Core candidate change scope" in str(exc), str(exc)
    else:
        raise AssertionError("unreviewed change-count drift must fail")
    try:
        check(base, candidate, candidate_rows, before_rows[:-1])
    except ValueError as exc:
        assert "historical question IDs" in str(exc)
    else:
        raise AssertionError("partial live rows must fail")
    tampered = deepcopy(candidate)
    tampered["mcq"][changed_ids[0]] = "0" * 64
    try:
        check(base, tampered, candidate_rows, before_rows)
    except ValueError as exc:
        assert "own lock" in str(exc)
    else:
        raise AssertionError("candidate lock tampering must fail")

    if check_real_baseline:
        original = read_pinned_lock()
        report = check(original, candidate, candidate_rows, candidate_rows)
        assert report["candidate_changed_official_core"] == EXPECTED_CHANGED, report
        assert report["live_state"] == "AFTER_ONLY"
        assert report["live_already_at_candidate_core"] == EXPECTED_CHANGED
    print("OFFICIAL CANDIDATE 3-WAY PREFLIGHT SELFTEST OK: 43/core/4800; before/after/partial/drift/grading, no writes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-pinned-real-baseline", action="store_true")
    args = parser.parse_args()
    run(args.with_pinned_real_baseline)

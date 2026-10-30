#!/usr/bin/env python3
"""Real 4,800-row deterministic pass and mutation-based official-core negatives."""
from __future__ import annotations

from copy import deepcopy
from official_live_snapshot_parity import compare, check_local
from historical_source_url_repair_plan import load_local_shards


def main() -> int:
    baseline = load_local_shards()
    assert len(baseline) == 4800
    initial = check_local(baseline)
    assert initial["status"] == "MATCH"
    assert initial["expected_questions"] == initial["live_questions"] == 4800

    def single_mutation(field: str, changed_value) -> dict:
        observed = [dict(x) for x in baseline]
        observed[0][field] = changed_value
        return compare(baseline, observed)

    q0 = baseline[0]
    typo = single_mutation("question", q0["question"] + "【unapproved modification】")
    assert typo["status"] == "HOLD_REVIEW_DRIFT"
    assert typo["summary"]["official_wording_drift"] == 1
    assert typo["official_wording_differences"][0]["fields"] == ["question"]
    assert typo["summary"]["grading_drift"] == 0
    for field in ("opt_a", "opt_b", "opt_c", "opt_d", "source_exam_code"):
        r = single_mutation(field, str(q0[field]) + "X")
        assert r["summary"]["official_wording_drift"] == 1, field

    wrong_answer = single_mutation("answer", "not-an-answer")
    assert wrong_answer["summary"]["grading_drift"] == 1
    assert wrong_answer["grading_differences"][0]["fields"] == ["answer"]
    wrong_mode = single_mutation("grading_mode", "auto-credit")
    assert wrong_mode["summary"]["grading_drift"] == 1
    wrong_accepted = single_mutation("accepted_answers", ["A", "D"])
    assert wrong_accepted["summary"]["grading_drift"] == 1

    # Local metadata/AI-enrichment divergence MUST NOT masquerade as an official
    # text or grading discrepancy, nor authorize changed official source text.
    metadata = [dict(x) for x in baseline]
    metadata[0]["exp_raw"] = "synthetic enrichment only"
    metadata[0]["analysis_status"] = "review"
    assert compare(baseline, metadata)["status"] == "MATCH"

    missing = compare(baseline, baseline[1:])
    assert missing["summary"]["missing_live"] == 1 and missing["status"] == "HOLD_REVIEW_DRIFT"
    extra = [dict(baseline[0], id="SYNTHETIC-116-1-001", year="116")]
    more = compare(baseline, baseline + extra)
    assert more["summary"]["unpublished_live"] == 1
    # Future exams must be able to enter the tracked manifest; counts must not
    # be permanently hardcoded to 4,800.
    assert compare(baseline + extra, baseline + extra)["status"] == "MATCH"

    duplicated = baseline + [dict(baseline[0])]
    try:
        compare(baseline, duplicated)
    except ValueError as e:
        assert "duplicate" in str(e)
    else:
        raise AssertionError("duplicate live ID not blocked")

    missing_field = [dict(x) for x in baseline]
    del missing_field[0]["grading_mode"]
    try:
        compare(baseline, missing_field)
    except ValueError as e:
        assert "missing official field" in str(e)
    else:
        raise AssertionError("missing grading_mode was not blocked")

    assert not initial["database_written"] and not initial["release_approved"]
    assert baseline[0] == q0, "a QA helper mutated the official input"
    print("OFFICIAL LIVE SNAPSHOT PARITY SELFTEST OK: 4800, 19k+ choices; official, grading, count, future, metadata negatives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

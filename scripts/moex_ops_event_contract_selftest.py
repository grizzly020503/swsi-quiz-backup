#!/usr/bin/env python3
"""Deterministic offline tests for moex_ops_event_contract.py."""
from __future__ import annotations

from moex_ops_event_contract import classify_payload, classify_probe


def probe(status: str, **extra):
    row = {
        "schema_version": 1,
        "probe": "moex_exam_page_structure_v1",
        "exam_code": "116030",
        "status": status,
        "source_url": "https://wwwq.moex.gov.tw/exam/example",
        "content_sha256": "a" * 64,
        "safe_to_parse_pdfs": status == "match",
    }
    row.update(extra)
    return row


def main() -> int:
    ok = classify_probe(probe("match"))
    assert ok["action"] == "continue"
    assert ok["ledger_outcome"] is None
    assert ok["review_item"] is None

    transient = classify_probe(probe("source_error"), retry_after_seconds=120)
    assert transient["action"] == "retry"
    assert transient["ledger_outcome"] == "failed_retryable"
    assert transient["review_required"] is False
    assert transient["retry_after_seconds"] == 120

    exhausted = classify_probe(probe("source_error"), retry_exhausted=True)
    assert exhausted["ledger_outcome"] == "failed_terminal"
    assert exhausted["review_required"] is True
    assert exhausted["review_item"]["reason"] == "source_unavailable_after_retries"

    for status, reason in (
        ("possible_scheme_change", "possible_exam_scheme_change"),
        ("target_class_missing", "target_class_missing"),
        ("unapproved_scheme", "unapproved_exam_scheme"),
    ):
        row = classify_probe(probe(status, diffs=[{"field": "subjects"}]))
        assert row["ledger_outcome"] == "quarantined"
        assert row["action"] == "quarantine"
        assert row["review_item"]["reason"] == reason
        assert row["review_item"]["metadata"]["diffs"] == [{"field": "subjects"}]

    unknown = classify_probe(probe("future_new_status"))
    assert unknown["ledger_outcome"] == "quarantined"
    assert unknown["review_item"]["reason"] == "unknown_probe_status"

    # Identical evidence must upsert the same durable review item rather than
    # create duplicate manual debt on every scheduled run.
    a = classify_probe(probe("possible_scheme_change"))
    b = classify_probe(probe("possible_scheme_change"))
    assert a["review_item"]["item_id"] == b["review_item"]["item_id"]

    payload_ok = classify_payload({
        "exam_code": "116030",
        "status": "match",
        "approved": True,
        "profile_id": "current",
        "source_ref": "incoming/116030.json",
    })
    assert payload_ok["action"] == "continue"

    candidate = classify_payload({
        "exam_code": "116030",
        "status": "candidate_change",
        "approved": False,
        "profile_id": "current",
        "source_ref": "incoming/116030.json",
        "diffs": [{"field": "mc_per_subject"}],
    })
    assert candidate["ledger_outcome"] == "quarantined"
    assert candidate["review_item"]["reason"] == "post_parse_scheme_change"

    identity = classify_payload({
        "exam_code": "116030",
        "status": "invalid_identity",
        "approved": False,
        "source_ref": "incoming/116030.json",
    })
    assert identity["review_item"]["reason"] == "invalid_exam_identity"

    contradictory = classify_payload({
        "exam_code": "116030",
        "status": "match",
        "approved": False,
        "source_ref": "incoming/116030.json",
    })
    assert contradictory["ledger_outcome"] == "quarantined"
    assert contradictory["review_item"]["reason"] == "unapproved_match_contract"

    try:
        classify_probe({"exam_code": "bad", "status": "match", "safe_to_parse_pdfs": True})
    except ValueError:
        pass
    else:
        raise AssertionError("bad exam code must fail closed")

    print("MOEX ops event contract self-test: PASS (retry, quarantine, review aging input)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

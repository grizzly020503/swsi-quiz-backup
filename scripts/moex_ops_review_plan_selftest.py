#!/usr/bin/env python3
"""Deterministic zero-network tests for moex_ops_review_plan.py."""
from __future__ import annotations

import copy

from moex_ops_event_contract import classify_payload, classify_probe
from moex_ops_review_plan import build_review_plan


def probe(status: str, **extra):
    row = {
        "schema_version": 1,
        "probe": "moex_exam_page_structure_v1",
        "exam_code": "116030",
        "status": status,
        "source_url": "fixture://moex",
        "content_sha256": "a" * 64,
        "safe_to_parse_pdfs": status == "match",
    }
    row.update(extra)
    return row


def must_fail(event: dict) -> None:
    try:
        build_review_plan(event)
    except ValueError:
        return
    raise AssertionError("tampered/invalid event must fail closed")


def main() -> int:
    transient = classify_probe(probe("source_error"))
    transient_plan = build_review_plan(transient)
    assert transient_plan["operation"] is None
    assert transient_plan["gateway_request"] is None

    scheme_change = classify_probe(
        probe("possible_scheme_change", diffs=[{"field": "subjects"}])
    )
    scheme_plan = build_review_plan(scheme_change)
    request = scheme_plan["gateway_request"]
    assert scheme_plan["operation"] == "review_upsert"
    assert request["action"] == "review_upsert"
    assert request["task_id"] == "moex-social-worker-sync"
    assert request["item_id"].startswith("moex:116030:possible_exam_scheme_change:")
    assert request["reason"] == "possible_exam_scheme_change"
    assert request["metadata"]["exam_code"] == "116030"

    exhausted = classify_probe(probe("source_error"), retry_exhausted=True)
    exhausted_plan = build_review_plan(exhausted)
    assert exhausted_plan["gateway_request"]["reason"] == "source_unavailable_after_retries"

    payload_change = classify_payload({
        "schema_version": 1,
        "exam_code": "116030",
        "status": "candidate_change",
        "approved": False,
        "profile_id": "current",
        "source_ref": "incoming/116030.json",
        "diffs": [{"field": "mc_per_subject"}],
    })
    payload_plan = build_review_plan(payload_change)
    assert payload_plan["gateway_request"]["reason"] == "post_parse_scheme_change"

    tampered = copy.deepcopy(scheme_change)
    tampered["review_item"]["item_id"] = "historical-law:wrong-namespace"
    must_fail(tampered)

    tampered = copy.deepcopy(scheme_change)
    tampered["review_item"]["reason"] = "arbitrary_reason"
    must_fail(tampered)

    tampered = copy.deepcopy(scheme_change)
    tampered["review_item"]["task_id"] = "historical-law-guardian-queue"
    must_fail(tampered)

    tampered = copy.deepcopy(scheme_change)
    tampered["review_item"]["metadata"]["exam_code"] = "116100"
    must_fail(tampered)

    tampered = copy.deepcopy(transient)
    tampered["review_item"] = {"item_id": "moex:should-not-exist"}
    must_fail(tampered)

    tampered = copy.deepcopy(scheme_change)
    tampered["task_id"] = "full-corpus-question-qa"
    must_fail(tampered)

    print("MOEX ops review plan self-test: PASS (dry-run request + fail-closed tamper cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

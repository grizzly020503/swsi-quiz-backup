#!/usr/bin/env python3
"""Offline behavior contract for moex_sync_guarded guarded intake."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from moex_sync_guarded import (
    GuardedIntakeBlocked,
    _default_exam_exists,
    _production_base_module,
    guarded_build,
    payload_ops_event,
    probe_ops_event,
)


def good_payload() -> dict:
    return {
        "exam_type": "專門職業及技術人員高等考試社會工作師",
        "exam_code": "116030",
        "roc_year": "116",
        "round": "第一次",
        "questions": [],
        "essays": [],
    }


def assert_v2_contract() -> None:
    """Verify production loading requires v2 patches and keeps exam_exists."""
    token_mc = object()
    token_rules = object()
    availability = {"116030": True, "116100": False}
    fake_base = SimpleNamespace(
        parse_mc=token_mc,
        _parse_correction_rules=token_rules,
        exam_exists=lambda code: availability.get(code, False),
    )
    fake_v2 = SimpleNamespace(
        base=fake_base,
        parse_mc_with_grading=token_mc,
        parse_correction_rules_with_grading=token_rules,
    )
    old = sys.modules.get("moex_sync_v2")
    sys.modules["moex_sync_v2"] = fake_v2
    try:
        assert _production_base_module() is fake_base
        assert _default_exam_exists("116030") is True
        assert _default_exam_exists("116100") is False

        fake_base.parse_mc = object()
        try:
            _production_base_module()
            raise AssertionError("guard must reject an inactive v2 parse_mc patch")
        except RuntimeError as exc:
            assert "parse_mc grading patch" in str(exc)
        fake_base.parse_mc = token_mc

        fake_base._parse_correction_rules = object()
        try:
            _production_base_module()
            raise AssertionError("guard must reject an inactive v2 correction patch")
        except RuntimeError as exc:
            assert "correction/grading patch" in str(exc)
    finally:
        if old is None:
            sys.modules.pop("moex_sync_v2", None)
        else:
            sys.modules["moex_sync_v2"] = old


def assert_ops_event_contract() -> None:
    structure = probe_ops_event({
        "schema_version": 1,
        "exam_code": "116030",
        "status": "possible_scheme_change",
        "source_url": "fixture://scheme-change",
        "content_sha256": "b" * 64,
        "safe_to_parse_pdfs": False,
        "diffs": [{"field": "subjects"}],
    })
    assert structure["ledger_outcome"] == "quarantined"
    assert structure["review_required"] is True
    assert structure["review_item"]["reason"] == "possible_exam_scheme_change"

    source = probe_ops_event({
        "schema_version": 1,
        "exam_code": "116030",
        "status": "source_error",
        "source_url": "fixture://source-error",
        "safe_to_parse_pdfs": False,
    })
    assert source["ledger_outcome"] == "failed_retryable"
    assert source["review_item"] is None

    post = payload_ops_event(
        "116030",
        {
            "status": "candidate_change",
            "approved": False,
            "profile_id": "current",
            "diffs": [{"field": "essay_per_subject"}],
        },
        source_ref="incoming/116030.json",
    )
    assert post["ledger_outcome"] == "quarantined"
    assert post["review_item"]["reason"] == "post_parse_scheme_change"


def main() -> int:
    assert_v2_contract()
    assert_ops_event_contract()
    calls = {"build": 0}

    def build(_code: str) -> dict:
        calls["build"] += 1
        return good_payload()

    def probe_match(_code: str) -> dict:
        return {"status": "match", "safe_to_parse_pdfs": True}

    def probe_change(_code: str) -> dict:
        return {"status": "possible_scheme_change", "safe_to_parse_pdfs": False}

    def probe_source_error(_code: str) -> dict:
        return {"status": "source_error", "safe_to_parse_pdfs": False}

    def scheme_match(_payload: dict) -> dict:
        return {"status": "match", "approved": True, "profile_id": "test"}

    def scheme_change(_payload: dict) -> dict:
        return {"status": "candidate_change", "approved": False, "profile_id": "test"}

    try:
        guarded_build("116030", probe_fn=probe_change, build_fn=build, compare_fn=scheme_match)
        raise AssertionError("structure change must block")
    except GuardedIntakeBlocked:
        pass
    assert calls["build"] == 0, "PDF parser/build must not start after structure mismatch"

    try:
        guarded_build("116030", probe_fn=probe_source_error, build_fn=build, compare_fn=scheme_match)
        raise AssertionError("source error must block")
    except GuardedIntakeBlocked:
        pass
    assert calls["build"] == 0, "source failure must not degrade into PDF parser attempt"

    payload, probe, scheme = guarded_build(
        "116030", probe_fn=probe_match, build_fn=build, compare_fn=scheme_match
    )
    assert calls["build"] == 1
    assert payload["exam_code"] == "116030"
    assert probe["status"] == "match"
    assert scheme["approved"] is True

    try:
        guarded_build("116030", probe_fn=probe_match, build_fn=build, compare_fn=scheme_change)
        raise AssertionError("post-parse scheme mismatch must block")
    except GuardedIntakeBlocked:
        pass
    assert calls["build"] == 2, "post-parse gate runs only after one parser/build attempt"

    print("Guarded MOEX intake self-test: PASS (v2 + availability + ops-event diagnostics + fail-closed gates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

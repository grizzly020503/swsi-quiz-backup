#!/usr/bin/env python3
"""Offline behavior contract for moex_sync_guarded.guarded_build."""

from __future__ import annotations

from moex_sync_guarded import GuardedIntakeBlocked, guarded_build


def good_payload() -> dict:
    return {
        "exam_type": "專門職業及技術人員高等考試社會工作師",
        "exam_code": "116030",
        "roc_year": "116",
        "round": "第一次",
        "questions": [],
        "essays": [],
    }


def main() -> int:
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

    print("Guarded MOEX intake self-test: PASS (pre-parse and post-parse fail-closed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

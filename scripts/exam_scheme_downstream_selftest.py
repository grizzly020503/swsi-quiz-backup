#!/usr/bin/env python3
"""Synthetic downstream regression for scheme-derived current-intake QA.

All future-regime examples here are hypothetical fixtures. They do not claim any
actual ROC 116+ Social Worker examination reform.
"""
from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from pathlib import Path

from exam_scheme import load_registry
from exam_scheme_qa_policy import derive_qa_policy

ROOT = Path(__file__).resolve().parents[1]
BASE_POLICY = json.loads((ROOT / "data" / "question_qa_policy_v1.json").read_text(encoding="utf-8"))


def main() -> int:
    registry = load_registry()

    current, current_meta = derive_qa_policy(BASE_POLICY, registry, "116", "第一次")
    assert current_meta["profile_id"] == "social-worker-five-subjects-v1"
    assert current["mcq"]["expected_total"] == 200
    assert current["essay"]["expected_total"] == 10
    assert current_meta["expected_total_items"] == 210
    assert len(current["subjects"]) == 5

    # Hypothetical *approved* future reform. The old profile is closed at 116-2;
    # a reviewed new profile begins at 117-1. This fixture proves downstream QA
    # follows effective-dated profiles without changing QA code or historical data.
    future_registry = deepcopy(registry)
    old = future_registry["profiles"][0]
    old["effective_to"] = {"roc_year": "116", "round": "第二次"}
    new_profile = deepcopy(old)
    new_profile["id"] = "SYNTHETIC-four-subjects-no-essay-v2"
    new_profile["effective_from"] = {"roc_year": "117", "round": "第一次"}
    new_profile["effective_to"] = None
    new_profile["subjects"] = new_profile["subjects"][:4]
    new_profile["mcq"]["per_subject"] = 30
    new_profile["mcq"]["expected_total"] = 120
    new_profile["mcq"]["qno_min"] = 1
    new_profile["mcq"]["qno_max"] = 30
    new_profile["essay"]["required"] = False
    new_profile["essay"]["per_subject"] = 0
    new_profile["essay"]["expected_total"] = 0
    new_profile["essay"]["qno_min"] = 0
    new_profile["essay"]["qno_max"] = 0
    new_profile["evidence"] = [{"type": "synthetic_test_fixture_only"}]
    future_registry["profiles"].append(new_profile)

    future, future_meta = derive_qa_policy(BASE_POLICY, future_registry, "117", "第一次")
    assert future_meta["profile_id"] == "SYNTHETIC-four-subjects-no-essay-v2"
    assert future["mcq"]["expected_total"] == 120
    assert future["mcq"]["expected_per_subject"] == 30
    assert future["essay"]["expected_total"] == 0
    assert future["essay"]["expected_per_subject"] == 0
    assert future_meta["expected_total_items"] == 120
    assert len(future["subjects"]) == 4

    historical, historical_meta = derive_qa_policy(BASE_POLICY, future_registry, "115", "第二次")
    assert historical_meta["profile_id"] == "social-worker-five-subjects-v1"
    assert historical_meta["expected_total_items"] == 210
    assert historical["mcq"]["expected_total"] == 200
    assert historical["essay"]["expected_total"] == 10

    # Semantic/risk policy is still owned by question_qa_policy_v1 and is not
    # silently weakened by structural derivation.
    assert future["release_gate"] == BASE_POLICY["release_gate"]
    assert future["risk_signals"] == BASE_POLICY["risk_signals"]
    assert future["mcq"]["valid_grading_modes"] == BASE_POLICY["mcq"]["valid_grading_modes"]
    assert future["mcq"]["special_answer_marker"] == BASE_POLICY["mcq"]["special_answer_marker"]

    print("EXAM SCHEME DOWNSTREAM SELFTEST OK")
    print("- current approved 116-1 profile -> 200 MCQ + 10 essay")
    print("- synthetic approved 117-1 profile -> 120 MCQ + 0 essay without QA code change")
    print("- historical 115-2 still resolves old 200+10 profile")
    print("- risk/release/grading semantics remain pinned to the base QA policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

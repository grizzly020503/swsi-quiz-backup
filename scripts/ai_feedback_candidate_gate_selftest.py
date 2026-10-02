#!/usr/bin/env python3
"""Deterministic self-test for ai_feedback_candidate_gate.py. No network/model calls."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = ROOT / "scripts" / "ai_feedback_candidate_gate.py"
EVAL_SELFTEST_PATH = ROOT / "scripts" / "ai_feedback_eval_selftest.py"
DATASET_PATH = ROOT / "ai_eval" / "golden_set.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    gate = load_module("swsi_ai_feedback_candidate_gate", GATE_PATH)
    eval_selftest = load_module("swsi_ai_feedback_eval_selftest_for_gate", EVAL_SELFTEST_PATH)
    evaluator = eval_selftest.load_module()
    dataset = evaluator.load_json(DATASET_PATH)

    require(
        gate.requires_candidate_evidence({"cloudflare/wandering-wave-4418/worker.js"}),
        "public model source change must require candidate evidence",
    )
    require(
        gate.requires_candidate_evidence({"monthly_patch_parts/99z.essay-trust-layer.part"}),
        "essay prompt source change must require candidate evidence",
    )
    require(
        gate.requires_candidate_evidence({"ai_eval/golden_set.json"}),
        "Golden Set contract change must require refreshed candidate evidence",
    )
    require(
        not gate.requires_candidate_evidence({"docs/README.md", "scripts/unrelated.py"}),
        "unrelated changes must not force a live-model evidence refresh",
    )

    payload = eval_selftest.build_good_payload(dataset)
    payload.update(
        {
            "generated_at": "2026-10-02T00:00:00Z",
            "capture_kind": "actual_candidate_model_outputs",
            "human_review_completed": True,
            "contract_fingerprint": gate.contract_fingerprint(dataset),
        }
    )
    errors = gate.validate_snapshot_metadata(dataset, payload)
    require(not errors, "valid candidate metadata must pass: " + repr(errors))

    stale = dict(payload)
    stale["contract_fingerprint"] = "sha256:" + "0" * 64
    errors = gate.validate_snapshot_metadata(dataset, stale)
    require(any("stale or missing" in error for error in errors), "stale fingerprint must fail closed")

    mislabeled = dict(payload)
    mislabeled["capture_kind"] = "synthetic_selftest"
    errors = gate.validate_snapshot_metadata(dataset, mislabeled)
    require(any("capture_kind" in error for error in errors), "synthetic output cannot masquerade as actual candidate evidence")

    unreviewed = dict(payload)
    unreviewed["human_review_completed"] = False
    errors = gate.validate_snapshot_metadata(dataset, unreviewed)
    require(any("human_review_completed" in error for error in errors), "unreviewed outputs must fail closed")

    stale_model = dict(payload)
    stale_model["model"] = "old/model"
    errors = gate.validate_snapshot_metadata(dataset, stale_model)
    require(any("model" in error for error in errors), "wrong model metadata must fail")

    report = evaluator.evaluate_outputs(dataset, payload, require_human_scores=True)
    require(report["passed"], "valid fully scored synthetic harness payload must satisfy evaluator contract")

    missing_scores = eval_selftest.build_good_payload(dataset)
    missing_scores.update(
        {
            "generated_at": "2026-10-02T00:00:00Z",
            "capture_kind": "actual_candidate_model_outputs",
            "human_review_completed": True,
            "contract_fingerprint": gate.contract_fingerprint(dataset),
        }
    )
    missing_scores["cases"][0].pop("human_scores", None)
    report = evaluator.evaluate_outputs(dataset, missing_scores, require_human_scores=True)
    require(not report["passed"], "candidate evidence without complete human scores must fail")

    print("AI FEEDBACK CANDIDATE GATE SELFTEST OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

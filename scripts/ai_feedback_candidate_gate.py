#!/usr/bin/env python3
"""Fail-closed gate for prompt/model changes that require captured candidate outputs.

Default CI remains zero-network. This script only evaluates a previously captured,
synthetic-Golden-Set output snapshot. A prompt/model/Golden-Set contract change
requires the snapshot to be refreshed and human-scored before merge.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVAL_PATH = ROOT / "scripts" / "ai_feedback_eval.py"
DEFAULT_DATASET = ROOT / "ai_eval" / "golden_set.json"
DEFAULT_OUTPUTS = ROOT / "ai_eval" / "captured" / "candidate.json"
MONITORED_PATHS = {
    "ai_eval/golden_set.json",
    "monthly_patch_parts/99z.essay-trust-layer.part",
    "cloudflare/wandering-wave-4418/worker.js",
}


def load_evaluator():
    spec = importlib.util.spec_from_file_location("swsi_ai_feedback_eval", EVAL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import evaluator from {EVAL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def read_changed_files(path: Path) -> set[str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        line.strip().replace("\\", "/")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def requires_candidate_evidence(changed_files: set[str]) -> bool:
    return bool(MONITORED_PATHS & changed_files)


def contract_fingerprint(dataset: dict[str, Any], root: Path = ROOT) -> str:
    """Bind captured evidence to exact Golden Set + prompt source + public model source."""
    digest = hashlib.sha256()
    canonical_dataset = json.dumps(
        dataset,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest.update(b"dataset\0")
    digest.update(canonical_dataset)

    for key in ("prompt_contract", "model_contract"):
        rel = dataset.get(key, {}).get("source")
        if not isinstance(rel, str) or not rel:
            raise ValueError(f"{key}.source is required before fingerprinting")
        source = root / rel
        if not source.is_file():
            raise FileNotFoundError(source)
        digest.update(b"\0path\0")
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0content\0")
        digest.update(source.read_bytes())
    return "sha256:" + digest.hexdigest()


def validate_snapshot_metadata(
    dataset: dict[str, Any],
    outputs: Any,
    root: Path = ROOT,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(outputs, dict):
        return ["candidate outputs must be a JSON object"]

    expected = {
        "schema_version": 1,
        "golden_set": dataset.get("name"),
        "model": dataset.get("model_contract", {}).get("public_model"),
        "prompt_version": dataset.get("prompt_contract", {}).get("guide_version"),
        "capture_kind": "actual_candidate_model_outputs",
        "human_review_completed": True,
    }
    for key, value in expected.items():
        if outputs.get(key) != value:
            errors.append(f"snapshot metadata mismatch for {key}: expected {value!r}, got {outputs.get(key)!r}")

    generated_at = outputs.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        errors.append("snapshot generated_at must be a non-empty timestamp string")

    try:
        expected_fingerprint = contract_fingerprint(dataset, root=root)
    except (OSError, ValueError) as exc:
        errors.append(f"cannot compute candidate contract fingerprint: {exc}")
    else:
        if outputs.get("contract_fingerprint") != expected_fingerprint:
            errors.append(
                "snapshot contract_fingerprint is stale or missing; regenerate outputs against the exact candidate contract"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed-files", type=Path)
    parser.add_argument("--outputs", type=Path, default=DEFAULT_OUTPUTS)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--force", action="store_true", help="require/evaluate candidate evidence even without a monitored diff")
    args = parser.parse_args(argv)

    dataset_path = args.dataset if args.dataset.is_absolute() else ROOT / args.dataset
    outputs_path = args.outputs if args.outputs.is_absolute() else ROOT / args.outputs

    changed_files: set[str] = set()
    if args.changed_files:
        changed_path = args.changed_files if args.changed_files.is_absolute() else ROOT / args.changed_files
        try:
            changed_files = read_changed_files(changed_path)
        except OSError as exc:
            print(f"ERROR: cannot read changed-files list: {exc}")
            return 1

    required = args.force or requires_candidate_evidence(changed_files)
    monitored_changed = sorted(MONITORED_PATHS & changed_files)
    print(f"Candidate evidence required: {'yes' if required else 'no'}")
    if monitored_changed:
        print("Monitored contract changes: " + ", ".join(monitored_changed))
    if not required:
        print("AI FEEDBACK CANDIDATE EVIDENCE GATE SKIPPED")
        return 0

    evaluator = load_evaluator()
    try:
        dataset = load_json(dataset_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot load dataset {dataset_path}: {exc}")
        return 1

    dataset_errors, dataset_warnings = evaluator.validate_dataset(dataset)
    for warning in dataset_warnings:
        print(f"WARNING: {warning}")
    if dataset_errors:
        for error in dataset_errors:
            print(f"ERROR: {error}")
        return 1

    try:
        outputs = load_json(outputs_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: candidate outputs evidence required but unavailable at {outputs_path}: {exc}")
        return 1

    metadata_errors = validate_snapshot_metadata(dataset, outputs)
    if metadata_errors:
        for error in metadata_errors:
            print(f"ERROR: {error}")
        return 1

    report = evaluator.evaluate_outputs(dataset, outputs, require_human_scores=True)
    evaluator.print_output_report(report)
    if not report["passed"]:
        return 1

    print("AI FEEDBACK CANDIDATE EVIDENCE GATE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

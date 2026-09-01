#!/usr/bin/env python3
"""Deterministic contract evaluator for SWSI essay AI feedback.

Default CI never calls a live model. It validates the Golden Set, pins the current
public model / prompt contract, and can score captured model outputs when a human
or a deliberate live-eval session supplies them.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "ai_eval" / "golden_set.json"

GUIDE_VERSION_RE = re.compile(r"var\s+GUIDE_VERSION\s*=\s*['\"]([^'\"]+)['\"]")
PUBLIC_MODEL_RE = re.compile(r"const\s+PUBLIC_MODEL\s*=\s*['\"]([^'\"]+)['\"]")
SCORE_RE = re.compile(r"(?:^|[^0-9])([0-9]{1,3})\s*分(?:[，。；：、\s]|$)")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)


def validate_dataset(dataset: Any, root: Path = ROOT) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(dataset, dict):
        return ["dataset must be a JSON object"], warnings
    if dataset.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if dataset.get("scope") != "text_essay_feedback":
        errors.append("scope must be text_essay_feedback")

    prompt = dataset.get("prompt_contract")
    if not isinstance(prompt, dict):
        errors.append("prompt_contract must be an object")
    else:
        source_rel = prompt.get("source")
        if not isinstance(source_rel, str) or not source_rel:
            errors.append("prompt_contract.source is required")
        else:
            source_path = root / source_rel
            if not source_path.is_file():
                errors.append(f"prompt source missing: {source_rel}")
            else:
                source = source_path.read_text(encoding="utf-8")
                match = GUIDE_VERSION_RE.search(source)
                actual_version = match.group(1) if match else None
                expected_version = prompt.get("guide_version")
                if actual_version != expected_version:
                    errors.append(
                        f"prompt guide version drift: dataset={expected_version!r} source={actual_version!r}"
                    )
                temp = prompt.get("text_temperature")
                if not isinstance(temp, (int, float)):
                    errors.append("prompt_contract.text_temperature must be numeric")
                else:
                    temp_token = f"temperature:{temp:g}"
                    if temp_token not in source:
                        errors.append(
                            f"text temperature drift: expected source to contain {temp_token!r}"
                        )
                clauses = prompt.get("required_clauses")
                if not _is_string_list(clauses):
                    errors.append("prompt_contract.required_clauses must be a non-empty string list")
                else:
                    for clause in clauses:
                        if clause not in source:
                            errors.append(f"prompt contract clause missing from source: {clause}")

    model = dataset.get("model_contract")
    if not isinstance(model, dict):
        errors.append("model_contract must be an object")
    else:
        source_rel = model.get("source")
        expected_model = model.get("public_model")
        if not isinstance(source_rel, str) or not source_rel:
            errors.append("model_contract.source is required")
        elif not isinstance(expected_model, str) or not expected_model:
            errors.append("model_contract.public_model is required")
        else:
            source_path = root / source_rel
            if not source_path.is_file():
                errors.append(f"model source missing: {source_rel}")
            else:
                source = source_path.read_text(encoding="utf-8")
                match = PUBLIC_MODEL_RE.search(source)
                actual_model = match.group(1) if match else None
                if actual_model != expected_model:
                    errors.append(
                        f"public model drift: dataset={expected_model!r} source={actual_model!r}"
                    )

    contract = dataset.get("global_output_contract")
    if not isinstance(contract, dict):
        errors.append("global_output_contract must be an object")
    else:
        for key in ("required_headings", "forbidden_phrases", "simplified_markers", "uncertainty_markers", "question_priority_markers"):
            if not _is_string_list(contract.get(key)):
                errors.append(f"global_output_contract.{key} must be a non-empty string list")
        for key in ("hard_min_chars", "hard_max_chars", "preferred_min_chars", "preferred_max_chars"):
            if not isinstance(contract.get(key), int) or contract.get(key) < 1:
                errors.append(f"global_output_contract.{key} must be a positive integer")
        if not errors:
            if contract["hard_min_chars"] >= contract["hard_max_chars"]:
                errors.append("hard_min_chars must be lower than hard_max_chars")
            if contract["preferred_min_chars"] >= contract["preferred_max_chars"]:
                errors.append("preferred_min_chars must be lower than preferred_max_chars")

    rubric = dataset.get("human_rubric")
    if not isinstance(rubric, dict):
        errors.append("human_rubric must be an object")
    else:
        dims = rubric.get("dimensions")
        if not _is_string_list(dims) or len(set(dims)) != len(dims):
            errors.append("human_rubric.dimensions must be a unique non-empty string list")
        for key in ("score_min", "score_max", "normal_case_pass_total", "high_risk_case_pass_total", "mean_pass_total"):
            if not isinstance(rubric.get(key), (int, float)):
                errors.append(f"human_rubric.{key} must be numeric")

    cases = dataset.get("cases")
    if not isinstance(cases, list):
        errors.append("cases must be a list")
        return errors, warnings
    if len(cases) < 20:
        errors.append(f"Golden Set must contain at least 20 cases; found {len(cases)}")

    seen: set[str] = set()
    for idx, case in enumerate(cases):
        prefix = f"case[{idx}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            errors.append(f"{prefix}.id is required")
            continue
        if case_id in seen:
            errors.append(f"duplicate case id: {case_id}")
        seen.add(case_id)
        if case.get("risk") not in {"normal", "high"}:
            errors.append(f"{case_id}: risk must be normal or high")
        for key in ("category", "question", "student_answer", "reference_status"):
            if not isinstance(case.get(key), str) or not case.get(key).strip():
                errors.append(f"{case_id}: {key} must be a non-empty string")
        exp = case.get("expectations")
        if not isinstance(exp, dict):
            errors.append(f"{case_id}: expectations must be an object")
            continue
        if not isinstance(exp.get("must_mention_all"), list) or not all(isinstance(x, str) for x in exp.get("must_mention_all", [])):
            errors.append(f"{case_id}: must_mention_all must be a string list")
        groups = exp.get("must_mention_any")
        if not isinstance(groups, list) or not all(_is_string_list(group) for group in groups):
            errors.append(f"{case_id}: must_mention_any must be a list of non-empty string lists")
        if not isinstance(exp.get("forbidden_phrases"), list) or not all(isinstance(x, str) for x in exp.get("forbidden_phrases", [])):
            errors.append(f"{case_id}: forbidden_phrases must be a string list")
        for key in ("require_uncertainty", "require_question_priority"):
            if not isinstance(exp.get(key), bool):
                errors.append(f"{case_id}: {key} must be boolean")

    if cases:
        categories = {case.get("category") for case in cases if isinstance(case, dict)}
        high_risk = sum(1 for case in cases if isinstance(case, dict) and case.get("risk") == "high")
        if len(categories) < 8:
            warnings.append(f"Golden Set category diversity is low: {len(categories)} categories")
        if high_risk < 5:
            warnings.append(f"Golden Set has only {high_risk} high-risk cases")

    return errors, warnings


def _compact_length(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def evaluate_case(case: dict[str, Any], text: str, contract: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(text, str) or not text.strip():
        return ["output is empty"], warnings

    compact_len = _compact_length(text)
    if compact_len < contract["hard_min_chars"]:
        errors.append(f"output too short: {compact_len} chars < hard minimum {contract['hard_min_chars']}")
    if compact_len > contract["hard_max_chars"]:
        errors.append(f"output too long: {compact_len} chars > hard maximum {contract['hard_max_chars']}")
    if compact_len < contract["preferred_min_chars"]:
        warnings.append(f"output below preferred length: {compact_len} chars")
    if compact_len > contract["preferred_max_chars"]:
        warnings.append(f"output above preferred length: {compact_len} chars")

    for heading in contract["required_headings"]:
        if heading not in text:
            errors.append(f"required feedback section missing: {heading}")

    for phrase in contract["forbidden_phrases"]:
        if phrase in text:
            errors.append(f"forbidden authoritative claim: {phrase}")
    for marker in contract["simplified_markers"]:
        if marker in text:
            errors.append(f"Simplified-Chinese marker found: {marker}")
    if SCORE_RE.search(text):
        errors.append("numeric score claim detected")

    exp = case["expectations"]
    for term in exp["must_mention_all"]:
        if term not in text:
            errors.append(f"case-critical term missing: {term}")
    for group in exp["must_mention_any"]:
        if not any(term in text for term in group):
            errors.append("case-critical concept missing; expected one of: " + " / ".join(group))
    for phrase in exp["forbidden_phrases"]:
        if phrase in text:
            errors.append(f"case-specific forbidden phrase found: {phrase}")

    if exp["require_uncertainty"] and not any(marker in text for marker in contract["uncertainty_markers"]):
        errors.append("uncertainty / verification language required but missing")
    if exp["require_question_priority"] and not any(marker in text for marker in contract["question_priority_markers"]):
        errors.append("question-priority language required but missing")

    return errors, warnings


def normalize_output_records(payload: Any) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {}, ["outputs file must be a JSON object"]
    raw_cases = payload.get("cases")
    records: dict[str, dict[str, Any]] = {}
    if isinstance(raw_cases, dict):
        for case_id, value in raw_cases.items():
            if isinstance(value, str):
                records[str(case_id)] = {"id": str(case_id), "output": value}
            elif isinstance(value, dict):
                item = dict(value)
                item.setdefault("id", str(case_id))
                records[str(case_id)] = item
            else:
                errors.append(f"output record {case_id!r} must be a string or object")
    elif isinstance(raw_cases, list):
        for idx, value in enumerate(raw_cases):
            if not isinstance(value, dict) or not isinstance(value.get("id"), str):
                errors.append(f"outputs cases[{idx}] must be an object with string id")
                continue
            case_id = value["id"]
            if case_id in records:
                errors.append(f"duplicate output case id: {case_id}")
            records[case_id] = value
    else:
        errors.append("outputs.cases must be an object or list")
    return records, errors


def validate_human_scores(
    scores: Any,
    rubric: dict[str, Any],
    case_risk: str,
) -> tuple[list[str], float | None]:
    errors: list[str] = []
    if not isinstance(scores, dict):
        return ["human_scores must be an object"], None
    total = 0.0
    for dim in rubric["dimensions"]:
        value = scores.get(dim)
        if not isinstance(value, (int, float)):
            errors.append(f"human score missing/non-numeric: {dim}")
            continue
        if value < rubric["score_min"] or value > rubric["score_max"]:
            errors.append(
                f"human score out of range for {dim}: {value} not in [{rubric['score_min']}, {rubric['score_max']}]"
            )
            continue
        total += float(value)
    if errors:
        return errors, None
    threshold = rubric["high_risk_case_pass_total"] if case_risk == "high" else rubric["normal_case_pass_total"]
    if total < threshold:
        errors.append(f"human rubric total {total:g} below case threshold {threshold:g}")
    return errors, total


def evaluate_outputs(
    dataset: dict[str, Any],
    outputs_payload: Any,
    require_human_scores: bool = False,
) -> dict[str, Any]:
    records, payload_errors = normalize_output_records(outputs_payload)
    report: dict[str, Any] = {
        "payload_errors": list(payload_errors),
        "cases": {},
        "human_mean": None,
        "passed": False,
    }
    dataset_cases = {case["id"]: case for case in dataset["cases"]}
    missing = sorted(set(dataset_cases) - set(records))
    extra = sorted(set(records) - set(dataset_cases))
    if missing:
        report["payload_errors"].append("missing output cases: " + ", ".join(missing))
    if extra:
        report["payload_errors"].append("unknown output cases: " + ", ".join(extra))

    human_totals: list[float] = []
    human_complete = True
    for case_id, case in dataset_cases.items():
        record = records.get(case_id)
        if not record:
            continue
        output = record.get("output")
        errors, warnings = evaluate_case(case, output if isinstance(output, str) else "", dataset["global_output_contract"])

        scores = record.get("human_scores")
        human_total: float | None = None
        if scores is None:
            human_complete = False
            if require_human_scores:
                errors.append("human_scores required for this evaluation")
        else:
            human_errors, human_total = validate_human_scores(scores, dataset["human_rubric"], case["risk"])
            errors.extend(human_errors)
            if human_total is not None:
                human_totals.append(human_total)

        report["cases"][case_id] = {
            "errors": errors,
            "warnings": warnings,
            "human_total": human_total,
            "passed": not errors,
        }

    if human_complete and len(human_totals) == len(dataset_cases):
        mean_score = statistics.mean(human_totals)
        report["human_mean"] = mean_score
        if mean_score < dataset["human_rubric"]["mean_pass_total"]:
            report["payload_errors"].append(
                f"human mean {mean_score:.2f} below required {dataset['human_rubric']['mean_pass_total']:.2f}"
            )

    report["passed"] = (
        not report["payload_errors"]
        and len(report["cases"]) == len(dataset_cases)
        and all(item["passed"] for item in report["cases"].values())
    )
    return report


def build_output_template(dataset: dict[str, Any]) -> dict[str, Any]:
    dims = dataset["human_rubric"]["dimensions"]
    return {
        "schema_version": 1,
        "golden_set": dataset["name"],
        "model": dataset["model_contract"]["public_model"],
        "prompt_version": dataset["prompt_contract"]["guide_version"],
        "generated_at": None,
        "cases": [
            {
                "id": case["id"],
                "output": "",
                "human_scores": {dim: None for dim in dims},
                "review_notes": "",
            }
            for case in dataset["cases"]
        ],
    }


def print_dataset_result(dataset: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    print(f"Golden Set: {dataset.get('name', '<unknown>')}")
    print(f"Cases: {len(dataset.get('cases', []))}")
    print(f"Prompt version: {dataset.get('prompt_contract', {}).get('guide_version')}")
    print(f"Public model: {dataset.get('model_contract', {}).get('public_model')}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")


def print_output_report(report: dict[str, Any]) -> None:
    failed_cases = [case_id for case_id, item in report["cases"].items() if not item["passed"]]
    warning_count = sum(len(item["warnings"]) for item in report["cases"].values())
    for error in report["payload_errors"]:
        print(f"ERROR: {error}")
    for case_id in failed_cases:
        for error in report["cases"][case_id]["errors"]:
            print(f"ERROR [{case_id}]: {error}")
    print(f"Evaluated cases: {len(report['cases'])}")
    print(f"Failed cases: {len(failed_cases)}")
    print(f"Warnings: {warning_count}")
    if report["human_mean"] is not None:
        print(f"Human rubric mean: {report['human_mean']:.2f}")
    print("AI FEEDBACK EVAL OK" if report["passed"] else "AI FEEDBACK EVAL FAILED")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--outputs", type=Path)
    parser.add_argument("--write-template", type=Path)
    parser.add_argument("--require-human-scores", action="store_true")
    args = parser.parse_args(argv)

    dataset_path = args.dataset if args.dataset.is_absolute() else ROOT / args.dataset
    try:
        dataset = load_json(dataset_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot load dataset {dataset_path}: {exc}")
        return 1

    errors, warnings = validate_dataset(dataset)
    print_dataset_result(dataset, errors, warnings)
    if errors:
        return 1

    if args.write_template:
        target = args.write_template if args.write_template.is_absolute() else ROOT / args.write_template
        dump_json(target, build_output_template(dataset))
        print(f"Wrote evaluation template: {target}")

    if args.outputs:
        outputs_path = args.outputs if args.outputs.is_absolute() else ROOT / args.outputs
        try:
            outputs = load_json(outputs_path)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: cannot load outputs {outputs_path}: {exc}")
            return 1
        report = evaluate_outputs(dataset, outputs, require_human_scores=args.require_human_scores)
        print_output_report(report)
        return 0 if report["passed"] else 1

    print("AI FEEDBACK GOLDEN SET CONTRACT OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
